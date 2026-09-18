"""Book outline import (V3.1 doc 04).

The student's real books arrive as plain-text tables of contents. Three of them
ship with the repository and have hand-written parsers; every *other* book (دهم،
دوازدهم، کتابی که تازه خریده) can be added without touching code through a
generic, indentation-aware parser:

* depth comes from the real indentation / bullet nesting of the file, so nothing
  is invented — a line that is not in the file does not exist in the tree;
* «آزمون چکاپ …» / «آزمون جامع …» lines become checkup markers (coverage ranges),
  not topics;
* ``preview`` shows exactly what would be created *before* anything is written;
* ``apply`` is **additive and idempotent** (existing nodes are reused by title,
  nothing is ever deleted or renamed).

The parser is deliberately conservative: when it cannot tell the structure it says
so in ``warnings`` and the preview shows the flat reading, so the student can fix
the file instead of the app guessing.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import List, Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..core.errors import NotFoundError, ValidationError
from ..db import models
from . import common

CHAPTER_PATTERNS = (
    re.compile(r"^فصل\b"),
    re.compile(r"^Chapter\b", re.IGNORECASE),
)
LESSON_PATTERNS = (
    re.compile(r"^درس\b"),
    re.compile(r"^درس[‌]?ها(ی)?\b"),
    re.compile(r"^گفتار\b"),
    re.compile(r"^Lesson\b", re.IGNORECASE),
)
SECTION_PATTERNS = (
    re.compile(r"^بخش\b"),
    re.compile(r"^گفتار\b"),
)
# «زیربخش/زیرعنوان» is always one level deeper than the thing above it
SUBTOPIC_PATTERNS = (
    re.compile(r"^زیر?بخش\b"),
    re.compile(r"^زیرعنوان\b"),
    re.compile(r"^زیرموضوع\b"),
)
# «۲-۱: جذب و دفع» / «۳-۲-۱ …» — the dash count gives the level
NUMBER_PATH_RE = re.compile(r"^([۰-۹\d]+(?:[-–][۰-۹\d]+)+)\s*[:：.\-]")
SIMPLE_NUMBER_RE = re.compile(r"^([۰-۹\d]+)\s*\.\s+")
HEADER_LINE_PATTERNS = (
    re.compile(r"^فهرست\b"),
    re.compile(r"^جلد\b"),
    re.compile(r"^کتاب\b"),
    re.compile(r"^(توجه|توضیح|نکته|منبع|نویسنده|ناشر|چاپ|پایان)\s*[:：]"),
)
SEPARATOR_RE = re.compile(r"^[=\-_*•▪◦\s]{3,}$")
END_LINE_PATTERNS = (
    re.compile(r"^پایان\b"),
    re.compile(r"^جمع\s*بندی\s+کل\b"),
)
MARKER_PATTERNS = (
    ("checkup", re.compile(r"آزمون\s*چکاپ")),
    ("comprehensive", re.compile(r"آزمون\s*جامع")),
    ("mock", re.compile(r"آزمون\s*(آزمایشی|جامع\s*کنکور)")),
)
BULLETS = "•▪◦‣·-–—*"
NODE_TYPES = {0: "chapter", 1: "section", 2: "subsection"}


@dataclass
class OutlineNode:
    title: str
    depth: int
    children: List["OutlineNode"] = field(default_factory=list)

    def add(self, child: "OutlineNode") -> "OutlineNode":
        self.children.append(child)
        return child


@dataclass
class OutlineMarker:
    kind: str
    label: str
    depth: int
    chapter_title: Optional[str]
    covered_to: Optional[str]


@dataclass
class ParsedOutline:
    nodes: List[OutlineNode] = field(default_factory=list)
    markers: List[OutlineMarker] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    skipped_lines: int = 0


def _normalize(text: str) -> str:
    return common.normalize_digits(text).replace("\u200f", "").replace("\u200e", "").rstrip()


def _indent_of(raw: str) -> int:
    spaces = 0
    for char in raw:
        if char == "\t":
            spaces += 4
        elif char == " ":
            spaces += 1
        else:
            break
    return spaces


BULLET_RANK = {"•": 1, "◦": 1, "-": 1, "–": 1, "—": 1, "*": 1, "·": 1, "▪": 2, "‣": 2}


def _strip_bullet(text: str) -> tuple[str, str]:
    """Return (title, bullet). ``bullet`` is "" when the line has no bullet."""
    stripped = text.lstrip()
    for bullet in BULLETS:
        if stripped.startswith(bullet):
            return stripped[len(bullet):].strip(), bullet
    return stripped, ""


def parse_outline(text: str, *, max_depth: int = 4) -> ParsedOutline:
    """فهرست کتاب → درخت مباحث، فقط با اطلاعاتی که در همان متن هست.

    Level is decided in this order (first match wins):

    1. explicit keywords: «فصل/Chapter» → level 0، «درس/گفتار/Lesson» → one below the
       current chapter، «بخش/زیربخش» → one below the current درس (or فصل);
    2. numeric paths: «2-1: …» → one dash = level 1، two dashes = level 2؛ a bare
       «1. عنوان» at the start of the file is a chapter;
    3. real indentation of the line (and bullets, which usually mark a child level).

    Anything the parser cannot tell is reported in ``warnings`` instead of guessed.
    """
    if not text or not text.strip():
        raise ValidationError("متن فهرست خالی است.")
    result = ParsedOutline()
    title_probe = ""
    for probe_line in text.splitlines():
        candidate = _normalize(probe_line).strip()
        if candidate:
            title_probe = candidate
            break
    stack: List[tuple[int, OutlineNode]] = []  # (level, node)
    last_title: Optional[str] = None
    current_chapter: Optional[str] = None
    last_strong_level: int = -1  # level of the deepest فصل/درس seen
    last_level: Optional[int] = None
    last_indent = 0
    last_kind = ""
    last_topic_level: Optional[int] = None
    indent_levels: dict[int, int] = {}
    seen_structure = False
    seen_chapter = False
    preamble_skipped = 0
    noise_skipped = 0

    for raw in text.splitlines():
        line = _normalize(raw)
        if not line.strip() or SEPARATOR_RE.match(line.strip()):
            continue
        indent = _indent_of(raw)
        stripped = line.strip()
        if any(pattern.match(stripped) for pattern in HEADER_LINE_PATTERNS) or any(
            pattern.match(stripped) for pattern in END_LINE_PATTERNS
        ):
            if not seen_structure:
                preamble_skipped += 1
            else:
                noise_skipped += 1
            continue
        title_raw, bullet = _strip_bullet(stripped)
        had_bullet = bool(bullet)
        title_raw = title_raw.strip()
        if not title_raw or len(title_raw) < 2:
            result.skipped_lines += 1
            continue

        marker_kind = None
        for kind, pattern in MARKER_PATTERNS:
            if pattern.search(title_raw):
                marker_kind = kind
                break
        if marker_kind:
            result.markers.append(
                OutlineMarker(
                    kind=marker_kind,
                    label=title_raw,
                    depth=min(indent // 2, max_depth),
                    chapter_title=current_chapter,
                    covered_to=last_title,
                )
            )
            continue

        level: Optional[int] = None
        is_chapter = False
        is_subtopic = any(pattern.match(title_raw) for pattern in SUBTOPIC_PATTERNS)
        if any(pattern.match(title_raw) for pattern in CHAPTER_PATTERNS):
            level, is_chapter = 0, True
            last_strong_level = 0
        elif any(pattern.match(title_raw) for pattern in LESSON_PATTERNS):
            level = last_level if last_kind == "lesson" and last_level is not None else (1 if seen_chapter else 0)
            last_strong_level = level
        elif any(pattern.match(title_raw) for pattern in SECTION_PATTERNS):
            if last_kind == "section" and last_level is not None:
                level = last_level  # «بخش ۲» is a sibling of «بخش ۱»
            else:
                level = min((last_strong_level if last_strong_level >= 0 else 0) + 1, max_depth)
        elif is_subtopic:
            if last_kind == "sub" and last_level is not None:
                level = last_level  # «زیرعنوان ۳-۲» is a sibling of «زیرعنوان ۳-۱»
            else:
                level = min((last_topic_level if last_topic_level is not None else 0) + 1, max_depth)
        else:
            path = NUMBER_PATH_RE.match(title_raw) or NUMBER_PATH_RE.match(stripped)
            if path:
                level = min(path.group(1).count("-") + path.group(1).count("–"), max_depth)
            else:
                simple = SIMPLE_NUMBER_RE.match(stripped)
                if simple:
                    level = 1 if seen_chapter else 0
                    is_chapter = level == 0

        if level is None:
            # no keyword and no numbering: read the real shape of the line
            # (indentation first, then the bullet character as a second signal)
            if indent in indent_levels:
                indent_level = indent_levels[indent]
            else:
                parent_level = None
                for seen_indent in sorted(indent_levels):
                    if seen_indent < indent:
                        parent_level = indent_levels[seen_indent]
                indent_level = 0 if parent_level is None else min(parent_level + 1, max_depth)
            if had_bullet:
                rank = BULLET_RANK.get(bullet, 1)
                bullet_level = rank if seen_chapter else max(rank - 1, 0)
                level = min(max(bullet_level, indent_level), max_depth)
            else:
                level = indent_level
            indent_levels.setdefault(indent, level)

        title = _clean_title(title_raw)
        if not title:
            result.skipped_lines += 1
            continue
        if (
            seen_structure
            and level == 0
            and not is_chapter
            and not NUMBER_PATH_RE.match(stripped)
            and not SIMPLE_NUMBER_RE.match(stripped)
            and title_probe
            and 6 <= len(title) <= 60
            and title in title_probe
        ):
            # a repeated book title («شیمی ۲ مبتکران») is a separator, not a chapter
            noise_skipped += 1
            continue
        if level is None:
            kind = "plain"
        elif is_chapter:
            kind = "chapter"
        elif is_subtopic:
            kind = "sub"
        elif any(pattern.match(title_raw) for pattern in LESSON_PATTERNS):
            kind = "lesson"
        elif any(pattern.match(title_raw) for pattern in SECTION_PATTERNS):
            kind = "section"
        else:
            kind = "plain"

        node = OutlineNode(title=title, depth=level)
        while stack and stack[-1][1].depth >= level:
            stack.pop()
        if stack:
            stack[-1][1].add(node)
        else:
            result.nodes.append(node)
        stack.append((level, node))

        if is_chapter:
            seen_chapter = True
            current_chapter = title
            stack = [(level, node)]
        seen_structure = True
        last_title = title
        last_level = level
        last_indent = indent
        last_kind = kind
        if kind != "sub":
            last_topic_level = level

    if preamble_skipped or noise_skipped:
        parts = []
        if preamble_skipped:
            parts.append(f"{preamble_skipped} خط ابتدایی (عنوان فهرست/یادداشت)")
        if noise_skipped:
            parts.append(f"{noise_skipped} خط تکراری/پایان")
        result.warnings.append("، ".join(parts) + " نادیده گرفته شد؛ مبحث نیست.")
    if result.nodes and not seen_chapter:
        result.warnings.append(
            "هیچ خط «فصل …» در فایل پیدا نشد؛ سطح اول فایل به‌عنوان فصل خوانده شد."
        )
    if not result.nodes:
        raise ValidationError("از این متن هیچ مبحثی خوانده نشد؛ فایل فهرست را بررسی کن.")
    return result


TITLE_PREFIX_RE = (
    re.compile(r"^(فصل|درس|گفتار|بخش|زیربخش|زیرعنوان|Chapter|Lesson|Section)\s+[^\s:：ـ]+?\s*[:：ـ]\s*"),
    re.compile(r"^[۰-۹\d]+(?:[-–][۰-۹\d]+)*\s*[:：.\-]\s*"),
)


def _clean_title(title: str) -> str:
    cleaned = title.strip()
    changed = True
    while changed:
        changed = False
        for pattern in TITLE_PREFIX_RE:
            new = pattern.sub("", cleaned)
            if new != cleaned and len(new.strip()) >= 2:
                cleaned = new.strip()
                changed = True
    return cleaned.strip(" :：.-")


def _flatten(nodes: List[OutlineNode]):
    for node in nodes:
        yield node
        yield from _flatten(node.children)


def outline_stats(parsed: ParsedOutline) -> dict:
    stats = {"chapters": 0, "sections": 0, "subsections": 0, "leaves": 0, "markers": len(parsed.markers), "topics": 0}
    for node in _flatten(parsed.nodes):
        key = NODE_TYPES.get(node.depth, "subsection") + "s"
        stats[key] = stats.get(key, 0) + 1
        if not node.children:
            stats["leaves"] += 1
    stats["topics"] = sum(stats.get(key, 0) for key in ("chapters", "sections", "subsections"))
    return stats


def _compare(db: Session, book: models.Book, parsed: ParsedOutline) -> dict:
    existing = list(db.scalars(select(models.Topic).where(models.Topic.book_id == book.id)))
    by_parent: dict[Optional[int], dict[str, models.Topic]] = {}
    for topic in existing:
        by_parent.setdefault(topic.parent_id, {})[topic.title.strip()] = topic
    new_titles = [node.title for node in _flatten(parsed.nodes)]
    known = {title for titles in by_parent.values() for title in titles}
    return {
        "existing_topics": len(existing),
        "in_file": len(new_titles),
        "new_titles": len([title for title in new_titles if title.strip() not in known]),
        "already_present": len([title for title in new_titles if title.strip() in known]),
    }


def preview(db: Session, book_id: int, text: str) -> dict:
    book = db.get(models.Book, book_id)
    if not book:
        raise NotFoundError("کتاب پیدا نشد.")
    parsed = parse_outline(text)
    comparison = _compare(db, book, parsed)
    sample: list[dict] = []

    def walk(nodes: List[OutlineNode], limit: int = 20):
        for node in nodes:
            if len(sample) >= limit:
                return
            sample.append({"title": node.title, "depth": node.depth, "node_type": NODE_TYPES.get(node.depth, "subsection")})
            walk(node.children, limit)

    walk(parsed.nodes)
    return {
        "book": {"id": book.id, "title": book.title, "grade": book.grade},
        "stats": outline_stats(parsed),
        "comparison": comparison,
        "sample": sample,
        "markers": [
            {"kind": marker.kind, "label": marker.label, "chapter": marker.chapter_title, "covered_to": marker.covered_to}
            for marker in parsed.markers[:12]
        ],
        "warnings": parsed.warnings,
        "applied": False,
        "policy": "پیش‌نمایش چیزی ذخیره نمی‌کند؛ اعمال فقط «افزودن» است و هیچ مبحثی پاک یا تغییرنام نمی‌شود.",
    }


def apply_outline(db: Session, user: models.User, book_id: int, text: str) -> dict:
    book = db.get(models.Book, book_id)
    if not book:
        raise NotFoundError("کتاب پیدا نشد.")
    parsed = parse_outline(text)
    comparison = _compare(db, book, parsed)

    created = 0
    reused = 0

    def ensure(nodes: List[OutlineNode], parent: Optional[models.Topic]) -> None:
        nonlocal created, reused
        siblings = list(
            db.scalars(
                select(models.Topic).where(
                    models.Topic.book_id == book.id,
                    models.Topic.parent_id == (parent.id if parent else None),
                )
            )
        )
        by_title = {row.title.strip(): row for row in siblings}
        for index, node in enumerate(nodes):
            node_type = NODE_TYPES.get(node.depth, "subsection")
            existing = by_title.get(node.title.strip())
            if existing:
                reused += 1
                if existing.node_type == "topic" and node_type != "topic":
                    # deepen the meaning of an existing row without losing anything
                    existing.node_type = node_type
                target = existing
            else:
                target = models.Topic(
                    book_id=book.id,
                    parent_id=parent.id if parent else None,
                    node_type=node_type,
                    title=node.title,
                    order_index=len(siblings) + index,
                    depth=(parent.depth + 1) if parent else 0,
                )
                db.add(target)
                db.flush()
                target.path = (parent.path + f"{parent.id}/") if parent else "/"
                created += 1
            if node.children:
                if target.is_leaf:
                    target.is_leaf = False
                ensure(node.children, target)

    ensure(parsed.nodes, None)
    db.flush()

    coverage_note = None
    if parsed.markers:
        from . import checkups as checkups_service

        coverage_note = checkups_service.seed_coverages_from_markers(db, book, parsed.markers)

    common.audit(
        db,
        "book_outline_imported",
        user_id=user.id,
        entity_type="book",
        entity_id=book.id,
        after={"created": created, "reused": reused, "markers": len(parsed.markers)},
    )
    db.flush()
    return {
        "book": {"id": book.id, "title": book.title, "grade": book.grade},
        "created": created,
        "reused": reused,
        "stats": outline_stats(parsed),
        "markers": len(parsed.markers),
        "coverage": coverage_note,
        "applied": True,
        "warnings": parsed.warnings,
        "comparison": comparison,
        "note": "فقط افزودن: مباحث موجود دست‌نخورده ماندند و هیچ‌چیز حذف نشد.",
    }


def tree_size(db: Session, book_id: int) -> dict:
    rows = list(db.scalars(select(models.Topic).where(models.Topic.book_id == book_id)))
    leaves = db.scalar(
        select(func.count(models.Topic.id)).where(models.Topic.book_id == book_id, models.Topic.is_leaf.is_(True))
    ) or 0
    return {
        "topic_count": len(rows),
        "leaf_count": int(leaves),
        "chapters": len([row for row in rows if row.node_type == "chapter"]),
        "has_tree": bool(rows),
    }
