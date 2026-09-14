import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.database import Base
from app.models.user import User
from app.models.subject import Subject
from app.models.book import Book
from app.services import academic_service, social_service
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

def test_taught_not_learned(db):
    user = User(email="test@test.com", username="testuser", hashed_password=get_password_hash("pass"))
    db.add(user)
    db.commit()
    subj = Subject(stable_id="subj", name="Subj")
    db.add(subj)
    db.commit()
    book = Book(stable_id="book", subject_id=subj.id, title="Book")
    db.add(book)
    db.commit()
    
    # Create taught lesson
    taught = academic_service.create_taught_lesson(db, user.id, {"book_id": book.id, "taught_date": "2024-01-01", "title": "Lesson taught"})
    assert taught.book_id == book.id
    
    # Mastery should still be 0
    from app.services.analytics_service import get_progress_detailed
    progress = get_progress_detailed(db, user.id)
    assert progress["overall"]["mastery"]["mastery_percent"] == 0

def test_homework_generates_task(db):
    user = User(email="test2@test.com", username="testuser2", hashed_password=get_password_hash("pass"))
    db.add(user)
    db.commit()
    
    hw = academic_service.create_homework(db, user.id, {"title": "Math homework", "due_date": "2024-01-10", "estimated_time_minutes": 60})
    
    assert hw.task_id is not None
    from app.models.task import Task
    task = db.query(Task).filter(Task.id == hw.task_id).first()
    assert task is not None
    assert task.source == "homework"
    assert task.source_id == hw.id

def test_social_private_by_default(db):
    user1 = User(email="user1@test.com", username="user1", hashed_password=get_password_hash("pass"))
    user2 = User(email="user2@test.com", username="user2", hashed_password=get_password_hash("pass"))
    db.add_all([user1, user2])
    db.commit()
    
    group = social_service.create_group(db, user1.id, "Test Group")
    social_service.join_group_by_code(db, user2.id, group.invite_code)
    
    # User2 tries to compare without permission - should get empty because private by default
    result = social_service.compare_group_metrics(db, user1.id, group.id, metric="accuracy")
    # Only user1 themselves should be visible without permission, user2 not allowed
    # Since user2 hasn't allowed sharing, result should only contain user1
    assert len(result) == 1
    assert result[0]["user_id"] == user1.id
    
    # Now user2 allows sharing
    social_service.set_sharing_permission(db, user2.id, group.id, "accuracy", True)
    result2 = social_service.compare_group_metrics(db, user1.id, group.id, metric="accuracy")
    assert len(result2) == 2

def test_telegram_consumes_services(db):
    user = User(email="tg@test.com", username="tguser", hashed_password=get_password_hash("pass"))
    db.add(user)
    db.commit()
    
    from app.services import telegram_service
    # Create connection
    conn = telegram_service.create_or_update_connection(db, user.id, telegram_user_id="123", chat_id="456")
    assert conn.telegram_user_id == "123"
    
    # Generate reports - should consume core services, not duplicate logic
    morning = telegram_service.generate_morning_report(db, user.id)
    assert "report_type" in morning
    assert "content" in morning
    assert "data" in morning
    
    evening = telegram_service.generate_evening_report(db, user.id)
    assert evening["report_type"] == "evening_report"
