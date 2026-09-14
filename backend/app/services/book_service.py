from sqlalchemy.orm import Session
from sqlalchemy import and_
from fastapi import HTTPException
from typing import List, Optional, Dict, Any
import json
from ..models.book import Book, UserBookActivation
from ..models.book_node import BookNode
from ..models.test_set import TestSet
from ..models.question import Question, QuestionTopicMap
from ..models.subject import Subject

def get_subjects(db: Session):
    return db.query(Subject).all()

def create_subject(db: Session, stable_id: str, name: str, name_fa: Optional[str] = None, color: Optional[str] = None):
    existing = db.query(Subject).filter(Subject.stable_id == stable_id).first()
    if existing:
        raise HTTPException(status_code=400, detail=f"Subject stable_id {stable_id} already exists")
    subj = Subject(stable_id=stable_id, name=name, name_fa=name_fa, color=color)
    db.add(subj)
    db.commit()
    db.refresh(subj)
    return subj

def get_books(db: Session, subject_id: Optional[int] = None, active_only: bool = False):
    q = db.query(Book)
    if subject_id:
        q = q.filter(Book.subject_id == subject_id)
    if active_only:
        q = q.filter(Book.is_active == True)
    return q.all()

def get_book_by_stable_id(db: Session, stable_id: str):
    return db.query(Book).filter(Book.stable_id == stable_id).first()

def create_book(db: Session, stable_id: str, subject_id: int, title: str, title_fa: Optional[str] = None, publisher: Optional[str] = None, hierarchy_config: Optional[Dict] = None, description: Optional[str] = None):
    existing = db.query(Book).filter(Book.stable_id == stable_id).first()
    if existing:
        raise HTTPException(status_code=400, detail=f"Book stable_id {stable_id} already exists")
    book = Book(stable_id=stable_id, subject_id=subject_id, title=title, title_fa=title_fa, publisher=publisher, hierarchy_config=hierarchy_config, description=description)
    db.add(book)
    db.commit()
    db.refresh(book)
    return book

def get_book_nodes(db: Session, book_id: int):
    return db.query(BookNode).filter(BookNode.book_id == book_id).order_by(BookNode.level, BookNode.order_index).all()

def build_node_tree(nodes: List[BookNode]) -> List[Dict]:
    # Build tree from flat list
    node_map = {n.id: {"node": n, "children": []} for n in nodes}
    roots = []
    for n in nodes:
        if n.parent_id and n.parent_id in node_map:
            node_map[n.parent_id]["children"].append(node_map[n.id])
        else:
            roots.append(node_map[n.id])
    # sort children by order_index
    def sort_tree(item):
        item["children"].sort(key=lambda x: x["node"].order_index)
        for child in item["children"]:
            sort_tree(child)
    for r in roots:
        sort_tree(r)
    roots.sort(key=lambda x: x["node"].order_index)
    return roots

def get_book_node_tree(db: Session, book_id: int):
    nodes = get_book_nodes(db, book_id)
    return build_node_tree(nodes)

def validate_no_cycle(nodes_data: List[Dict[str, Any]]):
    # nodes_data: list of dict with stable_id, parent_stable_id
    # Build graph and detect cycles via DFS
    graph = {}
    for nd in nodes_data:
        sid = nd.get("stable_id")
        parent = nd.get("parent_stable_id")
        graph[sid] = parent
    
    visited = set()
    rec_stack = set()
    
    def dfs(node_id):
        if node_id is None:
            return False
        if node_id in rec_stack:
            return True  # cycle
        if node_id in visited:
            return False
        visited.add(node_id)
        rec_stack.add(node_id)
        parent = graph.get(node_id)
        if parent and parent in graph:
            if dfs(parent):
                return True
        rec_stack.remove(node_id)
        return False
    
    for nid in graph:
        if dfs(nid):
            raise HTTPException(status_code=400, detail=f"Cyclic hierarchy detected involving {nid}")

