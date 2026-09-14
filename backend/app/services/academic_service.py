from sqlalchemy.orm import Session
from fastapi import HTTPException
from typing import List, Optional
from datetime import datetime, timezone
from ..models.schedule import Schedule, ClassSession
from ..models.academic import TaughtLesson, Homework, Exam, ExamQuestion, ExamSubjectResult
from ..models.book import Book
from ..models.book_node import BookNode
from ..models.subject import Subject
from ..models.task import Task
import json

# Schedules
def create_schedule(db: Session, user_id: int, data: dict):
    sched = Schedule(
        user_id=user_id,
        title=data.get("title"),
        schedule_type=data.get("schedule_type", "school"),
        day_of_week=data.get("day_of_week"),
        start_time=data.get("start_time"),
        end_time=data.get("end_time"),
        is_recurring=data.get("is_recurring", True),
        specific_date=data.get("specific_date"),
        subject_id=data.get("subject_id"),
        book_id=data.get("book_id"),
        location=data.get("location"),
        description=data.get("description")
    )
    db.add(sched)
    db.commit()
    db.refresh(sched)
    return sched

def get_schedules(db: Session, user_id: int, day_of_week: Optional[str] = None):
    q = db.query(Schedule).filter(Schedule.user_id == user_id)
    if day_of_week:
        q = q.filter(Schedule.day_of_week == day_of_week)
    return q.order_by(Schedule.start_time).all()

def get_schedule(db: Session, schedule_id: int, user_id: int):
    sched = db.query(Schedule).filter(Schedule.id == schedule_id, Schedule.user_id == user_id).first()
    if not sched:
        raise HTTPException(status_code=404, detail="Schedule not found")
    return sched

def update_schedule(db: Session, schedule_id: int, user_id: int, updates: dict):
    sched = get_schedule(db, schedule_id, user_id)
    for k, v in updates.items():
        if hasattr(sched, k):
            setattr(sched, k, v)
    db.commit()
    db.refresh(sched)
    return sched

def delete_schedule(db: Session, schedule_id: int, user_id: int):
    sched = get_schedule(db, schedule_id, user_id)
    db.delete(sched)
    db.commit()
    return True

