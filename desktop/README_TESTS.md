# Desktop App Test Suite

## Overview

This test suite verifies the Meet Lessons desktop app functionality, focusing on:
1. **Clipboard capture** - Ensures screenshots are captured correctly
2. **UI responsiveness** - Verifies no blocking/freezing/shaking
3. **OCR processing** - Tests text extraction from images
4. **Question detection** - Validates send-all architecture
5. **Daily grouping** - Confirms lessons are grouped by date

## Installation

Install test dependencies:

```bash
cd desktop
.venv/bin/pip install -r requirements.txt
```

This installs:
- `pytest` - Test framework
- `pytest-mock` - Mocking utilities

## Running Tests

### Run all tests:
```bash
cd desktop
.venv/bin/python -m pytest test_desktop.py -v
```

### Run specific test class:
```bash
.venv/bin/python -m pytest test_desktop.py::TestClipboardCapture -v
```

### Run specific test:
```bash
.venv/bin/python -m pytest test_desktop.py::TestUIResponsiveness::test_capture_screenshot_non_blocking -v
```

### Run with coverage:
```bash
.venv/bin/python -m pytest test_desktop.py --cov=. --cov-report=html
```

## Test Categories

### 1. Clipboard Capture Tests (`TestClipboardCapture`)
- ✅ `test_clipboard_grab_with_image` - Verifies image can be grabbed from clipboard
- ✅ `test_clipboard_grab_with_no_image` - Handles empty clipboard gracefully
- ✅ `test_image_signature_consistency` - Same image produces same hash
- ✅ `test_image_signature_different_images` - Different images produce different hashes

### 2. UI Responsiveness Tests (`TestUIResponsiveness`)
**Critical for preventing freezing/shaking:**
- ✅ `test_capture_screenshot_non_blocking` - Capture completes in < 1 second
- ✅ `test_process_image_runs_in_thread` - Processing doesn't block main thread

### 3. OCR Processing Tests (`TestOCRProcessing`)
- ✅ `test_ocr_extracts_text_from_image` - Text extraction works
- ✅ `test_ocr_handles_empty_image` - Handles blank images

### 4. Question Detection Tests (`TestQuestionDetection`)
**Tests send-all architecture:**
- ✅ `test_detect_simple_question` - "What is Python?"
- ✅ `test_detect_imperative_statement` - "Explain photosynthesis"
- ✅ `test_detect_single_word` - "photosynthesis"
- ✅ `test_detect_math_expression` - "5 + 3"
- ✅ `test_filter_noise` - URLs and UI trash filtered
- ✅ `test_clean_transcript_text` - Whitespace normalization

### 5. Daily Lesson Grouping Tests (`TestDailyLessonGrouping`)
- ✅ `test_daily_meeting_id_format` - Format: "screen-capture-YYYY-MM-DD"
- ✅ `test_same_day_captures_use_same_meeting_id` - All captures on same day grouped

### 6. Config Management Tests (`TestConfigManagement`)
- ✅ `test_config_defaults` - Proper default values
- ✅ `test_is_paired_with_token` - Pairing status detection
- ✅ `test_is_paired_without_token` - Unpaired state

## Performance Benchmarks

**UI Responsiveness (No Freezing):**
- Clipboard capture: < 1 second
- Image processing: < 5 seconds (including OCR + API calls)

**These tests prevent the "shaking" bug by ensuring no blocking operations.**

## Continuous Integration

Add to CI/CD pipeline:

```yaml
# .github/workflows/test.yml
- name: Test Desktop App
  run: |
    cd desktop
    pip install -r requirements.txt
    pytest test_desktop.py -v
```

## Troubleshooting

**Import errors:**
```bash
# Make sure you're in the desktop directory
cd /home/allan/code/python/auto-respond/desktop
.venv/bin/python -m pytest test_desktop.py -v
```

**Tkinter errors in tests:**
- Tests mock tkinter components, so no GUI is required
- If you see tkinter errors, ensure mocks are properly set up

**OCR/Tesseract errors:**
- Tests mock pytesseract, so Tesseract doesn't need to be installed for tests
- Real OCR tests would require Tesseract installed

## Adding New Tests

Follow this pattern:

```python
class TestNewFeature:
    """Test description."""
    
    def test_feature_works(self):
        """Test that feature works as expected."""
        # Arrange
        test_data = "sample"
        
        # Act
        result = some_function(test_data)
        
        # Assert
        assert result == expected_value
```

## Test Coverage Goals

- **Clipboard operations**: 100%
- **UI responsiveness**: 100% (critical for preventing freezing)
- **OCR processing**: 80%+
- **Question detection**: 90%+
- **API communication**: 70%+ (mocked)

## Known Limitations

- Tests use mocks for external dependencies (API, Tesseract, clipboard)
- Real integration tests would require running backend server
- UI tests don't test actual tkinter rendering (only logic)
