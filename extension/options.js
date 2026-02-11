async function getConfig() {
  const data = await chrome.storage.sync.get([
    'backendBaseUrl',
    'familyAccessKey',
    'lessonId',
    'installLabel'
  ]);
  return {
    backendBaseUrl: data.backendBaseUrl || 'http://localhost:8000',
    familyAccessKey: data.familyAccessKey || '',
    lessonId: data.lessonId || '',
    installLabel: data.installLabel || ''
  };
}

async function setConfig(cfg) {
  await chrome.storage.sync.set(cfg);
}

async function setStatus(msg) {
  const el = document.getElementById('status');
  el.textContent = msg;
}

async function refreshInstallToken() {
  const cfg = await getConfig();

  if (!cfg.backendBaseUrl || !cfg.familyAccessKey) {
    await setStatus('Set backend URL and family access key first.');
    return;
  }

  const url = cfg.backendBaseUrl.replace(/\/$/, '') + '/api/install';
  const resp = await fetch(url, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-Family-Key': cfg.familyAccessKey
    },
    body: JSON.stringify({ label: cfg.installLabel || '' })
  });

  if (!resp.ok) {
    const text = await resp.text();
    await setStatus('Install failed: ' + resp.status + ' ' + text);
    return;
  }

  const data = await resp.json();
  if (!data.token) {
    await setStatus('Install failed: missing token');
    return;
  }

  await chrome.storage.local.set({ installToken: data.token });
  await setStatus('Install token updated.');
}

document.addEventListener('DOMContentLoaded', async () => {
  const cfg = await getConfig();
  document.getElementById('backendBaseUrl').value = cfg.backendBaseUrl;
  document.getElementById('familyAccessKey').value = cfg.familyAccessKey;
  document.getElementById('lessonId').value = cfg.lessonId;
  document.getElementById('installLabel').value = cfg.installLabel;

  document.getElementById('form').addEventListener('submit', async (e) => {
    e.preventDefault();

    const backendBaseUrl = document.getElementById('backendBaseUrl').value.trim();
    const familyAccessKey = document.getElementById('familyAccessKey').value.trim();
    const lessonIdRaw = document.getElementById('lessonId').value.trim();
    const installLabel = document.getElementById('installLabel').value.trim();

    await setConfig({
      backendBaseUrl,
      familyAccessKey,
      lessonId: lessonIdRaw ? Number(lessonIdRaw) : '',
      installLabel
    });

    await setStatus('Saved.');
  });

  document.getElementById('installBtn').addEventListener('click', async () => {
    await setStatus('Requesting install token...');
    try {
      await refreshInstallToken();
    } catch (err) {
      await setStatus('Install error: ' + String(err));
    }
  });
});
