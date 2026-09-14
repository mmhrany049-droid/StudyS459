import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.database import Base
from app.models.user import User
from app.models.subject import Subject
from app.models.book import Book
from app.models.test_set import TestSet
from app.models.question import Question
from app.models.test_session import TestSession, TestSessionQuestion
from app.models.attempt import QuestionAttempt
from app.services.analytics_service import get_progress_detailed
from app.services.auth_service import get_password_hash
from datetime import datetime, timezone

engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

@pytest.fixture
def db():
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    yield db
    db.close()
    Base.metadata.drop_all(bind=engine)

def test_coverage_vs_accuracy_distinction(db):
    # Create user, book, questions
    user = User(email="test@test.com", username="testuser", hashed_password=get_password_hash("pass"))
    db.add(user)
    db.commit()
    
    subj = Subject(stable_id="subj", name="Subject")
    db.add(subj)
    db.commit()
    
    book = Book(stable_id="book", subject_id=subj.id, title="Book")
    db.add(book)
    db.commit()
    
    # Create 100 questions total
    for i in range(100):
        q = Question(book_id=book.id, stable_id=f"q{i}", question_text=f"Q{i}", correct_option="A")
        db.add(q)
    db.commit()
    
    # User attempts 25 questions, 18 correct (72% accuracy) -> coverage 25%
    questions = db.query(Question).limit(25).all()
    for idx, q in enumerate(questions):
        is_correct = idx < 18  # 18 correct
        attempt = QuestionAttempt(
            user_id=user.id,
            question_id=q.id,
            test_session_id=1,  # dummy, will need session
            book_id=book.id,
            user_answer="A" if is_correct else "B",
            correct_answer="A",
            is_correct=is_correct,
            is_unanswered=False,
            attempt_number=1
        )
        # Need test session for FK, create dummy
        # For simplicity, skip FK constraint by using session id 1 and handling? We'll create session
        db.add(attempt)
    # Actually need test session
    # Let's create a session first
    from app.models.test_session import TestSession
    ts = TestSession(user_id=user.id, book_id=book.id, test_type="normal", status="finished", total_questions=25, correct_count=18, wrong_count=7, unanswered_count=0)
    db.add(ts)
    db.commit()
    # Update attempts with real session id
    for att in db.query(QuestionAttempt).all():
        att.test_session_id = ts.id
    db.commit()
    
    progress = get_progress_detailed(db, user.id)
    
    coverage = progress["overall"]["coverage"]["coverage_percent"]
    accuracy = progress["overall"]["accuracy"]["accuracy_percent"]
    mastery = progress["overall"]["mastery"]["mastery_percent"]
    
    # Coverage should be ~25%
    assert abs(coverage - 25.0) < 1.0
    # Accuracy should be ~72%
    assert abs(accuracy - 72.0) < 1.0
    # Mastery should NOT be 72% of entire book, should be accuracy * coverage = 18%
    # With our formula mastery = accuracy * coverage
    assert mastery < accuracy
    assert mastery < 30  # Should be low because coverage low
    print(f"Coverage {coverage}, Accuracy {accuracy}, Mastery {mastery} - distinction preserved")

def test_taught_not_learned(db):
    from app.models.schedule import Schedule, ClassSession
    from app.models.academic import TaughtLesson
    from app.services.academic_service import create_taught_lesson
    
    user = User(email="test2@test.com", username="testuser2", hashed_password=get_password_hash("pass"))
    db.add(user)
    db.commit()
    
    subj = Subject(stable_id="subj2", name="Subject2")
    db.add(subj)
    db.commit()
    book = Book(stable_id="book2", subject_id=subj.id, title="Book2")
    db.add(book)
    db.commit()
    
    # Create taught lesson
    taught = TaughtLesson(user_id=user.id, book_id=book.id, taught_date="2024-01-01", title="Taught lesson")
    db.add(taught)
    db.commit()
    
    # Check that mastery still 0 without attempts
    progress = get_progress_detailed(db, user.id)
    assert progress["overall"]["mastery"]["mastery_percent"] == 0
    # Taught != learned: taught lesson exists but mastery not increased
