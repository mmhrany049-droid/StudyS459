from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from ...database import get_db
from ...schemas.test import TestSessionCreate, TestSessionOut, TestSessionQuestionOut, AnswerSubmit, AnswerSubmitBatch, TestFinishRequest, TestResultOut
from ...services import test_service
from ..deps import get_current_user
from ...models.user import User

router = APIRouter(prefix="/test-sessions", tags=["Test Sessions"])

@router.post("/", response_model=TestSessionOut)
def create_session(
    data: TestSessionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    session = test_service.create_test_session(
        db=db,
        user_id=current_user.id,
        book_id=data.book_id,
        test_set_id=data.test_set_id,
        book_node_ids=data.book_node_ids,
        test_type=data.test_type,
        mode=data.mode,
        time_limit_seconds=data.time_limit_seconds,
        question_count=data.question_count,
        difficulty_levels=data.difficulty_levels,
        exclude_recent_days=data.exclude_recent_days,
        task_id=data.task_id,
        title=data.title
    )
    # Load with questions
    db.refresh(session)
    # Build response
    sq_out = []
    for sq in session.session_questions:
        q = sq.question
        sq_out.append(TestSessionQuestionOut(
            id=sq.id,
            test_session_id=sq.test_session_id,
            question_id=sq.question_id,
            order_index=sq.order_index,
            user_answer=sq.user_answer,
            is_correct=sq.is_correct,
            is_answered=sq.is_answered,
            answered_at=sq.answered_at,
            time_spent_seconds=sq.time_spent_seconds,
            question={
                "id": q.id,
                "stable_id": q.stable_id,
                "question_text": q.question_text,
                "question_text_fa": q.question_text_fa,
                "image_url": q.image_url,
                "option_a": q.option_a,
                "option_b": q.option_b,
                "option_c": q.option_c,
                "option_d": q.option_d,
                "difficulty_level": q.difficulty_level,
                "book_id": q.book_id,
                "test_set_id": q.test_set_id
            } if q else None
        ))
    
    return TestSessionOut(
        id=session.id,
        user_id=session.user_id,
        book_id=session.book_id,
        test_set_id=session.test_set_id,
        task_id=session.task_id,
        title=session.title,
        test_type=session.test_type,
        status=session.status,
        mode=session.mode,
        time_limit_seconds=session.time_limit_seconds,
        elapsed_seconds=session.elapsed_seconds,
        started_at=session.started_at,
        finished_at=session.finished_at,
        total_questions=session.total_questions,
        correct_count=session.correct_count,
        wrong_count=session.wrong_count,
        unanswered_count=session.unanswered_count,
        questions=sq_out
    )

@router.get("/", response_model=List[TestSessionOut])
def list_sessions(
    status: Optional[str] = None,
    book_id: Optional[int] = None,
    limit: int = Query(50, le=200),
    offset: int = 0,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    sessions = test_service.get_user_test_sessions(db, current_user.id, status=status, book_id=book_id, limit=limit, offset=offset)
    result = []
    for s in sessions:
        result.append(TestSessionOut(
            id=s.id,
            user_id=s.user_id,
            book_id=s.book_id,
            test_set_id=s.test_set_id,
            task_id=s.task_id,
            title=s.title,
            test_type=s.test_type,
            status=s.status,
            mode=s.mode,
            time_limit_seconds=s.time_limit_seconds,
            elapsed_seconds=s.elapsed_seconds,
            started_at=s.started_at,
            finished_at=s.finished_at,
            total_questions=s.total_questions,
            correct_count=s.correct_count,
            wrong_count=s.wrong_count,
            unanswered_count=s.unanswered_count,
            questions=[]
        ))
    return result

@router.get("/{session_id}", response_model=TestSessionOut)
def get_session(session_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    session = test_service.get_test_session(db, session_id, current_user.id)
    sq_out = []
    for sq in session.session_questions:
        q = sq.question
        sq_out.append(TestSessionQuestionOut(
            id=sq.id,
            test_session_id=sq.test_session_id,
            question_id=sq.question_id,
            order_index=sq.order_index,
            user_answer=sq.user_answer,
            is_correct=sq.is_correct,
            is_answered=sq.is_answered,
            answered_at=sq.answered_at,
            time_spent_seconds=sq.time_spent_seconds,
            question={
                "id": q.id,
                "stable_id": q.stable_id,
                "question_text": q.question_text,
                "question_text_fa": q.question_text_fa,
                "image_url": q.image_url,
                "option_a": q.option_a,
                "option_b": q.option_b,
                "option_c": q.option_c,
                "option_d": q.option_d,
                "difficulty_level": q.difficulty_level,
                "book_id": q.book_id,
                "test_set_id": q.test_set_id
            } if q else None
        ))
    return TestSessionOut(
        id=session.id,
        user_id=session.user_id,
        book_id=session.book_id,
        test_set_id=session.test_set_id,
        task_id=session.task_id,
        title=session.title,
        test_type=session.test_type,
        status=session.status,
        mode=session.mode,
        time_limit_seconds=session.time_limit_seconds,
        elapsed_seconds=session.elapsed_seconds,
        started_at=session.started_at,
        finished_at=session.finished_at,
        total_questions=session.total_questions,
        correct_count=session.correct_count,
        wrong_count=session.wrong_count,
        unanswered_count=session.unanswered_count,
        questions=sq_out
    )

@router.post("/{session_id}/answer")
def submit_answer(
    session_id: int,
    answer: AnswerSubmit,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    sq = test_service.submit_answer(db, session_id, current_user.id, answer.question_id, answer.answer, answer.time_spent_seconds)
    return {"status": "ok", "session_question_id": sq.id}

@router.post("/{session_id}/answers/batch")
def submit_answers_batch(
    session_id: int,
    batch: AnswerSubmitBatch,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    answers = [{"question_id": a.question_id, "answer": a.answer, "time_spent_seconds": a.time_spent_seconds} for a in batch.answers]
    result = test_service.submit_answers_batch(db, session_id, current_user.id, answers)
    return {"status": "ok", "updated": len(result)}

@router.post("/{session_id}/finish", response_model=TestSessionOut)
def finish_session(
    session_id: int,
    finish_req: TestFinishRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    session = test_service.finish_test_session(db, session_id, current_user.id, elapsed_seconds=finish_req.elapsed_seconds, finish_token=finish_req.finish_token)
    return TestSessionOut(
        id=session.id,
        user_id=session.user_id,
        book_id=session.book_id,
        test_set_id=session.test_set_id,
        task_id=session.task_id,
        title=session.title,
        test_type=session.test_type,
        status=session.status,
        mode=session.mode,
        time_limit_seconds=session.time_limit_seconds,
        elapsed_seconds=session.elapsed_seconds,
        started_at=session.started_at,
        finished_at=session.finished_at,
        total_questions=session.total_questions,
        correct_count=session.correct_count,
        wrong_count=session.wrong_count,
        unanswered_count=session.unanswered_count,
        questions=[]
    )

@router.get("/{session_id}/result", response_model=TestResultOut)
def get_result(session_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    session = test_service.get_test_session(db, session_id, current_user.id)
    if session.status not in ["finished", "pending_correction"]:
        raise HTTPException(status_code=400, detail="Session not finished yet")
    
    sq_out = []
    topic_perf_map = {}
    diff_perf_map = {}
    
    for sq in session.session_questions:
        q = sq.question
        sq_out.append(TestSessionQuestionOut(
            id=sq.id,
            test_session_id=sq.test_session_id,
            question_id=sq.question_id,
            order_index=sq.order_index,
            user_answer=sq.user_answer,
            is_correct=sq.is_correct,
            is_answered=sq.is_answered,
            answered_at=sq.answered_at,
            time_spent_seconds=sq.time_spent_seconds,
            question={
                "id": q.id,
                "stable_id": q.stable_id,
                "question_text": q.question_text,
                "question_text_fa": q.question_text_fa,
                "image_url": q.image_url,
                "option_a": q.option_a,
                "option_b": q.option_b,
                "option_c": q.option_c,
                "option_d": q.option_d,
                "difficulty_level": q.difficulty_level,
                "book_id": q.book_id,
                "test_set_id": q.test_set_id
            } if q else None
        ))
        
        # Topic performance aggregation
        if q:
            for tm in q.topic_maps:
                node_id = tm.book_node_id
                if node_id not in topic_perf_map:
                    topic_perf_map[node_id] = {"total": 0, "correct": 0, "wrong": 0, "unanswered": 0, "node_title": tm.book_node.title if tm.book_node else f"Node {node_id}"}
                topic_perf_map[node_id]["total"] += 1
                if sq.user_answer is None:
                    topic_perf_map[node_id]["unanswered"] += 1
                elif sq.is_correct:
                    topic_perf_map[node_id]["correct"] += 1
                else:
                    topic_perf_map[node_id]["wrong"] += 1
            
            # Difficulty
            diff = q.difficulty_level or 0
            if diff not in diff_perf_map:
                diff_perf_map[diff] = {"total": 0, "correct": 0, "wrong": 0}
            diff_perf_map[diff]["total"] += 1
            if sq.is_correct:
                diff_perf_map[diff]["correct"] += 1
            elif sq.is_correct is False:
                diff_perf_map[diff]["wrong"] += 1
    
    topic_performance = []
    for node_id, data in topic_perf_map.items():
        acc = (data["correct"] / (data["correct"] + data["wrong"]) * 100) if (data["correct"] + data["wrong"]) > 0 else 0
        topic_performance.append({
            "book_node_id": node_id,
            "node_title": data["node_title"],
            "total": data["total"],
            "correct": data["correct"],
            "wrong": data["wrong"],
            "unanswered": data["unanswered"],
            "accuracy": acc
        })
    
    difficulty_performance = []
    for diff_level, data in diff_perf_map.items():
        acc = (data["correct"] / (data["correct"] + data["wrong"]) * 100) if (data["correct"] + data["wrong"]) > 0 else 0
        difficulty_performance.append({
            "difficulty_level": diff_level,
            "total": data["total"],
            "correct": data["correct"],
            "wrong": data["wrong"],
            "accuracy": acc
        })
    
    total_answered = session.correct_count + session.wrong_count
    accuracy = (session.correct_count / total_answered * 100) if total_answered > 0 else 0
    
    return TestResultOut(
        id=session.id,
        status=session.status,
        total_questions=session.total_questions,
        correct_count=session.correct_count,
        wrong_count=session.wrong_count,
        unanswered_count=session.unanswered_count,
        accuracy=accuracy,
        elapsed_seconds=session.elapsed_seconds,
        questions=sq_out,
        topic_performance=topic_performance,
        difficulty_performance=difficulty_performance
    )

@router.post("/{session_id}/correct-pending", response_model=TestSessionOut)
def correct_pending(session_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    session = test_service.correct_pending_session(db, session_id, current_user.id)
    return TestSessionOut(
        id=session.id,
        user_id=session.user_id,
        book_id=session.book_id,
        test_set_id=session.test_set_id,
        task_id=session.task_id,
        title=session.title,
        test_type=session.test_type,
        status=session.status,
        mode=session.mode,
        time_limit_seconds=session.time_limit_seconds,
        elapsed_seconds=session.elapsed_seconds,
        started_at=session.started_at,
        finished_at=session.finished_at,
        total_questions=session.total_questions,
        correct_count=session.correct_count,
        wrong_count=session.wrong_count,
        unanswered_count=session.unanswered_count,
        questions=[]
    )

@router.get("/questions/{question_id}/history")
def question_history(question_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    history = test_service.get_question_history(db, current_user.id, question_id)
    return history
