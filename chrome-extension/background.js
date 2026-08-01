// background.js - Manifest V3 Service Worker for AI Marketing Scheduler Companion

const DEFAULT_BACKEND_URL = "http://localhost:8000";

// Helper for notifications with safe inline data URL icon (Rule 15 safe)
const SAFE_ICON_DATA_URL = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==";

function notify(title, message) {
  try {
    chrome.notifications.create({
      type: "basic",
      iconUrl: SAFE_ICON_DATA_URL,
      title: title,
      message: message
    });
  } catch (err) {
    console.error("Notification error:", err);
  }
}

// Dynamic declarativeNetRequest rules to append CORS headers to CDN images
async function setupCorsRules() {
  try {
    if (!chrome.declarativeNetRequest) return;
    const existingRules = await chrome.declarativeNetRequest.getDynamicRules();
    const existingIds = existingRules.map(r => r.id);
    if (existingIds.length > 0) {
      await chrome.declarativeNetRequest.updateDynamicRules({ removeRuleIds: existingIds });
    }

    await chrome.declarativeNetRequest.updateDynamicRules({
      addRules: [
        {
          id: 1,
          priority: 1,
          action: {
            type: "modifyHeaders",
            responseHeaders: [
              { header: "Access-Control-Allow-Origin", operation: "set", value: "*" }
            ]
          },
          condition: {
            urlFilter: "oaiusercontent.com",
            resourceTypes: ["image", "xmlhttprequest"]
          }
        }
      ]
    });
    console.log("✅ Declarative Net Request CORS bypass rules registered successfully!");
  } catch (err) {
    console.debug("Note: declarativeNetRequest rule update skipped or not permitted:", err.message);
  }
}
setupCorsRules();

// Method 2: Chrome DevTools Protocol (CDP) Network Interceptor for wire-level image capture
const pendingImageResponses = new Map();

chrome.debugger.onEvent.addListener(async (source, method, params) => {
  if (method === "Network.responseReceived") {
    const resp = params.response;
    if (resp && resp.url && resp.url.includes("oaiusercontent.com") && resp.mimeType && resp.mimeType.startsWith("image/")) {
      pendingImageResponses.set(params.requestId, { tabId: source.tabId, url: resp.url, mimeType: resp.mimeType });
    }
  }

  if (method === "Network.loadingFinished") {
    const reqInfo = pendingImageResponses.get(params.requestId);
    if (reqInfo) {
      pendingImageResponses.delete(params.requestId);
      console.log("⚡ CDP Network.loadingFinished for DALL-E image:", reqInfo.url);
      
      try {
        const bodyRes = await chrome.debugger.sendCommand(
          { tabId: reqInfo.tabId },
          "Network.getResponseBody",
          { requestId: params.requestId }
        );

        if (bodyRes && bodyRes.body) {
          const dataUrl = bodyRes.base64Encoded
            ? `data:${reqInfo.mimeType || 'image/png'};base64,${bodyRes.body}`
            : bodyRes.body;

          if (dataUrl && dataUrl.length >= 20000) {
            console.log(`🎉 CDP Debugger extracted full DALL-E image (${Math.round(dataUrl.length / 1024)} KB)! Uploading directly...`);
            
            const { processingJobs = {}, backendUrl = DEFAULT_BACKEND_URL } = await chrome.storage.local.get(["processingJobs", "backendUrl"]);
            const jobIds = Object.keys(processingJobs);
            if (jobIds.length > 0) {
              const targetJobId = jobIds[0];
              console.log(`Completing job ${targetJobId} using wire-level CDP extracted image!`);
              
              const res = await fetch(`${backendUrl}/api/v1/extension/jobs/${targetJobId}/complete`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                  image_data: dataUrl,
                  notes: "Generated via ChatGPT Chrome Extension (CDP Protocol)"
                })
              });

              if (res.ok) {
                notify("AI Marketing Scheduler Companion", "✅ Graphic extracted via network protocol & sent to dashboard!");
                await chrome.action.setBadgeText({ text: "OK" });
                await chrome.action.setBadgeBackgroundColor({ color: "#10B981" });
                setTimeout(() => chrome.action.setBadgeText({ text: "" }), 4000);
                delete processingJobs[targetJobId];
                await chrome.storage.local.set({ processingJobs });
              }
            }
          }
        }
      } catch (err) {
        console.error("Failed to get response body via CDP:", err);
      }
    }
  }
});

