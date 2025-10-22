# infrastructure/api/main.py
from fastapi import FastAPI, HTTPException, BackgroundTasks, Depends, Request
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
import asyncio
import uuid # For generating task IDs if not using Celery
from pathlib import Path
import logging

# Assuming LanguageCode is defined elsewhere (e.g., core.domain.models or a common types file)
# If not, define it here:
from typing import NewType
LanguageCode = NewType('LanguageCode', str)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- Dependency Injection Setup ---
# Attempt to import DI container; handle potential import errors gracefully
try:
    from infrastructure.config.dependency_injection import get_container, ServiceContainer
except ImportError as e:
    logger.error(f"Failed to import dependency injection container: {e}. API might not function correctly.")
    # Define a dummy container or raise an error if critical
    class DummyServiceContainer:
        def __getattr__(self, name):
            raise RuntimeError("Dependency Injection container failed to load.")
    container_instance = DummyServiceContainer()
    def get_service_container() -> Any:
         return container_instance
else:
    # Get the actual container instance if import succeeded
    try:
        container_instance = get_container()
    except Exception as e:
         logger.error(f"Failed to initialize dependency injection container: {e}")
         class DummyServiceContainer:
             def __getattr__(self, name):
                 raise RuntimeError(f"Dependency Injection container failed to initialize: {e}")
         container_instance = DummyServiceContainer()
         def get_service_container() -> Any:
              return container_instance

# --- FastAPI App Initialization ---
app = FastAPI(
    title="Language Flashcard Generator API",
    version="1.1.0",
    description="Generate Anki flashcards from sentences in various languages."
)

# --- Request/Response Models ---

class GenerateCardRequest(BaseModel):
    sentence: str = Field(..., description="The sentence in the source language.")
    source_lang: Optional[LanguageCode] = Field(None, description="Source language code (e.g., 'fr', 'de'). Uses default if not provided.")
    target_lang: Optional[LanguageCode] = Field(None, description="Target language code (e.g., 'en', 'es'). Uses default if not provided.")
    include_audio: bool = Field(True, description="Whether to generate and include audio.")
    include_grammar: bool = Field(True, description="Whether to generate and include grammar notes.")

class WordDetail(BaseModel):
    text: str
    lemma: str
    pos: str
    definition: str # Definition in target language
    definition_native: Optional[str] = None # Definition in source language

class WordBreakdownResponse(BaseModel):
    words: List[WordDetail]

class GrammarNoteResponse(BaseModel):
    title: str
    explanation: str
    examples: List[str] = []

class GenerateCardResponse(BaseModel):
    card_id: str
    source_text: str = Field(..., alias="sourceText")
    target_text: str = Field(..., alias="targetText")
    source_lang: LanguageCode = Field(..., alias="sourceLang")
    target_lang: LanguageCode = Field(..., alias="targetLang")
    word_breakdown: WordBreakdownResponse = Field(..., alias="wordBreakdown")
    audio_url: Optional[str] = Field(None, alias="audioUrl")
    grammar_notes: List[GrammarNoteResponse] = Field([], alias="grammarNotes")

    class Config:
        populate_by_name = True # Allows using alias names

class GenerateDeckRequest(BaseModel):
    sentences: List[str] = Field(..., min_length=1, description="List of sentences in the source language.")
    deck_name: str = Field(..., description="Desired name for the Anki deck.")
    source_lang: Optional[LanguageCode] = Field(None, description="Source language code (e.g., 'fr', 'de'). Uses default if not provided.")
    target_lang: Optional[LanguageCode] = Field(None, description="Target language code (e.g., 'en', 'es'). Uses default if not provided.")
    include_audio: bool = Field(False, description="Whether to include audio (can be slow for large decks).") # Default False for batch
    include_grammar: bool = Field(True, description="Whether to include grammar notes.")

class GenerateDeckResponse(BaseModel):
    task_id: str = Field(..., alias="taskId") # Using task_id as a more generic term
    deck_name: str = Field(..., alias="deckName")
    card_count: int = Field(..., alias="cardCount")
    status: str = Field(..., description="Initial status (e.g., 'queued', 'processing').")
    # download_url: Optional[str] = Field(None, alias="downloadUrl") # URL might depend on task completion

    class Config:
        populate_by_name = True

