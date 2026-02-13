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

// ---------------------------------------------------------------------------
// Authenticated fetch helper
// ---------------------------------------------------------------------------

async function apiFetch(path, options = {}) {
  const cfg = await getConfig();
  if (!cfg.deviceToken) {
    return { ok: false, error: 'not_paired' };
  }

  const url = `${cfg.backendBaseUrl}${path}`;
  const headers = {
    'Content-Type': 'application/json',
    'X-Device-Token': cfg.deviceToken,
    ...(options.headers || {}),
  };

  try {
    const resp = await fetch(url, { ...options, headers });
    const data = await resp.json();
    return { ok: resp.ok, status: resp.status, data };
  } catch (err) {
    return { ok: false, error: err.message };
  }
}

// ---------------------------------------------------------------------------
// Message handler (content script → background)
// ---------------------------------------------------------------------------

chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
  (async () => {
    if (!msg || !msg.type) {
      sendResponse({ ok: false, error: 'unknown_message' });
      return;
    }

    if (msg.type === 'PING') {
      const cfg = await getConfig();
      sendResponse({
        ok: true,
        backendBaseUrl: cfg.backendBaseUrl,
        isPaired: Boolean(cfg.deviceToken),
      });
      return;
    }

    if (msg.type === 'CAPTION') {
      const result = await apiFetch('/api/captions/', {
        method: 'POST',
        body: JSON.stringify(msg.payload),
      });
      sendResponse(result);
      return;
    }

    if (msg.type === 'QUESTION') {
      const result = await apiFetch('/api/questions/', {
        method: 'POST',
        body: JSON.stringify(msg.payload),
      });
      sendResponse(result);
      return;
    }

    sendResponse({ ok: false, error: 'unknown_message_type' });
  })().catch((err) => {
    sendResponse({ ok: false, error: String(err) });
  });

  return true;
});
