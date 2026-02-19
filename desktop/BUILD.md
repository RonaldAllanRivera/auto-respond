# Desktop App — Windows Build Guide

This document explains how to build the Meet Lessons desktop app into a one-click Windows installer for end users.

**Build must be done on a Windows 11 machine** (or a Windows VM). PyInstaller bundles the Python runtime for the platform it runs on.

---

## Overview

```
desktop/main.py  →  PyInstaller  →  dist/MeetLessons.exe
                                          ↓
                               Inno Setup + Tesseract setup.exe
                                          ↓
                               dist/MeetLessonsInstaller.exe  →  GitHub Release  →  /devices/ download button
```

---

## Build method 1 — GitHub Actions (recommended, no Windows machine needed)

The workflow at `.github/workflows/build-desktop.yml` builds and publishes the installer automatically.

### How to release a new version

1. Commit and push your changes to GitHub.
2. Create and push a version tag:
   ```bash
   git tag v1.0.0
   git push origin v1.0.0
   ```
3. GitHub Actions spins up a Windows VM and automatically:
   - Installs Python, PyInstaller, Inno Setup, and Tesseract
   - Builds `MeetLessons.exe`
   - Compiles `MeetLessonsInstaller.exe`
   - Creates a GitHub Release and attaches the installer
4. Go to your GitHub repo → **Releases** → copy the direct download URL.
5. Set on Render:
   ```
   DESKTOP_DOWNLOAD_URL=https://github.com/<your-org>/<repo>/releases/download/v1.0.0/MeetLessonsInstaller.exe
   ```
6. The **Download for Windows** button on `/devices/` updates automatically.

**That's it — no Windows machine, no manual installs.**

---

## Build method 2 — Manual (`build.bat`, Windows machine required)

Use this if you need to build locally without pushing to GitHub.

### Prerequisites — install once on your Windows build machine

1. **Python 3.12** — https://www.python.org/downloads/
   - During install: check **"Add Python to PATH"**
2. **Inno Setup 6** — https://jrsoftware.org/isdl.php
3. **Tesseract OCR installer** — https://github.com/UB-Mannheim/tesseract/wiki
   - Download `tesseract-ocr-w64-setup-5.x.x.exe`
   - Place it in `desktop/installer/`

### Steps

1. Open `desktop/build.bat` and update the `TESSERACT_INSTALLER` line to match the exact filename you downloaded.
2. Double-click `desktop/build.bat`.
3. Output: `desktop/dist/MeetLessonsInstaller.exe`

The script checks all prerequisites and shows a clear error if anything is missing.

---

## After a manual build — publish to GitHub Releases

Only needed if you used `build.bat` (Method 2). GitHub Actions (Method 1) does this automatically.

1. Go to your GitHub repo → **Releases** → **Draft a new release**
2. Tag: `v1.0.0`, attach `dist/MeetLessonsInstaller.exe`, publish.
3. Copy the direct download URL and set on Render:
   ```
   DESKTOP_DOWNLOAD_URL=https://github.com/<your-org>/<repo>/releases/download/v1.0.0/MeetLessonsInstaller.exe
   ```

---

## Replacing the icon

The icon is already committed at `desktop/assets/icon.ico`.

To replace it in the future:
1. Get a new `.ico` with multiple sizes (256×256, 48×48, 32×32, 16×16).
   - https://icons8.com, https://www.flaticon.com, or https://www.svgrepo.com → convert at https://convertio.co/svg-ico/
2. Overwrite `desktop/assets/icon.ico` and commit it.

> `desktop/favicon_io/` is gitignored (local raw asset folder — not pushed to git).

---

## Troubleshooting

| Issue | Fix |
|---|---|
| `ModuleNotFoundError` at runtime | Add `--hidden-import <module>` to the PyInstaller command in `build.bat` |
| Tesseract not found after install | Ensure `C:\Program Files\Tesseract-OCR\` is in PATH |
| Antivirus flags the `.exe` | Expected for unsigned PyInstaller builds — code-sign with a certificate for production |
| `build.bat` says Inno Setup not found | Install Inno Setup 6 from https://jrsoftware.org/isdl.php |
| `build.bat` says Tesseract installer not found | Download `tesseract-ocr-w64-setup-5.x.x.exe` and place it in `desktop/installer/` |