// Initialize alarm for periodic polling (every 0.1 minutes = 6 seconds)
chrome.runtime.onInstalled.addListener(async () => {
  await setupCorsRules();
  await chrome.alarms.create("pollJobs", { periodInMinutes: 0.1 });
  await chrome.storage.local.set({ backendUrl: DEFAULT_BACKEND_URL });
  await chrome.action.setBadgeText({ text: "ON" });
  await chrome.action.setBadgeBackgroundColor({ color: "#2563EB" });
  console.log("AI Marketing Scheduler Companion installed and polling started.");
});

chrome.runtime.onStartup.addListener(async () => {
  await setupCorsRules();
  await chrome.alarms.create("pollJobs", { periodInMinutes: 0.1 });
});

chrome.alarms.onAlarm.addListener(async (alarm) => {
  if (alarm.name === "pollJobs") {
    await pollPendingJobs();
  }
});

// Check pending jobs from backend
async function pollPendingJobs() {
  const { backendUrl = DEFAULT_BACKEND_URL, processingJobs = {} } = await chrome.storage.local.get([
    "backendUrl",
    "processingJobs"
  ]);

  try {
    const res = await fetch(`${backendUrl}/api/v1/extension/jobs/pending`);
    if (!res.ok) return;

    const jobs = await res.json();
    if (!jobs || jobs.length === 0) return;

    // Filter jobs: execute only if not currently processing OR if stuck processing > 3 minutes
    const now = Date.now();
    for (const job of jobs) {
      const activeInfo = processingJobs[job.id];
      if (!activeInfo || now - activeInfo.startTime > 180000) {
        console.log(`Found pending job ${job.id}, claiming...`);
        processingJobs[job.id] = { startTime: now, prompt: job.prompt };
        await chrome.storage.local.set({ processingJobs });
        await claimAndExecuteJob(job, backendUrl, processingJobs);
        break; // Process one at a time
      }
    }
  } catch (err) {
    // Backend offline or unreachable, ignore quietly
  }
}

// Claim job and send to ChatGPT tab
async function claimAndExecuteJob(job, backendUrl, processingJobs) {
  try {
    await fetch(`${backendUrl}/api/v1/extension/jobs/${job.id}/claim`, { method: "POST" });

    // Find active ChatGPT tab or create one
    const tabs = await chrome.tabs.query({ url: ["*://chatgpt.com/*", "*://chat.openai.com/*"] });
    let tabId = null;

    if (tabs.length > 0) {
      tabId = tabs[0].id;
      await chrome.tabs.update(tabId, { active: true });
    } else {
      notify("AI Marketing Scheduler Companion", "Opening ChatGPT tab to generate DALL-E graphic...");
      const newTab = await chrome.tabs.create({ url: "https://chatgpt.com/", active: true });
      tabId = newTab.id;
      await new Promise(r => setTimeout(r, 5000));
    }

    // Attach CDP Debugger for wire-level network capture
    try {
      await chrome.debugger.attach({ tabId: tabId }, "1.3");
      await chrome.debugger.sendCommand({ tabId: tabId }, "Network.enable");
      console.log(`⚡ Attached Chrome DevTools Protocol debugger to tab ${tabId} for instant wire-level image capture!`);
    } catch (dbgErr) {
      console.warn("Debugger already attached or failed to attach:", dbgErr);
    }

    console.log(`Sending job ${job.id} to ChatGPT tab ${tabId}`);
    try {
      await chrome.tabs.sendMessage(tabId, {
        type: "GENERATE_IMAGE",
        jobId: job.id,
        prompt: job.prompt
      });
    } catch (sendErr) {
      console.warn("Content script not listening, injecting explicitly and retrying...", sendErr);
      await chrome.scripting.executeScript({
        target: { tabId: tabId },
        files: ["content.js"]
      });
      await new Promise(r => setTimeout(r, 1500));
      await chrome.tabs.sendMessage(tabId, {
        type: "GENERATE_IMAGE",
        jobId: job.id,
        prompt: job.prompt
      });
    }
  } catch (err) {
    console.error(`Failed to execute job ${job.id}:`, err);
    delete processingJobs[job.id];
    await chrome.storage.local.set({ processingJobs });
  }
}

