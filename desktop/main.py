#!/usr/bin/env python3
"""
Meet Lessons Desktop App — Screenshot Capture + OCR + Question Detection

Listens for Print Screen key, grabs the clipboard screenshot, runs local OCR,
detects questions, and sends data to the Django backend.

Usage:
    python main.py
"""

import hashlib
import sys
import threading
import time
import tkinter as tk
from collections import deque
from datetime import datetime
from tkinter import messagebox, ttk

from PIL import Image, ImageGrab
from pynput import keyboard

import api_client
import config
import detector
import ocr


class MeetLessonsApp:
    """Main tkinter application."""

    _CLIPBOARD_POLL_MS_MIN = 900
    _CLIPBOARD_POLL_MS_MAX = 4000
    _CLIPBOARD_POLL_BACKOFF_MULT = 1.35
    _PAIRING_REVALIDATE_MS = 30_000

    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Meet Lessons")
        self.root.geometry("520x700")
        self.root.resizable(True, True)
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

        self._hotkey_listener = None
        self._processing = False
        self._clipboard_job = None
        self._pairing_revalidate_job = None
        self._pairing_revalidate_running = False
        self._clipboard_last_sig = None
        self._clipboard_seen = deque(maxlen=200)
        self._pending_clipboard_image = None
        self._pending_clipboard_sig = None
        self._clipboard_poll_ms = self._CLIPBOARD_POLL_MS_MIN
        
        # Phase 16: Session context management (last 10 captions)
        self._session_context = deque(maxlen=10)
        
        # Phase 16: Mode selection and lesson management
        self._current_mode = config.get("capture_mode", "recitation")  # "recitation" or "lesson"
        self._selected_lesson_id = None
        self._selected_lesson_title = None
        self._lessons_list = []

        self._build_ui()
        self._refresh_pairing_status()
        self._start_pairing_revalidation()
        self._start_hotkey_listener()
        self._start_clipboard_watcher()
        
        # Phase 16: Initialize mode UI state
        self._on_mode_changed()

    # ------------------------------------------------------------------ UI
    # ------------------------------------------------------------------ UI

    def _build_ui(self):
        # Main container with padding
        main = ttk.Frame(self.root, padding=12)
        main.pack(fill=tk.BOTH, expand=True)

        # ---- Device Pairing ----
        pair_frame = ttk.LabelFrame(main, text="Device Pairing", padding=8)
        pair_frame.pack(fill=tk.X, pady=(0, 8))

        self.pair_status_var = tk.StringVar(value="Checking...")
        ttk.Label(pair_frame, textvariable=self.pair_status_var).pack(anchor=tk.W)

        pair_input_frame = ttk.Frame(pair_frame)
        pair_input_frame.pack(fill=tk.X, pady=(6, 0))

        self.code_var = tk.StringVar()
        self.code_entry = ttk.Entry(pair_input_frame, textvariable=self.code_var, width=20)
        self.code_entry.pack(side=tk.LEFT, padx=(0, 6))

        self.pair_btn = ttk.Button(pair_input_frame, text="Pair Device", command=self._pair_device)
        self.pair_btn.pack(side=tk.LEFT, padx=(0, 6))

        self.unpair_btn = ttk.Button(pair_input_frame, text="Unpair", command=self._unpair_device)
        self.unpair_btn.pack(side=tk.LEFT)

        # ---- Mode Selection (Phase 16) ----
        mode_frame = ttk.LabelFrame(main, text="Mode Selection", padding=8)
        mode_frame.pack(fill=tk.X, pady=(0, 8))

        self.mode_var = tk.StringVar(value=self._current_mode)
        ttk.Radiobutton(
            mode_frame,
            text="Recitation Mode (Live Capture)",
            variable=self.mode_var,
            value="recitation",
            command=self._on_mode_changed
        ).pack(anchor=tk.W)
        ttk.Radiobutton(
            mode_frame,
            text="Lesson Mode (Study Documents)",
            variable=self.mode_var,
            value="lesson",
            command=self._on_mode_changed
        ).pack(anchor=tk.W, pady=(4, 0))

        # Lesson selection (only visible in Lesson mode)
        self.lesson_select_frame = ttk.Frame(mode_frame)
        self.lesson_select_frame.pack(fill=tk.X, pady=(8, 0))

        ttk.Label(self.lesson_select_frame, text="Select Lesson:").pack(anchor=tk.W)
        
        lesson_combo_frame = ttk.Frame(self.lesson_select_frame)
        lesson_combo_frame.pack(fill=tk.X, pady=(4, 0))
        
        self.lesson_combo = ttk.Combobox(lesson_combo_frame, state="readonly", width=40)
        self.lesson_combo.pack(side=tk.LEFT, padx=(0, 6))
        self.lesson_combo.bind("<<ComboboxSelected>>", self._on_lesson_selected)
        
        ttk.Button(lesson_combo_frame, text="Refresh", command=self._refresh_lessons).pack(side=tk.LEFT)
        
        # Session context info
        self.session_info_var = tk.StringVar(value="Session: 0 captures")
        ttk.Label(mode_frame, textvariable=self.session_info_var, font=("Consolas", 8)).pack(anchor=tk.W, pady=(8, 0))
        
        ttk.Button(mode_frame, text="Clear Session Context", command=self._clear_session_context).pack(anchor=tk.W, pady=(4, 0))

        # ---- Capture Status ----
        capture_frame = ttk.LabelFrame(main, text="Screenshot Capture", padding=8)
        capture_frame.pack(fill=tk.X, pady=(0, 8))

        self.capture_status_var = tk.StringVar(value="Pair device to enable capture")
        ttk.Label(capture_frame, textvariable=self.capture_status_var).pack(anchor=tk.W)

        self.capture_btn = ttk.Button(capture_frame, text="Capture Now (Manual)", command=self._manual_capture,
                                      state=tk.DISABLED)
        self.capture_btn.pack(anchor=tk.W, pady=(6, 0))

        # ---- Activity Log ----
        log_frame = ttk.LabelFrame(main, text="Activity Log", padding=8)
        log_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 8))

        self.log_text = tk.Text(log_frame, height=15, state=tk.DISABLED, wrap=tk.WORD,
                                font=("Consolas", 9))
        scrollbar = ttk.Scrollbar(log_frame, orient=tk.VERTICAL, command=self.log_text.yview)
        self.log_text.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.log_text.pack(fill=tk.BOTH, expand=True)

        # ---- Dashboard Link ----
        bottom_frame = ttk.Frame(main)
        bottom_frame.pack(fill=tk.X)

        ttk.Button(bottom_frame, text="Open Dashboard in Browser",
                   command=self._open_dashboard).pack(side=tk.LEFT)
        ttk.Button(bottom_frame, text="Clear Log",
                   command=self._clear_log).pack(side=tk.RIGHT)

    # ------------------------------------------------------------------ Logging

    def _log(self, msg: str):
        """Append a timestamped message to the activity log."""
        ts = datetime.now().strftime("%H:%M:%S")
        line = f"{ts}  {msg}\n"

        self.log_text.configure(state=tk.NORMAL)
        self.log_text.insert(tk.END, line)
        
        # Limit log to last 500 lines to prevent memory growth in long sessions
        line_count = int(self.log_text.index('end-1c').split('.')[0])
        if line_count > 500:
            self.log_text.delete('1.0', f'{line_count - 500}.0')
        
        self.log_text.see(tk.END)
        self.log_text.configure(state=tk.DISABLED)

    def _clear_log(self):
        self.log_text.configure(state=tk.NORMAL)
        self.log_text.delete("1.0", tk.END)
        self.log_text.configure(state=tk.DISABLED)

    # ------------------------------------------------------------------ Pairing

    @staticmethod
    def _is_backend_auth_failure_reason(reason: str) -> bool:
        return (
            "Invalid or revoked device token" in reason
            or "Subscription required" in reason
            or "HTTP 401" in reason
            or "HTTP 403" in reason
        )

    def _refresh_pairing_status(self):
        if config.is_paired():
            valid, reason = api_client.validate_device_token()
            auth_failure = not valid and self._is_backend_auth_failure_reason(reason)
            if auth_failure:
                config.clear_device()
                self.pair_status_var.set("Not paired — enter a pairing code from the dashboard")
                self.code_entry.configure(state=tk.NORMAL)
                self.pair_btn.configure(state=tk.NORMAL)
                self.unpair_btn.configure(state=tk.DISABLED)
                self.capture_btn.configure(state=tk.DISABLED)
                self.capture_status_var.set("Pair device to enable capture")
                self._log(
                    f"Pairing cleared by backend policy ({reason}). Subscribe and pair again if needed."
                )
                return

            device_id = config.get("device_id", "")
            short_id = device_id[:8] if device_id else "?"
            self.pair_status_var.set(f"✓ Paired (device {short_id}...)")
            self.code_entry.configure(state=tk.DISABLED)
            self.pair_btn.configure(state=tk.DISABLED)
            self.unpair_btn.configure(state=tk.NORMAL)
            # Enable capture when paired
            self.capture_btn.configure(state=tk.NORMAL)
            self.capture_status_var.set("Press Print Screen to capture")
        else:
            self.pair_status_var.set("Not paired — enter a pairing code from the dashboard")
            self.code_entry.configure(state=tk.NORMAL)
            self.pair_btn.configure(state=tk.NORMAL)
            self.unpair_btn.configure(state=tk.DISABLED)
            # Disable capture when not paired
            self.capture_btn.configure(state=tk.DISABLED)
            self.capture_status_var.set("Pair device to enable capture")

    def _pair_device(self):
        code = self.code_var.get().strip()
        if not code:
            messagebox.showwarning("Pairing", "Enter a pairing code first.")
            return

        self._log(f"Pairing with code {code}...")
        try:
            result = api_client.pair_device(code, label="Desktop App")
            self._log(f"Paired successfully! Device ID: {result['device_id'][:8]}...")
            self.code_var.set("")
            self._refresh_pairing_status()
        except Exception as e:
            self._log(f"Pairing failed: {e}")
            messagebox.showerror("Pairing Error", str(e))

    def _unpair_device(self):
        config.clear_device()
        self._log("Device unpaired.")
        self._refresh_pairing_status()

    def _handle_backend_auth_error(self, err: Exception) -> bool:
        if not isinstance(err, api_client.BackendAPIError):
            return False
        if err.status_code not in (401, 403):
            return False

        config.clear_device()
        message = (
            f"Device access revoked by backend ({err}). "
            "Please subscribe (if needed) and pair again."
        )
        self.root.after(0, lambda: self._log(message))
        self.root.after(0, self._refresh_pairing_status)
        return True

    def _start_pairing_revalidation(self):
        if self._pairing_revalidate_job is not None:
            return
        self._pairing_revalidate_job = self.root.after(
            self._PAIRING_REVALIDATE_MS,
            self._run_pairing_revalidation,
        )

    def _stop_pairing_revalidation(self):
        job = self._pairing_revalidate_job
        self._pairing_revalidate_job = None
        if job is None:
            return
        try:
            self.root.after_cancel(job)
        except Exception:
            pass

    def _schedule_pairing_revalidation(self):
        if self._pairing_revalidate_job is not None:
            return
        self._pairing_revalidate_job = self.root.after(
            self._PAIRING_REVALIDATE_MS,
            self._run_pairing_revalidation,
        )

    def _run_pairing_revalidation(self):
        self._pairing_revalidate_job = None

        if self._pairing_revalidate_running or not config.is_paired():
            self._schedule_pairing_revalidation()
            return

        self._pairing_revalidate_running = True
        threading.Thread(target=self._pairing_revalidation_worker, daemon=True).start()

    def _pairing_revalidation_worker(self):
        try:
            valid, reason = api_client.validate_device_token()
            if not valid and self._is_backend_auth_failure_reason(reason):
                self.root.after(0, self._refresh_pairing_status)
        except Exception:
            pass
        finally:
            self.root.after(0, self._finish_pairing_revalidation)

    def _finish_pairing_revalidation(self):
        self._pairing_revalidate_running = False
        self._schedule_pairing_revalidation()

    # ------------------------------------------------------------------ Mode Selection & Lessons (Phase 16)

    def _on_mode_changed(self):
        """Handle mode selection change."""
        self._current_mode = self.mode_var.get()
        config.set_key("capture_mode", self._current_mode)
        
        # Show/hide lesson selection based on mode
        if self._current_mode == "lesson":
            self.lesson_select_frame.pack(fill=tk.X, pady=(8, 0))
            self._refresh_lessons()
            self._log(f"Switched to Lesson Mode - select a lesson to study")
        else:
            self.lesson_select_frame.pack_forget()
            self._selected_lesson_id = None
            self._selected_lesson_title = None
            self._log(f"Switched to Recitation Mode - live capture enabled")
        
        self._update_session_info()

    def _refresh_lessons(self):
        """Fetch lessons from backend API."""
        if not config.is_paired():
            self._log("Not paired - pair device first to load lessons")
            return
        
        self._log("Fetching lessons from backend...")
        try:
            lessons = api_client.fetch_lessons()
            self._lessons_list = lessons
            
            if not lessons:
                self.lesson_combo['values'] = ["(Upload lessons via web dashboard)"]
                self.lesson_combo.current(0)
                self.lesson_combo.configure(state="disabled")
                self._log("No lessons found - upload documents via web dashboard")
            else:
                lesson_titles = [f"{l['title']} (ID: {l['id']})" for l in lessons]
                self.lesson_combo['values'] = lesson_titles
                self.lesson_combo.configure(state="readonly")
                self._log(f"Loaded {len(lessons)} lesson(s)")
                
                # Auto-select first lesson if none selected
                if self._selected_lesson_id is None and lessons:
                    self.lesson_combo.current(0)
                    self._on_lesson_selected(None)
        except Exception as e:
            self._log(f"Failed to fetch lessons: {e}")
            self.lesson_combo['values'] = ["(Error loading lessons)"]
            self.lesson_combo.current(0)
            self.lesson_combo.configure(state="disabled")

    def _on_lesson_selected(self, event):
        """Handle lesson selection from dropdown."""
        if not self._lessons_list:
            return
        
        idx = self.lesson_combo.current()
        if idx >= 0 and idx < len(self._lessons_list):
            lesson = self._lessons_list[idx]
            self._selected_lesson_id = lesson['id']
            self._selected_lesson_title = lesson['title']
            self._log(f"Selected lesson: {self._selected_lesson_title}")

    def _clear_session_context(self):
        """Clear session context (last 10 captions)."""
        self._session_context.clear()
        self._update_session_info()
        self._log("Session context cleared")

    def _update_session_info(self):
        """Update session info display."""
        context_count = len(self._session_context)
        if self._current_mode == "recitation":
            self.session_info_var.set(f"Session: {context_count} capture(s) in context")
        else:
            self.session_info_var.set(f"Lesson Mode: Context from selected lesson")

    # ------------------------------------------------------------------ Hotkey

    def _start_hotkey_listener(self):
        """Start a global keyboard listener for Print Screen."""
        def on_press(key):
            if key == keyboard.Key.print_screen:
                # Run capture in a thread to avoid blocking the listener
                if not self._processing:
                    threading.Thread(
                        target=lambda: self._capture_screenshot(wait_for_clipboard=True),
                        daemon=True,
                    ).start()

        self._hotkey_listener = keyboard.Listener(on_press=on_press)
        self._hotkey_listener.daemon = True
        self._hotkey_listener.start()
        self._log("Hotkey listener started (Print Screen)")

    def _manual_capture(self):
        """Manual capture button — grabs current clipboard or takes screenshot."""
        if not self._processing:
            threading.Thread(
                target=lambda: self._capture_screenshot(wait_for_clipboard=False),
                daemon=True,
            ).start()

    # ------------------------------------------------------------------ Capture

    def _grab_image_from_clipboard(
        self,
        *,
        silent: bool = False,
        convert_rgb: bool = True,
    ) -> Image.Image | None:
        try:
            data = ImageGrab.grabclipboard()
        except Exception as exc:
            if not silent:
                self.root.after(0, lambda: self._log(f"Could not read image from clipboard: {exc}"))
            return None

        if data is None:
            return None

        if isinstance(data, Image.Image):
            return data.convert("RGB") if convert_rgb else data

        if isinstance(data, list) and data:
            try:
                image = Image.open(data[0])
                return image.convert("RGB") if convert_rgb else image
            except Exception as exc:
                if not silent:
                    self.root.after(0, lambda: self._log(f"Could not open clipboard image file: {exc}"))
                return None

        return None

    def _image_signature(self, image: Image.Image) -> str:
        thumb = image.convert("L").resize((32, 32), Image.BILINEAR)
        payload = thumb.tobytes()
        return hashlib.blake2b(payload, digest_size=16).hexdigest()

    def _start_clipboard_watcher(self):
        if self._clipboard_job is not None:
            return
        
        # Initialize with current clipboard to ignore pre-existing images
        try:
            image = self._grab_image_from_clipboard(silent=True, convert_rgb=False)
            if image is not None:
                self._clipboard_last_sig = self._image_signature(image)
                self._clipboard_seen.append(self._clipboard_last_sig)
        except Exception:
            pass
        
        self._clipboard_poll_ms = self._CLIPBOARD_POLL_MS_MIN
        self._poll_clipboard()

    def _stop_clipboard_watcher(self):
        job = self._clipboard_job
        self._clipboard_job = None
        if job is None:
            return
        try:
            self.root.after_cancel(job)
        except Exception:
            pass

    def _poll_clipboard(self):
        changed = False
        try:
            if config.is_paired():
                image = self._grab_image_from_clipboard(silent=True, convert_rgb=False)
                if image is not None:
                    sig = self._image_signature(image)
                    if sig != self._clipboard_last_sig and sig not in self._clipboard_seen:
                        self._clipboard_last_sig = sig
                        self._clipboard_seen.append(sig)
                        changed = True

                        if self._processing:
                            if self._pending_clipboard_sig != sig:
                                self._pending_clipboard_image = image
                                self._pending_clipboard_sig = sig
                                self.root.after(0, lambda: self._log(
                                    "Queued screenshot from clipboard; will process after current OCR completes."
                                ))
                        else:
                            threading.Thread(
                                target=lambda img=image.convert("RGB"): self._process_image(img),
                                daemon=True,
                            ).start()
        finally:
            if changed:
                self._clipboard_poll_ms = self._CLIPBOARD_POLL_MS_MIN
            else:
                if not config.is_paired():
                    self._clipboard_poll_ms = self._CLIPBOARD_POLL_MS_MAX
                else:
                    self._clipboard_poll_ms = min(
                        self._CLIPBOARD_POLL_MS_MAX,
                        int(self._clipboard_poll_ms * self._CLIPBOARD_POLL_BACKOFF_MULT) + 25,
                    )

            self._clipboard_job = self.root.after(self._clipboard_poll_ms, self._poll_clipboard)

    def _wait_for_clipboard_image(self, timeout_s: float = 8.0, poll_s: float = 0.2):
        deadline = time.time() + timeout_s
        while time.time() < deadline:
            image = self._grab_image_from_clipboard(silent=True)
            if image is not None:
                return image
            time.sleep(poll_s)
        return None

    def _capture_screenshot(self, *, wait_for_clipboard: bool):
        """Capture a screenshot from clipboard and process it."""
        if not config.is_paired():
            self.root.after(0, lambda: self._log("Not paired — pair your device first to enable capture"))
            return

        if wait_for_clipboard:
            # Non-blocking wait for clipboard using polling
            self.root.after(0, lambda: self._log("Waiting for screenshot — select region and press Ctrl+C"))
            self._poll_for_clipboard_image(deadline=time.time() + 8.0)
        else:
            # Manual capture - grab immediately
            try:
                time.sleep(0.3)
                image = self._grab_image_from_clipboard(silent=True)
                if image is None:
                    self.root.after(0, lambda: self._log("No image in clipboard — copy a screenshot first"))
                    return
                self._process_image(image)
            except Exception as e:
                self.root.after(0, lambda e=e: self._log(f"Screenshot capture error: {e}"))

    def _poll_for_clipboard_image(self, deadline: float):
        """Non-blocking clipboard polling using tkinter after() - prevents UI freezing."""
        if time.time() >= deadline:
            self.root.after(0, lambda: self._log("Screenshot timeout — try again: Print Screen → select region → Ctrl+C"))
            return
        
        try:
            image = self._grab_image_from_clipboard(silent=True)
            if image is not None:
                # Got image! Process it
                self._process_image(image)
                return
        except Exception as e:
            self.root.after(0, lambda e=e: self._log(f"Clipboard error: {e}"))
            return
        
        # No image yet, poll again in 200ms (non-blocking)
        self.root.after(200, lambda: self._poll_for_clipboard_image(deadline))

    def _process_image(self, image: Image.Image):
        if self._processing:
            return

        if not config.is_paired():
            self.root.after(0, lambda: self._log("Not paired — pair your device first to enable capture"))
            return

        self._processing = True
        try:
            self.root.after(0, lambda: self.capture_status_var.set("Capturing..."))
            self.root.after(0, lambda: self._log("Screenshot captured — running OCR..."))

            start = time.time()
            text = ocr.extract_text(image)
            ocr_ms = int((time.time() - start) * 1000)

            if not text or len(text) < 3:
                self.root.after(0, lambda: self._log(f"OCR returned no text ({ocr_ms}ms)"))
                return

            cleaned_text = detector.clean_transcript_text(text)
            if not cleaned_text or len(cleaned_text) < 3:
                if detector.looks_like_noise(text):
                    self.root.after(0, lambda: self._log(
                        "Capture looks like a URL / browser UI. Skipping send. Try capturing only the caption area."
                    ))
                    return
                payload_text = text
            else:
                payload_text = cleaned_text

            preview = payload_text[:100].replace("\n", " ")
            self.root.after(0, lambda: self._log(f"OCR done ({ocr_ms}ms): {preview}..."))

            # Phase 16: Add to session context
            self._session_context.append(payload_text)
            self.root.after(0, self._update_session_info)

            try:
                questions = detector.detect_questions(payload_text)
                if not questions:
                    self.root.after(0, lambda: self._log(
                        "No questions detected — not sending anything to the backend"
                    ))
                    return

                self.root.after(0, lambda: self._log(
                    f"Found {len(questions)} question(s): {questions[0][:80]}..."
                ))

                # Phase 16: Mode-specific behavior
                if self._current_mode == "lesson":
                    # Lesson mode: Require lesson selection
                    if self._selected_lesson_id is None:
                        self.root.after(0, lambda: self._log(
                            "Lesson mode: Please select a lesson first"
                        ))
                        return
                    
                    # Send questions with selected lesson_id
                    for q in questions:
                        try:
                            result = api_client.send_question(
                                question=q,
                                context="",  # Backend uses lesson transcript
                                lesson_id=self._selected_lesson_id,
                                initial_text=q
                            )
                            self.root.after(0, lambda q=q, r=result: self._log(
                                f"Question sent (Lesson Mode) → ID {r.get('question_id')}: {q[:60]}"
                            ))
                        except Exception as e:
                            if self._handle_backend_auth_error(e):
                                return
                            self.root.after(0, lambda e=e: self._log(f"Question send error: {e}"))
                else:
                    # Recitation mode: Use session context and daily grouping
                    from datetime import datetime
                    daily_meeting_id = f"screen-capture-{datetime.now().strftime('%Y-%m-%d')}"
                    
                    # Build session context string
                    session_context_str = "\n".join(self._session_context)
                    
                    result = api_client.send_caption(
                        text=payload_text,
                        speaker="",
                        meeting_id=daily_meeting_id,
                        meeting_title=""
                    )
                    self.root.after(0, lambda: self._log(
                        f"Caption sent → lesson {result.get('lesson_id')}, "
                        f"chunk {result.get('chunk_id')}, new={result.get('created')}"
                    ))

                    for q in questions:
                        try:
                            result = api_client.send_question(
                                question=q,
                                context=session_context_str,  # Last 10 captions
                                meeting_id=daily_meeting_id,
                                meeting_title="",
                                initial_text=q
                            )
                            self.root.after(0, lambda q=q, r=result: self._log(
                                f"Question sent (Recitation Mode) → ID {r.get('question_id')}: {q[:60]}"
                            ))
                        except Exception as e:
                            if self._handle_backend_auth_error(e):
                                return
                            self.root.after(0, lambda e=e: self._log(f"Question send error: {e}"))
            except Exception as e:
                if self._handle_backend_auth_error(e):
                    return
                self.root.after(0, lambda e=e: self._log(f"Send error: {e}"))

        except Exception as e:
            self.root.after(0, lambda e=e: self._log(f"Capture error: {e}"))
        finally:
            self._processing = False
            self.root.after(0, lambda: self.capture_status_var.set("Press Print Screen to capture"))

            if self._pending_clipboard_image is not None and self._pending_clipboard_sig is not None:
                pending = self._pending_clipboard_image
                self._pending_clipboard_image = None
                self._pending_clipboard_sig = None
                threading.Thread(
                    target=lambda img=pending: self._process_image(img),
                    daemon=True,
                ).start()
    # ------------------------------------------------------------------ Misc

    def _open_dashboard(self):
        import webbrowser
        url = config.get("backend_url", "http://localhost:8000")
        webbrowser.open(url)

    def _on_close(self):
        if self._hotkey_listener:
            self._hotkey_listener.stop()
        self._stop_pairing_revalidation()
        self._stop_clipboard_watcher()
        self.root.destroy()

    def run(self):
        self._log("Meet Lessons Desktop App started")
        self._log(f"Backend: {config.BACKEND_URL}")
        self._log("Open Google Meet → enable CC → press Print Screen to capture")
        self.root.mainloop()


def main():
    app = MeetLessonsApp()
    app.run()


if __name__ == "__main__":
    main()
