from typing import List, Dict
from ..config.settings import settings
from datetime import datetime, timezone, timedelta

def calculate_mastery(
    correct: int,
    wrong: int,
    total_attempts: int,
    coverage: float,
    recent_correct: int = 0,
    recent_total: int = 0,
    difficulty_weight: float = 1.0
) -> float:
    """
    Configurable mastery formula - open decision isolated here
    Default: weighted combination, not just accuracy
    """
    if total_attempts == 0:
        return 0.0
    
    # Accuracy component
    answered = correct + wrong
    accuracy = (correct / answered) if answered > 0 else 0.0
    
    # Coverage component - mastery cannot exceed coverage significantly
    # If coverage low, mastery limited
    # Example: 25% coverage with 72% accuracy != 72% overall mastery
    # Mastery = accuracy * coverage * adjustment
    
    # Apply configurable weights
    correct_weight = settings.mastery_correct_weight
    wrong_penalty = settings.mastery_wrong_penalty
    
    # Base mastery from accuracy and coverage
    # Using formula: mastery = (accuracy * coverage) adjusted by attempts
    base_mastery = accuracy * coverage
    
    # Adjust for minimum attempts
    min_attempts = settings.mastery_min_attempts_for_mastery
    if total_attempts < min_attempts:
        # Scale down if not enough attempts
        attempt_factor = total_attempts / min_attempts
        base_mastery *= attempt_factor
    
    # Difficulty weighting
    if settings.difficulty_weighting_enabled:
        base_mastery *= difficulty_weight
    
    # Ensure 0-100 range
    mastery_percent = max(0.0, min(100.0, base_mastery * 100))
    return mastery_percent

def calculate_topic_mastery(attempts: List[Dict], total_questions_in_topic: int) -> Dict:
    """
    Calculate mastery for a topic from raw attempts
    """
    if not attempts:
        return {"mastery": 0.0, "accuracy": 0.0, "coverage": 0.0}
    
    correct = sum(1 for a in attempts if a.get("is_correct") is True)
    wrong = sum(1 for a in attempts if a.get("is_correct") is False)
    answered = correct + wrong
    
    # Coverage: unique questions attempted / total in pool
    unique_attempted = len(set(a.get("question_id") for a in attempts))
    coverage = (unique_attempted / total_questions_in_topic) if total_questions_in_topic > 0 else 0.0
    
    accuracy = (correct / answered) if answered > 0 else 0.0
    
    # Recent performance (last 30 days)
    cutoff = datetime.now(timezone.utc) - timedelta(days=30)
    recent = [a for a in attempts if a.get("created_at") and a.get("created_at") >= cutoff]
    recent_correct = sum(1 for a in recent if a.get("is_correct") is True)
    recent_total = len([a for a in recent if a.get("is_correct") is not None])
    
    mastery = calculate_mastery(correct, wrong, len(attempts), coverage, recent_correct, recent_total)
    
    return {
        "mastery": mastery,
        "accuracy": accuracy * 100,
        "coverage": coverage * 100,
        "correct": correct,
        "wrong": wrong,
        "total_attempts": len(attempts),
        "unique_attempted": unique_attempted,
        "total_in_pool": total_questions_in_topic
    }

def mastery_level_from_percent(percent: float) -> str:
    if percent < 30:
        return "weak"
    elif percent < 60:
        return "medium"
    elif percent < 85:
        return "strong"
    else:
        return "mastered"
