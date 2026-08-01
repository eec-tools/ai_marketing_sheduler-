// popup.js - Controller for AI Marketing Scheduler Companion popup

document.addEventListener("DOMContentLoaded", async () => {
  const pendingCountEl = document.getElementById("pendingCount");
  const pollBtn = document.getElementById("pollBtn");
  const testBtn = document.getElementById("testBtn");
  const backendUrlDisplay = document.getElementById("backendUrlDisplay");

  // Load backend URL from storage
  const { backendUrl = "http://localhost:8000" } = await chrome.storage.local.get("backendUrl");
  backendUrlDisplay.textContent = backendUrl.replace("http://", "");

  // Initial check for pending jobs
  await checkPendingStats(backendUrl, pendingCountEl);

  pollBtn.addEventListener("click", async () => {
    pollBtn.disabled = true;
    pollBtn.textContent = "⏳ Checking...";
    try {
      await chrome.runtime.sendMessage({ type: "MANUAL_POLL" });
      await new Promise(r => setTimeout(r, 600));
      await checkPendingStats(backendUrl, pendingCountEl);
    } finally {
      pollBtn.disabled = false;
      pollBtn.innerHTML = "🔄 Check Pending Jobs Now";
    }
  });

  testBtn.addEventListener("click", async () => {
    testBtn.disabled = true;
    testBtn.textContent = "🚀 Starting Test...";
    try {
      const res = await chrome.runtime.sendMessage({
        type: "TEST_GENERATE",
        prompt: "A futuristic AI robot painting a glowing masterpiece on a digital canvas, high quality 3d render, vibrant studio lighting"
      });
      if (res && res.status === "success") {
        testBtn.textContent = "✅ Test Job Queued!";
      } else {
        testBtn.textContent = "❌ Test Failed";
      }
    } catch (err) {
      console.error(err);
      testBtn.textContent = "❌ Error";
    } finally {
      setTimeout(() => {
        testBtn.disabled = false;
        testBtn.innerHTML = "🧪 Test ChatGPT Generation";
      }, 3000);
    }
  });
});

async function checkPendingStats(backendUrl, countEl) {
  try {
    const res = await fetch(`${backendUrl}/api/v1/extension/jobs/pending`);
    if (res.ok) {
      const jobs = await res.json();
      countEl.textContent = Array.isArray(jobs) ? jobs.length : 0;
    } else {
      countEl.textContent = "Off";
    }
  } catch (err) {
    countEl.textContent = "Err";
  }
}
