#!/bin/bash
# Quick test script for document upload feature

echo "=== Testing Document Upload Feature ==="
echo ""

# Check if Docker is running
if ! docker compose ps | grep -q "web"; then
    echo "❌ Backend not running. Start with: docker compose up"
    exit 1
fi

echo "✅ Backend is running"
echo ""

# Check if migrations are applied
echo "Checking migrations..."
docker compose run --rm web python manage.py showmigrations lessons | tail -5

echo ""
echo "=== Manual Testing Steps ==="
echo ""
echo "1. Open browser: http://localhost:8000/"
echo "2. Login with your account"
echo "3. Click 'Upload Documents' button"
echo "4. Try uploading a PDF or image"
echo "5. Check if rate limit warning is visible"
echo ""
echo "=== API Endpoints Available ==="
echo ""
echo "POST /api/lessons/upload/     - Upload documents (session auth)"
echo "GET  /api/lessons/list/        - List lessons (device token)"
echo "GET  /lessons/                 - Dashboard with tabs"
echo "GET  /lessons/upload/          - Upload page"
echo ""
echo "=== Rate Limits ==="
echo ""
echo "- 10 uploads per hour per user"
echo "- Max 100 files per upload"
echo "- Max 100MB total size"
echo "- Max 10MB per file"
echo ""
