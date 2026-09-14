from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime

class TestSessionCreate(BaseModel):
    book_id: Optional[int] = None
    test_set_id: Optional[int] = None
    book_node_ids: List[int] = []  # topics
    test_type: str = "normal"  # normal, checkup, chapter_exam, comprehensive, concours, mock, custom
    mode: str = "timed"  # timed, untimed
    time_limit_seconds: Optional[int] = None
    question_count: int = 10
    difficulty_levels: List[int] = []  # filter by difficulty 1,2,3
    exclude_recent_days: Optional[int] = None
    task_id: Optional[int] = None
    title: Optional[str] = None

class TestSessionOut(BaseModel):
    id: int
    user_id: int
    book_id: Optional[int] = None
    test_set_id: Optional[int] = None
    task_id: Optional[int] = None
    title: Optional[str] = None
    test_type: str
    status: str
    mode: str
    time_limit_seconds: Optional[int] = None
    elapsed_seconds: Optional[int] = None
    started_at: datetime
    finished_at: Optional[datetime] = None
    total_questions: int
    correct_count: int
    wrong_count: int
    unanswered_count: int
    questions: List['TestSessionQuestionOut'] = []
    
    class Config:
        from_attributes = True

class TestSessionQuestionOut(BaseModel):
    id: int
    test_session_id: int
    question_id: int
    order_index: int
    user_answer: Optional[str] = None
    is_correct: Optional[bool] = None
    is_answered: bool
    answered_at: Optional[datetime] = None
    time_spent_seconds: Optional[int] = None
    question: Optional['QuestionDetailOut'] = None
    
    class Config:
        from_attributes = True

class QuestionDetailOut(BaseModel):
    id: int
    stable_id: str
    question_text: Optional[str] = None
    question_text_fa: Optional[str] = None
    image_url: Optional[str] = None
    option_a: Optional[str] = None
    option_b: Optional[str] = None
    option_c: Optional[str] = None
    option_d: Optional[str] = None
    difficulty_level: Optional[int] = None
    book_id: int
    test_set_id: Optional[int] = None
    
    class Config:
        from_attributes = True

class AnswerSubmit(BaseModel):
    question_id: int
    answer: Optional[str] = None  # A,B,C,D or None for unanswered
    time_spent_seconds: Optional[int] = None

class AnswerSubmitBatch(BaseModel):
    answers: List[AnswerSubmit]

class TestFinishRequest(BaseModel):
    elapsed_seconds: Optional[int] = None
    finish_token: Optional[str] = None

class TestResultOut(BaseModel):
    id: int
    status: str
    total_questions: int
    correct_count: int
    wrong_count: int
    unanswered_count: int
    accuracy: Optional[float] = None
    elapsed_seconds: Optional[int] = None
    questions: List[TestSessionQuestionOut] = []
    topic_performance: List['TopicPerformance'] = []
    difficulty_performance: List['DifficultyPerformance'] = []
    
    class Config:
        from_attributes = True

class TopicPerformance(BaseModel):
    book_node_id: int
    node_title: str
    total: int
    correct: int
    wrong: int
    unanswered: int
    accuracy: Optional[float] = None

class DifficultyPerformance(BaseModel):
    difficulty_level: int
    total: int
    correct: int
    wrong: int
    accuracy: Optional[float] = None

TestSessionOut.model_rebuild()
TestSessionQuestionOut.model_rebuild()
TestResultOut.model_rebuild()
