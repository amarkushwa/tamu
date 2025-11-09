"""
Batch Processing Module
Handles multiple document classification with real-time status updates
"""
import time
import uuid
from pathlib import Path
from typing import Dict, List
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock

from .document_processor import DocumentProcessor
from ..config import Config


class BatchJob:
    """Represents a batch processing job"""

    def __init__(self, job_id: str, files: List[Path]):
        self.job_id = job_id
        self.files = files
        self.total_files = len(files)
        self.processed_files = 0
        self.failed_files = 0
        self.results = []
        self.status = "QUEUED"  # QUEUED, PROCESSING, COMPLETED, FAILED
        self.started_at = None
        self.completed_at = None
        self.current_file = None
        self.lock = Lock()

    def to_dict(self) -> Dict:
        """Convert to dictionary for API responses"""
        return {
            'job_id': self.job_id,
            'total_files': self.total_files,
            'processed_files': self.processed_files,
            'failed_files': self.failed_files,
            'status': self.status,
            'progress_percent': (self.processed_files / self.total_files * 100) if self.total_files > 0 else 0,
            'current_file': self.current_file,
            'started_at': self.started_at,
            'completed_at': self.completed_at,
            'results': self.results
        }


class BatchProcessor:
    """
    Batch document processor with real-time status updates
    """

    def __init__(self, classifier, max_workers: int = 3):
        """
        Initialize batch processor

        Args:
            classifier: EnhancedGeminiClassifier instance
            max_workers: Maximum parallel workers
        """
        self.classifier = classifier
        self.max_workers = max_workers
        self.jobs = {}  # job_id -> BatchJob
        self.lock = Lock()

    def create_batch_job(self, files: List[Path]) -> str:
        """
        Create a new batch processing job

        Args:
            files: List of file paths to process

        Returns:
            Job ID for tracking
        """
        job_id = str(uuid.uuid4())
        job = BatchJob(job_id, files)

        with self.lock:
            self.jobs[job_id] = job

        return job_id

    def get_job_status(self, job_id: str) -> Dict:
        """
        Get current status of a batch job

        Args:
            job_id: Job identifier

        Returns:
            Job status dict
        """
        with self.lock:
            if job_id not in self.jobs:
                return {'error': 'Job not found', 'job_id': job_id}

            return self.jobs[job_id].to_dict()

    def process_batch(self, job_id: str) -> Dict:
        """
        Process batch job

        Args:
            job_id: Job identifier

        Returns:
            Final job results
        """
        with self.lock:
            if job_id not in self.jobs:
                return {'error': 'Job not found'}

            job = self.jobs[job_id]

        job.status = "PROCESSING"
        job.started_at = time.time()

        try:
            # Process files in parallel
            with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                future_to_file = {
                    executor.submit(self._process_single_file, file_path, job): file_path
                    for file_path in job.files
                }

                for future in as_completed(future_to_file):
                    file_path = future_to_file[future]
                    try:
                        result = future.result()

                        with job.lock:
                            job.results.append(result)
                            job.processed_files += 1
                            if result.get('error'):
                                job.failed_files += 1

                    except Exception as e:
                        with job.lock:
                            job.results.append({
                                'file': str(file_path),
                                'error': str(e),
                                'status': 'FAILED'
                            })
                            job.failed_files += 1
                            job.processed_files += 1

            job.status = "COMPLETED"
            job.completed_at = time.time()

        except Exception as e:
            job.status = "FAILED"
            job.completed_at = time.time()
            return {'error': str(e), 'job_id': job_id}

        return job.to_dict()

    def _process_single_file(self, file_path: Path, job: BatchJob) -> Dict:
        """
        Process a single file

        Args:
            file_path: Path to file
            job: Parent batch job

        Returns:
            Classification result
        """
        try:
            # Update current file
            with job.lock:
                job.current_file = file_path.name

            # Process document
            processor = DocumentProcessor(file_path)
            document_data = processor.process()
            document_data['file_name'] = file_path.name

            # Classify
            start_time = time.time()
            classification_result = self.classifier.classify(document_data)
            processing_time = time.time() - start_time

            return {
                'file': str(file_path),
                'document_id': classification_result['document_id'],
                'classification': classification_result['final_category'],
                'confidence': classification_result['confidence_score'],
                'hitl_status': classification_result.get('hitl_status'),
                'processing_time': processing_time,
                'status': 'SUCCESS'
            }

        except Exception as e:
            return {
                'file': str(file_path),
                'error': str(e),
                'status': 'FAILED'
            }

    def get_all_jobs(self) -> List[Dict]:
        """Get status of all batch jobs"""
        with self.lock:
            return [job.to_dict() for job in self.jobs.values()]

    def cancel_job(self, job_id: str) -> bool:
        """
        Cancel a running batch job

        Args:
            job_id: Job identifier

        Returns:
            True if cancelled successfully
        """
        with self.lock:
            if job_id not in self.jobs:
                return False

            job = self.jobs[job_id]
            if job.status == "PROCESSING":
                job.status = "CANCELLED"
                return True

        return False
