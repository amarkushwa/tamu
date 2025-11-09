"""
Classification Accuracy Tracker
Implements precision/recall metrics and performance monitoring
"""
import json
import time
from typing import Dict, List, Optional
from pathlib import Path
from collections import defaultdict

from ..config import Config


class AccuracyTracker:
    """
    Tracks classification accuracy metrics including:
    - Precision per category
    - Recall per category
    - F1 scores
    - Confusion matrix
    - Confidence calibration
    """

    def __init__(self):
        """Initialize accuracy tracker"""
        self.metrics_file = Config.BASE_DIR / "data" / "accuracy_metrics.json"
        self.metrics_file.parent.mkdir(parents=True, exist_ok=True)
        self.metrics = self._load_metrics()

    def _load_metrics(self) -> Dict:
        """Load existing metrics"""
        if self.metrics_file.exists():
            with open(self.metrics_file, 'r') as f:
                return json.load(f)
        return {
            'total_predictions': 0,
            'total_ground_truth': 0,
            'confusion_matrix': defaultdict(lambda: defaultdict(int)),
            'confidence_bins': defaultdict(list),
            'category_stats': defaultdict(lambda: {
                'true_positives': 0,
                'false_positives': 0,
                'false_negatives': 0,
                'precision': 0.0,
                'recall': 0.0,
                'f1_score': 0.0
            }),
            'hitl_corrections': []
        }

    def _save_metrics(self):
        """Save metrics to file"""
        # Convert defaultdicts to regular dicts for JSON serialization
        serializable = {
            'total_predictions': self.metrics['total_predictions'],
            'total_ground_truth': self.metrics['total_ground_truth'],
            'confusion_matrix': {k: dict(v) for k, v in self.metrics['confusion_matrix'].items()},
            'confidence_bins': {k: list(v) for k, v in self.metrics['confidence_bins'].items()},
            'category_stats': dict(self.metrics['category_stats']),
            'hitl_corrections': self.metrics['hitl_corrections']
        }

        with open(self.metrics_file, 'w') as f:
            json.dump(serializable, f, indent=2)

    def record_prediction(self, predicted: str, ground_truth: Optional[str],
                         confidence: float, document_id: str):
        """
        Record a prediction for accuracy tracking

        Args:
            predicted: Predicted category
            ground_truth: Actual category (from HITL or test set)
            confidence: Confidence score (0-1)
            document_id: Document identifier
        """
        self.metrics['total_predictions'] += 1

        # Record confidence bin
        confidence_bin = int(confidence * 10) / 10  # Round to nearest 0.1
        self.metrics['confidence_bins'][str(confidence_bin)].append({
            'predicted': predicted,
            'ground_truth': ground_truth,
            'correct': predicted == ground_truth if ground_truth else None,
            'document_id': document_id
        })

        if ground_truth:
            self.metrics['total_ground_truth'] += 1

            # Update confusion matrix
            self.metrics['confusion_matrix'][ground_truth][predicted] += 1

            # Update per-category stats
            for category in Config.CATEGORIES:
                if predicted == category and ground_truth == category:
                    # True Positive
                    self.metrics['category_stats'][category]['true_positives'] += 1
                elif predicted == category and ground_truth != category:
                    # False Positive
                    self.metrics['category_stats'][category]['false_positives'] += 1
                elif predicted != category and ground_truth == category:
                    # False Negative
                    self.metrics['category_stats'][category]['false_negatives'] += 1

            # Recalculate metrics
            self._recalculate_metrics()

        self._save_metrics()

    def record_hitl_correction(self, document_id: str, original: str,
                               corrected: str, confidence: float):
        """
        Record HITL correction for learning

        Args:
            document_id: Document identifier
            original: Original AI prediction
            corrected: SME-corrected category
            confidence: Original confidence score
        """
        self.metrics['hitl_corrections'].append({
            'document_id': document_id,
            'original': original,
            'corrected': corrected,
            'confidence': confidence,
            'timestamp': time.time()
        })

        # Treat correction as ground truth
        self.record_prediction(original, corrected, confidence, document_id)

    def _recalculate_metrics(self):
        """Recalculate precision, recall, and F1 for all categories"""
        for category in Config.CATEGORIES:
            stats = self.metrics['category_stats'][category]
            tp = stats['true_positives']
            fp = stats['false_positives']
            fn = stats['false_negatives']

            # Precision = TP / (TP + FP)
            if tp + fp > 0:
                precision = tp / (tp + fp)
            else:
                precision = 0.0

            # Recall = TP / (TP + FN)
            if tp + fn > 0:
                recall = tp / (tp + fn)
            else:
                recall = 0.0

            # F1 Score = 2 * (Precision * Recall) / (Precision + Recall)
            if precision + recall > 0:
                f1 = 2 * (precision * recall) / (precision + recall)
            else:
                f1 = 0.0

            stats['precision'] = round(precision, 4)
            stats['recall'] = round(recall, 4)
            stats['f1_score'] = round(f1, 4)

    def get_overall_accuracy(self) -> float:
        """
        Get overall classification accuracy

        Returns:
            Accuracy percentage (0-100)
        """
        if self.metrics['total_ground_truth'] == 0:
            return 0.0

        correct = sum(
            stats['true_positives']
            for stats in self.metrics['category_stats'].values()
        )

        return round((correct / self.metrics['total_ground_truth']) * 100, 2)

    def get_macro_f1(self) -> float:
        """
        Get macro-averaged F1 score across all categories

        Returns:
            Macro F1 score
        """
        f1_scores = [
            stats['f1_score']
            for stats in self.metrics['category_stats'].values()
            if stats['f1_score'] > 0
        ]

        if not f1_scores:
            return 0.0

        return round(sum(f1_scores) / len(f1_scores), 4)

    def get_confidence_calibration(self) -> Dict:
        """
        Get confidence calibration metrics
        Shows how well confidence scores match actual accuracy

        Returns:
            Dict mapping confidence bins to actual accuracy
        """
        calibration = {}

        for bin_str, predictions in self.metrics['confidence_bins'].items():
            correct = sum(1 for p in predictions if p['correct'] is True)
            total = len(predictions)

            if total > 0:
                actual_accuracy = correct / total
                expected_confidence = float(bin_str)
                calibration[bin_str] = {
                    'expected': expected_confidence,
                    'actual': round(actual_accuracy, 4),
                    'samples': total,
                    'calibration_error': round(abs(expected_confidence - actual_accuracy), 4)
                }

        return calibration

    def get_detailed_report(self) -> Dict:
        """
        Get comprehensive accuracy report

        Returns:
            Dict with all metrics
        """
        return {
            'overall_accuracy': self.get_overall_accuracy(),
            'macro_f1_score': self.get_macro_f1(),
            'total_predictions': self.metrics['total_predictions'],
            'total_with_ground_truth': self.metrics['total_ground_truth'],
            'category_metrics': dict(self.metrics['category_stats']),
            'confusion_matrix': {k: dict(v) for k, v in self.metrics['confusion_matrix'].items()},
            'confidence_calibration': self.get_confidence_calibration(),
            'hitl_correction_rate': self._get_hitl_correction_rate()
        }

    def _get_hitl_correction_rate(self) -> float:
        """Get percentage of predictions that required HITL correction"""
        if self.metrics['total_predictions'] == 0:
            return 0.0

        corrections = len(self.metrics['hitl_corrections'])
        return round((corrections / self.metrics['total_predictions']) * 100, 2)

    def export_report(self, output_path: Path):
        """
        Export detailed accuracy report

        Args:
            output_path: Path to save report
        """
        report = self.get_detailed_report()

        with open(output_path, 'w') as f:
            json.dump(report, f, indent=2)

        print(f"Accuracy report exported to: {output_path}")
