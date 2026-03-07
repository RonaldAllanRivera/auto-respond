"""
Document processing module for OCR and lesson creation.

Handles:
- PDF text extraction (PyMuPDF)
- PDF → image → OCR (for scanned PDFs)
- Image OCR (Pillow + pytesseract)
- AI lesson naming (OpenAI)
"""

import io
import time
from typing import BinaryIO

import fitz  # PyMuPDF
import pytesseract
from django.conf import settings
from openai import OpenAI
from PIL import Image, ImageEnhance

from .models import Lesson, TranscriptChunk

# File type validation
ALLOWED_IMAGE_TYPES = {
    'image/jpeg',
    'image/png',
    'image/webp',
    'image/tiff',
}

ALLOWED_PDF_TYPE = 'application/pdf'

# Processing limits
MAX_FILES_PER_UPLOAD = 100
MAX_TOTAL_SIZE_MB = 100
MAX_FILE_SIZE_MB = 10
MAX_IMAGE_DIMENSION = 4000

# OCR settings
MIN_TEXT_PER_PAGE = 10  # chars - if less, try OCR as fallback
PDF_RENDER_DPI = 300


def validate_file(file, filename: str) -> dict:
    """
    Validate uploaded file type and size.
    
    Returns:
        {
            'valid': bool,
            'error': str | None,
            'file_type': str,  # 'image' or 'pdf'
            'mime_type': str
        }
    """
    # Check file size
    file.seek(0, 2)  # Seek to end
    size_bytes = file.tell()
    file.seek(0)  # Reset to start
    
    if size_bytes > MAX_FILE_SIZE_MB * 1024 * 1024:
        return {
            'valid': False,
            'error': f'File too large: {filename} ({size_bytes / 1024 / 1024:.1f}MB > {MAX_FILE_SIZE_MB}MB)',
            'file_type': None,
            'mime_type': None,
        }
    
    # Read first bytes for magic number detection
    header = file.read(32)
    file.seek(0)
    
    # Detect file type by magic bytes
    if header.startswith(b'\xff\xd8\xff'):
        mime_type = 'image/jpeg'
        file_type = 'image'
    elif header.startswith(b'\x89PNG\r\n\x1a\n'):
        mime_type = 'image/png'
        file_type = 'image'
    elif header.startswith(b'RIFF') and b'WEBP' in header:
        mime_type = 'image/webp'
        file_type = 'image'
    elif header.startswith(b'II*\x00') or header.startswith(b'MM\x00*'):
        mime_type = 'image/tiff'
        file_type = 'image'
    elif header.startswith(b'%PDF'):
        mime_type = 'application/pdf'
        file_type = 'pdf'
    else:
        return {
            'valid': False,
            'error': f'Unsupported file type: {filename}',
            'file_type': None,
            'mime_type': None,
        }
    
    # Validate against allowed types
    if file_type == 'image' and mime_type not in ALLOWED_IMAGE_TYPES:
        return {
            'valid': False,
            'error': f'Image type not allowed: {mime_type}',
            'file_type': None,
            'mime_type': None,
        }
    
    if file_type == 'pdf' and mime_type != ALLOWED_PDF_TYPE:
        return {
            'valid': False,
            'error': f'PDF type not allowed: {mime_type}',
            'file_type': None,
            'mime_type': None,
        }
    
    return {
        'valid': True,
        'error': None,
        'file_type': file_type,
        'mime_type': mime_type,
    }


def preprocess_image(image: Image.Image) -> Image.Image:
    """
    Preprocess image for better OCR results.
    
    - Resize if too large
    - Enhance contrast
    - Convert to grayscale
    """
    # Resize if too large
    if image.width > MAX_IMAGE_DIMENSION or image.height > MAX_IMAGE_DIMENSION:
        ratio = min(MAX_IMAGE_DIMENSION / image.width, MAX_IMAGE_DIMENSION / image.height)
        new_size = (int(image.width * ratio), int(image.height * ratio))
        image = image.resize(new_size, Image.Resampling.LANCZOS)
    
    # Convert to RGB if needed (for RGBA, P, etc.)
    if image.mode not in ('RGB', 'L'):
        image = image.convert('RGB')
    
    # Convert to grayscale
    image = image.convert('L')
    
    # Enhance contrast
    enhancer = ImageEnhance.Contrast(image)
    image = enhancer.enhance(1.5)
    
    return image


