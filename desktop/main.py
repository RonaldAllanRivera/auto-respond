#!/usr/bin/env python3
"""
Meet Lessons Desktop App — Screenshot Capture + OCR + Question Detection

Listens for Print Screen key, grabs the clipboard screenshot, runs local OCR,
detects questions, and sends data to the Django backend.

Usage:
    python main.py
"""

import sys
import threading
import time
import tkinter as tk
from datetime import datetime
from tkinter import messagebox, ttk

from PIL import ImageGrab
from pynput import keyboard

import api_client
import config
import detector
import ocr


class MeetLessonsApp:
    """Main tkinter application."""

    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Meet Lessons")
        self.root.geometry("520x600")
        self.root.resizable(True, True)
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

        self._hotkey_listener = None
        self._processing = False

        self._build_ui()
        self._refresh_pairing_status()
        self._start_hotkey_listener()

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
        self.log_text.see(tk.END)
        self.log_text.configure(state=tk.DISABLED)

    def _clear_log(self):
        self.log_text.configure(state=tk.NORMAL)
        self.log_text.delete("1.0", tk.END)
        self.log_text.configure(state=tk.DISABLED)

    # ------------------------------------------------------------------ Pairing

    def _refresh_pairing_status(self):
        if config.is_paired():
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

    # ------------------------------------------------------------------ Hotkey

    def _start_hotkey_listener(self):
        """Start a global keyboard listener for Print Screen."""
        def on_press(key):
            if key == keyboard.Key.print_screen:
                # Run capture in a thread to avoid blocking the listener
                if not self._processing:
                    threading.Thread(target=self._capture_screenshot, daemon=True).start()

        self._hotkey_listener = keyboard.Listener(on_press=on_press)
        self._hotkey_listener.daemon = True
        self._hotkey_listener.start()
        self._log("Hotkey listener started (Print Screen)")

    def _manual_capture(self):
        """Manual capture button — grabs current clipboard or takes screenshot."""
        if not self._processing:
            threading.Thread(target=self._capture_screenshot, daemon=True).start()

    # ------------------------------------------------------------------ Capture

    def _capture_screenshot(self):
        """Grab screenshot from clipboard, OCR it, detect questions, send to backend."""
        if self._processing:
            return

        # Block capture entirely when not paired (paywall enforcement)
        if not config.is_paired():
            self.root.after(0, lambda: self._log("Not paired — pair your device first to enable capture"))
            return

        self._processing = True

        try:
            self.root.after(0, lambda: self.capture_status_var.set("Capturing..."))
            self.root.after(0, lambda: self._log("Screenshot captured — running OCR..."))

            # Small delay to let Print Screen populate the clipboard
            time.sleep(0.3)

            # Grab image from clipboard
            image = ImageGrab.grabclipboard()
            if image is None:
                # Fallback: grab entire screen
                self.root.after(0, lambda: self._log("No image in clipboard — capturing screen"))
                image = ImageGrab.grab()

            if image is None:
                self.root.after(0, lambda: self._log("ERROR: Could not capture screenshot"))
                return

            # OCR
            start = time.time()
            text = ocr.extract_text(image)
            ocr_ms = int((time.time() - start) * 1000)

            if not text or len(text) < 3:
                self.root.after(0, lambda: self._log(f"OCR returned no text ({ocr_ms}ms)"))
                return

            preview = text[:100].replace("\n", " ")
            self.root.after(0, lambda: self._log(f"OCR done ({ocr_ms}ms): {preview}..."))

            # Send full text as caption
            try:
                result = api_client.send_caption(text=text, speaker="", meeting_title="Screen Capture")
                self.root.after(0, lambda: self._log(
                    f"Caption sent → lesson {result.get('lesson_id')}, "
                    f"chunk {result.get('chunk_id')}, new={result.get('created')}"
                ))
            except Exception as e:
                self.root.after(0, lambda: self._log(f"Caption send error: {e}"))

            # Detect questions
            questions = detector.detect_questions(text)
            if questions:
                self.root.after(0, lambda: self._log(
                    f"Found {len(questions)} question(s): {questions[0][:80]}..."
                ))
                for q in questions:
                    try:
                        result = api_client.send_question(
                            question=q, context=text, meeting_title="Screen Capture"
                        )
                        self.root.after(0, lambda q=q, r=result: self._log(
                            f"Question sent → ID {r.get('question_id')}: {q[:60]}"
                        ))
                    except Exception as e:
                        self.root.after(0, lambda e=e: self._log(f"Question send error: {e}"))
            else:
                self.root.after(0, lambda: self._log("No questions detected in this capture"))

            self.root.after(0, lambda: self.capture_status_var.set("Press Print Screen to capture"))

        except Exception as e:
            self.root.after(0, lambda: self._log(f"Capture error: {e}"))
        finally:
            self._processing = False

    # ------------------------------------------------------------------ Misc

    def _open_dashboard(self):
        import webbrowser
        url = config.get("backend_url", "http://localhost:8000")
        webbrowser.open(url)

    def _on_close(self):
        if self._hotkey_listener:
            self._hotkey_listener.stop()
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