class TaskStatusResponse(BaseModel):
    task_id: str = Field(..., alias="taskId")
    status: str
    progress: Optional[float] = None # e.g., 0.0 to 100.0
    message: Optional[str] = None
    result_url: Optional[str] = Field(None, alias="resultUrl") # URL to download when complete
    error: Optional[str] = None

    class Config:
        populate_by_name = True

# Mock storage for task status/results if not using Celery/Redis
# In a real app, use Redis, a database, or Celery's backend
TASK_STATUS_DB: Dict[str, Dict[str, Any]] = {}

# --- Helper Functions ---

async def run_deck_generation_background(
    task_id: str,
    sentences: List[str],
    deck_name: str,
    source_lang: Optional[LanguageCode],
    target_lang: Optional[LanguageCode],
    include_audio: bool,
    include_grammar: bool,
    container: ServiceContainer # Pass container explicitly
):
    """Processes deck generation in the background."""
    output_dir = Path("./output/api_decks") # Define a specific output dir for API tasks
    output_dir.mkdir(parents=True, exist_ok=True)
    output_filename = f"{deck_name}_{task_id}.apkg"
    output_path = output_dir / output_filename

    TASK_STATUS_DB[task_id] = {"status": "processing", "progress": 0.0, "message": "Starting deck generation..."}
    logger.info(f"Starting background task {task_id} for deck '{deck_name}'...")

    try:
        use_case = container.create_deck_generator()
        # Note: The deck generator use case should ideally support progress reporting
        # For now, we simulate basic progress updates
        TASK_STATUS_DB[task_id]["progress"] = 10.0
        TASK_STATUS_DB[task_id]["message"] = f"Generating {len(sentences)} cards..."

        final_output_path = await use_case.execute(
            sentences=sentences,
            deck_name=deck_name,
            output_path=str(output_path),
            source_lang=source_lang, # Pass languages
            target_lang=target_lang,
            include_audio=include_audio,
            include_grammar=include_grammar
        )

        if final_output_path:
            # Task succeeded
            download_url = f"/api/v1/decks/download/{output_filename}" # Relative URL
            TASK_STATUS_DB[task_id].update({
                "status": "completed",
                "progress": 100.0,
                "message": f"Deck generated successfully: {output_filename}",
                "result_url": download_url
            })
            logger.info(f"Background task {task_id} completed. Output: {final_output_path}")
        else:
             # Use case returned None, indicating failure during generation
             raise RuntimeError("Deck generation use case failed to produce an output file.")

    except Exception as e:
        logger.error(f"Background task {task_id} failed: {e}", exc_info=True)
        TASK_STATUS_DB[task_id].update({
            "status": "failed",
            "progress": TASK_STATUS_DB[task_id].get("progress", 0.0), # Keep last known progress
            "message": "Deck generation failed.",
            "error": str(e)
        })

# --- API Endpoints ---

@app.post("/api/v1/cards", response_model=GenerateCardResponse, status_code=201)
async def generate_single_card(
    request: GenerateCardRequest,
    container: ServiceContainer = Depends(get_service_container)
):
    """
    Generates a single language flashcard with translation, word breakdown,
    optional audio, and optional grammar notes.
    """
    logger.info(f"Received request to generate card for sentence: '{request.sentence}'")
    try:
        use_case = container.create_card_generator()
        card = await use_case.execute(
            sentence_text=request.sentence,
            source_lang=request.source_lang, # Pass optional languages
            target_lang=request.target_lang,
            include_audio=request.include_audio,
            include_grammar=request.include_grammar
        )

        if not card: # Handle potential None return from use case on critical failure
            raise HTTPException(status_code=500, detail="Card generation failed unexpectedly.")

        # Map domain model to response model
        response_data = GenerateCardResponse(
            card_id=card.id,
            sourceText=card.sentence.text,
            targetText=card.translation.text,
            sourceLang=card.sentence.language,
            targetLang=card.translation.target_language,
            wordBreakdown=WordBreakdownResponse(
                words=[
                    WordDetail(
                        text=w.text,
                        lemma=w.lemma,
                        pos=w.pos,
                        definition=w.definition,
                        definition_native=w.definition_native
                    )
                    for w in card.word_breakdown.words
                ]
            ),
            audioUrl=card.audio.url if card.audio and card.audio.url else None, # Use URL if available
            grammarNotes=[
                GrammarNoteResponse(
                    title=note.title,
                    explanation=note.explanation,
                    examples=note.examples
                 )
                for note in card.grammar_notes
            ]
        )
        logger.info(f"Successfully generated card {card.id}")
        return response_data

    except ValueError as ve:
         logger.warning(f"Value error during card generation: {ve}")
         raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        logger.error(f"Unexpected error generating card: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error during card generation.")