// Listen for messages from content.js or popup.js
chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message.type === "IMAGE_READY") {
    (async () => {
      const { backendUrl = DEFAULT_BACKEND_URL, processingJobs = {} } = await chrome.storage.local.get([
        "backendUrl",
        "processingJobs"
      ]);

      console.log(`Job ${message.jobId} completed! Uploading to backend...`);
      try {
        const res = await fetch(`${backendUrl}/api/v1/extension/jobs/${message.jobId}/complete`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            image_data: message.dataUrl,
            notes: "Generated via ChatGPT Chrome Extension"
          })
        });

        if (res.ok) {
          notify("AI Marketing Scheduler Companion", "✅ Graphic generated and sent to your dashboard!");
          await chrome.action.setBadgeText({ text: "OK" });
          await chrome.action.setBadgeBackgroundColor({ color: "#10B981" });
          setTimeout(() => chrome.action.setBadgeText({ text: "" }), 4000);
        } else {
          notify("AI Marketing Scheduler Companion", "❌ Failed to send image to backend API.");
        }
      } catch (err) {
        console.error("Error sending completed image to backend:", err);
      } finally {
        delete processingJobs[message.jobId];
        await chrome.storage.local.set({ processingJobs });
      }
    })();
    return true;
  }

  if (message.type === "FETCH_IMAGE_TO_BASE64") {
    (async () => {
      try {
        console.log("Background worker fetching image url directly:", message.url);
        const res = await fetch(message.url, {
          credentials: "include",
          headers: {
            "Accept": "image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8",
            "Referer": "https://chatgpt.com/"
          }
        });
        if (!res.ok) {
          throw new Error(`HTTP status ${res.status} when fetching image from CDN`);
        }
        const blob = await res.blob();
        if (blob.size < 20000) {
          throw new Error(`Blob too small (${blob.size} bytes), likely an error page or thumbnail`);
        }
        const reader = new FileReader();
        reader.onloadend = () => sendResponse({ status: "success", dataUrl: reader.result });
        reader.onerror = (err) => sendResponse({ status: "error", error: err.toString() });
        reader.readAsDataURL(blob);
      } catch (err) {
        console.error("Background fetch error:", err);
        sendResponse({ status: "error", error: err.message });
      }
    })();
    return true;
  }

  if (message.type === "MANUAL_POLL") {
    (async () => {
      await pollPendingJobs();
      sendResponse({ status: "ok" });
    })();
    return true;
  }

  if (message.type === "TEST_GENERATE") {
    (async () => {
      const { backendUrl = DEFAULT_BACKEND_URL } = await chrome.storage.local.get("backendUrl");
      try {
        const res = await fetch(`${backendUrl}/api/v1/extension/jobs`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            prompt: message.prompt || "Professional social media banner showing modern business growth and technology, sleek lighting, 4k",
            style: "chatgpt"
          })
        });
        const job = await res.json();
        await pollPendingJobs();
        sendResponse({ status: "success", job });
      } catch (err) {
        sendResponse({ status: "error", error: err.message });
      }
    })();
    return true;
  }
});