# Class Sessions
def create_class_session(db: Session, user_id: int, data: dict):
    session = ClassSession(
        user_id=user_id,
        schedule_id=data.get("schedule_id"),
        date=data.get("date"),
        title=data.get("title"),
        attended=data.get("attended", True),
        notes=data.get("notes")
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    return session

def get_class_sessions(db: Session, user_id: int, date: Optional[str] = None):
    q = db.query(ClassSession).filter(ClassSession.user_id == user_id)
    if date:
        q = q.filter(ClassSession.date == date)
    return q.order_by(ClassSession.date.desc()).all()

# Taught Lessons - TAUGHT != LEARNED
def create_taught_lesson(db: Session, user_id: int, data: dict):
    # Validate book/node if provided
    book_id = data.get("book_id")
    book_node_id = data.get("book_node_id")
    if book_id:
        book = db.query(Book).filter(Book.id == book_id).first()
        if not book:
            raise HTTPException(status_code=400, detail="Invalid book_id")
    if book_node_id:
        node = db.query(BookNode).filter(BookNode.id == book_node_id).first()
        if not node:
            raise HTTPException(status_code=400, detail="Invalid book_node_id")
    
    lesson = TaughtLesson(
        user_id=user_id,
        class_session_id=data.get("class_session_id"),
        book_id=book_id,
        book_node_id=book_node_id,
        title=data.get("title"),
        notes=data.get("notes"),
        taught_date=data.get("taught_date")
    )
    db.add(lesson)
    db.commit()
    db.refresh(lesson)
    return lesson

def get_taught_lessons(db: Session, user_id: int, book_id: Optional[int] = None):
    q = db.query(TaughtLesson).filter(TaughtLesson.user_id == user_id)
    if book_id:
        q = q.filter(TaughtLesson.book_id == book_id)
    return q.order_by(TaughtLesson.taught_date.desc()).all()

# Homework
def create_homework(db: Session, user_id: int, data: dict):
    hw = Homework(
        user_id=user_id,
        title=data.get("title"),
        description=data.get("description"),
        source=data.get("source", "manual"),
        subject_id=data.get("subject_id"),
        book_id=data.get("book_id"),
        book_node_id=data.get("book_node_id"),
        due_date=data.get("due_date"),
        estimated_time_minutes=data.get("estimated_time_minutes", 30),
        priority=data.get("priority", 0),
        status=data.get("status", "pending")
    )
    db.add(hw)
    db.flush()
    
    # Generate planner Task for homework
    task = Task(
        user_id=user_id,
        title=f"تکلیف: {hw.title}",
        title_fa=f"تکلیف: {hw.title}",
        description=hw.description,
        source="homework",
        source_id=hw.id,
        book_id=hw.book_id,
        book_node_id=hw.book_node_id,
        task_type="homework",
        status="pending",
        priority=hw.priority,
        estimated_duration_minutes=hw.estimated_time_minutes,
        reason=f"تکلیف با مهلت {hw.due_date}" if hw.due_date else "تکلیف",
        reason_structured=json.dumps([{"type": "homework", "description": f"Homework {hw.title}", "description_fa": f"تکلیف {hw.title}", "weight": 2.0}], ensure_ascii=False),
        due_date=hw.due_date
    )
    db.add(task)
    db.flush()
    hw.task_id = task.id
    
    db.commit()
    db.refresh(hw)
    return hw

def get_homework_list(db: Session, user_id: int, status: Optional[str] = None):
    q = db.query(Homework).filter(Homework.user_id == user_id)
    if status:
        q = q.filter(Homework.status == status)
    return q.order_by(Homework.due_date.asc()).all()

def update_homework(db: Session, hw_id: int, user_id: int, updates: dict):
    hw = db.query(Homework).filter(Homework.id == hw_id, Homework.user_id == user_id).first()
    if not hw:
        raise HTTPException(status_code=404, detail="Homework not found")
    for k, v in updates.items():
        if hasattr(hw, k):
            setattr(hw, k, v)
    hw.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(hw)
    return hw

def delete_homework(db: Session, hw_id: int, user_id: int):
    hw = db.query(Homework).filter(Homework.id == hw_id, Homework.user_id == user_id).first()
    if not hw:
        raise HTTPException(status_code=404, detail="Homework not found")
    # Also delete linked task?
    if hw.task_id:
        task = db.query(Task).filter(Task.id == hw.task_id).first()
        if task:
            db.delete(task)
    db.delete(hw)
    db.commit()
    return True

# Exams
def create_exam(db: Session, user_id: int, data: dict):
    exam = Exam(
        user_id=user_id,
        name=data.get("name"),
        exam_type=data.get("exam_type", "school"),
        provider=data.get("provider"),
        exam_date=data.get("exam_date"),
        total_questions=data.get("total_questions"),
        duration_minutes=data.get("duration_minutes"),
        correct_count=data.get("correct_count", 0),
        wrong_count=data.get("wrong_count", 0),
        unanswered_count=data.get("unanswered_count", 0),
        percentage=data.get("percentage"),
        score=data.get("score"),
        notes=data.get("notes")
    )
    db.add(exam)
    db.flush()
    
    questions_data = data.get("questions", [])
    for q_data in questions_data:
        eq = ExamQuestion(
            exam_id=exam.id,
            question_number=q_data.get("question_number"),
            subject_id=q_data.get("subject_id"),
            book_id=q_data.get("book_id"),
            book_node_id=q_data.get("book_node_id"),
            question_image_url=q_data.get("question_image_url"),
            correct_answer=q_data.get("correct_answer"),
            user_answer=q_data.get("user_answer"),
            is_correct=q_data.get("is_correct"),
            is_unanswered=q_data.get("is_unanswered", False)
        )
        db.add(eq)
    
    db.commit()
    db.refresh(exam)
    return exam

def get_exams(db: Session, user_id: int, exam_type: Optional[str] = None):
    q = db.query(Exam).filter(Exam.user_id == user_id)
    if exam_type:
        q = q.filter(Exam.exam_type == exam_type)
    return q.order_by(Exam.exam_date.desc()).all()

def get_exam_detail(db: Session, exam_id: int, user_id: int):
    exam = db.query(Exam).filter(Exam.id == exam_id, Exam.user_id == user_id).first()
    if not exam:
        raise HTTPException(status_code=404, detail="Exam not found")
    return exam

def delete_exam(db: Session, exam_id: int, user_id: int):
    exam = get_exam_detail(db, exam_id, user_id)
    db.delete(exam)
    db.commit()
    return True
