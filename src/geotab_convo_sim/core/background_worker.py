import threading
from typing import Dict, Callable, Optional
from .pdf_utils import process_pdf
from .pinecone_utils import upsert_chunks, delete_namespace

# Global job storage
_jobs: Dict[str, Dict] = {}
_job_lock = threading.Lock()


def get_job_status(job_id: str) -> Optional[Dict]:
    with _job_lock:
        return _jobs.get(job_id)


def _process_pdf_job(job_id: str, pdf_path: str, chunk_size: int, overlap: int, namespace: str):
    """Internal function that runs in background thread."""
    try:
        with _job_lock:
            _jobs[job_id]["status"] = "processing"
            _jobs[job_id]["progress"] = "Clearing old documents..."
        
        # Step 0: Clear existing documents in the namespace
        try:
            delete_namespace(namespace)
        except Exception as e:
            print(f"Warning: Failed to clear namespace: {e}")
        
        with _job_lock:
            _jobs[job_id]["progress"] = "Extracting text from PDF..."
        
        # Step 1: Process PDF into chunks
        chunks = process_pdf(pdf_path, chunk_size=chunk_size, overlap=overlap)
        
        if not chunks:
            with _job_lock:
                _jobs[job_id]["status"] = "failed"
                _jobs[job_id]["error"] = "No text extracted from PDF"
            return
        
        with _job_lock:
            _jobs[job_id]["progress"] = f"Extracted {len(chunks)} chunks. Embedding and uploading..."
        
        # Step 2: Embed and upsert to Pinecone (one chunk at a time to track progress)
        total = len(chunks)
        uploaded = 0
        
        for i, chunk in enumerate(chunks):
            try:
                # Upsert single chunk
                result = upsert_chunks([chunk], namespace=namespace)
                uploaded += 1
                
                # Update progress
                with _job_lock:
                    _jobs[job_id]["progress"] = f"Uploaded {uploaded}/{total} chunks..."
            except Exception as e:
                print(f"Failed to upload chunk {i}: {e}")
                continue
        
        # Step 3: Mark as complete
        with _job_lock:
            _jobs[job_id]["status"] = "completed"
            _jobs[job_id]["progress"] = f"✓ Document ready! Uploaded {uploaded}/{total} chunks. Old documents have been replaced."
            _jobs[job_id]["chunks_uploaded"] = uploaded
            _jobs[job_id]["chunks_total"] = total
    
    except Exception as e:
        with _job_lock:
            _jobs[job_id]["status"] = "failed"
            _jobs[job_id]["error"] = str(e)


def start_pdf_processing(job_id: str, pdf_path: str, chunk_size: int = 500, overlap: int = 50, namespace: str = "company-docs") -> Dict:
    """Start a background job to process a PDF file.
    """
    with _job_lock:
        if job_id in _jobs:
            return _jobs[job_id]
        
        _jobs[job_id] = {
            "job_id": job_id,
            "status": "queued",
            "progress": "Job queued...",
            "pdf_path": pdf_path,
            "chunks_uploaded": 0,
            "chunks_total": 0
        }
    
    # Start background thread
    thread = threading.Thread(
        target=_process_pdf_job,
        args=(job_id, pdf_path, chunk_size, overlap, namespace),
        daemon=True
    )
    thread.start()
    
    return _jobs[job_id]


def clear_job(job_id: str):
    """Remove a job from tracking (cleanup).
    """
    with _job_lock:
        if job_id in _jobs:
            del _jobs[job_id]


def get_all_jobs() -> Dict[str, Dict]:
    """Get all tracked jobs.
    """
    with _job_lock:
        return dict(_jobs)
