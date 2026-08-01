// content.js - Runs inside https://chatgpt.com/*

console.log("AI Marketing Scheduler Companion content script loaded on ChatGPT.");

// Keep track of active jobs being watched
const activeJobs = new Map();

// Listen for job generation requests from background worker
chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message.type === "GENERATE_IMAGE") {
    console.log(`Received GENERATE_IMAGE request for job ${message.jobId}:`, message.prompt);
    startImageGeneration(message.jobId, message.prompt);
    sendResponse({ status: "started" });
  }
  return true;
});

async function startImageGeneration(jobId, rawPrompt) {
  if (activeJobs.has(jobId)) {
    console.log(`Job ${jobId} already in progress.`);
    return;
  }

  // Format prompt for direct DALL-E output
  const promptText = `Please generate a high quality graphic using DALL-E based exactly on this description:\n\n"${rawPrompt}"\n\nImportant: Do not ask any clarifying questions and do not output extra text. Just generate the DALL-E image immediately.`;

  // Find prompt textarea
  const textarea = await waitForElement("#prompt-textarea, div[contenteditable='true'], textarea[data-id='root']", 10000);
  if (!textarea) {
    console.error("Could not find ChatGPT prompt textarea!");
    return;
  }

  // Focus and insert text cleanly
  textarea.focus();
  
  if (textarea.tagName.toLowerCase() === "textarea") {
    textarea.value = promptText;
    textarea.dispatchEvent(new Event("input", { bubbles: true }));
    textarea.dispatchEvent(new Event("change", { bubbles: true }));
  } else {
    // contenteditable div (modern ChatGPT UI) - React requires execCommand to properly register the input
    const success = document.execCommand('insertText', false, promptText);
    if (!success) {
      // Fallback
      textarea.innerHTML = `<p>${promptText}</p>`;
    }
    // Always dispatch input event to ensure React notices it
    textarea.dispatchEvent(new Event("input", { bubbles: true, cancelable: true }));
  }

  // Poll to find and click the send button (React might take a moment to enable it)
  let sendAttempts = 0;
  const trySend = setInterval(() => {
    sendAttempts++;
    const sendButton = document.querySelector('button[data-testid="send-button"], button[aria-label="Send prompt"], button[data-testid="fruitcake-send-button"]');
    
    if (sendButton && !sendButton.disabled) {
      clearInterval(trySend);
      sendButton.click();
      console.log("Clicked send button.");
    } else if (sendAttempts >= 10) {
      clearInterval(trySend);
      console.log("Send button not found or disabled after 5 seconds, dispatching Enter key...");
      textarea.dispatchEvent(new KeyboardEvent("keydown", {
        key: "Enter",
        code: "Enter",
        keyCode: 13,
        which: 13,
        bubbles: true,
        cancelable: true
      }));
    }
  }, 500);

  // Register job watcher with snapshot of existing images on page and mark them as uploaded
  document.querySelectorAll('img').forEach(img => {
    if (img.naturalWidth >= 200 || img.width >= 200) img.dataset.aiSchedulerUploaded = "true";
  });
  const initialImageUrls = new Set(Array.from(document.querySelectorAll('img')).map(i => i.src));
  activeJobs.set(jobId, { startTime: Date.now(), prompt: rawPrompt, initialImageUrls });
  watchForGeneratedImage(jobId);
}

// Watch the conversation container for new DALL-E generated images
function watchForGeneratedImage(jobId) {
  console.log(`Watching DOM for DALL-E image output for job ${jobId}...`);
  
  let isFound = false;

    const checkImages = async (obsOrTimer) => {
    if (isFound) return;
    const jobInfo = activeJobs.get(jobId);
    if (!jobInfo || Date.now() - jobInfo.startTime > 600000) {
      console.warn(`Timeout waiting for image on job ${jobId}`);
      if (obsOrTimer && obsOrTimer.disconnect) obsOrTimer.disconnect();
      activeJobs.delete(jobId);
      return;
    }

    // Get all large images, prioritizing the latest assistant turn
    const assistantTurns = document.querySelectorAll('[data-message-author-role="assistant"]');
    const latestTurnContainer = assistantTurns.length > 0 ? assistantTurns[assistantTurns.length - 1] : document;
    const images = Array.from(latestTurnContainer.querySelectorAll('img')).concat(Array.from(document.querySelectorAll('main img, article img, img')));
    
    for (const img of images) {
      if (img.dataset.aiSchedulerUploaded === "true" || (jobInfo.initialImageUrls && jobInfo.initialImageUrls.has(img.src))) {
        continue;
      }

      // Must be a large rendered image (DALL-E images are 1024x1024+, whereas user avatars/icons are under 100px)
      if (img.naturalWidth >= 250 || (img.width >= 250 && img.height >= 250) || img.closest('[data-testid^="dall-e"], .dall-e-image, .group\\/dalle')) {
        if (!img.complete || img.naturalWidth === 0) {
          img.addEventListener('load', () => checkImages(obsOrTimer), { once: true });
          continue;
        }

        console.log(`Analyzing potential DALL-E image for job ${jobId}:`, img.src);

        try {
          const dataUrl = await convertImageToDataURL(img);
          if (!dataUrl || dataUrl.length < 20000) {
            console.warn(`Extraction returned null or tiny image (${dataUrl ? dataUrl.length : 0} bytes), retrying on next tick...`);
            continue;
          }

          isFound = true;
          img.dataset.aiSchedulerUploaded = "true";
          console.log(`🎉 Successfully converted DALL-E image (${Math.round(dataUrl.length / 1024)} KB) for job ${jobId}! Sending to background worker...`);
          if (obsOrTimer && obsOrTimer.disconnect) obsOrTimer.disconnect();
          if (timerId) clearInterval(timerId);
          activeJobs.delete(jobId);
          
          chrome.runtime.sendMessage({
            type: "IMAGE_READY",
            jobId: jobId,
            dataUrl: dataUrl
          });
          return;
        } catch (err) {
          console.error("Failed during image conversion attempt, retrying next tick...", err);
        }
      }
    }
  };

  const observer = new MutationObserver((mutations, obs) => checkImages(obs));
  observer.observe(document.body, {
    childList: true,
    subtree: true,
    attributes: true,
    attributeFilter: ["src", "class"]
  });

  const timerId = setInterval(() => {
    if (isFound || !activeJobs.has(jobId)) {
      clearInterval(timerId);
      return;
    }
    checkImages(observer);
  }, 1500);
}

