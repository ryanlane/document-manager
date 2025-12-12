from typing import List, Optional
from fastapi import FastAPI, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from src.db.session import get_db
from src.rag.search import search_entries_semantic
from src.llm_client import generate_text

app = FastAPI(title="Archive Brain API")

class AskRequest(BaseModel):
    query: str
    k: int = 5
    filters: Optional[dict] = None

class AskResponse(BaseModel):
    answer: str
    sources: List[dict]

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
        context_parts.append(f"Document {i+1}:\nTitle: {entry.title}\nContent: {entry.entry_text}\n")
        sources.append({
            "id": entry.id,
            "title": entry.title,
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
    answer = generate_text(prompt)
    
    if not answer:
        raise HTTPException(status_code=500, detail="Failed to generate answer")
        
    return AskResponse(answer=answer, sources=sources)

@app.get("/health")
def health():
    return {"status": "ok"}
