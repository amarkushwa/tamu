"""
Audit Logging System
SQLite database for tracking all classification results and HITL activities
"""
import sqlite3
import json
import time
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime

from .config import Config


class AuditLogger:
    """Manages audit logs in SQLite database"""

    def __init__(self, db_path: Optional[Path] = None):
        """
        Initialize audit logger

        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = db_path or Config.DATABASE_PATH
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_database()

    def _init_database(self):
        """Initialize database schema"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Classifications table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS classifications (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                document_id TEXT NOT NULL UNIQUE,
                file_name TEXT NOT NULL,
                final_category TEXT NOT NULL,
                confidence_score REAL NOT NULL,
                reasoning_summary TEXT,
                citation_snippet TEXT,
                hitl_status TEXT,
                validation_consensus BOOLEAN,
                dual_validation_pass1 REAL,
                dual_validation_pass2 REAL,
                blockchain_tx_hash TEXT,
                blockchain_audit_hash TEXT,
                audio_summary_path TEXT,
                processing_time_seconds REAL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # HITL Reviews table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS hitl_reviews (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                document_id TEXT NOT NULL,
                reviewer_name TEXT,
                original_category TEXT NOT NULL,
                corrected_category TEXT NOT NULL,
                reviewer_notes TEXT,
                reviewed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (document_id) REFERENCES classifications(document_id)
            )
        """)

        # Audit Events table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS audit_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                document_id TEXT NOT NULL,
                event_type TEXT NOT NULL,
                event_data TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (document_id) REFERENCES classifications(document_id)
            )
        """)

        # Performance Metrics table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS performance_metrics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                metric_name TEXT NOT NULL,
                metric_value REAL NOT NULL,
                metadata TEXT,
                recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Chat History table for document Q&A
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS chat_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                document_id TEXT,
                role TEXT NOT NULL,
                message TEXT NOT NULL,
                context_used TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (document_id) REFERENCES classifications(document_id)
            )
        """)

        # Create indexes
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_document_id ON classifications(document_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_hitl_status ON classifications(hitl_status)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_category ON classifications(final_category)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_created_at ON classifications(created_at)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_session_id ON chat_history(session_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_chat_document_id ON chat_history(document_id)")

        conn.commit()
        conn.close()

    def log_classification(self, classification_result: Dict, processing_time: float,
                          blockchain_record: Optional[Dict] = None,
                          audio_path: Optional[str] = None) -> int:
        """
        Log a classification result. Uses INSERT OR REPLACE to handle re-processing.
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        document_id = classification_result['document_id']

        # To maintain data integrity, first delete related records if we are about to replace a classification
        # This is necessary because INSERT OR REPLACE only works on the 'classifications' table
        cursor.execute("DELETE FROM hitl_reviews WHERE document_id = ?", (document_id,))
        cursor.execute("DELETE FROM audit_events WHERE document_id = ?", (document_id,))
        cursor.execute("DELETE FROM chat_history WHERE document_id = ?", (document_id,))

        # Extract dual validation data
        dual_val_data = classification_result.get('dual_validation_results', {})
        pass1_confidence = None
        pass2_confidence = None

        if isinstance(dual_val_data, dict):
            if 'pass1' in dual_val_data:
                pass1_confidence = dual_val_data['pass1'] if isinstance(dual_val_data['pass1'], (int, float)) else dual_val_data['pass1'].get('confidence')
            if 'pass2' in dual_val_data:
                pass2_confidence = dual_val_data['pass2'] if isinstance(dual_val_data['pass2'], (int, float)) else dual_val_data['pass2'].get('confidence')

        cursor.execute("""
            INSERT OR REPLACE INTO classifications (
                document_id, file_name, final_category, confidence_score,
                reasoning_summary, citation_snippet, hitl_status,
                validation_consensus, dual_validation_pass1, dual_validation_pass2,
                blockchain_tx_hash, blockchain_audit_hash, audio_summary_path,
                processing_time_seconds, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        """, (
            document_id,
            classification_result.get('file_name', 'unknown'),
            classification_result['final_category'],
            classification_result['confidence_score'],
            classification_result['reasoning_summary'],
            classification_result['citation_snippet'],
            classification_result.get('hitl_status', 'PENDING'),
            classification_result.get('validation_consensus'),
            pass1_confidence,
            pass2_confidence,
            blockchain_record.get('transaction_hash') if blockchain_record else None,
            blockchain_record.get('audit_hash') if blockchain_record else None,
            audio_path,
            processing_time
        ))

        record_id = cursor.lastrowid

        # Log audit event
        self._log_event(cursor, document_id, 'CLASSIFICATION_COMPLETED', {
            'category': classification_result['final_category'],
            'confidence': classification_result['confidence_score'],
            'hitl_status': classification_result.get('hitl_status')
        })

        conn.commit()
        conn.close()

        return record_id

    def log_hitl_review(self, document_id: str, original_category: str,
                       corrected_category: str, reviewer_name: str = "SME",
                       notes: str = "") -> int:
        """
        Log a HITL review

        Args:
            document_id: Document identifier
            original_category: Original AI classification
            corrected_category: SME-corrected classification
            reviewer_name: Name of reviewer
            notes: Review notes

        Returns:
            Review ID
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO hitl_reviews (
                document_id, reviewer_name, original_category,
                corrected_category, reviewer_notes
            ) VALUES (?, ?, ?, ?, ?)
        """, (document_id, reviewer_name, original_category, corrected_category, notes))

        review_id = cursor.lastrowid

        # Update classification record
        cursor.execute("""
            UPDATE classifications
            SET hitl_status = 'REVIEWED',
                final_category = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE document_id = ?
        """, (corrected_category, document_id))

        # Log audit event
        self._log_event(cursor, document_id, 'HITL_REVIEW_COMPLETED', {
            'original': original_category,
            'corrected': corrected_category,
            'reviewer': reviewer_name
        })

        conn.commit()
        conn.close()

        return review_id

    def _log_event(self, cursor, document_id: str, event_type: str, event_data: Dict):
        """Log an audit event"""
        cursor.execute("""
            INSERT INTO audit_events (document_id, event_type, event_data)
            VALUES (?, ?, ?)
        """, (document_id, event_type, json.dumps(event_data)))

    def get_classification(self, document_id: str) -> Optional[Dict]:
        """Get classification by document ID"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM classifications WHERE document_id = ?", (document_id,))
        row = cursor.fetchone()

        conn.close()

        if row:
            return dict(row)
        return None

    def get_pending_hitl_reviews(self) -> List[Dict]:
        """Get all classifications requiring HITL review"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute("""
            SELECT * FROM classifications
            WHERE hitl_status = 'REQUIRES_REVIEW'
            ORDER BY created_at DESC
        """)

        rows = cursor.fetchall()
        conn.close()

        return [dict(row) for row in rows]

    def get_all_classifications(self, limit: int = 100, offset: int = 0) -> List[Dict]:
        """Get all classifications with pagination"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute("""
            SELECT * FROM classifications
            ORDER BY created_at DESC
            LIMIT ? OFFSET ?
        """, (limit, offset))

        rows = cursor.fetchall()
        conn.close()

        return [dict(row) for row in rows]

    def get_statistics(self) -> Dict:
        """Get classification statistics"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        stats = {}

        # Total classifications
        cursor.execute("SELECT COUNT(*) FROM classifications")
        stats['total_classifications'] = cursor.fetchone()[0]

        # By category
        cursor.execute("""
            SELECT final_category, COUNT(*) as count
            FROM classifications
            GROUP BY final_category
        """)
        stats['by_category'] = {row[0]: row[1] for row in cursor.fetchall()}

        # By HITL status
        cursor.execute("""
            SELECT hitl_status, COUNT(*) as count
            FROM classifications
            GROUP BY hitl_status
        """)
        stats['by_hitl_status'] = {row[0]: row[1] for row in cursor.fetchall()}

        # Average confidence by category
        cursor.execute("""
            SELECT final_category, AVG(confidence_score) as avg_confidence
            FROM classifications
            GROUP BY final_category
        """)
        stats['avg_confidence_by_category'] = {row[0]: round(row[1], 3) for row in cursor.fetchall()}

        # Auto-approval rate
        cursor.execute("""
            SELECT
                COUNT(CASE WHEN hitl_status = 'AUTO_APPROVED' THEN 1 END) * 100.0 / COUNT(*) as rate
            FROM classifications
        """)
        stats['auto_approval_rate'] = round(cursor.fetchone()[0] or 0, 2)

        # Average processing time
        cursor.execute("SELECT AVG(processing_time_seconds) FROM classifications")
        stats['avg_processing_time'] = round(cursor.fetchone()[0] or 0, 3)

        conn.close()
        return stats

    def export_to_json(self, output_path: Path):
        """Export all data to JSON"""
        data = {
            'classifications': self.get_all_classifications(limit=10000),
            'statistics': self.get_statistics(),
            'exported_at': datetime.now().isoformat()
        }

        with open(output_path, 'w') as f:
            json.dump(data, f, indent=2, default=str)

        print(f"Audit data exported to: {output_path}")

    def log_chat_message(self, session_id: str, role: str, message: str,
                        document_id: Optional[str] = None, context_used: Optional[str] = None) -> int:
        """
        Log a chat message

        Args:
            session_id: Chat session identifier
            role: Message role (user/assistant)
            message: Message content
            document_id: Optional document ID for context
            context_used: Optional context information used

        Returns:
            Message ID
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO chat_history (session_id, document_id, role, message, context_used)
            VALUES (?, ?, ?, ?, ?)
        """, (session_id, document_id, role, message, context_used))

        message_id = cursor.lastrowid
        conn.commit()
        conn.close()

        return message_id

    def get_chat_history(self, session_id: str, limit: int = 50) -> List[Dict]:
        """
        Get chat history for a session

        Args:
            session_id: Chat session identifier
            limit: Maximum number of messages to retrieve

        Returns:
            List of chat messages
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute("""
            SELECT * FROM chat_history
            WHERE session_id = ?
            ORDER BY created_at ASC
            LIMIT ?
        """, (session_id, limit))

        rows = cursor.fetchall()
        conn.close()

        return [dict(row) for row in rows]

    def clear_all_logs(self):
        """Clear all data from all tables in the database."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("DELETE FROM classifications")
        cursor.execute("DELETE FROM hitl_reviews")
        cursor.execute("DELETE FROM audit_events")
        cursor.execute("DELETE FROM performance_metrics")
        cursor.execute("DELETE FROM chat_history")

        conn.commit()
        conn.close()
        print("All audit logs and related data cleared.")

