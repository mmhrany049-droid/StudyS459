from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime

class ScheduleCreate(BaseModel):
    title: str
    schedule_type: str = "school"
    day_of_week: str
    start_time: str
    end_time: str
    is_recurring: bool = True
    specific_date: Optional[str] = None
    subject_id: Optional[int] = None
    book_id: Optional[int] = None
    location: Optional[str] = None
    description: Optional[str] = None

class ScheduleOut(BaseModel):
    id: int
    user_id: int
    title: str
    schedule_type: str
    day_of_week: str
    start_time: str
    end_time: str
    is_recurring: bool
    specific_date: Optional[str] = None
    subject_id: Optional[int] = None
    book_id: Optional[int] = None
    location: Optional[str] = None
    description: Optional[str] = None
    
    class Config:
        from_attributes = True

class ClassSessionCreate(BaseModel):
    schedule_id: Optional[int] = None
    date: str
    title: Optional[str] = None
    attended: bool = True
    notes: Optional[str] = None

class ClassSessionOut(BaseModel):
    id: int
    user_id: int
    schedule_id: Optional[int] = None
    date: str
    title: Optional[str] = None
    attended: bool
    notes: Optional[str] = None
    
    class Config:
        from_attributes = True

class TaughtLessonCreate(BaseModel):
    class_session_id: Optional[int] = None
    book_id: Optional[int] = None
    book_node_id: Optional[int] = None
    title: Optional[str] = None
    notes: Optional[str] = None
    taught_date: str

class TaughtLessonOut(BaseModel):
    id: int
    user_id: int
    class_session_id: Optional[int] = None
    book_id: Optional[int] = None
    book_node_id: Optional[int] = None
    title: Optional[str] = None
    notes: Optional[str] = None
    taught_date: str
    book_title: Optional[str] = None
    node_title: Optional[str] = None
    
    class Config:
        from_attributes = True

class HomeworkCreate(BaseModel):
    title: str
    description: Optional[str] = None
    source: str = "manual"
    subject_id: Optional[int] = None
    book_id: Optional[int] = None
    book_node_id: Optional[int] = None
    due_date: Optional[str] = None
    estimated_time_minutes: int = 30
    priority: int = 0
    status: str = "pending"

class HomeworkOut(BaseModel):
    id: int
    user_id: int
    title: str
    description: Optional[str] = None
    source: str
    subject_id: Optional[int] = None
    book_id: Optional[int] = None
    book_node_id: Optional[int] = None
    due_date: Optional[str] = None
    estimated_time_minutes: int
    priority: int
    status: str
    task_id: Optional[int] = None
    book_title: Optional[str] = None
    node_title: Optional[str] = None
    
    class Config:
        from_attributes = True

class ExamQuestionCreate(BaseModel):
    question_number: int
    subject_id: Optional[int] = None
    book_id: Optional[int] = None
    book_node_id: Optional[int] = None
    question_image_url: Optional[str] = None
    correct_answer: Optional[str] = None
    user_answer: Optional[str] = None
    is_correct: Optional[bool] = None
    is_unanswered: bool = False

class ExamCreate(BaseModel):
    name: str
    exam_type: str = "school"
    provider: Optional[str] = None
    exam_date: str
    total_questions: Optional[int] = None
    duration_minutes: Optional[int] = None
    correct_count: int = 0
    wrong_count: int = 0
    unanswered_count: int = 0
    percentage: Optional[float] = None
    score: Optional[float] = None
    notes: Optional[str] = None
    questions: List[ExamQuestionCreate] = []

class ExamOut(BaseModel):
    id: int
    user_id: int
    name: str
    exam_type: str
    provider: Optional[str] = None
    exam_date: str
    total_questions: Optional[int] = None
    duration_minutes: Optional[int] = None
    correct_count: int
    wrong_count: int
    unanswered_count: int
    percentage: Optional[float] = None
    score: Optional[float] = None
    notes: Optional[str] = None
    
    class Config:
        from_attributes = True

class ExamDetailOut(ExamOut):
    questions: List['ExamQuestionOut'] = []

class ExamQuestionOut(BaseModel):
    id: int
    exam_id: int
    question_number: int
    subject_id: Optional[int] = None
    book_id: Optional[int] = None
    book_node_id: Optional[int] = None
    correct_answer: Optional[str] = None
    user_answer: Optional[str] = None
    is_correct: Optional[bool] = None
    is_unanswered: bool
    
    class Config:
        from_attributes = True

ExamDetailOut.model_rebuild()
