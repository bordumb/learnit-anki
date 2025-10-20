# infrastructure/jobs/celery_app.py
from celery import Celery
from infrastructure.config.dependency_injection import get_container

celery_app = Celery(
    'flashcard_generator',
    broker='redis://localhost:6379/0',
    backend='redis://localhost:6379/1'
)

celery_app.conf.update(
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,
)

@celery_app.task(name='generate_deck')
def generate_deck_task(
    sentences: list[str],
    deck_name: str,
    user_id: str
):
    """Celery task for deck generation"""
    import asyncio
    
    container = get_container()
    use_case = container.create_deck_generator()
    
    # Run async code in sync context
    loop = asyncio.get_event_loop()
    output_path = loop.run_until_complete(
        use_case.execute(
            sentences=sentences,
            deck_name=deck_name,
            output_path=f"./output/{user_id}/{deck_name}.apkg"
        )
    )
    
    return {
        'status': 'completed',
        'output_path': output_path,
        'user_id': user_id
    }

@celery_app.task(name='generate_card')
def generate_card_task(sentence: str):
    """Celery task for single card"""
    import asyncio
    
    container = get_container()
    use_case = container.create_card_generator()
    
    loop = asyncio.get_event_loop()
    card = loop.run_until_complete(
        use_case.execute(sentence_text=sentence)
    )
    
    return card.to_anki_fields()
