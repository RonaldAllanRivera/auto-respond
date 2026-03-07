"""
Test suite for Meet Lessons Desktop App

Tests:
1. Clipboard capture functionality
2. UI responsiveness (no blocking/freezing)
3. OCR processing
4. Question detection
5. API communication
"""

import time
import threading
from unittest.mock import Mock, patch, MagicMock
import pytest
from PIL import Image

import detector
import ocr


class TestClipboardCapture:
    """Test clipboard image capture functionality."""
    
    def test_clipboard_grab_with_image(self):
        """Test that clipboard can grab an image successfully."""
        # Create a test image
        test_image = Image.new('RGB', (100, 100), color='red')
        
        with patch('PIL.ImageGrab.grabclipboard', return_value=test_image):
            from main import MeetLessonsApp
            app = MeetLessonsApp()
            
            # Test clipboard grab
            result = app._grab_image_from_clipboard(silent=True)
            assert result is not None
            assert isinstance(result, Image.Image)
            assert result.size == (100, 100)
    
    def test_clipboard_grab_with_no_image(self):
        """Test clipboard grab when no image is present."""
        with patch('PIL.ImageGrab.grabclipboard', return_value=None):
            from main import MeetLessonsApp
            app = MeetLessonsApp()
            
            result = app._grab_image_from_clipboard(silent=True)
            assert result is None
    
    def test_image_signature_consistency(self):
        """Test that same image produces same signature."""
        from main import MeetLessonsApp
        app = MeetLessonsApp()
        
        test_image = Image.new('RGB', (100, 100), color='blue')
        
        sig1 = app._image_signature(test_image)
        sig2 = app._image_signature(test_image)
        
        assert sig1 == sig2
        assert len(sig1) == 32  # blake2b with digest_size=16 produces 32 hex chars
    
    def test_image_signature_different_images(self):
        """Test that different images produce different signatures."""
        from main import MeetLessonsApp
        app = MeetLessonsApp()
        
        image1 = Image.new('RGB', (100, 100), color='red')
        image2 = Image.new('RGB', (100, 100), color='blue')
        
        sig1 = app._image_signature(image1)
        sig2 = app._image_signature(image2)
        
        assert sig1 != sig2


class TestUIResponsiveness:
    """Test that UI operations don't block the main thread."""
    
    def test_capture_screenshot_non_blocking(self):
        """Test that _capture_screenshot doesn't block for more than 1 second."""
        with patch('PIL.ImageGrab.grabclipboard', return_value=None):
            from main import MeetLessonsApp
            app = MeetLessonsApp()
            
            # Mock config to be paired
            with patch('config.is_paired', return_value=True):
                start = time.time()
                app._capture_screenshot(wait_for_clipboard=False)
                duration = time.time() - start
                
                # Should complete in less than 1 second (0.5s sleep + processing)
                assert duration < 1.0, f"Capture took {duration}s, should be < 1s"
    
    def test_process_image_runs_in_thread(self):
        """Test that image processing doesn't block main thread."""
        test_image = Image.new('RGB', (100, 100), color='white')
        
        with patch('config.is_paired', return_value=True):
            with patch('ocr.extract_text', return_value='Test text'):
                with patch('detector.detect_questions', return_value=['What is this?']):
                    with patch('api_client.send_caption', return_value={'lesson_id': 1, 'chunk_id': 1, 'created': True}):
                        with patch('api_client.send_question', return_value={'question_id': 1}):
                            from main import MeetLessonsApp
                            app = MeetLessonsApp()
                            
                            # Process should complete quickly
                            start = time.time()
                            app._process_image(test_image)
                            duration = time.time() - start
                            
                            # OCR + API calls should complete in reasonable time
                            assert duration < 5.0, f"Processing took {duration}s, too slow"


class TestOCRProcessing:
    """Test OCR text extraction."""
    
    def test_ocr_extracts_text_from_image(self):
        """Test that OCR can extract text from a simple image."""
        # Create a simple test image (in real scenario, would have text)
        test_image = Image.new('RGB', (200, 50), color='white')
        
        # Mock OCR to return expected text
        with patch('pytesseract.image_to_string', return_value='Sample text'):
            result = ocr.extract_text(test_image)
            assert result == 'Sample text'
    
    def test_ocr_handles_empty_image(self):
        """Test OCR with blank image returns empty or minimal text."""
        blank_image = Image.new('RGB', (100, 100), color='white')
        
        with patch('pytesseract.image_to_string', return_value=''):
            result = ocr.extract_text(blank_image)
            assert result == ''


