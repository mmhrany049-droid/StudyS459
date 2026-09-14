from sqlalchemy.orm import Session
from sqlalchemy import func, and_
from typing import List, Dict, Optional
from datetime import datetime, timezone, timedelta
from ..models.attempt import QuestionAttempt
from ..models.question import Question, QuestionTopicMap
from ..models.book_node import BookNode
from ..models.book import Book
from ..models.test_session import TestSession
from ..analytics.coverage import calculate_coverage, calculate_volume, calculate_accuracy
from ..analytics.mastery import calculate_mastery, calculate_topic_mastery, mastery_level_from_percent

def get_overall_analytics(db: Session, user_id: int) -> Dict:
    volume = calculate_volume(db, user_id)
    coverage = calculate_coverage(db, user_id)
    accuracy = calculate_accuracy(db, user_id)
    
    # Mastery overall
    mastery_percent = calculate_mastery(
        correct=accuracy["correct"],
        wrong=accuracy["wrong"],
        total_attempts=volume["total_questions"],
        coverage=coverage["coverage_percent"]/100 if coverage["coverage_percent"] else 0
    )
    
    # Trends - last 7 days daily snapshots
    trends = []
    for i in range(7):
        date = datetime.now(timezone.utc) - timedelta(days=i)
        day_start = date.replace(hour=0, minute=0, second=0, microsecond=0)
        day_end = day_start + timedelta(days=1)
        day_attempts = db.query(QuestionAttempt).filter(
            QuestionAttempt.user_id == user_id,
            QuestionAttempt.created_at >= day_start,
            QuestionAttempt.created_at < day_end
        ).all()
        day_correct = sum(1 for a in day_attempts if a.is_correct)
        trends.append({
            "date": day_start.strftime("%Y-%m-%d"),
            "attempts": len(day_attempts),
            "correct": day_correct,
            "accuracy": (day_correct / len([a for a in day_attempts if a.is_correct is not None]) * 100) if day_attempts else 0
        })
    trends.reverse()
    
    return {
        "volume": volume,
        "coverage": coverage,
        "accuracy": accuracy,
        "mastery": {
            "mastery_percent": mastery_percent,
            "estimated_level": mastery_level_from_percent(mastery_percent),
            "calculation_method": "accuracy * coverage * attempt_factor"
        },
        "trends": trends
    }

def get_book_analytics(db: Session, user_id: int, book_id: int) -> Dict:
    volume = calculate_volume(db, user_id, book_id=book_id)
    coverage = calculate_coverage(db, user_id, book_id=book_id)
    accuracy = calculate_accuracy(db, user_id, book_id=book_id)
    
    mastery_percent = calculate_mastery(
        correct=accuracy["correct"],
        wrong=accuracy["wrong"],
        total_attempts=volume["total_questions"],
        coverage=coverage["coverage_percent"]/100 if coverage["coverage_percent"] else 0
    )
    
    # Topic breakdown
    nodes = db.query(BookNode).filter(BookNode.book_id == book_id).all()
    topics = []
    for node in nodes:
        # Skip if node has children? Include all but we can hierarchical later
        node_volume = calculate_volume(db, user_id, book_id=book_id)  # simplified, should filter by node
        # For node-specific, need attempts that map to node via question topic map
        question_ids = db.query(QuestionTopicMap.question_id).filter(QuestionTopicMap.book_node_id == node.id).distinct()
        node_attempts_query = db.query(QuestionAttempt).filter(
            QuestionAttempt.user_id == user_id,
            QuestionAttempt.question_id.in_(question_ids)
        )
        node_attempts = node_attempts_query.all()
        
        total_q_in_node = db.query(QuestionTopicMap).filter(QuestionTopicMap.book_node_id == node.id).count()
        
        topic_mastery_data = calculate_topic_mastery(
            attempts=[{"question_id": a.question_id, "is_correct": a.is_correct, "created_at": a.created_at} for a in node_attempts],
            total_questions_in_topic=total_q_in_node
        )
        
        topics.append({
            "book_node_id": node.id,
            "node_title": node.title,
            "node_type": node.node_type,
            "level": node.level,
            "volume": {"total_questions": len(node_attempts)},
            "coverage": {"coverage_percent": topic_mastery_data["coverage"]},
            "accuracy": {"accuracy_percent": topic_mastery_data["accuracy"]},
            "mastery": {"mastery_percent": topic_mastery_data["mastery"]},
            "children": []
        })
    
    return {
        "book_id": book_id,
        "volume": volume,
        "coverage": coverage,
        "accuracy": accuracy,
        "mastery": {
            "mastery_percent": mastery_percent,
            "estimated_level": mastery_level_from_percent(mastery_percent),
            "calculation_method": "accuracy * coverage"
        },
        "topics": topics
    }

