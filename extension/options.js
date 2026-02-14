// ---------------------------------------------------------------------------
// Storage helpers
// ---------------------------------------------------------------------------

async function getConfig() {
  const data = await chrome.storage.sync.get(['backendBaseUrl', 'deviceToken', 'deviceId']);
  return {
    backendBaseUrl: data.backendBaseUrl || 'http://localhost:8000',
    deviceToken: data.deviceToken || '',
    deviceId: data.deviceId || '',
  };
}

async function saveBackendUrl(url) {
  await chrome.storage.sync.set({ backendBaseUrl: url });
}

async function saveDeviceCredentials(deviceId, token) {
  await chrome.storage.sync.set({ deviceId, deviceToken: token });
}

async function clearDeviceCredentials() {
  await chrome.storage.sync.remove(['deviceId', 'deviceToken']);
}

// ---------------------------------------------------------------------------
// UI helpers
// ---------------------------------------------------------------------------

function showStatus(elementId, message, type) {
  const el = document.getElementById(elementId);
  el.className = `status status-${type}`;
  el.textContent = message;
  el.style.display = 'block';
  if (type === 'success') {
    setTimeout(() => { el.style.display = 'none'; }, 3000);
  }
}

function updatePairingUI(isPaired) {
  document.getElementById('pairedInfo').classList.toggle('hidden', !isPaired);
  document.getElementById('pairForm').classList.toggle('hidden', isPaired);
}

// ---------------------------------------------------------------------------
// Init
// ---------------------------------------------------------------------------

document.addEventListener('DOMContentLoaded', async () => {
  const cfg = await getConfig();

  // Populate backend URL
  document.getElementById('backendBaseUrl').value = cfg.backendBaseUrl;

  // Show paired/unpaired state
  updatePairingUI(Boolean(cfg.deviceToken));

  // Save backend URL
  document.getElementById('saveUrl').addEventListener('click', async () => {
    const url = document.getElementById('backendBaseUrl').value.trim();
    if (!url) {
      showStatus('urlStatus', 'Please enter a URL.', 'error');
      return;
    }
    await saveBackendUrl(url);
    showStatus('urlStatus', 'URL saved.', 'success');
  });

  // Pair device
  document.getElementById('pairBtn').addEventListener('click', async () => {
    const code = document.getElementById('pairingCode').value.trim().toUpperCase();
    if (!code) {
      showStatus('pairStatus', 'Please enter a pairing code.', 'error');
      return;
    }

    const backendBaseUrl = document.getElementById('backendBaseUrl').value.trim();
    showStatus('pairStatus', 'Pairing...', 'info');

    try {
      const resp = await fetch(`${backendBaseUrl}/api/devices/pair/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ code, label: 'Chrome Extension' }),
      });

      const data = await resp.json();

      if (!resp.ok) {
        showStatus('pairStatus', data.error || 'Pairing failed.', 'error');
        return;
      }

      await saveDeviceCredentials(data.device_id, data.token);
      updatePairingUI(true);
      showStatus('pairStatus', 'Device paired successfully!', 'success');
      document.getElementById('pairingCode').value = '';
    } catch (err) {
      showStatus('pairStatus', `Network error: ${err.message}`, 'error');
    }
  });

  // Unpair device
  document.getElementById('unpairBtn').addEventListener('click', async () => {
    if (!confirm('Unpair this device? You will need a new pairing code to reconnect.')) return;
    await clearDeviceCredentials();
    updatePairingUI(false);
    showStatus('pairStatus', 'Device unpaired.', 'info');
  });

  // Clear activity log
  document.getElementById('clearLogBtn').addEventListener('click', () => {
    chrome.storage.local.set({ activityLog: [] });
    renderActivityLog([]);
    renderQA([]);
  });

  // Poll activity log every 2 seconds
  let lastLogLength = 0;
  setInterval(() => {
    chrome.storage.local.get({ activityLog: [] }, (result) => {
      const logs = result.activityLog;
      if (logs.length !== lastLogLength) {
        lastLogLength = logs.length;
        renderActivityLog(logs);
        renderQA(logs);
      }
    });
  }, 2000);

  // Initial render
  chrome.storage.local.get({ activityLog: [] }, (result) => {
    renderActivityLog(result.activityLog);
    renderQA(result.activityLog);
  });
});

// ---------------------------------------------------------------------------
// Activity log rendering
// ---------------------------------------------------------------------------

function renderActivityLog(logs) {
  const container = document.getElementById('activityLog');

  if (!logs || logs.length === 0) {
    container.innerHTML = '<div class="empty-state">No activity yet. Join a Google Meet call with captions enabled.</div>';
    return;
  }

  container.innerHTML = logs.map((entry) => {
    const time = formatTime(entry.ts);
    switch (entry.type) {
      case 'status':
        return `<div class="log-entry"><span class="log-time">${time}</span> <span class="log-status">● ${esc(entry.msg)}</span></div>`;
      case 'caption':
        const speaker = entry.speaker ? `<span class="log-speaker">${esc(entry.speaker)}</span>: ` : '';
        return `<div class="log-entry"><span class="log-time">${time}</span> <span class="log-caption">💬</span> ${speaker}${esc(entry.text)}</div>`;
      case 'question':
        return `<div class="log-entry"><span class="log-time">${time}</span> <span class="log-question">❓ Question: ${esc(entry.text)}</span></div>`;
      case 'error':
        return `<div class="log-entry"><span class="log-time">${time}</span> <span class="log-error">⚠ ${esc(entry.msg)}</span></div>`;
      default:
        return `<div class="log-entry"><span class="log-time">${time}</span> ${esc(JSON.stringify(entry))}</div>`;
    }
  }).join('');

  // Auto-scroll to bottom
  container.scrollTop = container.scrollHeight;
}

// ---------------------------------------------------------------------------
// Q&A rendering
// ---------------------------------------------------------------------------

function renderQA(logs) {
  const container = document.getElementById('qaList');
  const questions = (logs || []).filter((e) => e.type === 'question');

  if (questions.length === 0) {
    container.innerHTML = '<div class="empty-state">No questions detected yet. Join a Google Meet call with captions enabled.</div>';
    return;
  }

  container.innerHTML = questions.map((q) => {
    return `<div class="qa-item">
      <div class="qa-question">${esc(q.text)}</div>
      <div class="qa-answer pending">AI answer will appear here once Phase 4 is implemented.</div>
      <div class="qa-meta">${formatTime(q.ts)}</div>
    </div>`;
  }).join('');
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function formatTime(isoString) {
  if (!isoString) return '';
  try {
    const d = new Date(isoString);
    return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
  } catch {
    return '';
  }
}

function esc(str) {
  if (!str) return '';
  const div = document.createElement('div');
  div.textContent = str;
  return div.innerHTML;
}
