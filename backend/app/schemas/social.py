from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime

class GroupCreate(BaseModel):
    name: str
    description: Optional[str] = None
    group_type: str = "class"

class GroupOut(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    group_type: str
    invite_code: Optional[str] = None
    created_by: Optional[int] = None
    member_count: int = 0
    
    class Config:
        from_attributes = True

class GroupMemberOut(BaseModel):
    id: int
    group_id: int
    user_id: int
    role: str
    joined_at: datetime
    username: Optional[str] = None
    full_name: Optional[str] = None
    
    class Config:
        from_attributes = True

class SharingPermissionCreate(BaseModel):
    group_id: int
    permission_type: str
    is_allowed: bool = True

class SharingPermissionOut(BaseModel):
    id: int
    user_id: int
    group_id: int
    permission_type: str
    is_allowed: bool
    
    class Config:
        from_attributes = True

class ComparisonRequest(BaseModel):
    group_id: int
    book_id: Optional[int] = None
    metric: str = "accuracy"  # tests_count, accuracy, coverage, etc

class ComparisonResult(BaseModel):
    user_id: int
    username: str
    metric_value: float
    details: dict = {}
