"""
Seed initial subjects/books/content required by documentation
Keep content importable, do not hard-code architecture around these books
Keep stable IDs, allow future books to be added without changing code
"""
from sqlalchemy.orm import Session
from ..database import SessionLocal
from ..models.subject import Subject
from ..models.book import Book
from ..models.book_node import BookNode
from ..models.test_set import TestSet
from ..models.question import Question, QuestionTopicMap

def seed_subjects(db: Session):
    subjects_data = [
        {"stable_id": "chem", "name": "Chemistry", "name_fa": "شیمی", "color": "#10b981"},
        {"stable_id": "calc", "name": "Calculus", "name_fa": "حسابان", "color": "#3b82f6"},
        {"stable_id": "physics", "name": "Physics", "name_fa": "فیزیک", "color": "#f59e0b"},
    ]
    for data in subjects_data:
        existing = db.query(Subject).filter(Subject.stable_id == data["stable_id"]).first()
        if not existing:
            subj = Subject(**data)
            db.add(subj)
    db.commit()
    print("Subjects seeded")

def seed_chemistry_book(db: Session):
    """
    Chemistry — شیمی 2 مبتکران
    فصل -> عنوان -> زیرعنوان (optional)
    Checkup tests may cover multiple titles
    Each chapter has two comprehensive chapter exams
    Ends with 1404 کنکور questions
    """
    chem_subject = db.query(Subject).filter(Subject.stable_id == "chem").first()
    if not chem_subject:
        print("Chemistry subject not found")
        return
    
    existing = db.query(Book).filter(Book.stable_id == "chem-mobtakran-2").first()
    if existing:
        print("Chemistry book already exists")
        return
    
    book = Book(
        stable_id="chem-mobtakran-2",
        subject_id=chem_subject.id,
        title="Chemistry 2 Mobtakran",
        title_fa="شیمی 2 مبتکران",
        publisher="مبتکران",
        edition="1403",
        description="شیمی 2 مبتکران - فصل -> عنوان -> زیرعنوان",
        hierarchy_config={"levels": ["فصل", "عنوان", "زیرعنوان"], "test_types": ["normal", "checkup", "chapter_exam", "comprehensive", "concours"]},
        is_active=True
    )
    db.add(book)
    db.flush()
    
    # Create nodes: 3 chapters example
    chapters = [
        {"stable_id": "chem-c1", "title": "Chapter 1 - Composition", "title_fa": "فصل 1 - ترکیب", "order": 0},
        {"stable_id": "chem-c2", "title": "Chapter 2 - Chemical Reactions", "title_fa": "فصل 2 - واکنش‌های شیمیایی", "order": 1},
        {"stable_id": "chem-c3", "title": "Chapter 3 - Solutions", "title_fa": "فصل 3 - محلول‌ها", "order": 2},
    ]
    
    chapter_nodes = {}
    for ch in chapters:
        node = BookNode(
            book_id=book.id,
            stable_id=ch["stable_id"],
            parent_id=None,
            node_type="فصل",
            title=ch["title"],
            title_fa=ch["title_fa"],
            order_index=ch["order"],
            level=0
        )
        db.add(node)
        db.flush()
        chapter_nodes[ch["stable_id"]] = node
    
    # Titles under each chapter
    titles_data = [
        # Chapter 1 titles
        {"stable_id": "chem-c1-t1", "parent": "chem-c1", "title": "Matter and its properties", "title_fa": "ماده و ویژگی‌های آن", "order": 0},
        {"stable_id": "chem-c1-t2", "parent": "chem-c1", "title": "Mixtures", "title_fa": "مخلوط‌ها", "order": 1},
        # Chapter 2 titles
        {"stable_id": "chem-c2-t1", "parent": "chem-c2", "title": "Chemical Equation", "title_fa": "معادله شیمیایی", "order": 0},
        {"stable_id": "chem-c2-t2", "parent": "chem-c2", "title": "Stoichiometry", "title_fa": "استوکیومتری", "order": 1},
        # Chapter 3 titles
        {"stable_id": "chem-c3-t1", "parent": "chem-c3", "title": "Solubility", "title_fa": "انحلال‌پذیری", "order": 0},
    ]
    
    title_nodes = {}
    for t in titles_data:
        parent_node = chapter_nodes.get(t["parent"])
        if not parent_node:
            continue
        node = BookNode(
            book_id=book.id,
            stable_id=t["stable_id"],
            parent_id=parent_node.id,
            node_type="عنوان",
            title=t["title"],
            title_fa=t["title_fa"],
            order_index=t["order"],
            level=1
        )
        db.add(node)
        db.flush()
        title_nodes[t["stable_id"]] = node
    
    # Subtitles optional
    subtitles_data = [
        {"stable_id": "chem-c1-t1-s1", "parent": "chem-c1-t1", "title": "Physical properties", "title_fa": "ویژگی‌های فیزیکی", "order": 0},
        {"stable_id": "chem-c1-t1-s2", "parent": "chem-c1-t1", "title": "Chemical properties", "title_fa": "ویژگی‌های شیمیایی", "order": 1},
    ]
    for s in subtitles_data:
        parent_node = title_nodes.get(s["parent"])
        if not parent_node:
            continue
        node = BookNode(
            book_id=book.id,
            stable_id=s["stable_id"],
            parent_id=parent_node.id,
            node_type="زیرعنوان",
            title=s["title"],
            title_fa=s["title_fa"],
            order_index=s["order"],
            level=2
        )
        db.add(node)
        db.flush()
    
    # Test sets: normal for each title, checkup covering multiple titles, chapter exams (2 per chapter), concours 1404
    # Normal test sets
    for title_id, node in title_nodes.items():
        ts = TestSet(
            book_id=book.id,
            stable_id=f"ts-{title_id}-normal",
            node_id=node.id,
            title=f"Test {node.title}",
            title_fa=f"آزمون {node.title_fa}",
            test_type="normal",
            order_index=node.order_index
        )
        db.add(ts)
    
    # Checkup tests covering multiple titles (example)
    checkup = TestSet(
        book_id=book.id,
        stable_id="ts-chem-c1-checkup",
        node_id=chapter_nodes["chem-c1"].id,
        title="Checkup Chapter 1",
        title_fa="آزمونک فصل 1",
        test_type="checkup",
        order_index=10
    )
    db.add(checkup)
    
    # Chapter exams - 2 per chapter
    for ch_id, ch_node in chapter_nodes.items():
        for i in [1,2]:
            ts = TestSet(
                book_id=book.id,
                stable_id=f"ts-{ch_id}-exam-{i}",
                node_id=ch_node.id,
                title=f"Chapter Exam {ch_id} #{i}",
                title_fa=f"آزمون جامع فصل {ch_node.title_fa} - {i}",
                test_type="chapter_exam",
                is_comprehensive=True,
                order_index=20+i
            )
            db.add(ts)
    
    # Concours 1404
    concours = TestSet(
        book_id=book.id,
        stable_id="ts-chem-concours-1404",
        node_id=None,
        title="Konkur 1404",
        title_fa="سوالات کنکور 1404",
        test_type="concours",
        is_comprehensive=True,
        order_index=100
    )
    db.add(concours)
    
    db.flush()
    
    # Create sample questions - data-driven, stable IDs
    # For each normal test set, create 10 questions
    all_test_sets = db.query(TestSet).filter(TestSet.book_id == book.id).all()
    q_counter = 1
    for ts in all_test_sets:
        # Determine count: normal 10, checkup 15, chapter_exam 20, concours 25
        count_map = {"normal": 10, "checkup": 15, "chapter_exam": 20, "concours": 25}
        count = count_map.get(ts.test_type, 10)
        for i in range(count):
            stable_id = f"chem-q-{q_counter:04d}"
            q = Question(
                book_id=book.id,
                test_set_id=ts.id,
                stable_id=stable_id,
                question_text=f"Chemistry question {q_counter} - sample content for {ts.title}",
                question_text_fa=f"سوال {q_counter} شیمی - نمونه سوال برای {ts.title_fa}",
                option_a="گزینه الف",
                option_b="گزینه ب",
                option_c="گزینه ج",
                option_d="گزینه د",
                correct_option=["A","B","C","D"][q_counter % 4],
                difficulty_level=None,
                is_concours=(ts.test_type == "concours"),
                concours_year=1404 if ts.test_type == "concours" else None,
                order_index=i
            )
            db.add(q)
            db.flush()
            
            # Many-to-many topic mapping: map to node if test_set has node, plus maybe extra for checkup
            if ts.node_id:
                mapping = QuestionTopicMap(question_id=q.id, book_node_id=ts.node_id)
                db.add(mapping)
                # For checkup, also map to multiple titles
                if ts.test_type == "checkup" and ts.node_id == chapter_nodes["chem-c1"].id:
                    # Map to both titles of chapter 1
                    for t_stable in ["chem-c1-t1", "chem-c1-t2"]:
                        t_node = title_nodes.get(t_stable)
                        if t_node and t_node.id != ts.node_id:
                            mapping2 = QuestionTopicMap(question_id=q.id, book_node_id=t_node.id)
                            db.add(mapping2)
            
            q_counter += 1
    
    db.commit()
    print(f"Chemistry book seeded with {q_counter-1} questions")

