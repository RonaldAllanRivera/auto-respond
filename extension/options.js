async function getConfig() {
  const data = await chrome.storage.sync.get(['backendBaseUrl', 'pairingCode']);
  return {
    backendBaseUrl: data.backendBaseUrl || 'http://localhost:8000',
    pairingCode: data.pairingCode || ''
  };
}

async function setConfig(cfg) {
  await chrome.storage.sync.set(cfg);
}

async function setStatus(msg) {
  const el = document.getElementById('status');
  el.textContent = msg;
}

document.addEventListener('DOMContentLoaded', async () => {
  const cfg = await getConfig();
  document.getElementById('backendBaseUrl').value = cfg.backendBaseUrl;
  document.getElementById('pairingCode').value = cfg.pairingCode;

  document.getElementById('form').addEventListener('submit', async (e) => {
    e.preventDefault();

    const backendBaseUrl = document.getElementById('backendBaseUrl').value.trim();
    const pairingCode = document.getElementById('pairingCode').value.trim();

    await setConfig({ backendBaseUrl, pairingCode });
    await setStatus('Saved.');
  });
});
