from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime, Boolean, ForeignKey
from sqlalchemy.orm import declarative_base, sessionmaker, relationship
from datetime import datetime

DATABASE_URL = "sqlite:///documents.db"

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine)

Base = declarative_base()


class Document(Base):
    __tablename__ = "documents"

    id = Column(Integer, primary_key=True, index=True)
    document_name = Column(String(255), nullable=False)
    number_of_pages = Column(Integer)
    status = Column(Boolean, default=False)
    
    comments = Column(Text)
    submitted_on = Column(DateTime, default=datetime.utcnow)

    ai_feedback = relationship(
        "AIAnalysis",
        back_populates="document",
        cascade="all, delete-orphan"
    )


class AIAnalysis(Base):
    __tablename__ = "ai_analysis"

    id = Column(Integer, primary_key=True, index=True)
    document_id = Column(Integer, ForeignKey("documents.id"))
    ai_observation = Column(Text)
    ai_recommendation = Column(Text)

    created_at = Column(DateTime, default=datetime.utcnow)

    document = relationship("Document", back_populates="ai_feedback")


def init_db():
    Base.metadata.create_all(bind=engine)
