from sqlalchemy.orm import Session,joinedload
from database import Document, AIAnalysis

def create_document_with_ai(
    db: Session,
    document_name: str,
    number_of_pages: int,
    ai_observations: list,
    ai_recommendations: list
):

    new_doc = Document(
        document_name=document_name,
        number_of_pages=number_of_pages
    )
    db.add(new_doc)
    db.commit()
    db.refresh(new_doc)

    # Save AI feedback entries
    for obs, rec in zip(ai_observations, ai_recommendations):
        ai_entry = AIAnalysis(
            document_id=new_doc.id,
            ai_observation=obs,
            ai_recommendation=rec
        )
        db.add(ai_entry)

    db.commit()
    return new_doc


def get_all_documents(db: Session):
    """Return ORM objects; convert to dict in Streamlit."""
    return  (
        db.query(Document)
        .options(joinedload(Document.ai_feedback))
        .all()
    )


def get_document_by_id(db: Session, document_id: int):
    """Return ORM object."""
    return (
        db.query(Document)
        .options(joinedload(Document.ai_feedback))
        .filter(Document.id == document_id)
        .first()
    )


def update_document(db: Session, document_id: int, status: bool = None, comments: str = None):
    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc:
        return None

    if status is not None:
        doc.status = status
    if comments is not None:
        doc.comments = comments

    db.commit()
    db.refresh(doc)
    return doc


def delete_document(db: Session, document_id: int):
    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc:
        return False

    db.delete(doc)
    db.commit()
    return True
