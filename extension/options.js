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
});
