"""Content migration: the three real books shipped with the repository.

The source of truth is the plain-text table of contents that lives in the
repository root (حسابان ۱ نشر الگو.txt, شیمی ۲ مبتکران.txt, فیزیک ۲ خیلی سبز.txt).

Per V3: "Existing content should be migrated rather than discarded."
The parsers below are deterministic, idempotent and never invent content:
if a line does not exist in the source file, it does not exist in the database.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from typing import List, Optional

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))

CALCULUS_FILE = "حسابان 1 نشر الگو.txt"
CHEMISTRY_FILE = "شیمی 2 مبتکران.txt"
PHYSICS_FILE = "فیزیک 2 خیلی سبز .txt"


@dataclass
class ParsedNode:
    title: str
    node_type: str
    children: List["ParsedNode"] = field(default_factory=list)
    note: Optional[str] = None

    def add(self, node: "ParsedNode") -> "ParsedNode":
        self.children.append(node)
        return node


@dataclass
class ParsedMarker:
    """A «آزمون چکاپ» / «آزمون جامع» line of the chemistry table of contents.

    V3.1 (doc 03) treats a checkup as a *coverage range*, not a single topic:
    «included_topics[] از سگمنت قبلی تا قبل چکاپ فعلی».
    """

    kind: str                  # checkup | comprehensive
    label: str                 # «آزمون چکاپ اول»
    chapter_title: Optional[str]
    index_in_chapter: int
    included_topics: List[str] = field(default_factory=list)
    covered_from: Optional[str] = None   # first topic of the segment
    covered_to: Optional[str] = None     # last topic before the marker
    scope: str = "segment"               # segment | chapter


@dataclass
class ParsedBook:
    stable_key: str
    title: str
    publisher: str
    subject_slug: str
    subject_name: str
    grade: str
    track: str
    source_file: str
    chapters: List[ParsedNode] = field(default_factory=list)
    hierarchy_note: Optional[str] = None
    levels: int = 1  # number of difficulty levels per topic (حسابان = 3)
    level_labels: List[str] = field(default_factory=list)
    markers: List[ParsedMarker] = field(default_factory=list)


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

_CHAPTER_RE = re.compile(r"^فصل\s*(?:[۰-۹0-9]+|اول|دوم|سوم|چهارم|پنجم|ششم)?\s*[:：]\s*(.+)$")
_LESSON_RE = re.compile(r"^درس\s+(?:اول|دوم|سوم|چهارم|پنجم|ششم|هفتم|هشتم|نهم|دهم|[\d۰-۹]+)\s*(?:و\s*درس\s*\w+)?\s*[:：]?\s*(.*)$")
_SECTION_RE = re.compile(r"^بخش\s+(?:اول|دوم|سوم|چهارم|پنجم|ششم|هفتم|هشتم|نهم|دهم|یازدهم|دوازدهم|[\d۰-۹]+)\s*[:：]\s*(.*)$")
_PHYSICS_SECTION_RE = re.compile(r"^بخش\s*[۰-۹0-9]+\s*[:：]\s*(.+)$")
# V3.1 chemistry TOC: «فصل ۱ ـ قدر هدایای زمینی را بدانیم» / «1. الگوها و روندها در رفتار مواد»
# / «زیرعنوان ۲-۱: جدول دوره‌ای ...» / «• آزمون چکاپ اول»
_CHEM_CHAPTER_RE = re.compile(r"^فصل\s*(?:[۰-۹0-9]+|[\u0600-\u06FF]+)?\s*(?:[ـ\-–—:：]\s*(.*))?$")
_CHEM_NUMBERED_RE = re.compile(r"^([۰-۹0-9]+)\s*[.\-)]\s*(.+)$")
_CHEM_SUBTOPIC_RE = re.compile(r"^زیرعنوان\s*[۰-۹0-9\-–]+\s*[:：]\s*(.+)$")
_CHEM_MARKER_RE = re.compile(r"^[•\-*\u25CF\u25CB]\s*آزمون\s+(چکاپ|جامع|جمع‌بندی)\s*(.*)$")
_SEPARATOR_RE = re.compile(r"^=+\s*$")
_CHEM_TITLE_HINT = re.compile(r"(فهرست|مبتکران)\s*$")


def _clean(text: str) -> str:
    return text.strip().strip("-").strip() if text else text


def _strip_bullet(line: str) -> tuple[int, str]:
    """Return (indent, text) for a bullet line."""
    indent = len(line) - len(line.lstrip(" "))
    return indent, _clean(line.strip())


def _read(path: str) -> Optional[str]:
    if not os.path.exists(path):
        return None
    with open(path, "r", encoding="utf-8") as handle:
        return handle.read()


# ---------------------------------------------------------------------------
# Calculus: فصل > درس > بخش > (سوالات کنکور / آزمون فصل)
# ---------------------------------------------------------------------------

def parse_calculus(path: str) -> Optional[ParsedBook]:
    raw = _read(path)
    if raw is None:
        return None
    book = ParsedBook(
        stable_key="calculus1-neshralgo",
        title="حسابان ۱ (یازدهم) – نشر الگو",
        publisher="نشر الگو",
        subject_slug="calculus",
        subject_name="حسابان",
        grade="یازدهم",
        track="ریاضی",
        source_file=os.path.basename(path),
        levels=3,
        level_labels=["سطح ۱", "سطح ۲", "سطح ۳"],
    )
    chapter: Optional[ParsedNode] = None
    lesson: Optional[ParsedNode] = None
    for raw_line in raw.splitlines():
        line = raw_line.rstrip()
        if not line.strip():
            continue
        if line.strip().startswith("در هر بخش") or line.strip().startswith("در پایان هر درس"):
            book.hierarchy_note = (book.hierarchy_note or "") + line.strip() + " "
            continue
        if line.startswith("کتاب:") or line.startswith("پایان کتاب"):
            continue
        chapter_match = _CHAPTER_RE.match(line.strip())
        if chapter_match and not line.startswith(" "):
            chapter = ParsedNode(_clean(chapter_match.group(1)), "chapter")
            book.chapters.append(chapter)
            lesson = None
            continue
        if chapter is None:
            continue
        text = line.strip()
        content = text[2:].strip() if text.startswith("-") else text
        if content.startswith("درس "):
            lesson_match = _LESSON_RE.match(content)
            title = _clean(lesson_match.group(1)) if lesson_match else _clean(content)
            if not title:  # "درسهای اول و دوم: ..." style handled below
                title = _clean(content)
            if content.startswith("درس‌های") or content.startswith("درسهای"):
                lesson = ParsedNode(_clean(content.split(":", 1)[-1]), "lesson")
            else:
                lesson = ParsedNode(title, "lesson")
            chapter.add(lesson)
            continue
        if content.startswith("بخش ") :
            section_match = _SECTION_RE.match(content) or _PHYSICS_SECTION_RE.match(content)
            title = _clean(section_match.group(1)) if section_match else _clean(content)
            parent = lesson or chapter
            parent.add(ParsedNode(title, "section"))
            continue
        if content.startswith("سوالات کنکور"):
            parent = lesson or chapter
            parent.add(ParsedNode("سوالات کنکور سراسری", "topic"))
            continue
        if content.startswith("آزمون"):
            chapter.add(ParsedNode(_clean(content), "topic"))
            continue
        if content:
            parent = lesson or chapter
            parent.add(ParsedNode(_clean(content), "topic"))
    return book


# ---------------------------------------------------------------------------
# Chemistry: فصل > topic > subtopic (indented bullets)
# ---------------------------------------------------------------------------

def parse_chemistry(path: str) -> Optional[ParsedBook]:
    """Chemistry TOC → chapter > topic > زیرعنوان, plus the checkup/comprehensive markers.

    V3.1 rewrote this parser: the refreshed table of contents uses
    «فصل ۱ ـ ...», numbered topics («1. ...»), «زیرعنوان ۲-۱: ...» and
    «• آزمون چکاپ اول» markers. The legacy bullet format is still accepted, so an
    older file keeps producing the same tree (nothing is lost in the upgrade).
    """
    raw = _read(path)
    if raw is None:
        return None
    book = ParsedBook(
        stable_key="chemistry2-mobtakeran",
        title="شیمی ۲ (یازدهم) – مبتکران",
        publisher="مبتکران",
        subject_slug="chemistry",
        subject_name="شیمی",
        grade="یازدهم",
        track="ریاضی-تجربی",
        source_file=os.path.basename(path),
    )
    chapter: Optional[ParsedNode] = None
    last_topic: Optional[ParsedNode] = None
    chapter_topics: List[str] = []
    segment_topics: List[str] = []
    marker_index = 0

    def close_marker(kind: str, label: str, scope: str) -> None:
        nonlocal marker_index, segment_topics
        if chapter is None:
            return
        if kind == "checkup":
            included = list(segment_topics)
        else:  # جامع: covers the whole chapter so far
            included = list(chapter_topics)
            scope = "chapter"
        marker_index += 1
        book.markers.append(
            ParsedMarker(
                kind=kind,
                label=label,
                chapter_title=chapter.title,
                index_in_chapter=marker_index,
                included_topics=included,
                covered_from=included[0] if included else None,
                covered_to=included[-1] if included else None,
                scope=scope,
            )
        )
        segment_topics = []

    blocks = re.split(_SEPARATOR_RE, raw)
    for block in blocks:
        lines = [line for line in block.splitlines() if line.strip()]
        if not lines:
            continue
        # title block: either the header («فهرست ...») or a lone book title
        if len(lines) == 1 and _CHEM_TITLE_HINT.search(lines[0].strip()):
            continue
        if lines[0].strip().startswith("فهرست") and len(lines) == 1:
            continue
        for raw_line in block.splitlines():
            line = raw_line.rstrip()
            stripped = line.strip()
            if not stripped or _SEPARATOR_RE.match(stripped):
                continue
            if stripped.startswith("کتاب:") or stripped.startswith("پایان کل کتاب"):
                continue
            if _CHEM_TITLE_HINT.search(stripped) and len(stripped) < 40 and not re.search(r"[۰-۹0-9]", stripped):
                continue

            marker_match = _CHEM_MARKER_RE.match(stripped)
            if marker_match:
                close_marker(
                    "checkup" if marker_match.group(1) == "چکاپ" else "comprehensive",
                    f"آزمون {marker_match.group(1)} {marker_match.group(2)}".strip(),
                    "segment",
                )
                continue

            chapter_match = _CHEM_CHAPTER_RE.match(stripped) if not line.startswith(" ") else None
            if chapter_match and _clean(chapter_match.group(1) or ""):
                title = _clean(chapter_match.group(1))
                # «فصل ۱ ـ قدر هدایای زمینی را بدانیم» → the sentence after the dash
                chapter = ParsedNode(title, "chapter")
                book.chapters.append(chapter)
                last_topic = None
                chapter_topics = []
                segment_topics = []
                marker_index = 0
                continue
            if chapter is None:
                continue

            subtopic_match = _CHEM_SUBTOPIC_RE.match(stripped)
            if subtopic_match and last_topic is not None:
                last_topic.add(ParsedNode(_clean(subtopic_match.group(1)), "subsection"))
                continue

            numbered_match = _CHEM_NUMBERED_RE.match(stripped) if not line.startswith(" ") else None
            if numbered_match:
                title = _clean(numbered_match.group(2))
                last_topic = ParsedNode(title, "section")
                chapter.add(last_topic)
                chapter_topics.append(title)
                segment_topics.append(title)
                continue

            # legacy layout: indented bullets are subtopics, top-level bullets are topics
            indent, content = _strip_bullet(line)
            if not content:
                continue
            if indent >= 2 and last_topic is not None:
                last_topic.add(ParsedNode(content, "subsection"))
            else:
                last_topic = ParsedNode(content, "section")
                chapter.add(last_topic)
                chapter_topics.append(content)
                segment_topics.append(content)
    return book


# ---------------------------------------------------------------------------
# Physics: فصل > بخش (+ درس‌نامه / پرسش‌ها, per the file's own note)
# ---------------------------------------------------------------------------

def parse_physics(path: str) -> Optional[ParsedBook]:
    raw = _read(path)
    if raw is None:
        return None
    book = ParsedBook(
        stable_key="physics2-kheilisabz",
        title="فیزیک ۲ (یازدهم) – خیلی سبز",
        publisher="خیلی سبز",
        subject_slug="physics",
        subject_name="فیزیک",
        grade="یازدهم",
        track="ریاضی-تجربی",
        source_file=os.path.basename(path),
    )
    chapter: Optional[ParsedNode] = None
    for raw_line in raw.splitlines():
        line = raw_line.rstrip()
        if not line.strip():
            continue
        stripped = line.strip()
        if stripped.startswith("کتاب:"):
            continue
        if stripped.startswith("توجه:"):
            book.hierarchy_note = stripped
            continue
        chapter_match = _CHAPTER_RE.match(stripped)
        if chapter_match:
            chapter = ParsedNode(_clean(chapter_match.group(1)), "chapter")
            book.chapters.append(chapter)
            continue
        if chapter is None:
            continue
        section_match = _PHYSICS_SECTION_RE.match(stripped)
        if section_match:
            section = ParsedNode(_clean(section_match.group(1)), "section")
            section.add(ParsedNode("درس‌نامه", "subsection"))
            section.add(ParsedNode("پرسش‌ها", "subsection"))
            chapter.add(section)
    return book


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def load_all(root: str | None = None) -> List[ParsedBook]:
    root = root or os.environ.get("STUDYS459_CONTENT_DIR") or REPO_ROOT
    books = []
    calculus = parse_calculus(os.path.join(root, CALCULUS_FILE))
    if calculus:
        books.append(calculus)
    chemistry = parse_chemistry(os.path.join(root, CHEMISTRY_FILE))
    if chemistry:
        books.append(chemistry)
    physics = parse_physics(os.path.join(root, PHYSICS_FILE))
    if physics:
        books.append(physics)
    return books


def count_nodes(book: ParsedBook) -> dict:
    stats = {"chapters": 0, "lessons": 0, "sections": 0, "subsections": 0, "topics": 0, "leaves": 0}

    def walk(node: ParsedNode):
        key = node.node_type + "s" if node.node_type != "chapter" else "chapters"
        stats[key] = stats.get(key, 0) + 1
        if not node.children:
            stats["leaves"] += 1
        for child in node.children:
            walk(child)

    for chapter in book.chapters:
        walk(chapter)
    return stats
