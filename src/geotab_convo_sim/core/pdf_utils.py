import re
from typing import List, Dict

def extract_text_from_pdf(pdf_path: str) -> List[Dict[str, any]]:
    """Extract text from a PDF file with page numbers.
    
    Tries pdfplumber first, falls back to PyPDF2 if needed.
    
    Returns:
        List of dicts with 'page_num' (1-indexed) and 'text' keys
    """
    try:
        import pdfplumber
        with pdfplumber.open(pdf_path) as pdf:
            pages = []
            for i, page in enumerate(pdf.pages, start=1):
                page_text = page.extract_text()
                if page_text:
                    pages.append({"page_num": i, "text": page_text})
            return pages
    except ImportError:
        # Fallback to PyPDF2
        try:
            import PyPDF2
            with open(pdf_path, "rb") as f:
                reader = PyPDF2.PdfReader(f)
                pages = []
                for i, page in enumerate(reader.pages, start=1):
                    page_text = page.extract_text()
                    if page_text:
                        pages.append({"page_num": i, "text": page_text})
                return pages
        except ImportError:
            raise ImportError("Neither pdfplumber nor PyPDF2 is installed.")


def chunk_pages(pages: List[Dict[str, any]], chunk_size: int = 500, overlap: int = 50) -> List[Dict[str, str]]:
    """Split pages into overlapping chunks by word count, preserving page numbers.
    
    Args:
        pages: List of dicts with 'page_num' and 'text' keys
        chunk_size: Target number of words per chunk
        overlap: Number of words to overlap between chunks
        
    Returns:
        List of dicts with 'text' and 'metadata' (including page_num) keys
    """
    if not pages:
        return []
    
    chunks = []
    chunk_index = 0
    
    for page_info in pages:
        page_num = page_info["page_num"]
        text = page_info["text"]
        
        if not text or not text.strip():
            continue
        
        # Normalize whitespace
        text = re.sub(r"\s+", " ", text.strip())
        words = text.split()
        
        if len(words) <= chunk_size:
            chunks.append({
                "text": text,
                "metadata": {
                    "chunk_index": chunk_index,
                    "page_num": page_num,
                    "total_words": len(words)
                }
            })
            chunk_index += 1
        else:
            # Split page into multiple chunks
            start = 0
            while start < len(words):
                end = start + chunk_size
                chunk_words = words[start:end]
                chunk_text = " ".join(chunk_words)
                
                chunks.append({
                    "text": chunk_text,
                    "metadata": {
                        "chunk_index": chunk_index,
                        "page_num": page_num,
                        "total_words": len(chunk_words),
                        "start_word": start,
                        "end_word": end
                    }
                })
                
                chunk_index += 1
                start += chunk_size - overlap
    
    return chunks


def process_pdf(pdf_path: str, chunk_size: int = 500, overlap: int = 50) -> List[Dict[str, str]]:
    """Extract text from PDF and split into chunks with page tracking.
    
    Args:
        pdf_path: Path to the PDF file
        chunk_size: Target number of words per chunk
        overlap: Number of words to overlap between chunks
        
    Returns:
        List of text chunks with metadata (including page numbers)
    """
    import os
    
    pages = extract_text_from_pdf(pdf_path)
    if not pages:
        return []
    
    chunks = chunk_pages(pages, chunk_size=chunk_size, overlap=overlap)
    
    # Add source filename to metadata
    filename = os.path.basename(pdf_path)
    for chunk in chunks:
        chunk["metadata"]["source_file"] = filename
    
    return chunks