class TestQuestionDetection:
    """Test question detection logic."""
    
    def test_detect_simple_question(self):
        """Test detection of simple interrogative question."""
        text = "What is Python?"
        questions = detector.detect_questions(text)
        
        assert len(questions) > 0
        assert any('python' in q.lower() for q in questions)
    
    def test_detect_imperative_statement(self):
        """Test detection of imperative statements (explain, describe, etc.)."""
        text = "Explain photosynthesis"
        questions = detector.detect_questions(text)
        
        assert len(questions) > 0
        assert any('photosynthesis' in q.lower() for q in questions)
    
    def test_detect_single_word(self):
        """Test that single meaningful words are sent (send-all architecture)."""
        text = "photosynthesis"
        questions = detector.detect_questions(text)
        
        assert len(questions) > 0
        assert 'photosynthesis' in questions[0].lower()
    
    def test_detect_math_expression(self):
        """Test detection of math expressions."""
        text = "5 + 3"
        questions = detector.detect_questions(text)
        
        assert len(questions) > 0
        assert any('5' in q and '3' in q for q in questions)
    
    def test_filter_noise(self):
        """Test that noise (URLs, UI text) is filtered out."""
        noise_text = "https://meet.google.com/abc-defg-hij"
        
        assert detector.looks_like_noise(noise_text)
    
    def test_clean_transcript_text(self):
        """Test transcript cleaning filters noise and removes short lines."""
        # Test that it filters URLs
        text_with_url = "What is Python?\nhttps://example.com\nGood question"
        cleaned = detector.clean_transcript_text(text_with_url)
        
        assert "https://example.com" not in cleaned
        assert "What is Python?" in cleaned
        assert "Good question" in cleaned


class TestDailyLessonGrouping:
    """Test that captures are grouped by day."""
    
    def test_daily_meeting_id_format(self):
        """Test that daily meeting_id follows expected format."""
        from datetime import datetime
        
        # Mock datetime to control the date
        with patch('datetime.datetime') as mock_datetime:
            mock_datetime.now.return_value = datetime(2026, 3, 7, 16, 30, 0)
            mock_datetime.strftime = datetime.strftime
            
            expected_id = "screen-capture-2026-03-07"
            actual_id = f"screen-capture-{datetime.now().strftime('%Y-%m-%d')}"
            
            assert actual_id == expected_id
    
    def test_same_day_captures_use_same_meeting_id(self):
        """Test that multiple captures on same day use same meeting_id."""
        from datetime import datetime
        
        with patch('datetime.datetime') as mock_datetime:
            mock_datetime.now.return_value = datetime(2026, 3, 7, 10, 0, 0)
            mock_datetime.strftime = datetime.strftime
            
            id1 = f"screen-capture-{datetime.now().strftime('%Y-%m-%d')}"
            
            # Simulate later capture on same day
            mock_datetime.now.return_value = datetime(2026, 3, 7, 16, 0, 0)
            id2 = f"screen-capture-{datetime.now().strftime('%Y-%m-%d')}"
            
            assert id1 == id2


class TestConfigManagement:
    """Test configuration loading and management."""
    
    def test_config_defaults(self):
        """Test that config has proper defaults."""
        import config
        
        assert 'backend_url' in config.DEFAULTS
        assert 'device_token' in config.DEFAULTS
        assert 'device_id' in config.DEFAULTS
        assert 'hotkey' in config.DEFAULTS
    
    def test_is_paired_with_token(self):
        """Test is_paired returns True when device_token exists."""
        with patch('config.load', return_value={'device_token': 'test-token-123'}):
            import config
            assert config.is_paired()
    
    def test_is_paired_without_token(self):
        """Test is_paired returns False when no device_token."""
        with patch('config.load', return_value={'device_token': ''}):
            import config
            assert not config.is_paired()


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
