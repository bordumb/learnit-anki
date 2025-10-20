# infrastructure/api/main.py
from fastapi import FastAPI, HTTPException, BackgroundTasks, Depends
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import List, Optional
import asyncio
from infrastructure.config.dependency_injection import get_container, ServiceContainer

app = FastAPI(
    title="French Flashcard Generator API",
    version="1.0.0",
    description="Generate Anki flashcards from French sentences"
)

# Request/Response models
class GenerateCardRequest(BaseModel):
    sentence: str
    include_audio: bool = True
    include_grammar: bool = True

class GenerateCardResponse(BaseModel):
    card_id: str
    french: str
    english: str
    word_breakdown: dict
    audio_url: Optional[str]
    grammar_notes: List[dict]

class GenerateDeckRequest(BaseModel):
    sentences: List[str]
    deck_name: str
    include_audio: bool = True
    include_grammar: bool = True

class GenerateDeckResponse(BaseModel):
    deck_id: str
    deck_name: str
    card_count: int
    download_url: str
    status: str  # "processing", "completed", "failed"

class SearchSentencesRequest(BaseModel):
    topic: str
    count: int = 20
    difficulty: Optional[str] = None

class SearchSentencesResponse(BaseModel):
    sentences: List[str]
    count: int

# Dependency
def get_service_container() -> ServiceContainer:
    return get_container()

# Endpoints
@app.post("/api/v1/cards/generate", response_model=GenerateCardResponse)
async def generate_card(
    request: GenerateCardRequest,
    container: ServiceContainer = Depends(get_service_container)
):
    """Generate a single flashcard"""
    try:
        use_case = container.create_card_generator()
        card = await use_case.execute(
            sentence_text=request.sentence,
            include_audio=request.include_audio,
            include_grammar=request.include_grammar
        )
        
        return GenerateCardResponse(
            card_id=card.id,
            french=card.sentence.text,
            english=card.translation.text,
            word_breakdown={
                "words": [
                    {
                        "text": w.text,
                        "pos": w.pos,
                        "definition": w.definition
                    }
                    for w in card.word_breakdown.words
                ]
            },
            audio_url=card.audio.url if card.audio else None,
            grammar_notes=[
                {"title": note.title, "explanation": note.explanation}
                for note in card.grammar_notes
            ]
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/v1/decks/generate", response_model=GenerateDeckResponse)
async def generate_deck(
    request: GenerateDeckRequest,
    container: ServiceContainer = Depends(get_service_container)
):
    """Generate a deck (async with Celery)"""
    
    # Queue the job
    task = generate_deck_task.delay(
        sentences=request.sentences,
        deck_name=request.deck_name,
        user_id="anonymous"  # TODO: Get from auth
    )
    
    return GenerateDeckResponse(
        deck_id=task.id,
        deck_name=request.deck_name,
        card_count=len(request.sentences),
        download_url=f"/api/v1/decks/{task.id}/download",
        status="queued"
    )

@app.get("/api/v1/decks/{task_id}/status")
async def get_deck_status(task_id: str):
    """Check Celery task status"""
    from celery.result import AsyncResult
    
    task = AsyncResult(task_id)
    
    if task.state == 'PENDING':
        response = {'status': 'queued'}
    elif task.state == 'PROGRESS':
        response = {'status': 'processing', 'progress': task.info.get('progress', 0)}
    elif task.state == 'SUCCESS':
        response = {'status': 'completed', 'result': task.result}
    else:
        response = {'status': 'failed', 'error': str(task.info)}
    
    return response

@app.get("/api/v1/decks/{deck_id}/download")
async def download_deck(deck_id: str):
    """Download generated deck"""
    # TODO: Implement file serving
    file_path = f"./output/{deck_id}.apkg"
    return FileResponse(
        file_path,
        media_type="application/octet-stream",
        filename=f"{deck_id}.apkg"
    )

@app.post("/api/v1/sentences/search", response_model=SearchSentencesResponse)
async def search_sentences(
    request: SearchSentencesRequest,
    container: ServiceContainer = Depends(get_service_container)
):
    """Search for example sentences"""
    # TODO: Implement sentence search
    return SearchSentencesResponse(
        sentences=[],
        count=0
    )

# Background task
async def process_deck_generation(
    deck_id: str,
    sentences: List[str],
    deck_name: str,
    container: ServiceContainer
):
    """Process deck generation in background"""
    try:
        use_case = container.create_deck_generator()
        output_path = await use_case.execute(
            sentences=sentences,
            deck_name=deck_name,
            output_path=f"./output/{deck_id}.apkg"
        )
        # TODO: Update status in database/cache
        print(f"✅ Deck {deck_id} completed: {output_path}")
    except Exception as e:
        # TODO: Update status to failed
        print(f"❌ Deck {deck_id} failed: {e}")

# Health check
@app.get("/health")
async def health_check():
    return {"status": "healthy"}