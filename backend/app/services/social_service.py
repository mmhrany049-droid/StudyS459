from sqlalchemy.orm import Session
from fastapi import HTTPException
from typing import List, Optional
import secrets
import string
from ..models.social import Group, GroupMember, SharingPermission
from ..models.user import User
from ..models.attempt import QuestionAttempt
from ..models.test_session import TestSession
from ..models.question import Question

def generate_invite_code(length=8):
    alphabet = string.ascii_uppercase + string.digits
    return ''.join(secrets.choice(alphabet) for _ in range(length))

def create_group(db: Session, user_id: int, name: str, description: Optional[str] = None, group_type: str = "class"):
    invite_code = generate_invite_code()
    # Ensure unique
    while db.query(Group).filter(Group.invite_code == invite_code).first():
        invite_code = generate_invite_code()
    
    group = Group(
        name=name,
        description=description,
        group_type=group_type,
        invite_code=invite_code,
        created_by=user_id
    )
    db.add(group)
    db.flush()
    
    # Add creator as owner
    member = GroupMember(
        group_id=group.id,
        user_id=user_id,
        role="owner"
    )
    db.add(member)
    db.commit()
    db.refresh(group)
    return group

def get_user_groups(db: Session, user_id: int):
    # Groups where user is member
    group_ids = db.query(GroupMember.group_id).filter(GroupMember.user_id == user_id).distinct()
    groups = db.query(Group).filter(Group.id.in_(group_ids)).all()
    # Add member count
    result = []
    for g in groups:
        count = db.query(GroupMember).filter(GroupMember.group_id == g.id).count()
        g.member_count = count
        result.append(g)
    return result

def get_group(db: Session, group_id: int, user_id: int):
    # Check if user is member
    membership = db.query(GroupMember).filter(GroupMember.group_id == group_id, GroupMember.user_id == user_id).first()
    if not membership:
        raise HTTPException(status_code=403, detail="Not a member of this group")
    group = db.query(Group).filter(Group.id == group_id).first()
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")
    return group

def join_group_by_code(db: Session, user_id: int, invite_code: str):
    group = db.query(Group).filter(Group.invite_code == invite_code).first()
    if not group:
        raise HTTPException(status_code=404, detail="Invalid invite code")
    
    existing = db.query(GroupMember).filter(GroupMember.group_id == group.id, GroupMember.user_id == user_id).first()
    if existing:
        raise HTTPException(status_code=400, detail="Already a member")
    
    member = GroupMember(
        group_id=group.id,
        user_id=user_id,
        role="member"
    )
    db.add(member)
    db.commit()
    return group

def get_group_members(db: Session, group_id: int, user_id: int):
    get_group(db, group_id, user_id)  # check membership
    members = db.query(GroupMember).filter(GroupMember.group_id == group_id).all()
    result = []
    for m in members:
        user = db.query(User).filter(User.id == m.user_id).first()
        result.append({
            "id": m.id,
            "group_id": m.group_id,
            "user_id": m.user_id,
            "role": m.role,
            "joined_at": m.joined_at,
            "username": user.username if user else None,
            "full_name": user.full_name if user else None
        })
    return result

def set_sharing_permission(db: Session, user_id: int, group_id: int, permission_type: str, is_allowed: bool):
    # Check group membership
    membership = db.query(GroupMember).filter(GroupMember.group_id == group_id, GroupMember.user_id == user_id).first()
    if not membership:
        raise HTTPException(status_code=403, detail="Not a member")
    
    perm = db.query(SharingPermission).filter(
        SharingPermission.user_id == user_id,
        SharingPermission.group_id == group_id,
        SharingPermission.permission_type == permission_type
    ).first()
    
    if perm:
        perm.is_allowed = is_allowed
    else:
        perm = SharingPermission(
            user_id=user_id,
            group_id=group_id,
            permission_type=permission_type,
            is_allowed=is_allowed
        )
        db.add(perm)
    
    db.commit()
    db.refresh(perm)
    return perm

def get_sharing_permissions(db: Session, user_id: int, group_id: Optional[int] = None):
    q = db.query(SharingPermission).filter(SharingPermission.user_id == user_id)
    if group_id:
        q = q.filter(SharingPermission.group_id == group_id)
    return q.all()

