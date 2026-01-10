"""PDF heatmap annotation service for highlighting clauses in PDF documents."""
import os
import logging
from dataclasses import dataclass
from typing import List

logger = logging.getLogger(__name__)

try:
    import fitz  # PyMuPDF
    PYMUPDF_AVAILABLE = True
except ImportError:
    PYMUPDF_AVAILABLE = False
    logger.warning("PyMuPDF not available - PDF annotation disabled")


@dataclass
class ClauseHit:
    """Represents a clause found in a document."""
    clause_type: str
    excerpt: str


def annotate_pdf_with_clauses(pdf_path: str, hits: List[ClauseHit], out_dir: str = "uploads") -> str:
    """
    Annotate a PDF with highlighted clause excerpts.
    
    Args:
        pdf_path: Path to the source PDF
        hits: List of ClauseHit objects with clause types and excerpts
        out_dir: Directory to save annotated PDF
        
    Returns:
        Path to the annotated PDF
    """
    if not PYMUPDF_AVAILABLE:
        logger.error("PyMuPDF not installed - cannot annotate PDF")
        return pdf_path
    
    os.makedirs(out_dir, exist_ok=True)
    
    try:
        doc = fitz.open(pdf_path)
        
        highlight_colors = {
            "Governing Law": (1, 1, 0.6),      # Yellow
            "Venue / Forum": (0.6, 1, 0.6),    # Green
            "Personal Guarantee": (1, 0.6, 0.6),  # Red
            "Arbitration": (0.6, 0.8, 1),      # Blue
            "Limitation of Liability": (1, 0.8, 0.6),  # Orange
            "Indemnification": (0.8, 0.6, 1),  # Purple
            "Termination": (0.6, 1, 1),        # Cyan
            "Negotiable Indicators": (1, 0.6, 0.8),  # Pink
        }
        
        for hit in hits:
            if not hit.excerpt:
                continue
                
            search_text = hit.excerpt[:100] if len(hit.excerpt) > 100 else hit.excerpt
            color = highlight_colors.get(hit.clause_type, (1, 1, 0.6))
            
            for page in doc:
                text_instances = page.search_for(search_text)
                for inst in text_instances:
                    highlight = page.add_highlight_annot(inst)
                    highlight.set_colors(stroke=color)
                    highlight.update()
        
        base_name = os.path.basename(pdf_path)
        out_path = os.path.join(out_dir, f"annotated_{base_name}")
        doc.save(out_path)
        doc.close()
        
        logger.info(f"Annotated PDF saved to {out_path}")
        return out_path
        
    except Exception as e:
        logger.error(f"Error annotating PDF: {e}")
        return pdf_path
