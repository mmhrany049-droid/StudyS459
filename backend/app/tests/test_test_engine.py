import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.database import Base
from app.models.user import User
from app.models.subject import Subject
from app.models.book import Book
from app.models.test_set import TestSet
from app.models.question import Question
from app.services import test_service
from app.services.auth_service import get_password_hash

engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

@pytest.fixture
def db():
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    yield db
    db.close()
    Base.metadata.drop_all(bind=engine)

@pytest.fixture
def setup_data(db):
    # Create user
    user = User(email="test@test.com", username="testuser", hashed_password=get_password_hash("password"))
    db.add(user)
    db.commit()
    
    subj = Subject(stable_id="subj", name="Subject")
    db.add(subj)
    db.commit()
    
    book = Book(stable_id="book", subject_id=subj.id, title="Book")
    db.add(book)
    db.commit()
    
    ts = TestSet(book_id=book.id, stable_id="ts1", title="TestSet", test_type="normal")
    db.add(ts)
    db.commit()
    
    # Create 20 questions
    for i in range(20):
        q = Question(book_id=book.id, test_set_id=ts.id, stable_id=f"q{i}", question_text=f"Q{i}", option_a="A", option_b="B", option_c="C", option_d="D", correct_option="A")
        db.add(q)
    db.commit()
    
    return {"user": user, "book": book, "test_set": ts}

def test_random_selection_no_duplicates(db, setup_data):
    user = setup_data["user"]
    book = setup_data["book"]
    
    session = test_service.create_test_session(db, user_id=user.id, book_id=book.id, question_count=10)
    
    assert len(session.session_questions) == 10
    question_ids = [sq.question_id for sq in session.session_questions]
    assert len(question_ids) == len(set(question_ids)), "No duplicates allowed"

def test_timed_vs_untimed(db, setup_data):
    user = setup_data["user"]
    book = setup_data["book"]
    
    timed = test_service.create_test_session(db, user_id=user.id, book_id=book.id, question_count=5, mode="timed", time_limit_seconds=1800)
    assert timed.mode == "timed"
    assert timed.time_limit_seconds == 1800
    
    untimed = test_service.create_test_session(db, user_id=user.id, book_id=book.id, question_count=5, mode="untimed")
    assert untimed.mode == "untimed"
    assert untimed.time_limit_seconds is None

def test_correct_wrong_unanswered_distinct(db, setup_data):
    user = setup_data["user"]
    book = setup_data["book"]
    
    session = test_service.create_test_session(db, user_id=user.id, book_id=book.id, question_count=3)
    sq_list = session.session_questions
    
    # Answer first correctly, second wrong, third unanswered
    q1 = db.query(Question).filter(Question.id == sq_list[0].question_id).first()
    correct_opt = q1.correct_option
    wrong_opt = "B" if correct_opt != "B" else "C"
    
    test_service.submit_answer(db, session.id, user.id, sq_list[0].question_id, correct_opt)
    test_service.submit_answer(db, session.id, user.id, sq_list[1].question_id, wrong_opt)
    # Leave third unanswered
    
    finished = test_service.finish_test_session(db, session.id, user.id, elapsed_seconds=100)
    
    assert finished.correct_count == 1
    assert finished.wrong_count == 1
    assert finished.unanswered_count == 1
    # Unanswered must NOT become wrong
    assert finished.wrong_count != 2

def test_idempotent_finish(db, setup_data):
    user = setup_data["user"]
    book = setup_data["book"]
    
    session = test_service.create_test_session(db, user_id=user.id, book_id=book.id, question_count=2)
    first_finish = test_service.finish_test_session(db, session.id, user.id, elapsed_seconds=50)
    
    # Second finish should be idempotent, not create duplicate attempts
    second_finish = test_service.finish_test_session(db, session.id, user.id, elapsed_seconds=50)
    
    assert first_finish.id == second_finish.id
    assert first_finish.status == second_finish.status

def test_insufficient_pool(db, setup_data):
    user = setup_data["user"]
    book = setup_data["book"]
    
    try:
        test_service.create_test_session(db, user_id=user.id, book_id=book.id, question_count=100)
        assert False, "Should raise insufficient pool error"
    except Exception as e:
        assert "Insufficient" in str(e) or "pool" in str(e).lower()

def test_missing_answer_key(db, setup_data):
    user = setup_data["user"]
    subj = db.query(Subject).first()
    book2 = Book(stable_id="book2", subject_id=subj.id, title="Book2")
    db.add(book2)
    db.commit()
    ts2 = TestSet(book_id=book2.id, stable_id="ts2", title="NoKey", test_type="normal")
    db.add(ts2)
    db.commit()
    q = Question(book_id=book2.id, test_set_id=ts2.id, stable_id="q-no-key", question_text="No key", correct_option=None)
    db.add(q)
    db.commit()
    
    session = test_service.create_test_session(db, user_id=user.id, book_id=book2.id, question_count=1)
    sq = session.session_questions[0]
    test_service.submit_answer(db, session.id, user.id, sq.question_id, "A")
    finished = test_service.finish_test_session(db, session.id, user.id)
    
    assert finished.status == "pending_correction"