def compare_group_metrics(db: Session, user_id: int, group_id: int, book_id: Optional[int] = None, metric: str = "accuracy"):
    """
    Private-by-default, opt-in sharing
    Potential comparisons: number of tests, average percentage/accuracy, wrong count, coverage, progress changes, topic performance, common-question performance
    Requires stable book/question IDs
    """
    # Check membership
    get_group(db, group_id, user_id)
    
    members = db.query(GroupMember).filter(GroupMember.group_id == group_id).all()
    results = []
    
    for member in members:
        member_user_id = member.user_id
        
        # Check if this member allows sharing for this metric
        perm = db.query(SharingPermission).filter(
            SharingPermission.user_id == member_user_id,
            SharingPermission.group_id == group_id,
            SharingPermission.permission_type == metric
        ).first()
        
        # If requesting user is not the member themselves, need permission
        if member_user_id != user_id:
            if not perm or not perm.is_allowed:
                continue  # skip private
        
        # Calculate metric
        metric_value = 0
        details = {}
        
        if metric == "tests_count":
            query = db.query(TestSession).filter(TestSession.user_id == member_user_id, TestSession.status == "finished")
            if book_id:
                query = query.filter(TestSession.book_id == book_id)
            metric_value = query.count()
            details = {"total_tests": metric_value}
        
        elif metric == "accuracy":
            attempts = db.query(QuestionAttempt).filter(QuestionAttempt.user_id == member_user_id)
            if book_id:
                attempts = attempts.filter(QuestionAttempt.book_id == book_id)
            attempts = attempts.all()
            correct = sum(1 for a in attempts if a.is_correct is True)
            wrong = sum(1 for a in attempts if a.is_correct is False)
            answered = correct + wrong
            accuracy = (correct / answered * 100) if answered > 0 else 0
            metric_value = accuracy
            details = {"correct": correct, "wrong": wrong, "accuracy": accuracy}
        
        elif metric == "coverage":
            from ..models.question import Question
            total_q = db.query(Question).count()
            if book_id:
                total_q = db.query(Question).filter(Question.book_id == book_id).count()
            attempted = db.query(QuestionAttempt.question_id).filter(QuestionAttempt.user_id == member_user_id)
            if book_id:
                attempted = attempted.filter(QuestionAttempt.book_id == book_id)
            attempted_count = attempted.distinct().count()
            coverage = (attempted_count / total_q * 100) if total_q else 0
            metric_value = coverage
            details = {"attempted": attempted_count, "total": total_q, "coverage": coverage}
        
        elif metric == "common_questions":
            # Common-question comparison requires stable book/question IDs
            # Find questions attempted by both requesting user and this member
            requesting_user_questions = set(
                qid for (qid,) in db.query(QuestionAttempt.question_id).filter(QuestionAttempt.user_id == user_id).distinct().all()
            )
            member_questions = set(
                qid for (qid,) in db.query(QuestionAttempt.question_id).filter(QuestionAttempt.user_id == member_user_id).distinct().all()
            )
            common = requesting_user_questions.intersection(member_questions)
            # Compare performance on common
            common_correct_user = 0
            common_correct_member = 0
            for qid in common:
                # Get latest attempt for each
                user_attempt = db.query(QuestionAttempt).filter(QuestionAttempt.user_id == user_id, QuestionAttempt.question_id == qid).order_by(QuestionAttempt.created_at.desc()).first()
                member_attempt = db.query(QuestionAttempt).filter(QuestionAttempt.user_id == member_user_id, QuestionAttempt.question_id == qid).order_by(QuestionAttempt.created_at.desc()).first()
                if user_attempt and user_attempt.is_correct:
                    common_correct_user += 1
                if member_attempt and member_attempt.is_correct:
                    common_correct_member += 1
            
            metric_value = len(common)
            details = {
                "common_questions": len(common),
                "user_correct_on_common": common_correct_user,
                "member_correct_on_common": common_correct_member
            }
        
        else:
            metric_value = 0
        
        user_obj = db.query(User).filter(User.id == member_user_id).first()
        results.append({
            "user_id": member_user_id,
            "username": user_obj.username if user_obj else f"user_{member_user_id}",
            "metric_value": metric_value,
            "details": details
        })
    
    # Sort by metric_value descending
    results.sort(key=lambda x: x["metric_value"], reverse=True)
    return results
