# Gemini Document Classifier

**Max Winning Project: Gemini-Centric Document Classification System**

A comprehensive, enterprise-grade document classification system powered by Google's Gemini 2.0 Flash, featuring RAG (Retrieval Augmented Generation), CAG (Context Augmented Generation), Solana blockchain audit trails, and ElevenLabs text-to-speech accessibility.

## 🌟 Features

### Phase 1: Foundation & Policy RAG
- ✅ **Policy Knowledge Base**: Comprehensive category definitions, PII patterns, and SME-validated examples
- ✅ **Multi-Modal Document Processing**: PDF parsing with OCR for text and images
- ✅ **Citation Mapping**: Precise source location tracking with bounding boxes
- ✅ **Gemini File Search Store**: RAG-based policy grounding

### Phase 2: Core AI Engine with RAG/CAG
- ✅ **Dynamic Prompt Tree**: Sequential classification flow (UNSAFE → CONFIDENTIAL → SENSITIVE → PUBLIC)
- ✅ **RAG + CAG Grounding**: Policy knowledge base + cached document content
- ✅ **Structured JSON Output**: Category, confidence, reasoning, and citations
- ✅ **Dual-Layer Validation**: Consensus-based auto-approval (90%+ confidence threshold)

### Phase 3: Auditability, UX & Compliance
- ✅ **Solana Blockchain**: Immutable audit trails on Solana devnet
- ✅ **ElevenLabs TTS**: Flash v2.5 model for ultra-low latency audio summaries (32 languages)
- ✅ **SQLite Audit Logs**: Complete classification history and HITL reviews
- ✅ **Web UI**: Flask-based interface with HITL feedback loop

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Document Upload (PDF)                     │
└─────────────────┬───────────────────────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────────────────────────┐
│  Document Processing (PyMuPDF + OCR + Citation Mapping)     │
└─────────────────┬───────────────────────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────────────────────────┐
│         Gemini Classifier (RAG + CAG Pipeline)              │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐     │
│  │ Policy RAG   │  │ Cached Doc   │  │ Dual Layer   │     │
│  │ (File Search)│ +│ (CAG)        │ +│ Validation   │     │
│  └──────────────┘  └──────────────┘  └──────────────┘     │
└─────────────────┬───────────────────────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────────────────────────┐
│              Classification Result + Metadata                │
└─────────┬───────────┬───────────┬───────────────────────────┘
          │           │           │
          ▼           ▼           ▼
┌──────────────┐ ┌─────────┐ ┌──────────────┐
│   Solana     │ │ElevenLabs│ │SQLite Audit  │
│ Blockchain   │ │   TTS    │ │   Logger     │
└──────────────┘ └─────────┘ └──────────────┘
                  │
                  ▼
┌─────────────────────────────────────────────────────────────┐
│        Web UI (Dashboard + HITL Review Queue)               │
└─────────────────────────────────────────────────────────────┘
```

## 📋 Requirements

- Python 3.9+
- Tesseract OCR
- API Keys:
  - Google Gemini API
  - ElevenLabs API
  - Solana Devnet access

## 🚀 Installation

### 1. Clone/Navigate to Project

```bash
cd gemini-classifier
```

### 2. Install System Dependencies

**macOS:**
```bash
brew install tesseract
```

**Ubuntu/Debian:**
```bash
sudo apt-get update
sudo apt-get install tesseract-ocr
```

**Windows:**
Download and install Tesseract from: https://github.com/UB-Mannheim/tesseract/wiki

### 3. Create Virtual Environment

```bash
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

### 4. Install Python Dependencies

```bash
pip install -r requirements.txt
```

### 5. Configure Environment Variables

The `.env` file is already configured with your API keys:

```env
GEMINI_API_KEY=AIzaSyA5CRA7vt5rLIVzrW9mTFOTMtFCasEhxlo
ELEVENLABS_API_KEY=sk_ba8d004de32d2f357738185dfe1fe6826a9b8e2bba9c9739
SOLANA_CLUSTER_URL=https://api.devnet.solana.com
```

**Note:** In production, use environment variables or secure secret management instead of committing API keys.