// Helper to wait for element presence in DOM
function waitForElement(selector, timeoutMs = 10000) {
  return new Promise((resolve) => {
    const el = document.querySelector(selector);
    if (el) return resolve(el);

    const obs = new MutationObserver(() => {
      const found = document.querySelector(selector);
      if (found) {
        obs.disconnect();
        resolve(found);
      }
    });

    obs.observe(document.body, { childList: true, subtree: true });

    setTimeout(() => {
      obs.disconnect();
      resolve(null);
    }, timeoutMs);
  });
}

// Multi-strategy image extraction (In-page fetch with session cookies, then background service worker fetch, then clean CORS image, then HTML5 Canvas)
async function convertImageToDataURL(imgOrUrl) {
  const url = typeof imgOrUrl === "string" ? imgOrUrl : (imgOrUrl.src || imgOrUrl.currentSrc);

  // Method 1: Authenticated in-page fetch (Sends ChatGPT active authentication cookies)
  try {
    const response = await fetch(url, {
      credentials: "include",
      mode: "cors",
      headers: {
        "Accept": "image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8"
      }
    });
    if (response.ok) {
      const blob = await response.blob();
      if (blob.size >= 20000) {
        const dataUrl = await new Promise((resolve, reject) => {
          const reader = new FileReader();
          reader.onloadend = () => resolve(reader.result);
          reader.onerror = reject;
          reader.readAsDataURL(blob);
        });
        if (dataUrl && dataUrl.startsWith("data:image") && dataUrl.length >= 20000) {
          console.log("✅ Converted image via in-page authenticated fetch.");
          return dataUrl;
        }
      }
    }
  } catch (err) {
    console.warn("In-page fetch failed, delegating to background service worker...", err);
  }

  // Method 2: Delegate to background.js with CORS bypass & Referer headers
  try {
    const bgResult = await new Promise((resolve) => {
      chrome.runtime.sendMessage({ type: "FETCH_IMAGE_TO_BASE64", url: url }, (res) => {
        if (chrome.runtime.lastError || !res || res.status !== "success") {
          resolve(null);
        } else {
          resolve(res.dataUrl);
        }
      });
    });
    if (bgResult && bgResult.startsWith("data:image") && bgResult.length >= 20000) {
      console.log("✅ Converted image via background worker fetch.");
      return bgResult;
    }
  } catch (err) {
    console.warn("Background worker fetch failed, trying Clean CORS Image + Canvas...", err);
  }

  // Method 2.5: Clean CORS Image Object loading (prevents canvas tainting)
  try {
    const corsDataUrl = await new Promise((resolve) => {
      const imgCors = new Image();
      imgCors.crossOrigin = "anonymous";
      imgCors.onload = () => {
        try {
          const canvas = document.createElement("canvas");
          canvas.width = imgCors.naturalWidth;
          canvas.height = imgCors.naturalHeight;
          const ctx = canvas.getContext("2d");
          ctx.drawImage(imgCors, 0, 0);
          const dataUrl = canvas.toDataURL("image/png");
          if (dataUrl && dataUrl.length >= 20000) resolve(dataUrl);
          else resolve(null);
        } catch (e) {
          resolve(null);
        }
      };
      imgCors.onerror = () => resolve(null);
      imgCors.src = url;
    });
    if (corsDataUrl) {
      console.log("✅ Converted image via Clean CORS Image + Canvas.");
      return corsDataUrl;
    }
  } catch (err) {
    console.warn("Clean CORS Image conversion failed:", err);
  }

  // Method 3: HTML5 Canvas export (If image is already decoded in memory without CORS taint)
  try {
    const img = typeof imgOrUrl === "string" ? document.querySelector(`img[src="${imgOrUrl}"]`) : imgOrUrl;
    if (img && img.complete && img.naturalWidth > 0) {
      const canvas = document.createElement("canvas");
      canvas.width = img.naturalWidth;
      canvas.height = img.naturalHeight;
      const ctx = canvas.getContext("2d");
      ctx.drawImage(img, 0, 0);
      const dataUrl = canvas.toDataURL("image/png");
      if (dataUrl && dataUrl.length >= 20000 && !dataUrl.includes("data:,")) {
        console.log("✅ Converted image via HTML5 Canvas.");
        return dataUrl;
      }
    }
  } catch (err) {
    console.warn("Canvas conversion failed:", err);
  }

  return null;
}