def create_book_node(db: Session, book_id: int, stable_id: str, node_type: str, title: str, parent_id: Optional[int] = None, title_fa: Optional[str] = None, order_index: int = 0, level: int = 0):
    # check duplicate stable_id within book
    existing = db.query(BookNode).filter(BookNode.book_id == book_id, BookNode.stable_id == stable_id).first()
    if existing:
        raise HTTPException(status_code=400, detail=f"Duplicate stable_id {stable_id} in book {book_id}")
    
    # validate parent belongs to same book if provided
    if parent_id:
        parent = db.query(BookNode).filter(BookNode.id == parent_id, BookNode.book_id == book_id).first()
        if not parent:
            raise HTTPException(status_code=400, detail=f"Invalid parent_id {parent_id} for book {book_id}")
        level = parent.level + 1
        # cycle check: walk up parents
        visited = set()
        curr = parent
        while curr:
            if curr.id in visited:
                raise HTTPException(status_code=400, detail="Cyclic hierarchy detected")
            if curr.stable_id == stable_id:
                raise HTTPException(status_code=400, detail="Cyclic hierarchy: node cannot be parent of itself")
            visited.add(curr.id)
            if curr.parent_id:
                curr = db.query(BookNode).filter(BookNode.id == curr.parent_id).first()
            else:
                curr = None
    
    node = BookNode(book_id=book_id, stable_id=stable_id, parent_id=parent_id, node_type=node_type, title=title, title_fa=title_fa, order_index=order_index, level=level)
    db.add(node)
    db.commit()
    db.refresh(node)
    return node

def get_user_book_activations(db: Session, user_id: int):
    return db.query(UserBookActivation).filter(UserBookActivation.user_id == user_id).all()

def activate_book(db: Session, user_id: int, book_id: int, is_active: bool = True):
    activation = db.query(UserBookActivation).filter(UserBookActivation.user_id == user_id, UserBookActivation.book_id == book_id).first()
    if activation:
        activation.is_active = is_active
    else:
        activation = UserBookActivation(user_id=user_id, book_id=book_id, is_active=is_active)
        db.add(activation)
    db.commit()
    db.refresh(activation)
    return activation

def get_test_sets(db: Session, book_id: int, node_id: Optional[int] = None):
    q = db.query(TestSet).filter(TestSet.book_id == book_id)
    if node_id:
        q = q.filter(TestSet.node_id == node_id)
    return q.order_by(TestSet.order_index).all()

def create_test_set(db: Session, book_id: int, stable_id: str, title: str, test_type: str, node_id: Optional[int] = None, difficulty_level: Optional[int] = None, is_comprehensive: bool = False, title_fa: Optional[str] = None):
    existing = db.query(TestSet).filter(TestSet.book_id == book_id, TestSet.stable_id == stable_id).first()
    if existing:
        raise HTTPException(status_code=400, detail=f"Duplicate test_set stable_id {stable_id}")
    ts = TestSet(book_id=book_id, stable_id=stable_id, title=title, title_fa=title_fa, test_type=test_type, node_id=node_id, difficulty_level=difficulty_level, is_comprehensive=is_comprehensive)
    db.add(ts)
    db.commit()
    db.refresh(ts)
    return ts

def get_questions(db: Session, book_id: Optional[int] = None, test_set_id: Optional[int] = None, node_id: Optional[int] = None, difficulty_level: Optional[int] = None, limit: int = 100, offset: int = 0):
    q = db.query(Question)
    if book_id:
        q = q.filter(Question.book_id == book_id)
    if test_set_id:
        q = q.filter(Question.test_set_id == test_set_id)
    if difficulty_level:
        q = q.filter(Question.difficulty_level == difficulty_level)
    if node_id:
        # many-to-many via question_topic_map
        q = q.join(QuestionTopicMap, QuestionTopicMap.question_id == Question.id).filter(QuestionTopicMap.book_node_id == node_id)
    return q.offset(offset).limit(limit).all()