def seed_calculus_book(db: Session):
    """
    Calculus — حسابان 1 نشر الگو
    فصل -> درس -> بخش
    Each section supports difficulty level 1,2,3
    Each lesson can have سوالات کنکور سراسری
    """
    calc_subject = db.query(Subject).filter(Subject.stable_id == "calc").first()
    if not calc_subject:
        print("Calculus subject not found")
        return
    
    existing = db.query(Book).filter(Book.stable_id == "calc-olgo-1").first()
    if existing:
        print("Calculus book already exists")
        return
    
    book = Book(
        stable_id="calc-olgo-1",
        subject_id=calc_subject.id,
        title="Calculus 1 Olgo",
        title_fa="حسابان 1 نشر الگو",
        publisher="نشر الگو",
        edition="1403",
        description="حسابان 1 نشر الگو - فصل -> درس -> بخش با سطوح دشواری 1/2/3",
        hierarchy_config={"levels": ["فصل", "درس", "بخش"], "difficulty_levels": [1,2,3], "has_konkur": True},
        is_active=True
    )
    db.add(book)
    db.flush()
    
    chapters = [
        {"stable_id": "calc-c1", "title": "Chapter 1 - Functions", "title_fa": "فصل 1 - تابع", "order": 0},
        {"stable_id": "calc-c2", "title": "Chapter 2 - Limits", "title_fa": "فصل 2 - حد", "order": 1},
    ]
    
    chapter_nodes = {}
    for ch in chapters:
        node = BookNode(
            book_id=book.id,
            stable_id=ch["stable_id"],
            parent_id=None,
            node_type="فصل",
            title=ch["title"],
            title_fa=ch["title_fa"],
            order_index=ch["order"],
            level=0
        )
        db.add(node)
        db.flush()
        chapter_nodes[ch["stable_id"]] = node
    
    lessons = [
        {"stable_id": "calc-c1-l1", "parent": "calc-c1", "title": "Lesson 1 - Function Definition", "title_fa": "درس 1 - تعریف تابع", "order": 0},
        {"stable_id": "calc-c1-l2", "parent": "calc-c1", "title": "Lesson 2 - Function Types", "title_fa": "درس 2 - انواع تابع", "order": 1},
        {"stable_id": "calc-c2-l1", "parent": "calc-c2", "title": "Lesson 1 - Limit Concept", "title_fa": "درس 1 - مفهوم حد", "order": 0},
    ]
    
    lesson_nodes = {}
    for l in lessons:
        parent = chapter_nodes.get(l["parent"])
        if not parent:
            continue
        node = BookNode(
            book_id=book.id,
            stable_id=l["stable_id"],
            parent_id=parent.id,
            node_type="درس",
            title=l["title"],
            title_fa=l["title_fa"],
            order_index=l["order"],
            level=1
        )
        db.add(node)
        db.flush()
        lesson_nodes[l["stable_id"]] = node
    
    # Sections with difficulty levels
    sections = [
        {"stable_id": "calc-c1-l1-s1", "parent": "calc-c1-l1", "title": "Section 1", "title_fa": "بخش 1", "order": 0},
        {"stable_id": "calc-c1-l1-s2", "parent": "calc-c1-l1", "title": "Section 2", "title_fa": "بخش 2", "order": 1},
        {"stable_id": "calc-c1-l2-s1", "parent": "calc-c1-l2", "title": "Section 1", "title_fa": "بخش 1", "order": 0},
    ]
    
    section_nodes = {}
    for s in sections:
        parent = lesson_nodes.get(s["parent"])
        if not parent:
            continue
        node = BookNode(
            book_id=book.id,
            stable_id=s["stable_id"],
            parent_id=parent.id,
            node_type="بخش",
            title=s["title"],
            title_fa=s["title_fa"],
            order_index=s["order"],
            level=2
        )
        db.add(node)
        db.flush()
        section_nodes[s["stable_id"]] = node
    
    # Test sets: for each section, difficulty 1,2,3 separately + concours per lesson
    q_counter = 1
    for sec_id, sec_node in section_nodes.items():
        for diff in [1,2,3]:
            ts = TestSet(
                book_id=book.id,
                stable_id=f"ts-{sec_id}-diff-{diff}",
                node_id=sec_node.id,
                title=f"{sec_node.title} Difficulty {diff}",
                title_fa=f"{sec_node.title_fa} - سطح {diff}",
                test_type="normal",
                difficulty_level=diff,
                order_index=diff
            )
            db.add(ts)
            db.flush()
            
            # Create 8 questions per difficulty
            for i in range(8):
                stable_id = f"calc-q-{q_counter:04d}"
                q = Question(
                    book_id=book.id,
                    test_set_id=ts.id,
                    stable_id=stable_id,
                    question_text=f"Calculus Q {q_counter} diff {diff}",
                    question_text_fa=f"سوال {q_counter} حسابان - سطح {diff}",
                    option_a="الف",
                    option_b="ب",
                    option_c="ج",
                    option_d="د",
                    correct_option=["A","B","C","D"][q_counter % 4],
                    difficulty_level=diff,
                    order_index=i
                )
                db.add(q)
                db.flush()
                mapping = QuestionTopicMap(question_id=q.id, book_node_id=sec_node.id)
                db.add(mapping)
                q_counter += 1
    
    # Konkur per lesson
    for lesson_id, lesson_node in lesson_nodes.items():
        ts = TestSet(
            book_id=book.id,
            stable_id=f"ts-{lesson_id}-konkur",
            node_id=lesson_node.id,
            title=f"Konkur {lesson_node.title}",
            title_fa=f"سوالات کنکور سراسری {lesson_node.title_fa}",
            test_type="concours",
            order_index=10
        )
        db.add(ts)
        db.flush()
        for i in range(10):
            stable_id = f"calc-q-{q_counter:04d}"
            q = Question(
                book_id=book.id,
                test_set_id=ts.id,
                stable_id=stable_id,
                question_text=f"Konkur Q {q_counter}",
                question_text_fa=f"سوال کنکور {q_counter} - {lesson_node.title_fa}",
                option_a="الف",
                option_b="ب",
                option_c="ج",
                option_d="د",
                correct_option=["A","B","C","D"][q_counter % 4],
                is_concours=True,
                order_index=i
            )
            db.add(q)
            db.flush()
            mapping = QuestionTopicMap(question_id=q.id, book_node_id=lesson_node.id)
            db.add(mapping)
            q_counter += 1
    
    db.commit()
    print(f"Calculus book seeded with {q_counter-1} questions")

