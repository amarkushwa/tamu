"""
Document Legibility Checker
Pre-processing validation to ensure documents are readable and processable
"""
import pytesseract
from PIL import Image
import io
from typing import Dict, Tuple


class LegibilityChecker:
    """Validates document legibility using OCR confidence scores"""

    # Thresholds
    MIN_CONFIDENCE = 60  # Minimum average OCR confidence
    MIN_TEXT_DENSITY = 100  # Minimum characters per page
    MAX_BLANK_PAGES = 0.3  # Maximum 30% blank pages allowed

    @staticmethod
    def check_image_legibility(image: Image.Image) -> Dict:
        """
        Check if an image is legible using OCR confidence

        Args:
            image: PIL Image object

        Returns:
            Dict with legibility metrics
        """
        try:
            # Get OCR data with confidence scores
            ocr_data = pytesseract.image_to_data(image, output_type=pytesseract.Output.DICT)

            # Calculate average confidence
            confidences = [
                int(conf) for conf in ocr_data['conf']
                if conf != '-1'  # Filter out non-text elements
            ]

            if not confidences:
                return {
                    'is_legible': False,
                    'confidence_score': 0,
                    'reason': 'No text detected',
                    'char_count': 0
                }

            avg_confidence = sum(confidences) / len(confidences)
            text = pytesseract.image_to_string(image)
            char_count = len(text.strip())

            is_legible = (
                avg_confidence >= LegibilityChecker.MIN_CONFIDENCE and
                char_count >= LegibilityChecker.MIN_TEXT_DENSITY
            )

            return {
                'is_legible': is_legible,
                'confidence_score': round(avg_confidence, 2),
                'char_count': char_count,
                'reason': LegibilityChecker._get_legibility_reason(avg_confidence, char_count)
            }

        except Exception as e:
            return {
                'is_legible': False,
                'confidence_score': 0,
                'reason': f'OCR error: {str(e)}',
                'char_count': 0
            }

    @staticmethod
    def check_page_legibility(page_image_bytes: bytes, page_number: int) -> Dict:
        """
        Check legibility of a PDF page

        Args:
            page_image_bytes: Page rendered as image bytes
            page_number: Page number for reporting

        Returns:
            Legibility assessment
        """
        try:
            image = Image.open(io.BytesIO(page_image_bytes))
            result = LegibilityChecker.check_image_legibility(image)
            result['page_number'] = page_number
            return result

        except Exception as e:
            return {
                'is_legible': False,
                'confidence_score': 0,
                'page_number': page_number,
                'reason': f'Page processing error: {str(e)}',
                'char_count': 0
            }

    @staticmethod
    def check_document_legibility(page_results: list) -> Dict:
        """
        Aggregate legibility check for entire document

        Args:
            page_results: List of per-page legibility results

        Returns:
            Overall document legibility assessment
        """
        if not page_results:
            return {
                'is_legible': False,
                'overall_confidence': 0,
                'legible_pages': 0,
                'total_pages': 0,
                'blank_pages': 0,
                'issues': ['No pages to analyze']
            }

        total_pages = len(page_results)
        legible_pages = sum(1 for p in page_results if p['is_legible'])
        blank_pages = sum(1 for p in page_results if p['char_count'] < LegibilityChecker.MIN_TEXT_DENSITY)

        # Calculate overall confidence (only from non-blank pages)
        non_blank_confidences = [
            p['confidence_score'] for p in page_results
            if p['char_count'] >= LegibilityChecker.MIN_TEXT_DENSITY
        ]

        overall_confidence = (
            sum(non_blank_confidences) / len(non_blank_confidences)
            if non_blank_confidences else 0
        )

        # Determine if document is legible
        blank_page_ratio = blank_pages / total_pages
        is_legible = (
            overall_confidence >= LegibilityChecker.MIN_CONFIDENCE and
            blank_page_ratio <= LegibilityChecker.MAX_BLANK_PAGES and
            legible_pages > 0
        )

        # Collect issues
        issues = []
        if overall_confidence < LegibilityChecker.MIN_CONFIDENCE:
            issues.append(f'Low OCR confidence: {overall_confidence:.1f}% (min: {LegibilityChecker.MIN_CONFIDENCE}%)')

        if blank_page_ratio > LegibilityChecker.MAX_BLANK_PAGES:
            issues.append(f'Too many blank pages: {blank_pages}/{total_pages} ({blank_page_ratio:.1%})')

        if legible_pages == 0:
            issues.append('No legible pages detected')

        # Find problematic pages
        problem_pages = [
            p['page_number'] for p in page_results
            if not p['is_legible'] and p['char_count'] >= LegibilityChecker.MIN_TEXT_DENSITY
        ]

        if problem_pages:
            issues.append(f'Illegible pages: {problem_pages}')

        return {
            'is_legible': is_legible,
            'overall_confidence': round(overall_confidence, 2),
            'legible_pages': legible_pages,
            'total_pages': total_pages,
            'blank_pages': blank_pages,
            'blank_page_ratio': round(blank_page_ratio, 2),
            'issues': issues if not is_legible else [],
            'recommendation': LegibilityChecker._get_recommendation(is_legible, issues)
        }

    @staticmethod
    def _get_legibility_reason(confidence: float, char_count: int) -> str:
        """Get human-readable reason for legibility assessment"""
        if confidence < LegibilityChecker.MIN_CONFIDENCE and char_count < LegibilityChecker.MIN_TEXT_DENSITY:
            return f'Low confidence ({confidence:.1f}%) and insufficient text ({char_count} chars)'
        elif confidence < LegibilityChecker.MIN_CONFIDENCE:
            return f'Low OCR confidence: {confidence:.1f}% (min: {LegibilityChecker.MIN_CONFIDENCE}%)'
        elif char_count < LegibilityChecker.MIN_TEXT_DENSITY:
            return f'Insufficient text: {char_count} characters (min: {LegibilityChecker.MIN_TEXT_DENSITY})'
        else:
            return f'Legible (confidence: {confidence:.1f}%, {char_count} characters)'

    @staticmethod
    def _get_recommendation(is_legible: bool, issues: list) -> str:
        """Get recommendation based on legibility assessment"""
        if is_legible:
            return 'Document is legible and ready for classification'

        if not issues:
            return 'Document may have quality issues - manual review recommended'

        recommendations = []

        for issue in issues:
            if 'Low OCR confidence' in issue:
                recommendations.append('Try rescanning at higher resolution or improving image quality')
            elif 'blank pages' in issue:
                recommendations.append('Remove blank pages or verify document completeness')
            elif 'Illegible pages' in issue:
                recommendations.append('Check specific pages for scan quality issues')

        return '; '.join(recommendations) if recommendations else 'Manual review required'
