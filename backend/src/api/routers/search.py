"""
Search API Router
Handles semantic search, RAG (ask/chat), and similarity calculations.
"""
import os
import numpy as np
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import text
from pydantic import BaseModel

from src.db.session import get_db
from src.db.models import Entry, RawFile
from src.llm_client import embed_text, generate_text, MODEL
from src.rag.search import search_entries_semantic, search_two_stage

router = APIRouter(tags=["search"])


# ============================================================================
# Pydantic Models
# ============================================================================

class AskRequest(BaseModel):
    query: str
    k: int = 5
    model: Optional[str] = None
    filters: Optional[dict] = None
    search_mode: Optional[str] = 'hybrid'
    vector_weight: Optional[float] = 0.7


class AskResponse(BaseModel):
    answer: str
    sources: list


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    messages: list[ChatMessage]
    model: Optional[str] = None


class ChatResponse(BaseModel):
    response: str
    model: str


class SimilarityRequest(BaseModel):
    text1: str
    text2: str


class TwoStageSearchRequest(BaseModel):
    query: str
    k: int = 10
    stage1_docs: int = 20
    filters: Optional[dict] = None


# ============================================================================
# RAG Endpoints
# ============================================================================

@router.post("/ask", response_model=AskResponse)
def ask(request: AskRequest, db: Session = Depends(get_db)):
    """Answer questions using semantic search and LLM generation."""
    # 1. Search with configurable mode
    search_mode = request.search_mode or 'hybrid'
    vector_weight = request.vector_weight or 0.7
    
    results = search_entries_semantic(
        db, 
        request.query, 
        k=request.k, 
        filters=request.filters or {},
        mode=search_mode,
        vector_weight=vector_weight
    )
    
    if not results:
        return AskResponse(answer="I couldn't find any relevant documents in the archive.", sources=[])
    
    # 2. Build Context
    context_parts = []
    sources = []
    for i, entry in enumerate(results):
        # Fallback to filename if title is missing
        title = entry.title
        if not title and entry.raw_file:
            # Use filename without extension
            title = os.path.splitext(entry.raw_file.filename)[0]
            
        context_parts.append(f"Document {i+1}:\nTitle: {title}\nContent: {entry.entry_text}\n")
        sources.append({
            "id": entry.id,
            "file_id": entry.file_id,
            "title": title,
            "path": entry.raw_file.path if entry.raw_file else None
        })
    
    context = "\n".join(context_parts)
    
    # 3. Prompt
    prompt = f"""You are my personal archive assistant.
Use ONLY the following documents to answer the question.
If the answer is not in these documents, say "I can't find that in this archive."

Documents:
{context}

Question: {request.query}
"""

    # 4. Generate
    model_to_use = request.model if request.model else MODEL
    answer = generate_text(prompt, model=model_to_use)
    
    if not answer:
        raise HTTPException(status_code=500, detail="Failed to generate answer")
        
    return AskResponse(answer=answer, sources=sources)


@router.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest):
    """Simple chat endpoint for direct LLM interaction."""
    # Build prompt from messages
    prompt_parts = []
    for msg in request.messages:
        if msg.role == 'system':
            prompt_parts.append(f"System: {msg.content}")
        elif msg.role == 'user':
            prompt_parts.append(msg.content)
        elif msg.role == 'assistant':
            prompt_parts.append(f"Assistant: {msg.content}")
    
    prompt = "\n\n".join(prompt_parts)
    
    # Use requested model or default
    model_to_use = request.model if request.model else MODEL
    response = generate_text(prompt, model=model_to_use)
    
    if not response:
        raise HTTPException(status_code=500, detail="Failed to generate response")
    
    return ChatResponse(response=response, model=model_to_use)


# ============================================================================
# Search Endpoints
# ============================================================================