def seed_physics_book(db: Session):
    """
    Physics — فیزیک 2 خیلی سبز
    فصل -> بخش -> زیر بخش
    """
    physics_subject = db.query(Subject).filter(Subject.stable_id == "physics").first()
    if not physics_subject:
        print("Physics subject not found")
        return
    
    existing = db.query(Book).filter(Book.stable_id == "physics-kheilisabz-2").first()
    if existing:
        print("Physics book already exists")
        return
    
    book = Book(
        stable_id="physics-kheilisabz-2",
        subject_id=physics_subject.id,
        title="Physics 2 Kheili Sabz",
        title_fa="فیزیک 2 خیلی سبز",
        publisher="خیلی سبز",
        edition="1403",
        description="فیزیک 2 خیلی سبز - فصل -> بخش -> زیر بخش",
        hierarchy_config={"levels": ["فصل", "بخش", "زیر بخش"]},
        is_active=True
    )
    db.add(book)
    db.flush()
    
    chapters = [
        {"stable_id": "phys-c1", "title": "Chapter 1 - Electrostatics", "title_fa": "فصل 1 - الکتریسیته ساکن", "order": 0},
        {"stable_id": "phys-c2", "title": "Chapter 2 - Electric Current", "title_fa": "فصل 2 - جریان الکتریکی", "order": 1},
    ]
    
    chapter_nodes = {}
    for ch in chapters:
        node = BookNode(
            book_id=book.id,
            stable_id=ch["stable_id"],
            parent_id=None,
            node_type="فصل",
            title=ch["title"],
            title_fa=ch["title_fa"],
            order_index=ch["order"],
            level=0
        )
        db.add(node)
        db.flush()
        chapter_nodes[ch["stable_id"]] = node
    
    sections = [
        {"stable_id": "phys-c1-b1", "parent": "phys-c1", "title": "Section 1 - Charge", "title_fa": "بخش 1 - بار الکتریکی", "order": 0},
        {"stable_id": "phys-c1-b2", "parent": "phys-c1", "title": "Section 2 - Electric Field", "title_fa": "بخش 2 - میدان الکتریکی", "order": 1},
        {"stable_id": "phys-c2-b1", "parent": "phys-c2", "title": "Section 1 - Current", "title_fa": "بخش 1 - جریان", "order": 0},
    ]
    
    section_nodes = {}
    for sec in sections:
        parent = chapter_nodes.get(sec["parent"])
        if not parent:
            continue
        node = BookNode(
            book_id=book.id,
            stable_id=sec["stable_id"],
            parent_id=parent.id,
            node_type="بخش",
            title=sec["title"],
            title_fa=sec["title_fa"],
            order_index=sec["order"],
            level=1
        )
        db.add(node)
        db.flush()
        section_nodes[sec["stable_id"]] = node
    
    subsections = [
        {"stable_id": "phys-c1-b1-sb1", "parent": "phys-c1-b1", "title": "Subsection 1", "title_fa": "زیر بخش 1", "order": 0},
        {"stable_id": "phys-c1-b1-sb2", "parent": "phys-c1-b1", "title": "Subsection 2", "title_fa": "زیر بخش 2", "order": 1},
    ]
    
    subsection_nodes = {}
    for sb in subsections:
        parent = section_nodes.get(sb["parent"])
        if not parent:
            continue
        node = BookNode(
            book_id=book.id,
            stable_id=sb["stable_id"],
            parent_id=parent.id,
            node_type="زیر بخش",
            title=sb["title"],
            title_fa=sb["title_fa"],
            order_index=sb["order"],
            level=2
        )
        db.add(node)
        db.flush()
        subsection_nodes[sb["stable_id"]] = node
    
    # Test sets
    q_counter = 1
    all_nodes = {**section_nodes, **subsection_nodes}
    for node_id, node in all_nodes.items():
        ts = TestSet(
            book_id=book.id,
            stable_id=f"ts-{node_id}",
            node_id=node.id,
            title=f"Test {node.title}",
            title_fa=f"آزمون {node.title_fa}",
            test_type="normal",
            order_index=node.order_index
        )
        db.add(ts)
        db.flush()
        for i in range(10):
            stable_id = f"phys-q-{q_counter:04d}"
            q = Question(
                book_id=book.id,
                test_set_id=ts.id,
                stable_id=stable_id,
                question_text=f"Physics Q {q_counter}",
                question_text_fa=f"سوال {q_counter} فیزیک - {node.title_fa}",
                option_a="الف",
                option_b="ب",
                option_c="ج",
                option_d="د",
                correct_option=["A","B","C","D"][q_counter % 4],
                order_index=i
            )
            db.add(q)
            db.flush()
            mapping = QuestionTopicMap(question_id=q.id, book_node_id=node.id)
            db.add(mapping)
            q_counter += 1
    
    db.commit()
    print(f"Physics book seeded with {q_counter-1} questions")

def run_seed():
    db = SessionLocal()
    try:
        seed_subjects(db)
        seed_chemistry_book(db)
        seed_calculus_book(db)
        seed_physics_book(db)
        print("All seed completed")
    finally:
        db.close()

if __name__ == "__main__":
    run_seed()
