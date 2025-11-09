"""
Document Chat Service
Enables natural language queries about classified documents
"""
import uuid
from typing import Dict, List, Optional
from pathlib import Path
import google.generativeai as genai

from .config import Config
from .audit_logger import AuditLogger
from .processing import DocumentProcessor


class DocumentChatService:
    """Handles chat queries about documents"""

    def __init__(self):
        """Initialize chat service"""
        genai.configure(api_key=Config.GEMINI_API_KEY)
        self.model = genai.GenerativeModel(Config.GEMINI_MODEL)
        self.audit_logger = AuditLogger()

    def _get_document_context(self, document_id: str) -> Optional[Dict]:
        """
        Retrieve document content and classification context

        Args:
            document_id: Document identifier

        Returns:
            Document context dict or None
        """
        # Get classification record
        classification = self.audit_logger.get_classification(document_id)
        if not classification:
            return None

        # Find and read the PDF file
        file_name = classification['file_name']
        file_path = Config.UPLOAD_DIR / file_name

        if not file_path.exists():
            return None

        # Extract text from PDF
        try:
            processor = DocumentProcessor(str(file_path))
            doc_data = processor.process()
            text_content = doc_data['full_text']
        except Exception as e:
            print(f"Error extracting PDF text: {e}")
            text_content = "[PDF content could not be extracted]"

        return {
            'document_id': document_id,
            'file_name': file_name,
            'text_content': text_content,
            'classification': {
                'category': classification['final_category'],
                'confidence': classification['confidence_score'],
                'reasoning': classification['reasoning_summary'],
                'citation': classification['citation_snippet']
            },
            'metadata': {
                'created_at': classification['created_at'],
                'blockchain_tx': classification.get('blockchain_tx_hash'),
                'hitl_status': classification.get('hitl_status')
            }
        }

    def _build_system_prompt(self, document_context: Dict) -> str:
        """
        Build system prompt with document context

        Args:
            document_context: Document context dict

        Returns:
            System prompt string
        """
        prompt = f"""You are a helpful AI assistant that answers questions about classified documents.

Document Information:
- File Name: {document_context['file_name']}
- Document ID: {document_context['document_id']}
- Classification: {document_context['classification']['category']} (Confidence: {document_context['classification']['confidence']:.2%})
- Classification Reasoning: {document_context['classification']['reasoning']}
- Key Citation: {document_context['classification']['citation']}

Document Content (First 50,000 characters):
{document_context['text_content'][:50000]}

Instructions:
1. Answer questions ONLY based on the document content provided above
2. Be specific and cite relevant sections from the document when possible
3. If the answer is not in the document, say "I don't have that information in this document"
4. Maintain context awareness about the document's classification and sensitivity level
5. Be concise but thorough in your responses
6. If asked about classification details, refer to the classification information provided above
"""
        return prompt

    def chat(self, message: str, document_id: Optional[str] = None,
             session_id: Optional[str] = None) -> Dict:
        """
        Process a chat message

        Args:
            message: User message
            document_id: Optional document ID for context
            session_id: Optional session ID for conversation history

        Returns:
            Chat response dict
        """
        # Generate session ID if not provided
        if not session_id:
            session_id = str(uuid.uuid4())

        # Log user message
        self.audit_logger.log_chat_message(
            session_id=session_id,
            role='user',
            message=message,
            document_id=document_id
        )

        # Get document context if document_id provided
        context_info = None
        if document_id:
            document_context = self._get_document_context(document_id)
            if not document_context:
                response_text = f"Document '{document_id}' not found in the system."
            else:
                context_info = f"Document: {document_context['file_name']}"
                response_text = self._query_with_context(message, document_context, session_id)
        else:
            # General query without specific document
            response_text = self._query_general(message, session_id)

        # Log assistant response
        self.audit_logger.log_chat_message(
            session_id=session_id,
            role='assistant',
            message=response_text,
            document_id=document_id,
            context_used=context_info
        )

        return {
            'session_id': session_id,
            'message': response_text,
            'document_id': document_id,
            'context_used': context_info is not None
        }

    def _query_with_context(self, message: str, document_context: Dict, session_id: str) -> str:
        """
        Query with document context

        Args:
            message: User message
            document_context: Document context
            session_id: Session ID

        Returns:
            Response text
        """
        try:
            # Build system prompt with document context
            system_prompt = self._build_system_prompt(document_context)

            # Get recent chat history for this session
            chat_history = self.audit_logger.get_chat_history(session_id, limit=10)

            # Build conversation history
            conversation_parts = [system_prompt]

            # Add recent history (exclude the last user message as we'll add it fresh)
            for msg in chat_history[:-1]:  # Exclude the last message (current user message)
                if msg['role'] == 'user':
                    conversation_parts.append(f"User: {msg['message']}")
                elif msg['role'] == 'assistant':
                    conversation_parts.append(f"Assistant: {msg['message']}")

            # Add current user message
            conversation_parts.append(f"User: {message}")

            # Generate response
            full_prompt = "\n\n".join(conversation_parts)
            response = self.model.generate_content(full_prompt)

            return response.text

        except Exception as e:
            print(f"Chat error: {e}")
            return f"I encountered an error processing your question: {str(e)}"

    def _query_general(self, message: str, session_id: str) -> str:
        """
        Query without specific document context

        Args:
            message: User message
            session_id: Session ID

        Returns:
            Response text
        """
        try:
            # Check if user is asking about available documents
            if any(keyword in message.lower() for keyword in ['documents', 'files', 'what do you have', 'list', 'show', 'available']):
                return self._list_available_documents()

            # Check if user is asking a question that needs a document
            question_keywords = ['what', 'how', 'why', 'when', 'where', 'who', 'contains', 'about', 'explain', 'describe', 'summarize', 'summary']
            if any(keyword in message.lower() for keyword in question_keywords):
                return self._suggest_document_selection()

            # Get recent chat history
            chat_history = self.audit_logger.get_chat_history(session_id, limit=10)

            # Build conversation
            conversation_parts = [
                "You are a helpful AI assistant for a document classification system. "
                "You can answer questions about documents that have been uploaded and classified. "
                "Be friendly and guide users to select a document if they're asking document-specific questions."
            ]

            for msg in chat_history[:-1]:
                if msg['role'] == 'user':
                    conversation_parts.append(f"User: {msg['message']}")
                elif msg['role'] == 'assistant':
                    conversation_parts.append(f"Assistant: {msg['message']}")

            conversation_parts.append(f"User: {message}")

            full_prompt = "\n\n".join(conversation_parts)
            response = self.model.generate_content(full_prompt)

            return response.text

        except Exception as e:
            print(f"Chat error: {e}")
            return f"I encountered an error: {str(e)}"

    def _suggest_document_selection(self) -> str:
        """
        Suggest user to select a document

        Returns:
            Suggestion message
        """
        classifications = self.audit_logger.get_all_classifications(limit=5)

        if not classifications:
            return ("📄 **No documents available yet.**\n\n"
                    "Please upload a document first using the upload area above. "
                    "Once uploaded, I'll be able to answer questions about it!")

        doc_preview = "\n".join([
            f"• **{doc['file_name']}** ({doc['final_category']})"
            for doc in classifications[:3]
        ])

        return (f"📄 **I'd be happy to help!**\n\n"
                f"To answer your question, please select a document from the list. "
                f"Click the **📁 Select Document** button above.\n\n"
                f"**Recently classified documents:**\n{doc_preview}"
                + ("\n• *...and more*" if len(classifications) > 3 else ""))

    def _list_available_documents(self) -> str:
        """
        List available documents in the system

        Returns:
            Formatted list of documents
        """
        classifications = self.audit_logger.get_all_classifications(limit=20)

        if not classifications:
            return "No documents have been classified yet. Please upload a document first."

        doc_list = ["Here are the recently classified documents:\n"]
        for i, doc in enumerate(classifications, 1):
            doc_list.append(
                f"{i}. **{doc['file_name']}** "
                f"(ID: `{doc['document_id']}`, Category: {doc['final_category']}, "
                f"Confidence: {doc['confidence_score']:.1%})"
            )

        doc_list.append("\nYou can ask me questions about any of these documents by referencing the document ID.")

        return "\n".join(doc_list)

    def get_session_history(self, session_id: str) -> List[Dict]:
        """
        Get chat history for a session

        Args:
            session_id: Session ID

        Returns:
            List of messages
        """
        return self.audit_logger.get_chat_history(session_id)
