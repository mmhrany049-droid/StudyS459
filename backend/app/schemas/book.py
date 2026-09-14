from pydantic import BaseModel
from typing import Optional, List, Any, Dict
from datetime import datetime

class SubjectOut(BaseModel):
    id: int
    stable_id: str
    name: str
    name_fa: Optional[str] = None
    color: Optional[str] = None
    
    class Config:
        from_attributes = True

class BookOut(BaseModel):
    id: int
    stable_id: str
    subject_id: int
    title: str
    title_fa: Optional[str] = None
    publisher: Optional[str] = None
    edition: Optional[str] = None
    description: Optional[str] = None
    hierarchy_config: Optional[Any] = None
    is_active: bool
    subject: Optional[SubjectOut] = None
    
    class Config:
        from_attributes = True

class BookNodeOut(BaseModel):
    id: int
    book_id: int
    stable_id: str
    parent_id: Optional[int] = None
    node_type: str
    title: str
    title_fa: Optional[str] = None
    order_index: int
    level: int
    children: List['BookNodeOut'] = []
    
    class Config:
        from_attributes = True

class BookNodeCreate(BaseModel):
    book_id: int
    stable_id: str
    parent_id: Optional[int] = None
    node_type: str
    title: str
    title_fa: Optional[str] = None
    order_index: int = 0
    level: int = 0

class TestSetOut(BaseModel):
    id: int
    book_id: int
    stable_id: str
    node_id: Optional[int] = None
    title: str
    title_fa: Optional[str] = None
    test_type: str
    difficulty_level: Optional[int] = None
    is_comprehensive: bool
    question_count: int = 0
    
    class Config:
        from_attributes = True

class QuestionOut(BaseModel):
    id: int
    book_id: int
    test_set_id: Optional[int] = None
    stable_id: str
    question_text: Optional[str] = None
    question_text_fa: Optional[str] = None
    image_url: Optional[str] = None
    option_a: Optional[str] = None
    option_b: Optional[str] = None
    option_c: Optional[str] = None
    option_d: Optional[str] = None
    correct_option: Optional[str] = None  # Only for authorized contexts
    difficulty_level: Optional[int] = None
    is_concours: bool
    concours_year: Optional[int] = None
    topic_node_ids: List[int] = []
    
    class Config:
        from_attributes = True

class QuestionCreate(BaseModel):
    book_id: int
    test_set_id: Optional[int] = None
    stable_id: str
    question_text: Optional[str] = None
    question_text_fa: Optional[str] = None
    option_a: Optional[str] = None
    option_b: Optional[str] = None
    option_c: Optional[str] = None
    option_d: Optional[str] = None
    correct_option: Optional[str] = None
    difficulty_level: Optional[int] = None
    topic_node_ids: List[int] = []
    order_index: int = 0

class UserBookActivationOut(BaseModel):
    id: int
    user_id: int
    book_id: int
    is_active: bool
    book: Optional[BookOut] = None
    
    class Config:
        from_attributes = True

class BookImportRequest(BaseModel):
    book_data: Dict[str, Any]
    nodes: List[Dict[str, Any]]
    test_sets: List[Dict[str, Any]] = []
    questions: List[Dict[str, Any]] = []

BookNodeOut.model_rebuild()
