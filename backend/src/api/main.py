from typing import List, Optional
from fastapi import FastAPI, Depends, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session
import os

from src.db.session import get_db
from src.db.models import RawFile
from src.rag.search import search_entries_semantic
from src.llm_client import generate_text, list_models, OLLAMA_URL, MODEL, EMBEDDING_MODEL
import requests

app = FastAPI(title="Archive Brain API")

class AskRequest(BaseModel):
    query: str
    k: int = 5
    model: Optional[str] = None
    filters: Optional[dict] = None

class AskResponse(BaseModel):
    answer: str
    sources: List[dict]

class FileDetail(BaseModel):
    id: int
    filename: str
    path: str
    raw_text: str

@app.get("/health")
def health_check():
    return {"status": "ok"}

@app.get("/system/status")
def get_system_status():
    ollama_status = "offline"
    available_models = []
    try:
        # Simple check to see if Ollama is responding
        resp = requests.get(f"{OLLAMA_URL}", timeout=1)
        if resp.status_code == 200:
            ollama_status = "online"
            available_models = list_models()
    except Exception:
        pass
        
    return {
        "ollama": {
            "status": ollama_status,
            "url": OLLAMA_URL,
            "chat_model": MODEL,
            "embedding_model": EMBEDDING_MODEL,
            "available_models": available_models
        }
    }

@app.get("/files/{file_id}/content")
def get_file_content(file_id: int, db: Session = Depends(get_db)):
    file = db.query(RawFile).filter(RawFile.id == file_id).first()
    if not file:
        raise HTTPException(status_code=404, detail="File not found")
    
    if not os.path.exists(file.path):
        raise HTTPException(status_code=404, detail="File not found on disk")
        
    return FileResponse(file.path, filename=file.filename)

@app.get("/files/{file_id}", response_model=FileDetail)
def get_file_details(file_id: int, db: Session = Depends(get_db)):
    file = db.query(RawFile).filter(RawFile.id == file_id).first()
    if not file:
        raise HTTPException(status_code=404, detail="File not found")
    return file

@app.post("/ask", response_model=AskResponse)
def ask(request: AskRequest, db: Session = Depends(get_db)):
    # 1. Search
    results = search_entries_semantic(db, request.query, k=request.k)
    
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
    # Use requested model or default to env var
    model_to_use = request.model if request.model else MODEL
    answer = generate_text(prompt, model=model_to_use)
    
    if not answer:
        raise HTTPException(status_code=500, detail="Failed to generate answer")
        
    return AskResponse(answer=answer, sources=sources)

@app.get("/health")
def health():
    return {"status": "ok"}
