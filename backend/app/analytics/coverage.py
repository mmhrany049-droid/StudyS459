from typing import List, Dict, Set
from sqlalchemy.orm import Session
from ..models.question import Question
from ..models.attempt import QuestionAttempt

def calculate_coverage(
    db: Session,
    user_id: int,
    book_id: int = None,
    book_node_id: int = None
) -> Dict:
    """
    Strict distinction between volume, coverage, accuracy, mastery
    """
    # Total questions in pool
    q_query = db.query(Question)
    if book_id:
        q_query = q_query.filter(Question.book_id == book_id)
    if book_node_id:
        from ..models.question import QuestionTopicMap
        q_query = q_query.join(QuestionTopicMap, QuestionTopicMap.question_id == Question.id).filter(QuestionTopicMap.book_node_id == book_node_id)
    total_in_pool = q_query.count()
    
    # Attempted questions (unique)
    attempt_query = db.query(QuestionAttempt).filter(QuestionAttempt.user_id == user_id)
    if book_id:
        attempt_query = attempt_query.filter(QuestionAttempt.book_id == book_id)
    # For node filtering, need join via question topic map - simplified: filter by question ids that map to node
    if book_node_id:
        from ..models.question import QuestionTopicMap
        question_ids_in_node = db.query(QuestionTopicMap.question_id).filter(QuestionTopicMap.book_node_id == book_node_id).distinct()
        attempt_query = attempt_query.filter(QuestionAttempt.question_id.in_(question_ids_in_node))
    
    all_attempts = attempt_query.all()
    unique_attempted = len(set(a.question_id for a in all_attempts))
    
    coverage_percent = (unique_attempted / total_in_pool * 100) if total_in_pool > 0 else 0.0
    unseen_count = total_in_pool - unique_attempted
    
    return {
        "total_questions_in_pool": total_in_pool,
        "attempted_questions": unique_attempted,
        "coverage_percent": coverage_percent,
        "unseen_count": unseen_count,
        "total_attempts": len(all_attempts)
    }

def calculate_volume(db: Session, user_id: int, book_id: int = None, days: int = None) -> Dict:
    from datetime import datetime, timedelta, timezone
    query = db.query(QuestionAttempt).filter(QuestionAttempt.user_id == user_id)
    if book_id:
        query = query.filter(QuestionAttempt.book_id == book_id)
    if days:
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        query = query.filter(QuestionAttempt.created_at >= cutoff)
    
    attempts = query.all()
    total_questions = len(attempts)
    
    # Total tests
    from ..models.test_session import TestSession
    test_query = db.query(TestSession).filter(TestSession.user_id == user_id)
    if book_id:
        test_query = test_query.filter(TestSession.book_id == book_id)
    if days:
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        test_query = test_query.filter(TestSession.started_at >= cutoff)
    total_tests = test_query.count()
    
    total_time = sum(a.time_spent_seconds or 0 for a in attempts)
    avg_duration = (total_time / total_questions) if total_questions > 0 else 0
    
    return {
        "total_tests": total_tests,
        "total_questions": total_questions,
        "total_time_seconds": total_time,
        "average_duration": avg_duration
    }

def calculate_accuracy(db: Session, user_id: int, book_id: int = None, book_node_id: int = None) -> Dict:
    query = db.query(QuestionAttempt).filter(QuestionAttempt.user_id == user_id)
    if book_id:
        query = query.filter(QuestionAttempt.book_id == book_id)
    if book_node_id:
        from ..models.question import QuestionTopicMap
        question_ids_in_node = db.query(QuestionTopicMap.question_id).filter(QuestionTopicMap.book_node_id == book_node_id).distinct()
        query = query.filter(QuestionAttempt.question_id.in_(question_ids_in_node))
    
    attempts = query.all()
    correct = sum(1 for a in attempts if a.is_correct is True)
    wrong = sum(1 for a in attempts if a.is_correct is False)
    unanswered = sum(1 for a in attempts if a.is_unanswered)
    answered_total = correct + wrong
    accuracy = (correct / answered_total * 100) if answered_total > 0 else 0.0
    
    return {
        "correct": correct,
        "wrong": wrong,
        "unanswered": unanswered,
        "answered_total": answered_total,
        "accuracy_percent": accuracy
    }
