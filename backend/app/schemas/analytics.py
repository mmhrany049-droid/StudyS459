from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from datetime import datetime

class VolumeMetrics(BaseModel):
    total_tests: int
    total_questions: int
    total_time_seconds: int
    average_duration: Optional[float] = None

class CoverageMetrics(BaseModel):
    total_questions_in_pool: int
    attempted_questions: int
    coverage_percent: float
    unseen_count: int

class AccuracyMetrics(BaseModel):
    correct: int
    wrong: int
    unanswered: int
    answered_total: int
    accuracy_percent: float  # correct / answered

class MasteryMetrics(BaseModel):
    mastery_percent: float
    estimated_level: str  # weak, medium, strong
    calculation_method: str

class AnalyticsOverview(BaseModel):
    volume: VolumeMetrics
    coverage: CoverageMetrics
    accuracy: AccuracyMetrics
    mastery: MasteryMetrics
    trends: List[Dict[str, Any]] = []

class TopicAnalytics(BaseModel):
    book_node_id: int
    node_title: str
    node_type: str
    level: int
    volume: VolumeMetrics
    coverage: CoverageMetrics
    accuracy: AccuracyMetrics
    mastery: MasteryMetrics
    children: List['TopicAnalytics'] = []

class BookAnalytics(BaseModel):
    book_id: int
    book_title: str
    volume: VolumeMetrics
    coverage: CoverageMetrics
    accuracy: AccuracyMetrics
    mastery: MasteryMetrics
    topics: List[TopicAnalytics] = []

class QuestionHistoryOut(BaseModel):
    question_id: int
    stable_id: str
    attempts: List[Dict[str, Any]]
    latest_result: Optional[str] = None
    total_attempts: int
    correct_count: int
    wrong_count: int

class WeaknessOut(BaseModel):
    book_node_id: int
    node_title: str
    accuracy: float
    total_attempts: int
    wrong_count: int
    last_attempted: Optional[str] = None

class ProgressResponse(BaseModel):
    overall: AnalyticsOverview
    by_subject: List[Dict[str, Any]] = []
    by_book: List[BookAnalytics] = []
    weakest_topics: List[WeaknessOut] = []
    recent_mistakes: List[Dict[str, Any]] = []
    unseen_questions_summary: Dict[str, Any] = {}

TopicAnalytics.model_rebuild()
