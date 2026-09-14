import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.database import Base
from app.models.user import User
from app.models.subject import Subject
from app.models.book import Book
from app.models.book_node import BookNode
from app.services import goal_service, planner_service
from app.services.auth_service import get_password_hash
from datetime import datetime, timedelta

engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

@pytest.fixture
def db():
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    yield db
    db.close()
    Base.metadata.drop_all(bind=engine)

def test_goals_count_only_topic_only_both(db):
    user = User(email="test@test.com", username="testuser", hashed_password=get_password_hash("pass"))
    db.add(user)
    db.commit()
    subj = Subject(stable_id="subj", name="Subj")
    db.add(subj)
    db.commit()
    book = Book(stable_id="book", subject_id=subj.id, title="Book")
    db.add(book)
    db.commit()
    node = BookNode(book_id=book.id, stable_id="node1", node_type="عنوان", title="Node1", level=0)
    db.add(node)
    db.commit()
    
    # Count-only goal
    goal_count = goal_service.create_weekly_goal(db, user_id=user.id, week_start_date="2024-01-06", week_end_date="2024-01-12", test_count_goal=5, items=[])
    assert goal_count.test_count_goal == 5
    assert not goal_count.topic_goal_enabled
    
    # Topic-only
    goal_topic = goal_service.create_weekly_goal(db, user_id=user.id, week_start_date="2024-01-13", week_end_date="2024-01-19", test_count_goal=None, items=[{"book_id": book.id, "book_node_id": node.id, "target_tests": 2}])
    assert goal_topic.topic_goal_enabled
    assert len(goal_topic.items) == 1
    
    # Both
    goal_both = goal_service.create_weekly_goal(db, user_id=user.id, week_start_date="2024-01-20", week_end_date="2024-01-26", test_count_goal=10, items=[{"book_id": book.id, "book_node_id": node.id, "target_tests": 3}])
    assert goal_both.test_count_goal == 10
    assert goal_both.topic_goal_enabled
    
    # Generate candidate tasks - topic goals drive selection, count controls volume
    tasks = goal_service.generate_candidate_tasks_from_goal(db, weekly_goal_id=goal_both.id, user_id=user.id)
    # Should create tasks based on topic goal
    assert len(tasks) >= 1

def test_planner_capacity_warning(db):
    from app.models.schedule import Schedule
    user = User(email="test2@test.com", username="testuser2", hashed_password=get_password_hash("pass"))
    db.add(user)
    db.commit()
    
    # Add school schedule 8am-2pm (6 hours busy)
    sched = Schedule(user_id=user.id, title="School", schedule_type="school", day_of_week="saturday", start_time="08:00", end_time="14:00")
    db.add(sched)
    db.commit()
    
    from app.planning.capacity import calculate_available_capacity, check_over_capacity
    cap = calculate_available_capacity(db, user.id, "2024-01-06", "saturday")
    # Baseline 10h = 600min - 360 busy = 240 available
    assert cap == 600 - 360
    
    # Create task that exceeds capacity
    task = planner_service.create_task(db, user.id, {"title": "Long task", "estimated_duration_minutes": 500})
    placement = planner_service.create_placement(db, user.id, task.id, "2024-01-06", "saturday", 0)
    
    check = check_over_capacity(db, user.id, "2024-01-06", "saturday")
    assert check["is_over_capacity"] == True
    # System must warn, NOT silently delete
    assert check["planned_minutes"] == 500

def test_catchup_priorities(db):
    user = User(email="test3@test.com", username="testuser3", hashed_password=get_password_hash("pass"))
    db.add(user)
    db.commit()
    
    # Create tasks with different priorities
    t_overdue = planner_service.create_task(db, user.id, {"title": "Overdue", "due_date": "2024-01-01", "priority": 0, "estimated_duration_minutes": 30})
    t_homework = planner_service.create_task(db, user.id, {"title": "Homework", "task_type": "homework", "source": "homework", "priority": 0})
    t_goal = planner_service.create_task(db, user.id, {"title": "Goal", "weekly_goal_id": 1, "priority": 0})
    t_review = planner_service.create_task(db, user.id, {"title": "Review", "source": "review", "priority": 0})
    t_other = planner_service.create_task(db, user.id, {"title": "Other", "priority": 0})
    
    from app.planning.catchup import get_catchup_candidates
    candidates = get_catchup_candidates(db, user.id)
    
    # Check priority order: overdue first, then homework, goal, review, other
    # Our scoring: overdue 100, homework 70, goal 60, review 50, other priority
    assert candidates[0].title == "Overdue"
    assert candidates[1].title == "Homework"