def ocr_image(image: Image.Image) -> str:
    """
    Run Tesseract OCR on an image.
    
    Returns:
        Extracted text (empty string if no text found)
    """
    try:
        # Preprocess for better OCR
        processed = preprocess_image(image)
        
        # Run Tesseract
        text = pytesseract.image_to_string(processed, lang='eng')
        
        return text.strip()
    except Exception as e:
        # Log error but don't crash
        print(f"OCR error: {e}")
        return ""


def process_pdf(file: BinaryIO, filename: str) -> dict:
    """
    Process a PDF file: extract text or render to images for OCR.
    
    Returns:
        {
            'text': str,
            'pages': list[dict],  # [{'page_num': int, 'text': str}, ...]
            'page_count': int,
            'processing_time_ms': int
        }
    """
    start = time.time()
    pages_data = []
    
    try:
        # Read PDF into memory
        file.seek(0)
        pdf_bytes = file.read()
        
        # Open with PyMuPDF
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        page_count = len(doc)
        
        for page_num in range(page_count):
            page = doc[page_num]
            
            # Try text extraction first (fast path)
            text = page.get_text().strip()
            
            # Debug: log extracted text length
            print(f"PDF {filename} page {page_num + 1}: extracted {len(text)} chars via PyMuPDF")
            
            # If text is sparse, try OCR as fallback
            if len(text) < MIN_TEXT_PER_PAGE:
                print(f"PDF {filename} page {page_num + 1}: text sparse, trying OCR fallback")
                
                # Render page to image
                pix = page.get_pixmap(dpi=PDF_RENDER_DPI)
                
                # Convert to PIL Image
                img_bytes = pix.tobytes("png")
                image = Image.open(io.BytesIO(img_bytes))
                
                # Run OCR
                ocr_text = ocr_image(image)
                
                # Use OCR text only if it's longer than extracted text
                if len(ocr_text) > len(text):
                    print(f"PDF {filename} page {page_num + 1}: OCR produced {len(ocr_text)} chars (better)")
                    text = ocr_text
                else:
                    print(f"PDF {filename} page {page_num + 1}: keeping PyMuPDF text ({len(text)} chars)")
            
            # Always keep the text even if it's short
            # Empty pages are OK - they'll be filtered later
            
            pages_data.append({
                'page_num': page_num + 1,
                'text': text.strip(),
            })
        
        doc.close()
        
        # Combine all pages
        full_text = "\n\n".join(p['text'] for p in pages_data if p['text'])
        
        processing_time_ms = int((time.time() - start) * 1000)
        
        return {
            'text': full_text,
            'pages': pages_data,
            'page_count': page_count,
            'processing_time_ms': processing_time_ms,
        }
    
    except Exception as e:
        raise ValueError(f"Failed to process PDF {filename}: {str(e)}")


def process_image_file(file: BinaryIO, filename: str) -> dict:
    """
    Process an image file with OCR.
    
    Returns:
        {
            'text': str,
            'processing_time_ms': int
        }
    """
    start = time.time()
    
    try:
        # Read image
        file.seek(0)
        image = Image.open(file)
        
        # Run OCR
        text = ocr_image(image)
        
        processing_time_ms = int((time.time() - start) * 1000)
        
        return {
            'text': text,
            'processing_time_ms': processing_time_ms,
        }
    
    except Exception as e:
        raise ValueError(f"Failed to process image {filename}: {str(e)}")


