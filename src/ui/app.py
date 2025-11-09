"""
Flask Web UI for Document Classification System
Provides upload interface and HITL review queue
"""
import time
import os
from pathlib import Path
from flask import Flask, render_template, request, jsonify, send_file, url_for
from werkzeug.utils import secure_filename
from flask_cors import CORS

from ..config import Config
from ..processing import DocumentProcessor
from ..classification import EnhancedGeminiClassifier, PolicyRAG
from ..blockchain import SolanaAuditTrail
from ..audio import TTSGenerator
from ..audit_logger import AuditLogger
from ..chat_service import DocumentChatService


app = Flask(__name__,
           template_folder='../../templates',
           static_folder='../../static')
CORS(app)
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024  # 50MB max file size
app.config['UPLOAD_FOLDER'] = Config.UPLOAD_DIR

# Initialize components
policy_rag = PolicyRAG()
classifier = EnhancedGeminiClassifier(policy_rag)
blockchain = SolanaAuditTrail()
tts_generator = TTSGenerator()
audit_logger = AuditLogger()
chat_service = DocumentChatService()

# Initialize RAG on startup
classifier.initialize_rag()

@app.route('/')
def index():
    """Main page"""
    stats = audit_logger.get_statistics()
    return render_template('index.html', stats=stats)


