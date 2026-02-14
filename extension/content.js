// ---------------------------------------------------------------------------
// Meet Lessons — Content Script (Google Meet caption reader)
// Runs on https://meet.google.com/* pages
//
// Approach based on TranscripTonic (proven, actively maintained extension):
//   1. Wait for call_end icon → meeting has started
//   2. Wait for div[role="region"][tabindex="0"] → caption container
//   3. Observe characterData mutations on that container
//   4. Read mutation.target.parentElement for text, .previousSibling for speaker
// ---------------------------------------------------------------------------

console.log('[Meet Lessons] content.js loaded');

(function () {
  'use strict';

  var QUESTION_COOLDOWN = 5000;
  var BUFFER_MAX        = 2000;
  var MAX_LOG           = 200;
  var PING_RETRY_MS     = 3000;
  var PING_MAX_RETRIES  = 5;

  var INTERROGATIVE_LIST = [
    'what','when','where','who','why','how',
    'is','are','do','does','did',
    'can','could','will','would','should'
  ];

  var captionBuffer = '';
  var lastQTime     = 0;
  var meetingId     = '';
  var meetingTitle  = '';
  var isPaired      = false;
  var containerObservers = [];
  var containerState = new WeakMap();
  var seenCaptionSet = {};
  var seenCaptionCount = 0;

  // Buffer: accumulate text per speaker before sending
  var personNameBuffer = '';
  var transcriptTextBuffer = '';

  // ---- Logging ----

  function log(msg) {
    console.log('[Meet Lessons] ' + msg);
  }

  function appendLog(entry) {
    try {
      chrome.storage.local.get({ activityLog: [] }, function(r) {
        if (chrome.runtime.lastError) return;
        var logs = r.activityLog || [];
        entry.ts = new Date().toISOString();
        logs.push(entry);
        while (logs.length > MAX_LOG) logs.shift();
        chrome.storage.local.set({ activityLog: logs });
      });
    } catch (e) {}
  }

  // ---- Helpers ----

  function getMeetingId() {
    var m = location.pathname.match(/\/([a-z]{3}-[a-z]{4}-[a-z]{3})/);
    return m ? m[1] : location.pathname.replace(/^\//, '');
  }

  function getMeetingTitle() {
    var el = document.querySelector('[data-meeting-title]');
    if (el) return el.getAttribute('data-meeting-title');
    var t = document.title.replace(/\s*[-–]\s*Google Meet\s*$/i, '').trim();
    return t || 'Untitled Meeting';
  }

  // ---- Background messaging ----

  function sendBg(type, payload) {
    try {
      chrome.runtime.sendMessage({ type: type, payload: payload }, function() {
        if (chrome.runtime.lastError) { /* swallow */ }
      });
    } catch (e) {}
  }

  function pingWithRetry(attempt) {
    if (attempt > PING_MAX_RETRIES) {
      appendLog({ type: 'status', msg: 'Backend unreachable — logging locally' });
      return;
    }
    try {
      chrome.runtime.sendMessage({ type: 'PING' }, function(resp) {
        if (chrome.runtime.lastError) {
          setTimeout(function() { pingWithRetry(attempt + 1); }, PING_RETRY_MS);
          return;
        }
        if (resp && resp.isPaired) {
          isPaired = true;
          log('Device paired');
          appendLog({ type: 'status', msg: 'Device paired ✓' });
        } else {
          appendLog({ type: 'status', msg: 'Not paired — pair in extension options to send to backend' });
        }
      });
    } catch (e) {
      setTimeout(function() { pingWithRetry(attempt + 1); }, PING_RETRY_MS);
    }
  }

  function flushBufferedCaption() {
    if (personNameBuffer && transcriptTextBuffer) {
      sendCaption(personNameBuffer, transcriptTextBuffer);
      personNameBuffer = '';
      transcriptTextBuffer = '';
    }
  }

  // ---- Question detection ----

  function isQuestion(text) {
    var t = text.trim();
    if (!t) return false;
    if (t.charAt(t.length - 1) === '?') return true;
    var sentences = t.split(/[.!]\s+/);
    var last = sentences[sentences.length - 1].trim().toLowerCase();
    var first = last.split(/\s+/)[0];
    for (var i = 0; i < INTERROGATIVE_LIST.length; i++) {
      if (first === INTERROGATIVE_LIST[i]) return true;
    }
    return false;
  }

  // ---- Send a completed caption block ----

  function sendCaption(speaker, text) {
    if (!text || text.length < 2) return;

    var key = (speaker || '') + '|' + text;
    if (seenCaptionSet[key]) return;
    seenCaptionSet[key] = true;
    seenCaptionCount += 1;
    if (seenCaptionCount > 1000) {
      seenCaptionSet = {};
      seenCaptionCount = 0;
    }

    captionBuffer += ' ' + text;
    if (captionBuffer.length > BUFFER_MAX)
      captionBuffer = captionBuffer.slice(-BUFFER_MAX);

    log('Caption [' + (speaker || '?') + ']: ' + text.substring(0, 120));
    appendLog({ type: 'caption', speaker: speaker || '', text: text.substring(0, 200) });

    sendBg('CAPTION', {
      meeting_id: meetingId, meeting_title: meetingTitle,
      speaker: speaker || '', text: text
    });

    if (isQuestion(text) && Date.now() - lastQTime > QUESTION_COOLDOWN) {
      lastQTime = Date.now();
      log('Question: ' + text.substring(0, 120));
      appendLog({ type: 'question', text: text.substring(0, 200) });
      sendBg('QUESTION', {
        question: text, context: captionBuffer.trim(),
        meeting_id: meetingId, meeting_title: meetingTitle
      });
    }
  }

  // ---- Wait for a DOM element to appear ----

  function waitForElement(selector, textContent) {
    return new Promise(function(resolve) {
      // Check if already exists
      var existing = findElement(selector, textContent);
      if (existing) { resolve(existing); return; }

      var observer = new MutationObserver(function() {
        var el = findElement(selector, textContent);
        if (el) {
          observer.disconnect();
          resolve(el);
        }
      });
      observer.observe(document.body, { childList: true, subtree: true });
    });
  }

  function findElement(selector, textContent) {
    var elements = document.querySelectorAll(selector);
    if (!textContent) return elements[0] || null;
    for (var i = 0; i < elements.length; i++) {
      if (elements[i].textContent.trim() === textContent) return elements[i];
    }
    return null;
  }

  // ---- Transcript MutationObserver callback ----
  // Based on TranscripTonic's proven approach

  function isUiNoiseLine(line) {
    var l = line.toLowerCase();
    var noise = [
      'captions', 'caption settings', 'open caption settings',
      'font size', 'font color', 'format_size', 'circle',
      'turn on captions', 'turn off captions',
      'present now', 'raise hand', 'leave call',
      'you', 'test call'
    ];
    for (var i = 0; i < noise.length; i++) {
      if (l === noise[i]) return true;
    }
    return false;
  }

  function processContainerText(container) {
    var text = '';
    try {
      text = (container.innerText || '').trim();
    } catch (_) {
      return;
    }
    if (!text) return;

    var prev = containerState.get(container) || '';
    if (text === prev) return;
    containerState.set(container, text);

    var lines = text.split('\n')
      .map(function (x) { return x.trim(); })
      .filter(function (x) { return x.length >= 2 && !isUiNoiseLine(x); });

    if (!lines.length) return;

    for (var i = 0; i < lines.length; i++) {
      var line = lines[i];
      var speaker = '';

      var looksLikeSpeaker = line.length < 48 &&
        /^[A-Z][a-zA-Z]/.test(line) &&
        !/[.?!,:;]$/.test(line) &&
        line.split(/\s+/).length <= 5;

      if (looksLikeSpeaker && i + 1 < lines.length) {
        speaker = line;
        i += 1;
        line = lines[i] || '';
      }

      if (!line || isUiNoiseLine(line)) continue;
      if (speaker && line.toLowerCase().indexOf(speaker.toLowerCase()) === 0) {
        line = line.slice(speaker.length).trim();
      }
      if (line.length < 2) continue;

      sendCaption(speaker, line);
    }
  }

  function transcriptMutationCallback(mutationsList) {
    for (var m = 0; m < mutationsList.length; m++) {
      var mutation = mutationsList[m];
      try {
        var base = mutation.target && mutation.target.nodeType === 1
          ? mutation.target
          : mutation.target && mutation.target.parentElement
            ? mutation.target.parentElement
            : null;
        if (!base) continue;

        var container = base.closest('div[role="region"], div[aria-live]');
        if (!container) continue;
        processContainerText(container);
      } catch (err) {
        log('Mutation error: ' + err.message);
      }
    }
  }

  // ---- Main meeting flow ----

  function findCaptionContainers() {
    var selectors = [
      'div[role="region"][tabindex="0"]',
      'div[role="region"][aria-live]',
      'div[aria-live="assertive"]',
      'div[aria-live="polite"]'
    ];
    var found = [];
    var seen = new Set();

    for (var i = 0; i < selectors.length; i++) {
      var nodes = document.querySelectorAll(selectors[i]);
      for (var j = 0; j < nodes.length; j++) {
        var rect = nodes[j].getBoundingClientRect();
        if (!rect || rect.width < 100 || rect.height < 20) continue;
        // Captions are rendered in the lower half of the viewport.
        if (rect.top >= window.innerHeight * 0.45) {
          if (!seen.has(nodes[j])) {
            seen.add(nodes[j]);
            found.push(nodes[j]);
          }
        }
      }
    }
    return found;
  }

  function isObservedContainer(container) {
    for (var i = 0; i < containerObservers.length; i++) {
      if (containerObservers[i].el === container) return true;
    }
    return false;
  }

  function attachObserverIfNeeded() {
    var containers = findCaptionContainers();
    for (var i = 0; i < containers.length; i++) {
      var container = containers[i];
      if (isObservedContainer(container)) continue;

      var observer = new MutationObserver(transcriptMutationCallback);
      observer.observe(container, {
        childList: true,
        attributes: true,
        subtree: true,
        characterData: true
      });
      containerObservers.push({ el: container, observer: observer });

      // Also process current snapshot immediately.
      processContainerText(container);

      log('Caption container found — observing mutations');
      appendLog({ type: 'status', msg: 'Caption container found — capturing started ✓' });
    }
  }

  function startMeetingRoutines() {
    log('Starting caption capture (no meeting-start gate)');
    appendLog({ type: 'status', msg: 'Looking for caption container...' });

    // Try immediately and then keep retrying as Meet frequently re-renders overlays.
    attachObserverIfNeeded();
    setInterval(attachObserverIfNeeded, 1000);

    // Polling fallback: some Meet updates do not emit useful mutation records.
    setInterval(function () {
      for (var i = 0; i < containerObservers.length; i++) {
        processContainerText(containerObservers[i].el);
      }
    }, 800);
  }

  // ---- Init ----

  meetingId = getMeetingId();
  meetingTitle = getMeetingTitle();

  log('Loaded for meeting: ' + meetingId);
  chrome.storage.local.set({ activityLog: [] });
  appendLog({ type: 'status', msg: 'Content script loaded — meeting ' + meetingId });

  // PING background with retry
  pingWithRetry(1);

  // Poll meeting title
  setInterval(function() {
    var t = getMeetingTitle();
    if (t && t !== meetingTitle) meetingTitle = t;
  }, 5000);

  startMeetingRoutines();

  // Flush any buffered caption when tab/page unloads.
  window.addEventListener('beforeunload', flushBufferedCaption);

})();