def count_questions(db: Session, book_id: Optional[int] = None, test_set_id: Optional[int] = None, node_ids: Optional[List[int]] = None, difficulty_levels: Optional[List[int]] = None, exclude_recent_days: Optional[int] = None, user_id: Optional[int] = None):
    q = db.query(Question)
    if book_id:
        q = q.filter(Question.book_id == book_id)
    if test_set_id:
        q = q.filter(Question.test_set_id == test_set_id)
    if difficulty_levels:
        q = q.filter(Question.difficulty_level.in_(difficulty_levels))
    if node_ids:
        q = q.join(QuestionTopicMap, QuestionTopicMap.question_id == Question.id).filter(QuestionTopicMap.book_node_id.in_(node_ids)).distinct()
    
    # exclude recent if needed
    if exclude_recent_days and user_id:
        from ..models.attempt import QuestionAttempt
        from datetime import datetime, timedelta, timezone
        cutoff = datetime.now(timezone.utc) - timedelta(days=exclude_recent_days)
        recent_q_ids = db.query(QuestionAttempt.question_id).filter(QuestionAttempt.user_id == user_id, QuestionAttempt.created_at >= cutoff).distinct()
        q = q.filter(~Question.id.in_(recent_q_ids))
    
    return q.count()

def create_question(db: Session, book_id: int, stable_id: str, question_text: Optional[str] = None, option_a: Optional[str] = None, option_b: Optional[str] = None, option_c: Optional[str] = None, option_d: Optional[str] = None, correct_option: Optional[str] = None, test_set_id: Optional[int] = None, difficulty_level: Optional[int] = None, topic_node_ids: List[int] = [], order_index: int = 0, question_text_fa: Optional[str] = None):
    existing = db.query(Question).filter(Question.book_id == book_id, Question.stable_id == stable_id).first()
    if existing:
        raise HTTPException(status_code=400, detail=f"Duplicate question stable_id {stable_id} in book {book_id}")
    question = Question(book_id=book_id, stable_id=stable_id, question_text=question_text, question_text_fa=question_text_fa, option_a=option_a, option_b=option_b, option_c=option_c, option_d=option_d, correct_option=correct_option, test_set_id=test_set_id, difficulty_level=difficulty_level, order_index=order_index)
    db.add(question)
    db.flush()  # to get id
    
    # validate topic mappings
    for node_id in topic_node_ids:
        node = db.query(BookNode).filter(BookNode.id == node_id, BookNode.book_id == book_id).first()
        if not node:
            db.rollback()
            raise HTTPException(status_code=400, detail=f"Invalid topic mapping: node_id {node_id} not in book {book_id}")
        mapping = QuestionTopicMap(question_id=question.id, book_node_id=node_id)
        db.add(mapping)
    
    db.commit()
    db.refresh(question)
    return question

