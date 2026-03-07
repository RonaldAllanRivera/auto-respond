# Document Ingestion Pipeline

This guide explains how to use the document ingestion feature to create lessons from uploaded images and PDFs.

## Overview

The document ingestion pipeline allows subscribers to:
- Upload images (JPG, PNG, WEBP, TIFF) and PDFs via the web dashboard
- Automatically transcribe content using OCR (Tesseract)
- Generate AI-powered lesson names
- Use transcribed content as context for AI Q&A
- Select lessons in the desktop app for targeted learning

## Architecture

### Three Capture Modes

1. **Recitation Mode** (Live Capture)
   - Real-time Google Meet screenshot capture
   - OCR via Print Screen hotkey
   - Auto-creates lessons per meeting
   - Source type: `recitation`

2. **Lesson Mode** (Document Upload)
   - Upload images/PDFs via web dashboard
   - Batch OCR processing
   - AI-generated lesson names
   - Source type: `lesson`
   - Desktop app can select these lessons for Q&A

3. **Pro Mode** (Custom AI Context)
   - Custom AI persona (e.g., "You are a Senior Math Teacher")
   - Custom description (e.g., "Help with fractions and percentages")
   - Enhanced AI answering with personalized context
   - Works with both Recitation and Lesson modes

## Web Dashboard Upload

### Step 1: Navigate to Upload Page

1. Log in to the dashboard
2. Click **"Upload Documents"** in the navigation
3. Or visit: `https://your-app.com/lessons/upload/`

### Step 2: Select Files

**Supported formats:**
- Images: JPG, JPEG, PNG, WEBP, TIFF
- Documents: PDF

**Limits:**
- Max 100 files per upload
- Max 100MB total size
- Max 10MB per file

**Upload methods:**
- Drag and drop files into the upload area
- Click "Browse Files" to select from file picker

### Step 3: Review and Process

1. Review the file list (name, size, page count)
2. Remove unwanted files if needed
3. Click **"Generate Lesson"**
4. Wait for processing (progress bar shows status)

### Step 4: Success

- AI-generated lesson name is displayed
- View the lesson immediately or upload more
- Lesson is now available in the desktop app

## Desktop App: Lesson Mode

### Selecting a Mode

1. Open the desktop app
2. In the **Capture Mode** section, select:
   - **Recitation** (default): Live screenshot capture
   - **Lesson**: Select from uploaded lessons
   - **Pro**: Custom AI persona/description

### Using Lesson Mode

1. Select **Lesson** mode
2. Choose a lesson from the dropdown (filtered by title and date)
3. Capture screenshots or type questions manually
4. AI answers are based on the selected lesson's transcript

**Benefits:**
- Focused Q&A on specific lesson content
- Better context for AI answers
- Study specific topics in depth

## Desktop App: Pro Mode

### Setting Up Pro Mode

1. Select **Pro** mode
2. Enter **AI Persona**:
   ```
   You are a Senior Math Teacher with 20 years of experience
   ```

3. Enter **AI Description**:
   ```
   Help me answer questions about fractions, percentages, and algebra.
   Focus on step-by-step explanations suitable for Grade 5 students.
   ```

4. Optionally select a lesson for additional context

### How Pro Mode Works

- AI uses your custom persona and description
- Answers are tailored to your specified focus areas
- Works with both live captures and uploaded lessons
- Persona/description is sent with every question

**Example use cases:**
- Math tutor persona for homework help
- Science teacher persona for lab explanations
- History professor persona for essay guidance

## Enhanced Question Detection

The desktop app now detects:

**Questions (existing):**
- WH-questions: What, When, Where, Who, Why, How
- Math expressions: "5 + 3", "1/4 x 1/5"

**Statements (new):**
- Explain: "Explain photosynthesis"
- Describe: "Describe the water cycle"
- Define: "Define mitosis"
- Compare: "Compare fractions and decimals"
- Summarize: "Summarize the lesson"
- List: "List the steps"

All detected prompts are sent to AI for answering.

## Document Processing Details

### PDF Processing

**Text-based PDFs:**
1. Extract text directly (fast, <1s per page)
2. Create TranscriptChunk per page
3. Track page numbers

**Scanned PDFs:**
1. Render each page to image (300 DPI)
2. Run Tesseract OCR (~2-3s per page)
3. Create TranscriptChunk per page
4. Track page numbers

**Mixed PDFs:**
- Try text extraction first
- Fall back to OCR if text is sparse (<50 chars/page)

### Image Processing

1. Validate format (magic bytes, not just extension)
2. Resize if >4000px (maintain aspect ratio)
3. Enhance contrast for better OCR
4. Run Tesseract OCR (~1-2s per image)
5. Create single TranscriptChunk

### AI Lesson Naming

**Process:**
1. Extract first 500 characters of transcribed text
2. Send to OpenAI API (gpt-4o-mini)
3. Prompt: "Generate a concise lesson title (max 60 chars)"
4. Fallback: Use first sentence if AI fails

