import os
from typing import List, Dict, Optional
from dotenv import load_dotenv

load_dotenv()

_pinecone_client = None
_pinecone_index = None


def _get_openai_embedding(text: str, model: str = "text-embedding-3-small") -> List[float]:
    """Generate OpenAI embedding for a text string.
    """
    from openai import OpenAI
    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    
    response = client.embeddings.create(
        input=text,
        model=model
    )
    return response.data[0].embedding


def initialize_pinecone(index_name: str = "geotab-coach") -> object:
    """Initialize Pinecone client and return index.
    """
    global _pinecone_client, _pinecone_index
    
    if _pinecone_index is not None:
        return _pinecone_index
    
    try:
        from pinecone import Pinecone, ServerlessSpec
    except ImportError:
        raise ImportError("Pinecone SDK not installed. Install with: pip install pinecone")
    
    api_key = os.getenv("PINECONE_API_KEY")
    if not api_key:
        raise ValueError("PINECONE_API_KEY not found in environment variables")
    
    # Initialize Pinecone client
    _pinecone_client = Pinecone(api_key=api_key)
    
    # Check if index exists, create if not
    existing_indexes = [idx.name for idx in _pinecone_client.list_indexes()]
    
    if index_name not in existing_indexes:
        # Create index with 1536 dimensions (text-embedding-3-small dimension)
        _pinecone_client.create_index(
            name=index_name,
            dimension=1536,
            metric="cosine",
            spec=ServerlessSpec(
                cloud="aws",
                region="us-east-1"
            )
        )
    
    _pinecone_index = _pinecone_client.Index(index_name)
    return _pinecone_index


def upsert_chunks(chunks: List[Dict[str, str]], namespace: str = "company-docs") -> Dict:
    """Embed and upsert text chunks to Pinecone.
    """
    index = initialize_pinecone()
    
    vectors = []
    for i, chunk in enumerate(chunks):
        text = chunk.get("text", "")
        if not text.strip():
            continue
        
        # Generate embedding
        embedding = _get_openai_embedding(text)
        
        # Create vector ID
        vector_id = f"chunk_{i}_{hash(text) % 1000000}"
        
        # Prepare metadata
        metadata = chunk.get("metadata", {})
        metadata["text"] = text  # Store original text in metadata for retrieval
        
        vectors.append({
            "id": vector_id,
            "values": embedding,
            "metadata": metadata
        })
    
    if not vectors:
        return {"upserted_count": 0}
    
    # Upsert to Pinecone
    result = index.upsert(vectors=vectors, namespace=namespace)
    
    return {
        "upserted_count": result.upserted_count if hasattr(result, 'upserted_count') else len(vectors),
        "total_chunks": len(chunks)
    }


def query_relevant_chunks(query_text: str, top_k: int = 3, namespace: str = "company-docs") -> List[Dict[str, any]]:
    """Query Pinecone for relevant document chunks.
    """
    try:
        index = initialize_pinecone()
    except Exception as e:
        # If Pinecone is not configured, return empty list
        print(f"Pinecone query failed: {e}")
        return []
    
    # Generate query embedding
    try:
        query_embedding = _get_openai_embedding(query_text)
    except Exception as e:
        print(f"Embedding generation failed: {e}")
        return []
    
    # Query Pinecone
    try:
        results = index.query(
            vector=query_embedding,
            top_k=top_k,
            namespace=namespace,
            include_metadata=True
        )
    except Exception as e:
        print(f"Pinecone query failed: {e}")
        return []
    
    # Extract text and metadata from results
    chunks = []
    if hasattr(results, 'matches'):
        for match in results.matches:
            if hasattr(match, 'metadata') and 'text' in match.metadata:
                metadata = match.metadata
                chunks.append({
                    "text": metadata.get('text', ''),
                    "page_num": metadata.get('page_num'),
                    "source_file": metadata.get('source_file')
                })
    
    return chunks


def delete_namespace(namespace: str = "company-docs") -> bool:
    """Delete all vectors in a namespace (for testing/cleanup).
    """
    try:
        index = initialize_pinecone()
        index.delete(delete_all=True, namespace=namespace)
        return True
    except Exception as e:
        print(f"Delete failed: {e}")
        return False
