# infrastructure/database/repository.py
from sqlalchemy.orm import Session
from typing import Optional, List
from .models import User, DeckRecord, CardRecord

class UserRepository:
    def __init__(self, db: Session):
        self.db = db
    
    def get_by_email(self, email: str) -> Optional[User]:
        return self.db.query(User).filter(User.email == email).first()
    
    def create(self, email: str) -> User:
        user = User(id=str(uuid.uuid4()), email=email)
        self.db.add(user)
        self.db.commit()
        return user
    
    def check_limits(self, user_id: str) -> bool:
        """Check if user is within free tier limits"""
        user = self.db.query(User).filter(User.id == user_id).first()
        if not user:
            return False
        
        if user.is_premium:
            return True
        
        # Free tier: 50 cards per month
        return user.cards_generated_this_month < 50

class DeckRepository:
    def __init__(self, db: Session):
        self.db = db
    
    def create(self, user_id: str, name: str, card_count: int) -> DeckRecord:
        deck = DeckRecord(
            id=str(uuid.uuid4()),
            user_id=user_id,
            name=name,
            card_count=card_count
        )
        self.db.add(deck)
        self.db.commit()
        return deck
    
    def update_status(self, deck_id: str, status: str, file_path: Optional[str] = None):
        deck = self.db.query(DeckRecord).filter(DeckRecord.id == deck_id).first()
        if deck:
            deck.status = status
            if file_path:
                deck.file_path = file_path
            if status == 'completed':
                deck.completed_at = datetime.utcnow()
            self.db.commit()
    
    def get_by_user(self, user_id: str) -> List[DeckRecord]:
        return self.db.query(DeckRecord).filter(DeckRecord.user_id == user_id).all()
    