**Examples:**
- "Introduction to Photosynthesis"
- "Fraction Multiplication Practice"
- "World War II Timeline"

**Cost:** ~$0.0001 per lesson (very cheap)

## Editing Lessons

### Edit Lesson Name

1. Go to lesson detail page: `/lessons/<id>/`
2. Click the edit icon next to the lesson title
3. Enter new name (max 255 characters)
4. Click save

### Edit Transcript Text

1. Go to lesson detail page: `/lessons/<id>/`
2. Find the transcript chunk to edit
3. Click the edit icon
4. Correct OCR errors or add notes
5. Click save

**Use cases:**
- Fix OCR mistakes
- Add clarifications
- Improve context for AI

## API Reference

### Upload Documents

```http
POST /api/lessons/upload/
Content-Type: multipart/form-data
Authorization: Session (login required)

files: [file1, file2, ...]
```

**Response:**
```json
{
  "lesson_id": 123,
  "lesson_name": "Introduction to Photosynthesis",
  "pages_processed": 15,
  "processing_time_ms": 12340
}
```

**Errors:**
- 400: Invalid file type, too many files, or too large
- 403: Subscription required
- 429: Rate limit exceeded (10 uploads/hour)

### List Lessons

```http
GET /api/lessons/list/?source_type=lesson
Authorization: X-Device-Token (device token required)
```

**Response:**
```json
{
  "lessons": [
    {
      "id": 123,
      "title": "Introduction to Photosynthesis",
      "created_at": "2026-03-07T10:30:00Z",
      "page_count": 15
    }
  ]
}
```

### Submit Question (with Pro mode)

```http
POST /api/questions/
Content-Type: application/json
Authorization: X-Device-Token

{
  "question": "Explain photosynthesis",
  "lesson_id": 123,
  "persona": "You are a Senior Biology Teacher",
  "description": "Help me understand plant biology concepts"
}
```

## Rate Limits

- **Uploads:** 10 per hour per user
- **Files:** Max 100 per upload
- **Size:** Max 100MB total, 10MB per file

## Storage Policy

**No server storage:**
- Files are processed in memory only
- Transcribed text is saved to database
- Original files are deleted immediately after processing
- Privacy-friendly and cost-effective

**What is stored:**
- Lesson metadata (title, date, source type)
- Transcribed text (TranscriptChunk records)
- Page numbers (for PDFs)
- AI-generated answers

## Troubleshooting

### Upload fails with "Invalid file type"

**Solution:** Ensure files are:
- Images: JPG, PNG, WEBP, TIFF
- Documents: PDF only
- Not corrupted or password-protected

### OCR quality is poor

**Solutions:**
1. Use higher resolution images (300 DPI minimum)
2. Ensure text is clear and not blurry
3. Avoid handwritten text (OCR works best with printed text)
4. Edit transcript chunks to fix errors

### AI lesson name is generic

**Solutions:**
1. Ensure uploaded documents have clear content
2. Edit the lesson name manually after creation
3. Upload more pages for better context

### Rate limit exceeded

**Solution:** Wait 1 hour before uploading again (10 uploads/hour limit)

### Desktop app doesn't show lessons

**Solutions:**
1. Ensure you're in Lesson mode
2. Check that lessons exist (upload via web dashboard first)
3. Refresh the lesson list
4. Check internet connection

## Best Practices

### For Best OCR Results

1. **Use high-quality scans** (300 DPI or higher)
2. **Ensure good contrast** (black text on white background)
3. **Avoid skewed images** (straighten pages before scanning)
4. **Use clean fonts** (avoid decorative or handwritten text)

### For Better AI Answers

1. **Upload complete lessons** (not just single pages)
2. **Use descriptive lesson names** (helps with context)
3. **Edit OCR errors** (improves AI understanding)
4. **Use Pro mode** for specialized topics

### For Efficient Workflow

1. **Batch upload** related documents together
2. **Organize by subject** (use clear lesson names)
3. **Review transcripts** after upload (fix errors early)
4. **Use Lesson mode** for focused study sessions

## Security & Privacy

- All uploads require active subscription
- Files are processed server-side (not stored)
- Transcribed text is private to your account
- Multi-tenant isolation (can't access other users' lessons)
- Rate limiting prevents abuse

## Performance

**Expected processing times:**
- Text-based PDF: ~1s per page
- Scanned PDF: ~3s per page
- Image: ~2s per image
- AI naming: ~2s
- **Total for 100-page PDF:** ~5-6 minutes

**Optimization tips:**
- Upload text-based PDFs when possible (faster)
- Split very large PDFs into smaller batches
- Upload during off-peak hours for faster processing

## Future Enhancements

- Multi-language OCR support
- Advanced OCR settings (DPI, language selection)
- Lesson folders and categories
- Lesson sharing and collaboration
- Export lessons to PDF/DOCX
- Bulk lesson management
- OCR confidence scores
- Automatic image enhancement

## Support

For issues or questions:
1. Check this documentation
2. Review `TEST.md` for verification steps
3. Check Django Admin logs (if you're the owner)
4. Contact support via dashboard
