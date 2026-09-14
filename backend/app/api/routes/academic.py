from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from ...database import get_db
from ...schemas.academic import ScheduleCreate, ScheduleOut, ClassSessionCreate, ClassSessionOut, TaughtLessonCreate, TaughtLessonOut, HomeworkCreate, HomeworkOut, ExamCreate, ExamOut, ExamDetailOut
from ...services import academic_service
from ..deps import get_current_user
from ...models.user import User

router = APIRouter(prefix="/academic", tags=["Academic"])

# Schedules
@router.post("/schedules", response_model=ScheduleOut)
def create_schedule(data: ScheduleCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return academic_service.create_schedule(db, current_user.id, data.model_dump())

@router.get("/schedules", response_model=List[ScheduleOut])
def list_schedules(day_of_week: Optional[str] = None, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return academic_service.get_schedules(db, current_user.id, day_of_week=day_of_week)

@router.patch("/schedules/{schedule_id}", response_model=ScheduleOut)
def update_schedule(schedule_id: int, updates: dict, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return academic_service.update_schedule(db, schedule_id, current_user.id, updates)

@router.delete("/schedules/{schedule_id}")
def delete_schedule(schedule_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    academic_service.delete_schedule(db, schedule_id, current_user.id)
    return {"status": "deleted"}

# Class Sessions
@router.post("/class-sessions", response_model=ClassSessionOut)
def create_class_session(data: ClassSessionCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return academic_service.create_class_session(db, current_user.id, data.model_dump())

@router.get("/class-sessions", response_model=List[ClassSessionOut])
def list_class_sessions(date: Optional[str] = None, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return academic_service.get_class_sessions(db, current_user.id, date=date)

# Taught Lessons
@router.post("/taught-lessons", response_model=TaughtLessonOut)
def create_taught_lesson(data: TaughtLessonCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    lesson = academic_service.create_taught_lesson(db, current_user.id, data.model_dump())
    return build_taught_lesson_out(db, lesson)

@router.get("/taught-lessons", response_model=List[TaughtLessonOut])
def list_taught_lessons(book_id: Optional[int] = None, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    lessons = academic_service.get_taught_lessons(db, current_user.id, book_id=book_id)
    return [build_taught_lesson_out(db, l) for l in lessons]

# Homework
@router.post("/homework", response_model=HomeworkOut)
def create_homework(data: HomeworkCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    hw = academic_service.create_homework(db, current_user.id, data.model_dump())
    return build_homework_out(db, hw)

@router.get("/homework", response_model=List[HomeworkOut])
def list_homework(status: Optional[str] = None, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    hws = academic_service.get_homework_list(db, current_user.id, status=status)
    return [build_homework_out(db, hw) for hw in hws]

@router.patch("/homework/{hw_id}", response_model=HomeworkOut)
def update_homework(hw_id: int, updates: dict, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    hw = academic_service.update_homework(db, hw_id, current_user.id, updates)
    return build_homework_out(db, hw)

@router.delete("/homework/{hw_id}")
def delete_homework(hw_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    academic_service.delete_homework(db, hw_id, current_user.id)
    return {"status": "deleted"}

# Exams
@router.post("/exams", response_model=ExamOut)
def create_exam(data: ExamCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return academic_service.create_exam(db, current_user.id, data.model_dump())

@router.get("/exams", response_model=List[ExamOut])
def list_exams(exam_type: Optional[str] = None, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return academic_service.get_exams(db, current_user.id, exam_type=exam_type)

@router.get("/exams/{exam_id}", response_model=ExamDetailOut)
def get_exam(exam_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    exam = academic_service.get_exam_detail(db, exam_id, current_user.id)
    from ...models.academic import ExamQuestion
    questions = db.query(ExamQuestion).filter(ExamQuestion.exam_id == exam.id).all()
    return ExamDetailOut(
        id=exam.id,
        user_id=exam.user_id,
        name=exam.name,
        exam_type=exam.exam_type,
        provider=exam.provider,
        exam_date=exam.exam_date,
        total_questions=exam.total_questions,
        duration_minutes=exam.duration_minutes,
        correct_count=exam.correct_count,
        wrong_count=exam.wrong_count,
        unanswered_count=exam.unanswered_count,
        percentage=exam.percentage,
        score=exam.score,
        notes=exam.notes,
        questions=[
            {
                "id": q.id,
                "exam_id": q.exam_id,
                "question_number": q.question_number,
                "subject_id": q.subject_id,
                "book_id": q.book_id,
                "book_node_id": q.book_node_id,
                "correct_answer": q.correct_answer,
                "user_answer": q.user_answer,
                "is_correct": q.is_correct,
                "is_unanswered": q.is_unanswered
            } for q in questions
        ]
    )

@router.delete("/exams/{exam_id}")
def delete_exam(exam_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    academic_service.delete_exam(db, exam_id, current_user.id)
    return {"status": "deleted"}

def build_taught_lesson_out(db, lesson):
    from ...models.book import Book
    from ...models.book_node import BookNode
    book_title = None
    node_title = None
    if lesson.book_id:
        book = db.query(Book).filter(Book.id == lesson.book_id).first()
        if book:
            book_title = book.title_fa or book.title
    if lesson.book_node_id:
        node = db.query(BookNode).filter(BookNode.id == lesson.book_node_id).first()
        if node:
            node_title = node.title_fa or node.title
    return TaughtLessonOut(
        id=lesson.id,
        user_id=lesson.user_id,
        class_session_id=lesson.class_session_id,
        book_id=lesson.book_id,
        book_node_id=lesson.book_node_id,
        title=lesson.title,
        notes=lesson.notes,
        taught_date=lesson.taught_date,
        book_title=book_title,
        node_title=node_title
    )

def build_homework_out(db, hw):
    from ...models.book import Book
    from ...models.book_node import BookNode
    book_title = None
    node_title = None
    if hw.book_id:
        book = db.query(Book).filter(Book.id == hw.book_id).first()
        if book:
            book_title = book.title_fa or book.title
    if hw.book_node_id:
        node = db.query(BookNode).filter(BookNode.id == hw.book_node_id).first()
        if node:
            node_title = node.title_fa or node.title
    return HomeworkOut(
        id=hw.id,
        user_id=hw.user_id,
        title=hw.title,
        description=hw.description,
        source=hw.source,
        subject_id=hw.subject_id,
        book_id=hw.book_id,
        book_node_id=hw.book_node_id,
        due_date=hw.due_date,
        estimated_time_minutes=hw.estimated_time_minutes,
        priority=hw.priority,
        status=hw.status,
        task_id=hw.task_id,
        book_title=book_title,
        node_title=node_title
    )