@router.get("/search/explain")
def search_with_explanation(
    query: str,
    k: int = 10,
    mode: str = 'hybrid',
    db: Session = Depends(get_db)
):
    """Search with detailed explanation of scores and matches."""
    # Get query embedding
    query_embedding = embed_text(query)
    if not query_embedding:
        raise HTTPException(status_code=500, detail="Failed to embed query")
    
    # Perform search
    results = search_entries_semantic(db, query, k=k, mode=mode)
    
    explained_results = []
    for entry in results:
        # Calculate individual scores
        vector_score = None
        
        if entry.embedding is not None:
            # Calculate vector similarity
            entry_emb = np.array(entry.embedding)
            query_emb = np.array(query_embedding)
            vector_score = float(np.dot(entry_emb, query_emb) / (np.linalg.norm(entry_emb) * np.linalg.norm(query_emb)))
        
        # Check for keyword matches
        query_words = set(query.lower().split())
        text_words = set((entry.entry_text or '').lower().split()[:500])
        title_words = set((entry.title or '').lower().split())
        matching_words = query_words & (text_words | title_words)
        
        explained_results.append({
            "id": entry.id,
            "title": entry.title,
            "summary": entry.summary,
            "category": entry.category,
            "author": entry.author,
            "scores": {
                "vector_similarity": round(vector_score, 4) if vector_score else None,
                "combined": getattr(entry, '_search_scores', {}).get('combined_score'),
                "keyword": getattr(entry, '_search_scores', {}).get('keyword_score')
            },
            "match_explanation": {
                "matching_keywords": list(matching_words),
                "keyword_match_count": len(matching_words)
            },
            "file_path": entry.raw_file.path if entry.raw_file else None
        })
    
    return {
        "query": query,
        "search_mode": mode,
        "result_count": len(explained_results),
        "results": explained_results,
        "explanation": {
            "vector_search": "Converts query to 768-dimensional embedding and finds entries with similar semantic meaning.",
            "keyword_search": "Uses PostgreSQL full-text search (BM25) to find exact word matches.",
            "hybrid_search": "Combines vector (70%) and keyword (30%) scores for best results."
        }
    }


@router.post("/search/two-stage")
def search_two_stage_endpoint(
    request: TwoStageSearchRequest,
    db: Session = Depends(get_db)
):
    """
    Two-stage retrieval for large collections.
    
    Stage 1: Search doc-level embeddings to find relevant documents (fast, ~125k docs).
    Stage 2: Search chunk-level embeddings within top N docs (precise, filtered set).
    """
    result = search_two_stage(
        db=db,
        query=request.query,
        k=request.k,
        stage1_docs=request.stage1_docs,
        filters=request.filters or {}
    )
    
    # Serialize entries
    entries = []
    for entry in result.get('entries', []):
        entries.append({
            "id": entry.id,
            "title": entry.title,
            "summary": entry.summary,
            "category": entry.category,
            "author": entry.author,
            "tags": entry.tags,
            "entry_text": entry.entry_text[:500] if entry.entry_text else None,
            "doc_id": entry.file_id,
            "file_path": entry.raw_file.path if entry.raw_file else None
        })
    
    return {
        "query": request.query,
        "search_mode": "two_stage",
        "stages": {
            "stage1": {
                "docs_searched": "~125k doc-level embeddings",
                "docs_returned": result.get('stats', {}).get('docs_searched', 0)
            },
            "stage2": {
                "docs_filtered": result.get('stats', {}).get('docs_searched', 0),
                "chunks_returned": len(entries)
            }
        },
        "timing": result.get('stats', {}),
        "entries": entries,
        "doc_context": result.get('docs', [])
    }


# ============================================================================
# Similarity & Educational Endpoints
# ============================================================================

@router.post("/similarity")
def calculate_similarity(request: SimilarityRequest):
    """
    Calculate cosine similarity between two pieces of text.
    Educational tool to demonstrate how semantic search works.
    """
    if not request.text1.strip() or not request.text2.strip():
        raise HTTPException(status_code=400, detail="Both texts are required")
    
    # Get embeddings for both texts
    emb1 = embed_text(request.text1)
    emb2 = embed_text(request.text2)
    
    if not emb1 or not emb2:
        raise HTTPException(status_code=500, detail="Failed to generate embeddings")
    
    # Calculate cosine similarity
    emb1 = np.array(emb1)
    emb2 = np.array(emb2)
    
    dot_product = np.dot(emb1, emb2)
    norm1 = np.linalg.norm(emb1)
    norm2 = np.linalg.norm(emb2)
    
    similarity = dot_product / (norm1 * norm2)
    
    return {
        "similarity": float(similarity),
        "text1_length": len(request.text1),
        "text2_length": len(request.text2),
        "embedding_dimensions": len(emb1)
    }