def get_weakest_topics(db: Session, user_id: int, limit: int = 10) -> List[Dict]:
    # Find nodes where accuracy low and attempts sufficient
    nodes = db.query(BookNode).all()
    weaknesses = []
    for node in nodes:
        question_ids = db.query(QuestionTopicMap.question_id).filter(QuestionTopicMap.book_node_id == node.id).distinct()
        attempts = db.query(QuestionAttempt).filter(
            QuestionAttempt.user_id == user_id,
            QuestionAttempt.question_id.in_(question_ids)
        ).all()
        if len(attempts) < 3:
            continue
        correct = sum(1 for a in attempts if a.is_correct is True)
        wrong = sum(1 for a in attempts if a.is_correct is False)
        answered = correct + wrong
        if answered == 0:
            continue
        accuracy = correct / answered * 100
        if accuracy < 70:  # threshold for weakness
            last_attempt = max((a.created_at for a in attempts), default=None)
            weaknesses.append({
                "book_node_id": node.id,
                "node_title": node.title,
                "accuracy": accuracy,
                "total_attempts": len(attempts),
                "wrong_count": wrong,
                "last_attempted": last_attempt.strftime("%Y-%m-%d") if last_attempt else None
            })
    weaknesses.sort(key=lambda x: x["accuracy"])
    return weaknesses[:limit]

def get_recent_mistakes(db: Session, user_id: int, limit: int = 20) -> List[Dict]:
    attempts = db.query(QuestionAttempt).filter(
        QuestionAttempt.user_id == user_id,
        QuestionAttempt.is_correct == False
    ).order_by(QuestionAttempt.created_at.desc()).limit(limit).all()
    
    result = []
    for att in attempts:
        q = db.query(Question).filter(Question.id == att.question_id).first()
        result.append({
            "attempt_id": att.id,
            "question_id": att.question_id,
            "question_stable_id": q.stable_id if q else None,
            "question_text": q.question_text_fa or q.question_text if q else None,
            "created_at": att.created_at.isoformat(),
            "book_id": att.book_id
        })
    return result

def get_progress_detailed(db: Session, user_id: int) -> Dict:
    overall = get_overall_analytics(db, user_id)
    
    # By book
    books = db.query(Book).all()
    by_book = []
    for book in books:
        analytics = get_book_analytics(db, user_id, book.id)
        by_book.append({
            "book_id": book.id,
            "book_title": book.title_fa or book.title,
            "subject_id": book.subject_id,
            **analytics
        })
    
    # By subject aggregation
    from ..models.subject import Subject
    subjects = db.query(Subject).all()
    by_subject = []
    for subj in subjects:
        subj_books = [b for b in books if b.subject_id == subj.id]
        if not subj_books:
            continue
        subj_book_ids = [b.id for b in subj_books]
        vol = calculate_volume(db, user_id)  # simplified aggregate
        # Filter for subject books
        subj_attempts = db.query(QuestionAttempt).filter(
            QuestionAttempt.user_id == user_id,
            QuestionAttempt.book_id.in_(subj_book_ids)
        ).all()
        subj_correct = sum(1 for a in subj_attempts if a.is_correct)
        subj_wrong = sum(1 for a in subj_attempts if a.is_correct is False)
        subj_answered = subj_correct + subj_wrong
        subj_accuracy = (subj_correct / subj_answered * 100) if subj_answered else 0
        by_subject.append({
            "subject_id": subj.id,
            "subject_name": subj.name_fa or subj.name,
            "total_questions": len(subj_attempts),
            "accuracy": subj_accuracy,
            "book_count": len(subj_books)
        })
    
    weakest = get_weakest_topics(db, user_id)
    recent_mistakes = get_recent_mistakes(db, user_id)
    
    # Unseen summary
    total_q = db.query(Question).count()
    attempted_q = db.query(QuestionAttempt.question_id).filter(QuestionAttempt.user_id == user_id).distinct().count()
    unseen_summary = {
        "total_questions": total_q,
        "attempted": attempted_q,
        "unseen": total_q - attempted_q,
        "coverage_percent": (attempted_q / total_q * 100) if total_q else 0
    }
    
    return {
        "overall": overall,
        "by_subject": by_subject,
        "by_book": by_book,
        "weakest_topics": weakest,
        "recent_mistakes": recent_mistakes,
        "unseen_questions_summary": unseen_summary
    }

def get_question_history(db: Session, user_id: int, question_id: int) -> Dict:
    attempts = db.query(QuestionAttempt).filter(
        QuestionAttempt.user_id == user_id,
        QuestionAttempt.question_id == question_id
    ).order_by(QuestionAttempt.created_at.asc()).all()
    
    correct = sum(1 for a in attempts if a.is_correct is True)
    wrong = sum(1 for a in attempts if a.is_correct is False)
    
    q = db.query(Question).filter(Question.id == question_id).first()
    
    return {
        "question_id": question_id,
        "stable_id": q.stable_id if q else None,
        "attempts": [
            {
                "id": a.id,
                "user_answer": a.user_answer,
                "correct_answer": a.correct_answer,
                "is_correct": a.is_correct,
                "is_unanswered": a.is_unanswered,
                "created_at": a.created_at.isoformat(),
                "time_spent_seconds": a.time_spent_seconds
            } for a in attempts
        ],
        "latest_result": attempts[-1].is_correct if attempts else None,
        "total_attempts": len(attempts),
        "correct_count": correct,
        "wrong_count": wrong
    }
