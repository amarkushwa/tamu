"""
Document Processing Module
Handles PDF parsing, OCR, image extraction, and citation mapping
"""
import io
import base64
import hashlib
import time
from pathlib import Path
from typing import Dict, List, Tuple, Optional
import PyPDF2
import fitz  # PyMuPDF
from PIL import Image
import pytesseract

class DocumentProcessor:
    """Multi-modal document processor with OCR and citation mapping"""

    def __init__(self, document_path: str):
        """
        Initialize document processor

        Args:
            document_path: Path to the PDF document
        """
        self.document_path = Path(document_path)
        self.document_id = self._generate_document_id()
        self.metadata = {}
        self.pages = []
        self.images = []
        self.full_text = ""

    def _generate_document_id(self) -> str:
        """Generate unique document ID based on file hash and timestamp"""
        with open(self.document_path, 'rb') as f:
            file_hash = hashlib.sha256(f.read()).hexdigest()
        timestamp = int(time.time() * 1000) # Milliseconds
        return f"DOC_{file_hash[:12]}_{timestamp}"

    def process(self) -> Dict:
        """
        Main processing pipeline

        Returns:
            Dict containing processed document data
        """
        # Step 1: Extract metadata
        self.metadata = self._extract_metadata()

        # Step 2: Pre-processing checks
        num_pages = self.metadata.get('num_pages', 0)
        print(f"Processing document: {self.document_path.name}")
        print(f"Pages: {num_pages}, Document ID: {self.document_id}")

        # Step 3: Extract text and images with citation mapping
        self._extract_content_with_citations()

        # Step 4: Prepare for caching
        cached_content = self._prepare_cached_content()

        return {
            'document_id': self.document_id,
            'metadata': self.metadata,
            'pages': self.pages,
            'images': self.images,
            'full_text': self.full_text,
            'cached_content': cached_content
        }

    def _extract_metadata(self) -> Dict:
        """Extract document metadata using PyMuPDF"""
        doc = fitz.open(self.document_path)

        metadata = {
            'num_pages': len(doc),
            'num_images': 0,
            'file_size': self.document_path.stat().st_size,
            'file_name': self.document_path.name,
            'title': doc.metadata.get('title', ''),
            'author': doc.metadata.get('author', ''),
            'creation_date': doc.metadata.get('creationDate', '')
        }

        # Count images
        for page_num in range(len(doc)):
            page = doc[page_num]
            image_list = page.get_images()
            metadata['num_images'] += len(image_list)

        doc.close()
        return metadata

    def _extract_content_with_citations(self):
        """Extract text and images with precise citation information"""
        doc = fitz.open(self.document_path)

        full_text_parts = []

        for page_num in range(len(doc)):
            page = doc[page_num]
            page_data = {
                'page_number': page_num + 1,
                'text_blocks': [],
                'images': []
            }

            # Extract text blocks with bounding boxes for citation mapping
            text_blocks = page.get_text("dict")["blocks"]

            page_text_parts = []
            for block_idx, block in enumerate(text_blocks):
                if block['type'] == 0:  # Text block
                    block_text = ""
                    lines = []

                    for line in block.get("lines", []):
                        line_text = ""
                        for span in line.get("spans", []):
                            line_text += span.get("text", "")
                        lines.append(line_text)
                        block_text += line_text + " "

                    if block_text.strip():
                        # Store with citation information
                        bbox = block['bbox']  # (x0, y0, x1, y1)
                        citation_info = {
                            'page': page_num + 1,
                            'block_index': block_idx,
                            'bbox': {
                                'x0': round(bbox[0], 2),
                                'y0': round(bbox[1], 2),
                                'x1': round(bbox[2], 2),
                                'y1': round(bbox[3], 2)
                            },
                            'text': block_text.strip(),
                            'lines': lines
                        }

                        page_data['text_blocks'].append(citation_info)
                        page_text_parts.append(block_text.strip())

            # Extract images with OCR
            image_list = page.get_images()
            for img_idx, img in enumerate(image_list):
                try:
                    xref = img[0]
                    base_image = doc.extract_image(xref)
                    image_bytes = base_image["image"]

                    # Convert to PIL Image
                    image = Image.open(io.BytesIO(image_bytes))

                    # OCR the image
                    ocr_text = pytesseract.image_to_string(image)

                    # Convert to base64 for Gemini
                    buffered = io.BytesIO()
                    image.save(buffered, format=base_image["ext"].upper())
                    img_base64 = base64.b64encode(buffered.getvalue()).decode()

                    image_data = {
                        'page': page_num + 1,
                        'image_index': img_idx,
                        'format': base_image["ext"],
                        'base64': img_base64,
                        'ocr_text': ocr_text.strip(),
                        'width': base_image.get("width", 0),
                        'height': base_image.get("height", 0)
                    }

                    page_data['images'].append(image_data)
                    self.images.append(image_data)

                    # Add OCR text to page text
                    if ocr_text.strip():
                        page_text_parts.append(f"[IMAGE OCR]: {ocr_text.strip()}")

                except Exception as e:
                    print(f"Error processing image {img_idx} on page {page_num + 1}: {e}")

            # Combine page text
            page_text = "\n".join(page_text_parts)
            page_data['full_text'] = page_text

            self.pages.append(page_data)
            full_text_parts.append(f"--- Page {page_num + 1} ---\n{page_text}")

        self.full_text = "\n\n".join(full_text_parts)
        doc.close()

    def _prepare_cached_content(self) -> str:
        """
        Prepare document content for Gemini caching

        Returns:
            Formatted content string for caching
        """
        cached_parts = [
            f"DOCUMENT ID: {self.document_id}",
            f"FILE NAME: {self.metadata['file_name']}",
            f"TOTAL PAGES: {self.metadata['num_pages']}",
            f"TOTAL IMAGES: {self.metadata['num_images']}",
            "",
            "=" * 80,
            "FULL DOCUMENT CONTENT WITH CITATION MAPPING",
            "=" * 80,
            ""
        ]

        # Add page-by-page content with citation markers
        for page_data in self.pages:
            cached_parts.append(f"\n{'='*80}")
            cached_parts.append(f"PAGE {page_data['page_number']}")
            cached_parts.append(f"{'='*80}\n")

            # Add text blocks with citation tags
            for block in page_data['text_blocks']:
                bbox = block['bbox']
                citation_tag = f"[CITATION: Page {block['page']}, Block {block['block_index']}, BBox: ({bbox['x0']},{bbox['y0']})-({bbox['x1']},{bbox['y1']})]"
                cached_parts.append(f"{citation_tag}")
                cached_parts.append(block['text'])
                cached_parts.append("")

            # Add image OCR content
            for img in page_data['images']:
                if img['ocr_text']:
                    cached_parts.append(f"[IMAGE {img['image_index']} OCR on Page {img['page']}]")
                    cached_parts.append(img['ocr_text'])
                    cached_parts.append("")

        return "\n".join(cached_parts)

    def get_citation_for_text(self, text_snippet: str) -> Optional[str]:
        """
        Find citation information for a text snippet

        Args:
            text_snippet: The text to find citation for

        Returns:
            Citation string or None
        """
        for page_data in self.pages:
            for block in page_data['text_blocks']:
                if text_snippet.lower() in block['text'].lower():
                    bbox = block['bbox']
                    return (f"Page {block['page']}, Block {block['block_index']}, "
                           f"Location: ({bbox['x0']:.1f}, {bbox['y0']:.1f})-({bbox['x1']:.1f}, {bbox['y1']:.1f})")
        return None

    def export_images_for_gemini(self) -> List[Dict]:
        """
        Export images in format suitable for Gemini Vision API

        Returns:
            List of image data dicts
        """
        return [{
            'mime_type': f'image/{img["format"]}',
            'data': img['base64']
        } for img in self.images]