@app.post("/api/v1/decks", response_model=GenerateDeckResponse, status_code=202)
async def generate_deck_async(
    request: GenerateDeckRequest,
    background_tasks: BackgroundTasks,
    container: ServiceContainer = Depends(get_service_container)
):
    """
    Initiates asynchronous generation of an Anki deck from multiple sentences.
    Returns a task ID to track progress.
    """
    task_id = str(uuid.uuid4())
    logger.info(f"Received request to generate deck '{request.deck_name}' ({len(request.sentences)} sentences). Task ID: {task_id}")

    # Add background task
    background_tasks.add_task(
        run_deck_generation_background,
        task_id=task_id,
        sentences=request.sentences,
        deck_name=request.deck_name,
        source_lang=request.source_lang,
        target_lang=request.target_lang,
        include_audio=request.include_audio,
        include_grammar=request.include_grammar,
        container=container # Pass the container
    )

    # Initial status - store it
    TASK_STATUS_DB[task_id] = {"status": "queued", "message": "Deck generation task received."}

    return GenerateDeckResponse(
        taskId=task_id,
        deckName=request.deck_name,
        cardCount=len(request.sentences),
        status="queued"
    )

@app.get("/api/v1/decks/status/{task_id}", response_model=TaskStatusResponse)
async def get_deck_status(task_id: str):
    """
    Retrieves the status of an asynchronous deck generation task.
    """
    logger.debug(f"Checking status for task ID: {task_id}")
    status_info = TASK_STATUS_DB.get(task_id)

    if not status_info:
        logger.warning(f"Status requested for unknown task ID: {task_id}")
        raise HTTPException(status_code=404, detail="Task ID not found.")

    return TaskStatusResponse(
        taskId=task_id,
        status=status_info.get("status", "unknown"),
        progress=status_info.get("progress"),
        message=status_info.get("message"),
        resultUrl=status_info.get("result_url"),
        error=status_info.get("error")
    )

@app.get("/api/v1/decks/download/{filename}")
async def download_generated_deck(filename: str):
    """
    Downloads the generated Anki deck (.apkg file).
    Ensure filename includes the task_id or is otherwise unique.
    Basic security: prevent path traversal.
    """
    logger.info(f"Request received to download deck file: {filename}")
    output_dir = Path("./output/api_decks").resolve() # Use absolute path for security check
    requested_path = (output_dir / filename).resolve()

    # Security Check: Ensure the requested path is within the designated output directory
    if not str(requested_path).startswith(str(output_dir)):
        logger.warning(f"Attempted path traversal detected for filename: {filename}")
        raise HTTPException(status_code=400, detail="Invalid filename.")

    if not requested_path.is_file():
        logger.error(f"Download request for non-existent file: {requested_path}")
        raise HTTPException(status_code=404, detail="File not found or not yet generated.")

    # Check task status (optional but good practice)
    # Extract task_id from filename if needed, e.g., filename format deckname_taskid.apkg
    # task_id = ... extract from filename ...
    # if TASK_STATUS_DB.get(task_id, {}).get("status") != "completed":
    #    raise HTTPException(status_code=404, detail="Deck generation not completed.")

    logger.info(f"Serving file for download: {requested_path}")
    return FileResponse(
        path=str(requested_path),
        media_type="application/octet-stream", # Standard for .apkg downloads
        filename=filename # Suggests the original filename to the browser
    )

# --- Root and Health Check ---

@app.get("/")
async def read_root():
    return {"message": "Welcome to the Language Flashcard Generator API!"}

@app.get("/health")
async def health_check():
    """Basic health check endpoint."""
    # Could add checks for DB, cache, etc. here
    return {"status": "healthy"}

# --- Exception Handling ---

@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled exception for request {request.url}: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"message": "An unexpected internal server error occurred."},
    )
