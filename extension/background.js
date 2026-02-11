async function getConfig() {
  const syncCfg = await chrome.storage.sync.get(['backendBaseUrl', 'pairingCode']);
  return {
    backendBaseUrl: syncCfg.backendBaseUrl || 'http://localhost:8000',
    pairingCode: syncCfg.pairingCode || ''
  };
}

chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
  (async () => {
    if (!msg || msg.type !== 'PING') {
      sendResponse({ ok: false, error: 'unknown_message' });
      return;
    }

    const cfg = await getConfig();
    sendResponse({ ok: true, backendBaseUrl: cfg.backendBaseUrl, hasPairingCode: Boolean(cfg.pairingCode) });
  })().catch((err) => {
    sendResponse({ ok: false, error: String(err) });
  });

  return true;
});
