import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.database import Base
from app.models.subject import Subject
from app.models.book import Book
from app.models.book_node import BookNode
from app.services import book_service

# Use in-memory SQLite for tests
engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

@pytest.fixture
def db():
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    yield db
    db.close()
    Base.metadata.drop_all(bind=engine)

def test_multiple_hierarchy_types(db):
    # Create subject
    subj = Subject(stable_id="test-subj", name="Test", name_fa="تست")
    db.add(subj)
    db.commit()
    
    # Chemistry hierarchy: فصل -> عنوان -> زیرعنوان
    book1 = Book(stable_id="test-book-chem", subject_id=subj.id, title="Chem", title_fa="شیمی", hierarchy_config={"levels": ["فصل", "عنوان", "زیرعنوان"]})
    db.add(book1)
    db.commit()
    
    فصل = book_service.create_book_node(db, book_id=book1.id, stable_id="f1", node_type="فصل", title="Chapter 1", order_index=0, level=0)
    عنوان = book_service.create_book_node(db, book_id=book1.id, stable_id="t1", node_type="عنوان", title="Title 1", parent_id=فصل.id, order_index=0)
    زیرعنوان = book_service.create_book_node(db, book_id=book1.id, stable_id="st1", node_type="زیرعنوان", title="Subtitle", parent_id=عنوان.id, order_index=0)
    
    assert زیرعنوان.level == 2
    
    # Calculus hierarchy: فصل -> درس -> بخش
    book2 = Book(stable_id="test-book-calc", subject_id=subj.id, title="Calc", title_fa="حسابان", hierarchy_config={"levels": ["فصل", "درس", "بخش"]})
    db.add(book2)
    db.commit()
    
    فصل2 = book_service.create_book_node(db, book_id=book2.id, stable_id="f1", node_type="فصل", title="Chapter", order_index=0)
    درس = book_service.create_book_node(db, book_id=book2.id, stable_id="l1", node_type="درس", title="Lesson", parent_id=فصل2.id)
    بخش = book_service.create_book_node(db, book_id=book2.id, stable_id="b1", node_type="بخش", title="Section", parent_id=درس.id)
    
    assert بخش.level == 2

def test_multi_topic_mapping(db):
    subj = Subject(stable_id="subj1", name="Subj")
    db.add(subj)
    db.commit()
    book = Book(stable_id="book1", subject_id=subj.id, title="Book")
    db.add(book)
    db.commit()
    
    n1 = book_service.create_book_node(db, book_id=book.id, stable_id="n1", node_type="عنوان", title="Node1")
    n2 = book_service.create_book_node(db, book_id=book.id, stable_id="n2", node_type="عنوان", title="Node2")
    
    # Question with many-to-many mapping
    q = book_service.create_question(db, book_id=book.id, stable_id="q1", question_text="Test", topic_node_ids=[n1.id, n2.id])
    
    assert len(q.topic_maps) == 2

def test_duplicate_stable_id(db):
    subj = Subject(stable_id="subj2", name="Subj2")
    db.add(subj)
    db.commit()
    book = Book(stable_id="book2", subject_id=subj.id, title="Book2")
    db.add(book)
    db.commit()
    
    book_service.create_book_node(db, book_id=book.id, stable_id="dup", node_type="فصل", title="First")
    
    try:
        book_service.create_book_node(db, book_id=book.id, stable_id="dup", node_type="فصل", title="Second")
        assert False, "Should have raised duplicate error"
    except Exception as e:
        assert "Duplicate" in str(e)

def test_cyclic_hierarchy_detection(db):
    # Test via import validation
    nodes_data = [
        {"stable_id": "a", "parent_stable_id": "b", "node_type": "فصل", "title": "A"},
        {"stable_id": "b", "parent_stable_id": "a", "node_type": "عنوان", "title": "B"},
    ]
    try:
        book_service.validate_no_cycle(nodes_data)
        assert False, "Should detect cycle"
    except Exception as e:
        assert "Cyclic" in str(e)
