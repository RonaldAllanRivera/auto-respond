async function getConfig() {
  const syncCfg = await chrome.storage.sync.get(['backendBaseUrl', 'familyAccessKey', 'lessonId']);
  const localCfg = await chrome.storage.local.get(['installToken']);

  return {
    backendBaseUrl: syncCfg.backendBaseUrl || 'http://localhost:8000',
    familyAccessKey: syncCfg.familyAccessKey || '',
    lessonId: syncCfg.lessonId || null,
    installToken: localCfg.installToken || ''
  };
}

async function postJson(url, headers, payload) {
  const resp = await fetch(url, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...headers
    },
    body: JSON.stringify(payload)
  });

  return {
    ok: resp.ok,
    status: resp.status
  };
}

chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
  (async () => {
    if (!msg || msg.type !== 'CAPTION_EVENT') {
      sendResponse({ ok: false, error: 'unknown_message' });
      return;
    }

    const cfg = await getConfig();
    if (!cfg.familyAccessKey || !cfg.installToken || !cfg.backendBaseUrl) {
      sendResponse({ ok: false, error: 'not_configured' });
      return;
    }

    const url = cfg.backendBaseUrl.replace(/\/$/, '') + '/api/captions/ingest';

    const payload = {
      lesson_id: cfg.lessonId || null,
      meeting_title: msg.payload.meeting_title || '',
      meeting_code: msg.payload.meeting_code || '',
      speaker: msg.payload.speaker || '',
      text: msg.payload.text || '',
      captured_at: msg.payload.captured_at || new Date().toISOString()
    };

    if (!payload.text) {
      sendResponse({ ok: false, error: 'empty_text' });
      return;
    }

    const res = await postJson(
      url,
      {
        'X-Family-Key': cfg.familyAccessKey,
        'Authorization': 'Bearer ' + cfg.installToken
      },
      payload
    );

    sendResponse(res);
  })().catch((err) => {
    sendResponse({ ok: false, error: String(err) });
  });

  return true;
});
