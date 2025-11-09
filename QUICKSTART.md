# Quick Start Guide

Get the Gemini Document Classifier running in 5 minutes!

## Prerequisites

- Python 3.9 or higher
- pip package manager
- Tesseract OCR installed on your system

## Installation Steps

### 1. Install Tesseract OCR

**macOS:**
```bash
brew install tesseract
```

**Ubuntu/Debian:**
```bash
sudo apt-get update && sudo apt-get install tesseract-ocr
```

**Windows:**
Download from: https://github.com/UB-Mannheim/tesseract/wiki

### 2. Set Up Python Environment

```bash
# Navigate to project directory
cd gemini-classifier

# Create virtual environment
python3 -m venv venv

# Activate virtual environment
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### 3. Verify Installation

```bash
python test_system.py
```

If all tests pass, you're ready to go! ✅

### 4. Start the Application

```bash
python main.py
```

The web interface will open at: **http://localhost:5001**

> **Note:** Using port 5001 to avoid conflict with macOS AirPlay Receiver on port 5000.

## First Classification

1. Open http://localhost:5001 in your browser
2. Drag and drop a PDF file or click "Select File"
3. Wait 5-15 seconds for processing
4. View your classification result with:
   - Category (UNSAFE/CONFIDENTIAL/SENSITIVE/PUBLIC)
   - Confidence score and reasoning
   - Blockchain audit hash
   - Audio summary (click to play)

## Dashboard & Analytics

Visit http://localhost:5001/dashboard to see:
- Total classifications
- Category breakdown
- Auto-approval rate
- Average processing time
- Recent classifications

## HITL Review Queue

Visit http://localhost:5001/hitl/queue to:
- Review low-confidence classifications
- Correct AI decisions
- Improve the system through feedback

When you correct a classification, it's automatically added to the knowledge base!

## API Usage

### Classify via API

```bash
curl -X POST -F "file=@document.pdf" http://localhost:5001/upload
```

### Get Statistics

```bash
curl http://localhost:5001/api/statistics
```

### Get All Classifications

```bash
curl http://localhost:5001/api/classifications
```

## Test Documents

Create simple test PDFs with different classification levels:

**Public Document:**
```
FOR IMMEDIATE RELEASE
Company Announces New Product
Contact: press@company.com
```

**Sensitive Document:**
```
INTERNAL ONLY - Team Meeting Notes
Attendees: john@company.com, jane@company.com
Project launch scheduled for Q2 2024
```

**Confidential Document:**
```
CONFIDENTIAL - Executive Summary
M&A Target: TechCorp - $500M offer
Customer Database:
Name: John Smith
SSN: 123-45-6789
Credit Card: 4532-1234-5678-9010
```

## Troubleshooting

**"Tesseract not found"**
→ Make sure Tesseract is installed and in your PATH

**"Module not found"**
→ Run `pip install -r requirements.txt` again

**"API key error"**
→ Check that your `.env` file has valid API keys

**"Port 5000 already in use"**
→ Edit `main.py` to change the port, or stop the other service

## Next Steps

- ✅ Classify your first document
- ✅ Review the dashboard
- ✅ Try the HITL review process
- ✅ Check the blockchain audit trail
- ✅ Listen to audio summaries
- ✅ Review the policy files in `policies/` directory
- ✅ Read the full README.md for advanced features

## Architecture Overview

```
PDF Upload → Document Processing (OCR) → Gemini AI Classification
              ↓
         Policy RAG (Knowledge Base)
              ↓
    Dual Validation & Consensus Check
              ↓
     ┌────────┼────────┬────────────┐
     ▼        ▼        ▼            ▼
  Solana  ElevenLabs SQLite    Web UI
 Blockchain   TTS     Audit   (HITL Queue)
```

## Support

For detailed documentation, see:
- **README.md** - Complete documentation
- **Code comments** - Extensively documented source code
- **Policy files** - `policies/*.json` for category definitions

---

🚀 **Happy Classifying!**
