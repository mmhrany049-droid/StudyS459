from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Boolean, Text, Index, UniqueConstraint
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
from ..database import Base

class Group(Base):
    __tablename__ = "groups"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    group_type = Column(String, default="class")  # class, study_group, friends
    invite_code = Column(String, unique=True, nullable=True, index=True)
    
    created_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    
    members = relationship("GroupMember", back_populates="group", cascade="all, delete-orphan")
    creator = relationship("User")

class GroupMember(Base):
    __tablename__ = "group_members"
    __table_args__ = (
        UniqueConstraint('group_id', 'user_id', name='uq_group_user'),
        Index('ix_group_member_user', 'user_id'),
    )
    
    id = Column(Integer, primary_key=True, index=True)
    group_id = Column(Integer, ForeignKey("groups.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    
    role = Column(String, default="member")  # member, admin, owner - configurable open decision
    joined_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    
    group = relationship("Group", back_populates="members")
    user = relationship("User", back_populates="group_memberships")

class SharingPermission(Base):
    """
    Private-by-default. Opt-in sharing.
    """
    __tablename__ = "sharing_permissions"
    __table_args__ = (
        UniqueConstraint('user_id', 'group_id', 'permission_type', name='uq_sharing_perm'),
    )
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    group_id = Column(Integer, ForeignKey("groups.id", ondelete="CASCADE"), nullable=False, index=True)
    
    permission_type = Column(String, nullable=False)  # tests_count, accuracy, coverage, topic_performance, common_questions, progress
    is_allowed = Column(Boolean, default=False)
    
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    
    user = relationship("User", back_populates="sharing_permissions")
    group = relationship("Group")
