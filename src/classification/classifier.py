"""
Core Classification Engine with RAG/CAG Pipeline
Implements the Gemini-centric classifier with dual validation
"""
import json
import time
from typing import Dict, List, Optional, Tuple
import google.generativeai as genai
from google.generativeai.types import HarmCategory, HarmBlockThreshold

from ..config import Config
from .policy_rag import PolicyRAG


class GeminiClassifier:
    """
    Gemini-based document classifier with RAG (policy) and CAG (document caching)
    """

    def __init__(self, policy_rag: PolicyRAG):
        """
        Initialize classifier

        Args:
            policy_rag: PolicyRAG instance for knowledge base access
        """
        genai.configure(api_key=Config.GEMINI_API_KEY)
        self.policy_rag = policy_rag
        self.model_name = Config.GEMINI_MODEL

        # Initialize model with safety settings
        self.model = genai.GenerativeModel(
            model_name=self.model_name,
            safety_settings={
                HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
                HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
                HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
                HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE,
            }
        )

        self.policy_file_uri = None
        self.cached_content = {}

    def initialize_rag(self):
        """Initialize RAG by uploading policy documents"""
        print("Initializing Policy RAG...")
        self.policy_file_uri = self.policy_rag.upload_policy_to_gemini()
        print("Policy RAG initialized successfully")

    def cache_document(self, document_data: Dict) -> str:
        """
        Cache document content using Gemini Caching API

        Args:
            document_data: Processed document data

        Returns:
            Cache identifier
        """
        document_id = document_data['document_id']
        cached_content = document_data['cached_content']

        # Store in memory cache (Gemini API caching happens automatically with context)
        self.cached_content[document_id] = cached_content

        print(f"Document {document_id} cached ({len(cached_content)} characters)")
        return document_id

    def classify(self, document_data: Dict, use_dual_validation: bool = True) -> Dict:
        """
        Classify document using RAG/CAG pipeline

        Args:
            document_data: Processed document data
            use_dual_validation: Whether to use dual-layer validation

        Returns:
            Classification result with citations and confidence
        """
        document_id = document_data['document_id']

        # Cache the document
        self.cache_document(document_data)

        if use_dual_validation and Config.DUAL_VALIDATION_ENABLED:
            print("Using dual-layer validation...")
            result1 = self._classify_single(document_data, validation_pass=1)
            result2 = self._classify_single(document_data, validation_pass=2)

            # Consensus logic
            if (result1['final_category'] == result2['final_category'] and
                result1['confidence_score'] >= Config.CONFIDENCE_THRESHOLD and
                result2['confidence_score'] >= Config.CONFIDENCE_THRESHOLD):

                result1['hitl_status'] = 'AUTO_APPROVED'
                result1['validation_consensus'] = True
                result1['dual_validation_results'] = {
                    'pass1': result1['confidence_score'],
                    'pass2': result2['confidence_score']
                }
                print(f"Dual validation consensus: {result1['final_category']} (Auto-approved)")
                return result1
            else:
                result1['hitl_status'] = 'REQUIRES_REVIEW'
                result1['validation_consensus'] = False
                result1['dual_validation_results'] = {
                    'pass1': {'category': result1['final_category'], 'confidence': result1['confidence_score']},
                    'pass2': {'category': result2['final_category'], 'confidence': result2['confidence_score']}
                }
                print(f"Dual validation mismatch - requires HITL review")
                return result1
        else:
            result = self._classify_single(document_data, validation_pass=1)
            result['hitl_status'] = 'REQUIRES_REVIEW' if result['confidence_score'] < Config.CONFIDENCE_THRESHOLD else 'AUTO_APPROVED'
            result['validation_consensus'] = None
            return result

    def _classify_single(self, document_data: Dict, validation_pass: int = 1) -> Dict:
        """
        Perform single classification pass

        Args:
            document_data: Processed document data
            validation_pass: Validation pass number (1 or 2)

        Returns:
            Classification result
        """
        document_id = document_data['document_id']
        cached_content = self.cached_content.get(document_id, document_data['cached_content'])

        # Build the prompt tree
        results = {
            'document_id': document_id,
            'validation_pass': validation_pass
        }

        # Step 1: Safety Check (always first)
        safety_result = self._check_safety(cached_content, validation_pass)
        results['safety_check'] = safety_result

        if safety_result['is_unsafe']:
            return {
                'document_id': document_id,
                'final_category': 'UNSAFE',
                'confidence_score': safety_result['confidence'],
                'reasoning_summary': safety_result['reasoning'],
                'citation_snippet': safety_result.get('citation', 'Safety violation detected'),
                'step_results': results,
                'validation_pass': validation_pass
            }

        # Step 2: Confidential Check
        confidential_result = self._check_confidential(cached_content, validation_pass)
        results['confidential_check'] = confidential_result

        if confidential_result['is_confidential']:
            return {
                'document_id': document_id,
                'final_category': 'CONFIDENTIAL',
                'confidence_score': confidential_result['confidence'],
                'reasoning_summary': confidential_result['reasoning'],
                'citation_snippet': confidential_result.get('citation', 'Confidential content detected'),
                'step_results': results,
                'validation_pass': validation_pass
            }

        # Step 3: Sensitive Check
        sensitive_result = self._check_sensitive(cached_content, validation_pass)
        results['sensitive_check'] = sensitive_result

        if sensitive_result['is_sensitive']:
            return {
                'document_id': document_id,
                'final_category': 'SENSITIVE',
                'confidence_score': sensitive_result['confidence'],
                'reasoning_summary': sensitive_result['reasoning'],
                'citation_snippet': sensitive_result.get('citation', 'Sensitive content detected'),
                'step_results': results,
                'validation_pass': validation_pass
            }

        # Default: PUBLIC
        return {
            'document_id': document_id,
            'final_category': 'PUBLIC',
            'confidence_score': 0.95,
            'reasoning_summary': 'Document contains no unsafe, confidential, or sensitive information. Suitable for public distribution.',
            'citation_snippet': 'No restricted content found',
            'step_results': results,
            'validation_pass': validation_pass
        }

    def _check_safety(self, document_content: str, validation_pass: int) -> Dict:
        """Check for unsafe content"""
        prompt = f"""
{self.policy_rag.get_policy_context()}

VALIDATION PASS: {validation_pass}

TASK: Analyze the following document for UNSAFE content.

UNSAFE content includes:
- Violent, threatening, or harmful content
- Instructions for illegal activities
- Malware, exploits, or security vulnerabilities
- Content promoting harm to individuals or groups
- Explicitly prohibited content per enterprise policies

DOCUMENT CONTENT:
{document_content}

Respond in JSON format:
{{
    "is_unsafe": true/false,
    "confidence": 0.0-1.0,
    "reasoning": "Detailed explanation",
    "citation": "Exact quote and location if unsafe content found"
}}
"""

        try:
            response = self.model.generate_content(
                prompt,
                generation_config=genai.GenerationConfig(
                    temperature=0.1 if validation_pass == 1 else 0.3,
                    response_mime_type="application/json"
                )
            )

            result = json.loads(response.text)
            return result
        except Exception as e:
            print(f"Safety check error: {e}")
            return {'is_unsafe': False, 'confidence': 0.5, 'reasoning': f'Error: {e}', 'citation': ''}

    def _check_confidential(self, document_content: str, validation_pass: int) -> Dict:
        """Check for confidential content"""
        prompt = f"""
{self.policy_rag.get_policy_context()}

VALIDATION PASS: {validation_pass}

TASK: Analyze the following document for CONFIDENTIAL content.

CONFIDENTIAL content includes:
- Trade secrets and proprietary algorithms
- Financial records and banking information
- Legal documents under attorney-client privilege
- Merger & acquisition plans
- Executive compensation details
- Source code and intellectual property
- Customer databases with high-risk PII (SSN, credit cards, medical records)

HIGH-RISK PII PATTERNS:
- SSN: XXX-XX-XXXX format
- Credit cards: 16 digits
- Bank accounts: 8-17 digits
- Medical record numbers
- Passport numbers

DOCUMENT CONTENT:
{document_content}

Respond in JSON format:
{{
    "is_confidential": true/false,
    "confidence": 0.0-1.0,
    "reasoning": "Detailed explanation citing specific evidence",
    "citation": "Exact quote and location of confidential content",
    "pii_found": ["list of PII types detected"]
}}
"""

        try:
            response = self.model.generate_content(
                prompt,
                generation_config=genai.GenerationConfig(
                    temperature=0.1 if validation_pass == 1 else 0.3,
                    response_mime_type="application/json"
                )
            )

            result = json.loads(response.text)
            return result
        except Exception as e:
            print(f"Confidential check error: {e}")
            return {'is_confidential': False, 'confidence': 0.5, 'reasoning': f'Error: {e}', 'citation': '', 'pii_found': []}

    def _check_sensitive(self, document_content: str, validation_pass: int) -> Dict:
        """Check for sensitive content"""
        prompt = f"""
{self.policy_rag.get_policy_context()}

VALIDATION PASS: {validation_pass}

TASK: Analyze the following document for SENSITIVE content.

SENSITIVE content includes:
- Internal memos and communications
- Employee contact information
- Draft documents not for external distribution
- Internal project plans
- Budget information (non-executive)
- Customer feedback and survey data
- Performance reviews

MEDIUM-RISK PII PATTERNS:
- Email addresses
- Phone numbers
- Physical addresses
- Employee IDs
- Dates of birth

DOCUMENT CONTENT:
{document_content}

Respond in JSON format:
{{
    "is_sensitive": true/false,
    "confidence": 0.0-1.0,
    "reasoning": "Detailed explanation citing specific evidence",
    "citation": "Exact quote and location of sensitive content",
    "pii_found": ["list of PII types detected"]
}}
"""

        try:
            response = self.model.generate_content(
                prompt,
                generation_config=genai.GenerationConfig(
                    temperature=0.1 if validation_pass == 1 else 0.3,
                    response_mime_type="application/json"
                )
            )

            result = json.loads(response.text)
            return result
        except Exception as e:
            print(f"Sensitive check error: {e}")
            return {'is_sensitive': False, 'confidence': 0.5, 'reasoning': f'Error: {e}', 'citation': '', 'pii_found': []}
