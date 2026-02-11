const STATE = {
  lastSentAtMs: 0,
  recent: new Map(),
  observer: null,
  lastContainerCheckAtMs: 0,
  captionContainer: null
};

function nowMs() {
  return Date.now();
}

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

function meetingCodeFromUrl() {
  try {
    const path = new URL(location.href).pathname;
    const parts = path.split('/').filter(Boolean);
    return parts.length > 0 ? parts[0] : '';
  } catch {
    return '';
  }
}

function meetingTitleFromDoc() {
  const t = document.title || '';
  return t.replace(/\s*-\s*Google\s+Meet\s*$/i, '').trim();
}

function cleanupRecent(maxAgeMs = 60_000) {
  const cutoff = nowMs() - maxAgeMs;
  for (const [k, ts] of STATE.recent.entries()) {
    if (ts < cutoff) STATE.recent.delete(k);
  }
}

function shouldSend(key, minIntervalMs = 900) {
  const t = nowMs();
  if (t - STATE.lastSentAtMs < minIntervalMs) return false;

  cleanupRecent();
  if (STATE.recent.has(key)) return false;

  STATE.recent.set(key, t);
  STATE.lastSentAtMs = t;
  return true;
}

function normalizeText(s) {
  return String(s || '')
    .replace(/\s+/g, ' ')
    .trim();
}

function tryParseCaptionFromNode(node) {
  if (!node) return null;

  const text = normalizeText(node.textContent);
  if (!text) return null;

  const lines = text.split('\n').map(normalizeText).filter(Boolean);
  if (lines.length === 0) return null;

  if (lines.length >= 2) {
    const speaker = lines[0];
    const caption = normalizeText(lines.slice(1).join(' '));
    if (caption) return { speaker, text: caption };
  }

  return { speaker: '', text };
}

function findCaptionContainer() {
  const ariaLive = document.querySelector('[aria-live="polite"], [aria-live="assertive"]');
  if (ariaLive) return ariaLive;

  const candidates = Array.from(document.querySelectorAll('div, section'))
    .filter((el) => {
      const t = normalizeText(el.textContent);
      return t.length > 0 && t.length < 240;
    })
    .slice(0, 200);

  return candidates.length ? candidates[0] : null;
}

async function postCaption({ speaker, text }) {
  const payload = {
    meeting_title: meetingTitleFromDoc(),
    meeting_code: meetingCodeFromUrl(),
    speaker: speaker || '',
    text,
    captured_at: new Date().toISOString()
  };

  try {
    await chrome.runtime.sendMessage({
      type: 'CAPTION_EVENT',
      payload
    });
  } catch {
  }
}

function attachObserver(container) {
  if (STATE.observer) {
    try { STATE.observer.disconnect(); } catch {}
    STATE.observer = null;
  }

  if (!container) return;

  STATE.captionContainer = container;

  STATE.observer = new MutationObserver(async (mutations) => {
    for (const m of mutations) {
      if (!m.addedNodes) continue;
      for (const n of m.addedNodes) {
        if (!(n instanceof HTMLElement)) continue;
        const cap = tryParseCaptionFromNode(n);
        if (!cap) continue;

        const key = normalizeText((cap.speaker ? cap.speaker + ':' : '') + cap.text).toLowerCase();
        if (!shouldSend(key)) continue;

        await postCaption(cap);
      }
    }
  });

  STATE.observer.observe(container, { childList: true, subtree: true });
}

async function tick() {
  const t = nowMs();
  if (!STATE.captionContainer || (t - STATE.lastContainerCheckAtMs) > 5000) {
    STATE.lastContainerCheckAtMs = t;
    const container = findCaptionContainer();
    if (container && container !== STATE.captionContainer) {
      attachObserver(container);
    }
  }

  setTimeout(tick, 1000);
}

tick();