def import_book_data(db: Session, import_request: Dict[str, Any]):
    """
    Extensible import mechanism
    Validates duplicate stable IDs, invalid parent refs, cyclic hierarchy
    """
    book_data = import_request.get("book_data")
    nodes_data = import_request.get("nodes", [])
    test_sets_data = import_request.get("test_sets", [])
    questions_data = import_request.get("questions", [])
    
    if not book_data or not book_data.get("stable_id"):
        raise HTTPException(status_code=400, detail="book_data.stable_id required")
    
    # Check duplicate book
    existing_book = get_book_by_stable_id(db, book_data["stable_id"])
    if existing_book:
        raise HTTPException(status_code=400, detail=f"Book {book_data['stable_id']} already exists")
    
    # Validate subject exists
    subject = db.query(Subject).filter(Subject.id == book_data["subject_id"]).first()
    if not subject:
        raise HTTPException(status_code=400, detail="Invalid subject_id")
    
    # Validate nodes for duplicate stable_ids within import
    seen_stable = set()
    for nd in nodes_data:
        sid = nd.get("stable_id")
        if not sid:
            raise HTTPException(status_code=400, detail="Node stable_id required")
        if sid in seen_stable:
            raise HTTPException(status_code=400, detail=f"Duplicate node stable_id in import: {sid}")
        seen_stable.add(sid)
    
    # Validate no cycle
    validate_no_cycle(nodes_data)
    
    # Create book
    book = Book(
        stable_id=book_data["stable_id"],
        subject_id=book_data["subject_id"],
        title=book_data["title"],
        title_fa=book_data.get("title_fa"),
        publisher=book_data.get("publisher"),
        hierarchy_config=book_data.get("hierarchy_config"),
        description=book_data.get("description")
    )
    db.add(book)
    db.flush()
    
    # Create nodes - need to handle parent_stable_id resolution
    stable_to_id = {}
    # First pass: create nodes without parent
    # Sort by level if provided, else attempt topological order
    # Simple approach: iterate multiple times until all parents resolved or max iterations
    remaining = nodes_data[:]
    max_iter = len(nodes_data) * 2 + 5
    iter_count = 0
    created_nodes = []
    
    while remaining and iter_count < max_iter:
        iter_count += 1
        still_remaining = []
        for nd in remaining:
            parent_stable = nd.get("parent_stable_id")
            parent_id = None
            if parent_stable:
                parent_id = stable_to_id.get(parent_stable)
                if not parent_id:
                    # parent not yet created, defer
                    still_remaining.append(nd)
                    continue
            # create node
            node = BookNode(
                book_id=book.id,
                stable_id=nd["stable_id"],
                parent_id=parent_id,
                node_type=nd["node_type"],
                title=nd["title"],
                title_fa=nd.get("title_fa"),
                order_index=nd.get("order_index", 0),
                level=nd.get("level", 0 if not parent_id else 1)  # will be corrected later
            )
            if parent_id:
                parent_node = db.query(BookNode).filter(BookNode.id == parent_id).first()
                if parent_node:
                    node.level = parent_node.level + 1
            db.add(node)
            db.flush()
            stable_to_id[node.stable_id] = node.id
            created_nodes.append(node)
        remaining = still_remaining
        if not remaining:
            break
    
    if remaining:
        db.rollback()
        raise HTTPException(status_code=400, detail=f"Invalid parent references for nodes: {[n['stable_id'] for n in remaining]}")
    
    # Create test sets
    for ts_data in test_sets_data:
        if not ts_data.get("stable_id"):
            db.rollback()
            raise HTTPException(status_code=400, detail="test_set stable_id required")
        node_id = None
        if ts_data.get("node_stable_id"):
            node_id = stable_to_id.get(ts_data["node_stable_id"])
            if not node_id:
                db.rollback()
                raise HTTPException(status_code=400, detail=f"Invalid node_stable_id {ts_data['node_stable_id']} for test_set")
        ts = TestSet(
            book_id=book.id,
            stable_id=ts_data["stable_id"],
            title=ts_data["title"],
            title_fa=ts_data.get("title_fa"),
            test_type=ts_data.get("test_type", "normal"),
            node_id=node_id,
            difficulty_level=ts_data.get("difficulty_level"),
            is_comprehensive=ts_data.get("is_comprehensive", False)
        )
        db.add(ts)
    db.flush()
    
    # Create questions
    stable_to_testset = {ts.stable_id: ts.id for ts in db.query(TestSet).filter(TestSet.book_id == book.id).all()}
    for q_data in questions_data:
        if not q_data.get("stable_id"):
            db.rollback()
            raise HTTPException(status_code=400, detail="question stable_id required")
        test_set_id = None
        if q_data.get("test_set_stable_id"):
            test_set_id = stable_to_testset.get(q_data["test_set_stable_id"])
            if not test_set_id:
                db.rollback()
                raise HTTPException(status_code=400, detail=f"Invalid test_set_stable_id {q_data['test_set_stable_id']}")
        q = Question(
            book_id=book.id,
            stable_id=q_data["stable_id"],
            test_set_id=test_set_id,
            question_text=q_data.get("question_text"),
            question_text_fa=q_data.get("question_text_fa"),
            option_a=q_data.get("option_a"),
            option_b=q_data.get("option_b"),
            option_c=q_data.get("option_c"),
            option_d=q_data.get("option_d"),
            correct_option=q_data.get("correct_option"),
            difficulty_level=q_data.get("difficulty_level"),
            is_concours=q_data.get("is_concours", False),
            concours_year=q_data.get("concours_year"),
            order_index=q_data.get("order_index", 0)
        )
        db.add(q)
        db.flush()
        # topic mappings
        for topic_stable in q_data.get("topic_stable_ids", []):
            node_id = stable_to_id.get(topic_stable)
            if not node_id:
                db.rollback()
                raise HTTPException(status_code=400, detail=f"Invalid topic_stable_id {topic_stable} for question {q_data['stable_id']}")
            mapping = QuestionTopicMap(question_id=q.id, book_node_id=node_id)
            db.add(mapping)
    
    db.commit()
    db.refresh(book)
    return book
