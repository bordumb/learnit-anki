# infrastructure/database/models.py
from sqlalchemy import Column, String, Integer, DateTime, ForeignKey, JSON, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from datetime import datetime

Base = declarative_base()

class User(Base):
    __tablename__ = 'users'
    
    id = Column(String, primary_key=True)
    email = Column(String, unique=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Limits for free tier
    cards_generated_this_month = Column(Integer, default=0)
    is_premium = Column(Boolean, default=False)
    
    decks = relationship("DeckRecord", back_populates="user")

class DeckRecord(Base):
    __tablename__ = 'decks'
    
    id = Column(String, primary_key=True)
    user_id = Column(String, ForeignKey('users.id'))
    name = Column(String, nullable=False)
    card_count = Column(Integer, default=0)
    status = Column(String, default='pending')  # pending, processing, completed, failed
    file_path = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime)
    
    user = relationship("User", back_populates="decks")
    cards = relationship("CardRecord", back_populates="deck")

class CardRecord(Base):
    __tablename__ = 'cards'
    
    id = Column(String, primary_key=True)
    deck_id = Column(String, ForeignKey('decks.id'))
    french_text = Column(String, nullable=False)
    english_text = Column(String, nullable=False)
    word_breakdown = Column(JSON)
    audio_url = Column(String)
    grammar_notes = Column(JSON)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    deck = relationship("DeckRecord", back_populates="cards")

class APIUsage(Base):
    __tablename__ = 'api_usage'
    
    id = Column(Integer, primary_key=True)
    user_id = Column(String, ForeignKey('users.id'))
    endpoint = Column(String)
    cards_generated = Column(Integer)
    cost = Column(Integer)  # in cents
    timestamp = Column(DateTime, default=datetime.utcnow)