@router.get("/embeddings/stats")
def get_embeddings_stats(db: Session = Depends(get_db)):
    """
    Get statistics about embeddings in the database.
    """
    doc_count = db.query(RawFile).filter(RawFile.doc_embedding.isnot(None)).count()
    chunk_count = db.query(Entry).filter(Entry.embedding.isnot(None)).count()
    
    return {
        "docs_with_embeddings": doc_count,
        "chunks_with_embeddings": chunk_count
    }


@router.get("/embeddings/visualize")
def visualize_embeddings(
    source: str = 'entries',
    algorithm: str = 'umap',
    dimensions: int = 2,
    limit: int = 1000,
    category: Optional[str] = None,
    author: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """
    Generate 2D or 3D visualization of embeddings using TSNE or UMAP.
    Useful for exploring the semantic space of your documents.
    """
    try:
        from sklearn.manifold import TSNE
        from umap import UMAP
    except ImportError:
        raise HTTPException(
            status_code=501,
            detail="Visualization requires sklearn and umap-learn. Install with: pip install scikit-learn umap-learn"
        )
    
    embeddings = []
    metadata = []
    
    # Collect embeddings
    if source == 'docs':
        # Use doc-level embeddings
        query = db.query(RawFile).filter(
            RawFile.doc_embedding.isnot(None)
        )
        
        if category:
            query = query.filter(RawFile.source == category)
        
        files = query.limit(limit).all()
        
        for file in files:
            if file.doc_embedding is not None and len(file.doc_embedding) > 0:
                embeddings.append(file.doc_embedding)
                
                metadata.append({
                    "file_id": file.id,
                    "title": file.filename,
                    "category": file.source or 'Unknown',
                    "author": file.author_key or 'Unknown',
                    "file_type": file.extension,
                    "filename": file.filename,
                    "summary": (file.doc_summary or "")[:100] if file.doc_summary else ""
                })
    else:
        # Use entry-level embeddings
        query = db.query(Entry).filter(
            Entry.embedding.isnot(None)
        )
        
        if category:
            query = query.filter(Entry.category == category)
        if author:
            query = query.filter(Entry.author == author)
        
        entries = query.limit(limit).all()
        
        for entry in entries:
            if entry.embedding is not None and len(entry.embedding) > 0:
                embeddings.append(entry.embedding)
                
                # Get file info
                raw_file = db.query(RawFile).filter(RawFile.id == entry.file_id).first()
                
                metadata.append({
                    "entry_id": entry.id,
                    "title": entry.title or "Untitled",
                    "category": entry.category or "Unknown",
                    "author": entry.author or "Unknown",
                    "file_type": raw_file.extension if raw_file else "unknown",
                    "filename": raw_file.filename if raw_file else "",
                    "summary": (entry.summary or "")[:100]
                })
    
    if len(embeddings) < 2:
        return {
            "error": f"Not enough {source} with embeddings",
            "count": len(embeddings),
            "points": []
        }
    
    # Convert to numpy array
    embeddings_array = np.array(embeddings)
    
    # Perform dimensionality reduction
    if algorithm == 'tsne':
        reducer = TSNE(
            n_components=dimensions,
            random_state=42,
            perplexity=min(30, len(embeddings) - 1)
        )
    else:  # umap
        reducer = UMAP(
            n_components=dimensions,
            random_state=42,
            n_neighbors=min(15, len(embeddings) - 1)
        )
    
    reduced = reducer.fit_transform(embeddings_array)
    
    # Combine with metadata
    points = []
    for i, coords in enumerate(reduced):
        point = metadata[i].copy()
        point['x'] = float(coords[0])
        point['y'] = float(coords[1])
        if dimensions == 3:
            point['z'] = float(coords[2])
        points.append(point)
    
    # Get unique categories and authors for legend
    categories = list(set(p['category'] for p in points if p['category']))
    authors = list(set(p['author'] for p in points if p['author']))
    file_types = list(set(p['file_type'] for p in points if p['file_type']))
    
    return {
        "points": points,
        "count": len(points),
        "dimensions": dimensions,
        "algorithm": algorithm,
        "source": source,
        "categories": sorted(categories),
        "authors": sorted(authors),
        "file_types": sorted(file_types)
    }