def generate_lesson_name(text: str) -> str:
    """
    Generate a concise lesson name using OpenAI API.
    
    Args:
        text: Transcribed text from documents
    
    Returns:
        AI-generated lesson name (max 60 chars)
    """
    if not text or len(text.strip()) < 10:
        return "Untitled Lesson"
    
    # Use first 500 chars for context
    excerpt = text[:500].strip()
    
    try:
        client = OpenAI(api_key=settings.OPENAI_API_KEY)
        
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": "You are a helpful assistant that generates concise, descriptive lesson titles."
                },
                {
                    "role": "user",
                    "content": f"""Based on the following text excerpt from a document, generate a concise, descriptive lesson title.

Requirements:
- Maximum 60 characters
- Clear and specific
- Academic/educational tone
- No quotes or special formatting
- Just the title, nothing else

Text excerpt:
{excerpt}

Lesson title:"""
                }
            ],
            max_tokens=20,
            temperature=0.7,
        )
        
        title = response.choices[0].message.content.strip()
        
        # Remove quotes if present
        title = title.strip('"\'')
        
        # Truncate to 60 chars
        if len(title) > 60:
            title = title[:57] + "..."
        
        return title if title else "Untitled Lesson"
    
    except Exception as e:
        print(f"AI naming error: {e}")
        
        # Fallback: use first sentence
        sentences = text.split('.')
        if sentences and len(sentences[0].strip()) > 0:
            fallback = sentences[0].strip()[:60]
            return fallback if fallback else "Untitled Lesson"
        
        return "Untitled Lesson"


def create_lesson_from_uploads(user, files: list, filenames: list) -> dict:
    """
    Process uploaded files and create a Lesson with transcribed content.
    
    Args:
        user: Django User instance
        files: List of file objects (BinaryIO)
        filenames: List of original filenames
    
    Returns:
        {
            'lesson': Lesson instance,
            'lesson_id': int,
            'lesson_name': str,
            'pages_processed': int,
            'total_processing_time_ms': int,
            'errors': list[str]
        }
    """
    start = time.time()
    
    all_text_parts = []
    total_pages = 0
    errors = []
    
    # Process each file
    for file, filename in zip(files, filenames):
        try:
            # Validate file
            validation = validate_file(file, filename)
            
            if not validation['valid']:
                errors.append(validation['error'])
                continue
            
            # Process based on type
            if validation['file_type'] == 'pdf':
                result = process_pdf(file, filename)
                all_text_parts.append(result['text'])
                total_pages += result['page_count']
                
                # Store pages data for later (we'll create chunks after lesson)
                if not hasattr(create_lesson_from_uploads, '_pages_data'):
                    create_lesson_from_uploads._pages_data = []
                create_lesson_from_uploads._pages_data.extend(result['pages'])
            
            elif validation['file_type'] == 'image':
                result = process_image_file(file, filename)
                all_text_parts.append(result['text'])
                total_pages += 1
                
                # Store as single page
                if not hasattr(create_lesson_from_uploads, '_pages_data'):
                    create_lesson_from_uploads._pages_data = []
                create_lesson_from_uploads._pages_data.append({
                    'page_num': total_pages,
                    'text': result['text'],
                })
        
        except Exception as e:
            errors.append(f"{filename}: {str(e)}")
            continue
    
    # Combine all text
    full_text = "\n\n".join(part for part in all_text_parts if part)
    
    # Debug logging
    print(f"Total files processed: {len(files)}")
    print(f"Text parts collected: {len(all_text_parts)}")
    print(f"Full text length: {len(full_text)}")
    print(f"Full text preview: {full_text[:200]}")
    
    if not full_text or len(full_text.strip()) < 10:
        error_msg = f"No text could be extracted from uploaded files. Processed {len(files)} files, got {len(all_text_parts)} text parts, total length: {len(full_text)}"
        if errors:
            error_msg += f". Errors: {', '.join(errors)}"
        raise ValueError(error_msg)
    
    # Generate AI lesson name
    lesson_name = generate_lesson_name(full_text)
    
    # Create Lesson
    lesson = Lesson.objects.create(
        user=user,
        title=lesson_name,
        source_type=Lesson.SOURCE_LESSON,
        meeting_date=None,
    )
    
    # Create TranscriptChunk records for each page
    pages_data = getattr(create_lesson_from_uploads, '_pages_data', [])
    for page_data in pages_data:
        if page_data['text']:
            TranscriptChunk.objects.create(
                lesson=lesson,
                speaker="",
                text=page_data['text'],
                page_number=page_data['page_num'],
            )
    
    # Clean up temporary data
    if hasattr(create_lesson_from_uploads, '_pages_data'):
        delattr(create_lesson_from_uploads, '_pages_data')
    
    total_processing_time_ms = int((time.time() - start) * 1000)
    
    return {
        'lesson': lesson,
        'lesson_id': lesson.id,
        'lesson_name': lesson_name,
        'pages_processed': total_pages,
        'total_processing_time_ms': total_processing_time_ms,
        'errors': errors,
    }