@app.route('/upload', methods=['POST'])
def upload_file():
    """Handle file upload and classification"""
    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400

    file = request.files['file']

    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400

    if not file.filename.lower().endswith('.pdf'):
        return jsonify({'error': 'Only PDF files are supported'}), 400

    try:
        # Save uploaded file
        filename = secure_filename(file.filename)
        filepath = Config.UPLOAD_DIR / filename
        file.save(filepath)

        # Process document
        start_time = time.time()

        print(f"\n{'='*80}")
        print(f"Processing uploaded file: {filename}")
        print(f"{'='*80}\n")

        # Step 1: Document processing
        try:
            print("Step 1: Processing document...")
            processor = DocumentProcessor(filepath)
            document_data = processor.process()
            document_data['file_name'] = filename
            print("✓ Document processing complete")
        except Exception as e:
            print(f"✗ Document processing failed: {e}")
            raise

        # Step 2: Classification
        try:
            print("Step 2: Classifying document...")
            classification_result = classifier.classify(document_data)
            classification_result['file_name'] = filename
            print("✓ Classification complete")
        except Exception as e:
            print(f"✗ Classification failed: {e}")
            raise

        # Step 3: Blockchain audit
        try:
            print("Step 3: Recording to blockchain...")
            blockchain_record = blockchain.record_to_blockchain(classification_result)
            print("✓ Blockchain recording complete")
        except Exception as e:
            print(f"✗ Blockchain recording failed: {e}")
            raise

        # Step 4: Generate audio summary
        try:
            print("Step 4: Generating audio summary...")
            audio_path = tts_generator.generate_full_report_audio(
                classification_result,
                classification_result['document_id']
            )
            print("✓ Audio generation complete")
        except Exception as e:
            print(f"✗ Audio generation failed: {e}")
            raise

        # Step 5: Log to database
        try:
            print("Step 5: Logging to database...")
            processing_time = time.time() - start_time
            audit_logger.log_classification(
                classification_result,
                processing_time,
                blockchain_record,
                audio_path
            )
            print("✓ Database logging complete")
        except Exception as e:
            print(f"✗ Database logging failed: {e}")
            raise

        # Prepare response
        response = {
            'document_id': classification_result['document_id'],
            'file_name': filename,
            'classification': classification_result['final_category'],
            'confidence': classification_result['confidence_score'],
            'reasoning': classification_result['reasoning_summary'],
            'citation': classification_result['citation_snippet'],
            'hitl_status': classification_result.get('hitl_status'),
            'validation_consensus': classification_result.get('validation_consensus'),
            'blockchain': {
                'tx_hash': blockchain_record.get('transaction_hash'),
                'audit_hash': blockchain_record.get('audit_hash'),
                'status': blockchain_record.get('status'),
                'explorer_url': blockchain_record.get('explorer_url')
            },
            'audio_available': audio_path is not None,
            'processing_time': round(processing_time, 2),
            'metadata': {
                'pages': document_data['metadata']['num_pages'],
                'images': document_data['metadata']['num_images'],
                'file_size': document_data['metadata']['file_size']
            }
        }

        print(f"\n{'='*80}")
        print(f"Classification Complete")
        print(f"Category: {response['classification']}")
        print(f"Confidence: {response['confidence']:.2%}")
        print(f"Processing Time: {processing_time:.2f}s")
        print(f"{'='*80}\n")

        return jsonify(response), 200

    except Exception as e:
        print(f"Error processing file: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@app.route('/hitl/queue')
def hitl_queue():
    """HITL review queue page"""
    pending_reviews = audit_logger.get_pending_hitl_reviews()
    return render_template('hitl_queue.html', reviews=pending_reviews)


@app.route('/hitl/review/<document_id>')
def hitl_review_detail(document_id):
    """HITL review detail page"""
    classification = audit_logger.get_classification(document_id)

    if not classification:
        return "Document not found", 404

    return render_template('hitl_review.html', classification=classification)


@app.route('/hitl/submit', methods=['POST'])
def submit_hitl_review():
    """Submit HITL review"""
    try:
        data = request.json
        document_id = data.get('document_id')
        corrected_category = data.get('corrected_category')
        reviewer_name = data.get('reviewer_name', 'SME')
        notes = data.get('notes', '')

        # Get original classification
        original = audit_logger.get_classification(document_id)

        if not original:
            return jsonify({'error': 'Document not found'}), 404

        # Log HITL review
        audit_logger.log_hitl_review(
            document_id,
            original['final_category'],
            corrected_category,
            reviewer_name,
            notes
        )

        # Add to RAG knowledge base if correction was made
        if original['final_category'] != corrected_category:
            # Get document content for the example
            doc_path = Config.UPLOAD_DIR / original['file_name']
            if doc_path.exists():
                processor = DocumentProcessor(doc_path)
                doc_data = processor.process()

                # Add as few-shot example
                policy_rag.add_hitl_example(
                    doc_data['full_text'][:1000],  # First 1000 chars
                    corrected_category,
                    f"SME correction: {notes}",
                    original['citation_snippet'],
                    "HITL Validated"
                )

        return jsonify({
            'success': True,
            'message': 'Review submitted successfully',
            'document_id': document_id
        }), 200

    except Exception as e:
        print(f"Error submitting review: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/statistics')
def get_statistics():
    """Get classification statistics"""
    stats = audit_logger.get_statistics()
    return jsonify(stats)


@app.route('/api/classifications')
def get_classifications():
    """Get all classifications"""
    limit = request.args.get('limit', 100, type=int)
    offset = request.args.get('offset', 0, type=int)

    classifications = audit_logger.get_all_classifications(limit, offset)
    return jsonify(classifications)


@app.route('/api/classification/<document_id>')
def get_classification(document_id):
    """Get specific classification"""
    classification = audit_logger.get_classification(document_id)

    if not classification:
        return jsonify({'error': 'Document not found'}), 404

    return jsonify(classification)


@app.route('/audio/<document_id>')
def get_audio(document_id):
    """Serve audio file"""
    classification = audit_logger.get_classification(document_id)

    if not classification or not classification.get('audio_summary_path'):
        return "Audio not found", 404

    audio_path = classification['audio_summary_path']

    if not os.path.exists(audio_path):
        return "Audio file not found", 404

    return send_file(audio_path, mimetype='audio/mpeg')


@app.route('/api/chat', methods=['POST'])
def chat():
    """Handle chat queries about documents"""
    try:
        data = request.json
        message = data.get('message')
        document_id = data.get('document_id')
        session_id = data.get('session_id')

        if not message:
            return jsonify({'error': 'Message is required'}), 400

        # Process chat message
        response = chat_service.chat(
            message=message,
            document_id=document_id,
            session_id=session_id
        )

        return jsonify(response), 200

    except Exception as e:
        print(f"Chat error: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@app.route('/api/chat/history/<session_id>')
def get_chat_history(session_id):
    """Get chat history for a session"""
    try:
        history = chat_service.get_session_history(session_id)
        return jsonify(history), 200
    except Exception as e:
        print(f"Error getting chat history: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/dashboard')
def dashboard():
    """Dashboard page"""
    stats = audit_logger.get_statistics()
    recent = audit_logger.get_all_classifications(limit=10)
    return render_template('dashboard.html', stats=stats, recent=recent)


def run_server(host='0.0.0.0', port=5000, debug=False):
    """Run Flask server"""
    print(f"\n{'='*80}")
    print(f"Gemini Document Classifier - Web UI")
    print(f"{'='*80}")
    print(f"Server: http://{host}:{port}")
    print(f"Dashboard: http://{host}:{port}/dashboard")
    print(f"HITL Queue: http://{host}:{port}/hitl/queue")
    print(f"{'='*80}\n")

    app.run(host=host, port=port, debug=debug)


if __name__ == '__main__':
    run_server(debug=True)
