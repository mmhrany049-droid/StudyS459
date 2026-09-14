from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy.pool import StaticPool
from .config.settings import settings

# SQLite for dev, PostgreSQL-ready architecture
connect_args = {}
if settings.database_url.startswith("sqlite"):
    connect_args = {"check_same_thread": False}

engine = create_engine(
    settings.database_url,
    connect_args=connect_args,
    poolclass=StaticPool if settings.database_url.startswith("sqlite:///:memory:") else None,
    echo=False,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def init_db():
    # Import all models to register with Base
    from .models.user import User
    from .models.subject import Subject
    from .models.book import Book, UserBookActivation
    from .models.book_node import BookNode
    from .models.test_set import TestSet
    from .models.question import Question, QuestionTopicMap
    from .models.test_session import TestSession, TestSessionQuestion
    from .models.attempt import QuestionAttempt
    from .models.goal import WeeklyGoal, WeeklyGoalItem
    from .models.task import Task, DailyTaskPlacement
    from .models.schedule import Schedule, ClassSession
    from .models.academic import TaughtLesson, Homework, Exam, ExamQuestion, ExamSubjectResult
    from .models.review import ReviewQueue
    from .models.social import Group, GroupMember, SharingPermission
    from .models.telegram import TelegramConnection
    from .models.snapshot import PerformanceSnapshot
    Base.metadata.create_all(bind=engine)