## 🎯 Usage

### Start the Web Application

```bash
python main.py
```

The application will be available at:
- **Main Upload**: http://localhost:5000
- **Dashboard**: http://localhost:5000/dashboard
- **HITL Queue**: http://localhost:5000/hitl/queue

### Classify a Document

1. Navigate to http://localhost:5000
2. Upload a PDF file (drag-and-drop or click to browse)
3. Wait for processing (typically 5-15 seconds)
4. Review the classification result with:
   - Category (UNSAFE/CONFIDENTIAL/SENSITIVE/PUBLIC)
   - Confidence score
   - Reasoning and citations
   - Blockchain audit hash
   - Audio summary (click to play)

### HITL Review Process

1. Navigate to **HITL Queue** (http://localhost:5000/hitl/queue)
2. Click "Review Document" on any pending classification
3. Verify or correct the classification
4. Add reviewer notes
5. Submit review

**Important:** Corrected classifications are automatically added to the RAG knowledge base as new few-shot examples, improving future accuracy.

## 📊 Classification Categories

### 1. UNSAFE (Priority 1)
- Harmful, violent, or threatening content
- Illegal activity instructions
- Malware or security exploits
- **Action:** Immediate rejection and escalation

### 2. CONFIDENTIAL (Priority 2)
- Trade secrets and proprietary algorithms
- Financial records (with SSN, credit cards)
- Legal documents (attorney-client privilege)
- M&A plans, executive compensation
- Source code and IP
- **PII:** SSN, credit cards, bank accounts, medical records, passports

### 3. SENSITIVE (Priority 3)
- Internal memos and communications
- Employee directories
- Draft documents
- Internal project plans
- Non-executive budgets
- **PII:** Emails, phone numbers, addresses, employee IDs

### 4. PUBLIC (Priority 4)
- Published marketing materials
- Public website content
- Press releases
- Open-source code
- Public documentation

## 🔧 API Endpoints

### Upload and Classify
```http
POST /upload
Content-Type: multipart/form-data

Response: {
  "document_id": "DOC_abc123...",
  "classification": "CONFIDENTIAL",
  "confidence": 0.95,
  "reasoning": "...",
  "citation": "...",
  "blockchain": {...},
  "audio_available": true
}
```

### Get Statistics
```http
GET /api/statistics

Response: {
  "total_classifications": 42,
  "auto_approval_rate": 85.5,
  "avg_processing_time": 8.3,
  "by_category": {...}
}
```

### Get All Classifications
```http
GET /api/classifications?limit=100&offset=0
```

### Get Specific Classification
```http
GET /api/classification/<document_id>
```

### Submit HITL Review
```http
POST /hitl/submit
Content-Type: application/json

{
  "document_id": "DOC_abc123...",
  "corrected_category": "SENSITIVE",
  "reviewer_name": "Jane Doe",
  "notes": "..."
}
```

### Get Audio Summary
```http
GET /audio/<document_id>
```

## 🧪 Testing

### Test with Sample Documents

Create test PDFs with different content types:

**Confidential Example:**
```
CONFIDENTIAL - Board Meeting Minutes
Acquisition Target: TechCorp
Offer: $500M
Employee Data:
  John Smith - SSN: 123-45-6789
  Credit Card: 4532-1234-5678-9010
```

**Public Example:**
```
FOR IMMEDIATE RELEASE
Product Launch Announcement
Contact: press@company.com
```

### Verify System Components

1. **RAG Policy Upload**: Check console for "Policy uploaded successfully"
2. **Classification**: Verify JSON output with category, confidence, reasoning
3. **Blockchain**: Check for transaction hash (may be simulated if devnet is down)
4. **TTS**: Audio file should be generated in `data/cache/audio/`
5. **Database**: SQLite file at `data/audit_logs.db`

## 📁 Project Structure

```
gemini-classifier/
├── main.py                      # Main entry point
├── requirements.txt             # Python dependencies
├── .env                        # Environment variables (API keys)
├── README.md                   # This file
├── src/
│   ├── config.py               # Configuration management
│   ├── audit_logger.py         # SQLite audit logging
│   ├── processing/
│   │   ├── __init__.py
│   │   └── document_processor.py  # PDF/OCR processing
│   ├── classification/
│   │   ├── __init__.py
│   │   ├── policy_rag.py       # RAG knowledge base
│   │   └── classifier.py       # Core AI classifier
│   ├── blockchain/
│   │   ├── __init__.py
│   │   └── solana_audit.py     # Solana integration
│   ├── audio/
│   │   ├── __init__.py
│   │   └── tts_generator.py    # ElevenLabs TTS
│   └── ui/
│       ├── __init__.py
│       └── app.py              # Flask web application
├── policies/
│   ├── categories.json         # Category definitions
│   ├── pii_patterns.json       # PII detection patterns
│   └── few_shot_examples.json  # SME-validated examples
├── templates/
│   ├── base.html
│   ├── index.html              # Upload page
│   ├── dashboard.html          # Statistics dashboard
│   ├── hitl_queue.html         # Review queue
│   └── hitl_review.html        # Review detail page
└── data/
    ├── uploads/                # Uploaded PDFs
    ├── cache/                  # Cached content & audio
    ├── audit_logs/             # Log files
    └── audit_logs.db           # SQLite database
```

## 🎓 Key Technologies

| Component | Technology | Purpose |
|-----------|-----------|---------|
| AI Model | Gemini 2.0 Flash | Fast, high-quality classification |
| RAG | Gemini File Search | Policy knowledge grounding |
| CAG | Gemini Caching API | Document context optimization |
| Blockchain | Solana (Devnet) | Immutable audit trails |
| TTS | ElevenLabs Flash v2.5 | Ultra-low latency audio (75ms) |
| Database | SQLite | Local audit logging |
| Web Framework | Flask | REST API & web UI |
| OCR | Tesseract + PyMuPDF | Multi-modal document processing |

## 🔐 Security Considerations

1. **API Keys**: Never commit API keys to version control. Use environment variables.
2. **PII Detection**: High-risk PII triggers CONFIDENTIAL classification.
3. **Audit Trail**: All decisions are logged to SQLite and Solana blockchain.
4. **HITL Review**: Human oversight for low-confidence or mismatched validations.
5. **Safety Checks**: UNSAFE content is detected first and rejected immediately.

## 📈 Performance Metrics

- **Processing Speed**: ~5-15 seconds per document (depends on page count)
- **Auto-Approval Rate**: Target 85%+ with dual validation
- **Confidence Threshold**: 90% for auto-approval
- **TTS Latency**: ~75ms (ElevenLabs Flash v2.5)
- **Supported Languages**: 32 languages (TTS)

## 🐛 Troubleshooting

### "Tesseract not found"
Install Tesseract OCR (see Installation section)

### "File processing failed"
Check that the PDF is not corrupted or password-protected

### "Blockchain recording error"
The system will create a simulated transaction hash if Solana devnet is unavailable. This is normal for demo purposes.

### "Audio generation error"
Verify ElevenLabs API key is valid and has available quota

### Gemini API errors
- Check API key validity
- Verify quota/billing is enabled
- Ensure Gemini 2.0 Flash access is enabled

## 🤝 HITL Feedback Loop

The system implements a continuous improvement cycle:

1. Document is classified by AI
2. If confidence < 90% or dual validation mismatch → HITL queue
3. SME reviews and corrects classification
4. Correction is added to `policies/few_shot_examples.json`
5. Policy RAG is updated automatically
6. Future similar documents benefit from the correction

## 📝 License

This is a demonstration project for educational purposes.

## 🙏 Acknowledgments

- **Google Gemini**: Advanced AI classification engine
- **ElevenLabs**: Ultra-fast, high-quality TTS
- **Solana**: Blockchain infrastructure for audit trails
- **Tesseract OCR**: Open-source OCR engine

## 📞 Support

For issues or questions about this implementation, please review:
1. This README
2. The code comments (extensively documented)
3. The policy JSON files in `policies/` directory

---

**Built with ❤️ using Gemini 2.0 Flash, ElevenLabs, and Solana**
