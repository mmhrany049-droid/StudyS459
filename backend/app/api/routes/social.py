from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from typing import List, Optional
from ...database import get_db
from ...schemas.social import GroupCreate, GroupOut, GroupMemberOut, SharingPermissionCreate, SharingPermissionOut, ComparisonRequest, ComparisonResult
from ...services import social_service
from ..deps import get_current_user
from ...models.user import User

router = APIRouter(prefix="/social", tags=["Social"])

@router.post("/groups", response_model=GroupOut)
def create_group(data: GroupCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    group = social_service.create_group(db, current_user.id, name=data.name, description=data.description, group_type=data.group_type)
    # Build out
    count = db.query(social_service.GroupMember).filter(social_service.GroupMember.group_id == group.id).count()
    return GroupOut(
        id=group.id,
        name=group.name,
        description=group.description,
        group_type=group.group_type,
        invite_code=group.invite_code,
        created_by=group.created_by,
        member_count=count
    )

@router.get("/groups", response_model=List[GroupOut])
def list_groups(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    groups = social_service.get_user_groups(db, current_user.id)
    result = []
    for g in groups:
        result.append(GroupOut(
            id=g.id,
            name=g.name,
            description=g.description,
            group_type=g.group_type,
            invite_code=g.invite_code,
            created_by=g.created_by,
            member_count=getattr(g, 'member_count', 0)
        ))
    return result

@router.post("/groups/join")
def join_group(invite_code: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    group = social_service.join_group_by_code(db, current_user.id, invite_code)
    return {"status": "joined", "group_id": group.id, "group_name": group.name}

@router.get("/groups/{group_id}/members", response_model=List[GroupMemberOut])
def group_members(group_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    members = social_service.get_group_members(db, group_id, current_user.id)
    return members

@router.post("/sharing", response_model=SharingPermissionOut)
def set_sharing(data: SharingPermissionCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    perm = social_service.set_sharing_permission(db, current_user.id, data.group_id, data.permission_type, data.is_allowed)
    return perm

@router.get("/sharing", response_model=List[SharingPermissionOut])
def list_sharing(group_id: Optional[int] = None, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return social_service.get_sharing_permissions(db, current_user.id, group_id=group_id)

@router.post("/compare")
def compare(data: ComparisonRequest, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    results = social_service.compare_group_metrics(db, current_user.id, data.group_id, book_id=data.book_id, metric=data.metric)
    return results
