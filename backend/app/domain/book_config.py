"""Pure validation + normalization of book config JSON (spec 05/13).

Framework-free: no FastAPI/SQLAlchemy imports. Raises BookConfigError
carrying every issue found (capped), so authors can fix configs in one pass.

Accepted shape (see backend/book_configs/README.md)::

    {
      "book": {"stable_key", "title", "publisher", "grade", "track",
               "edition", "config_version",
               "subject": {"name", "grade"?, "track"?, "type"}},
      "node_types": ["chapter", ...],        # optional declaration
      "difficulty_levels": ["L1", ...],      # optional declaration
      "nodes": [{"key", "type", "title", "code"?, "order", "parent"?, "meta"?}],
      "test_sets": [{"key", "title", "test_type", "node"?, "meta"?}],
      "questions": [{"test_set", "sequence_no", "stable_key"?, "answer_key"?,
                     "answer_type"?, "difficulty"?, "topics"?, "meta"?}],
      "sample_data"?: bool, "notes"?: str
    }
"""

import hashlib
import json
from dataclasses import dataclass, field


ALLOWED_TEST_TYPES: tuple[str, ...] = (
    "normal",
    "checkup",
    "chapter_exam",
    "comprehensive",
    "concours",
    "mock",
    "custom",
)

_MAX_ISSUES = 100


@dataclass(frozen=True)
class ConfigIssue:
    path: str
    message: str


class BookConfigError(Exception):
    """Raised when a book config is invalid. Carries all issues found."""

    def __init__(self, issues: list[ConfigIssue], truncated: int = 0) -> None:
        self.issues = issues
        self.truncated = truncated
        super().__init__(f"invalid book config ({len(issues)} issue(s))")


@dataclass(frozen=True)
class ValidatedSubject:
    name: str
    grade: int
    track: str
    type: str


@dataclass(frozen=True)
class ValidatedBook:
    stable_key: str
    title: str
    publisher: str
    grade: int
    track: str
    edition: str
    config_version: int
    subject: ValidatedSubject


@dataclass(frozen=True)
class ValidatedNode:
    key: str
    type: str
    title: str
    code: str
    order: int
    parent_key: str | None
    meta: dict = field(compare=False)


@dataclass(frozen=True)
class ValidatedTestSet:
    key: str
    title: str
    test_type: str
    node_key: str | None
    meta: dict = field(compare=False)


@dataclass(frozen=True)
class ValidatedQuestion:
    test_set_key: str
    sequence_no: int
    stable_key: str
    answer_key: str | None
    answer_type: str
    difficulty: str | None
    topic_keys: tuple[str, ...]
    meta: dict = field(compare=False)


@dataclass(frozen=True)
class ValidatedConfig:
    book: ValidatedBook
    node_types_declared: tuple[str, ...] | None
    difficulty_levels_declared: tuple[str, ...] | None
    nodes: tuple[ValidatedNode, ...]
    test_sets: tuple[ValidatedTestSet, ...]
    questions: tuple[ValidatedQuestion, ...]
    content_hash: str
    sample_data: bool


def content_hash(config: dict) -> str:
    canonical = json.dumps(config, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _is_int(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _is_non_empty_str(value: object) -> bool:
    return isinstance(value, str) and value.strip() != ""


class _Validator:
    def __init__(self, config: object) -> None:
        self._config = config
        self.issues: list[ConfigIssue] = []
        self.truncated = 0

    def _add(self, path: str, message: str) -> None:
        if len(self.issues) < _MAX_ISSUES:
            self.issues.append(ConfigIssue(path, message))
        else:
            self.truncated += 1

    def _unknown_keys(self, obj: dict, allowed: set[str], path: str) -> None:
        for key in obj:
            if key not in allowed:
                self._add(f"{path}.{key}", f"unknown key '{key}' (allowed: {sorted(allowed)})")

    # -- top level -----------------------------------------------------
    def validate(self) -> ValidatedConfig:
        if not isinstance(self._config, dict):
            self._add("$", "config must be a JSON object")
            raise BookConfigError(self.issues, self.truncated)
        cfg = self._config
        self._unknown_keys(
            cfg,
            {"book", "node_types", "difficulty_levels", "nodes", "test_sets", "questions", "sample_data", "notes"},
            "$",
        )

        sample_data = cfg.get("sample_data", False)
        if not isinstance(sample_data, bool):
            self._add("$.sample_data", "must be a boolean")
            sample_data = False
        if "notes" in cfg and not isinstance(cfg["notes"], str):
            self._add("$.notes", "must be a string")

        book = self._validate_book(cfg.get("book"))
        node_types = self._validate_str_list(cfg.get("node_types"), "$.node_types", required=False)
        difficulties = self._validate_str_list(cfg.get("difficulty_levels"), "$.difficulty_levels", required=False)
        nodes = self._validate_nodes(cfg.get("nodes"), node_types)
        node_keys = {n.key for n in nodes}
        test_sets = self._validate_test_sets(cfg.get("test_sets"), node_keys)
        test_set_map = {t.key: t for t in test_sets}
        questions = self._validate_questions(
            cfg.get("questions"), book, test_set_map, node_keys, difficulties
        )

        if self.issues:
            raise BookConfigError(self.issues, self.truncated)
        assert book is not None  # validated above; keeps typing honest
        return ValidatedConfig(
            book=book,
            node_types_declared=tuple(node_types) if node_types is not None else None,
            difficulty_levels_declared=tuple(difficulties) if difficulties is not None else None,
            nodes=tuple(nodes),
            test_sets=tuple(test_sets),
            questions=tuple(questions),
            content_hash=content_hash(cfg),
            sample_data=sample_data,
        )

    # -- book / subject ------------------------------------------------
    def _validate_book(self, raw: object) -> ValidatedBook | None:
        if not isinstance(raw, dict):
            self._add("$.book", "book must be an object")
            return None
        self._unknown_keys(
            raw,
            {"stable_key", "title", "publisher", "grade", "track", "edition", "config_version", "subject"},
            "$.book",
        )
        stable_key = raw.get("stable_key")
        title = raw.get("title")
        publisher = raw.get("publisher")
        grade = raw.get("grade")
        track = raw.get("track")
        edition = raw.get("edition")
        version = raw.get("config_version")
        ok = True
        if not _is_non_empty_str(stable_key):
            self._add("$.book.stable_key", "must be a non-empty string"); ok = False
        if not _is_non_empty_str(title):
            self._add("$.book.title", "must be a non-empty string"); ok = False
        if not _is_non_empty_str(publisher):
            self._add("$.book.publisher", "must be a non-empty string"); ok = False
        if not _is_int(grade) or (grade if _is_int(grade) else 0) < 1:
            self._add("$.book.grade", "must be an integer >= 1"); ok = False
        if not _is_non_empty_str(track):
            self._add("$.book.track", "must be a non-empty string"); ok = False
        if not _is_non_empty_str(edition):
            self._add("$.book.edition", "must be a non-empty string"); ok = False
        if not _is_int(version) or (version if _is_int(version) else 0) < 1:
            self._add("$.book.config_version", "must be an integer >= 1"); ok = False
        subject = self._validate_subject(raw.get("subject"), grade if _is_int(grade) else None,
                                         track if isinstance(track, str) else None)
        if not ok or subject is None:
            return None
        assert isinstance(stable_key, str) and isinstance(title, str) and isinstance(publisher, str)
        assert isinstance(track, str) and isinstance(edition, str)
        assert _is_int(grade) and _is_int(version)
        return ValidatedBook(
            stable_key=stable_key.strip(), title=title.strip(), publisher=publisher.strip(),
            grade=grade, track=track.strip(), edition=edition.strip(),
            config_version=version, subject=subject,
        )

    def _validate_subject(self, raw: object, book_grade: int | None, book_track: str | None) -> ValidatedSubject | None:
        if not isinstance(raw, dict):
            self._add("$.book.subject", "subject must be an object")
            return None
        self._unknown_keys(raw, {"name", "grade", "track", "type"}, "$.book.subject")
        name = raw.get("name")
        grade = raw.get("grade", book_grade)
        track = raw.get("track", book_track)
        type_ = raw.get("type")
        ok = True
        if not _is_non_empty_str(name):
            self._add("$.book.subject.name", "must be a non-empty string"); ok = False
        if not _is_int(grade) or grade < 1:
            self._add("$.book.subject.grade", "must be an integer >= 1"); ok = False
        if not _is_non_empty_str(track):
            self._add("$.book.subject.track", "must be a non-empty string"); ok = False
        if not _is_non_empty_str(type_):
            self._add("$.book.subject.type", "must be a non-empty string (e.g. 'specialized')"); ok = False
        if not ok:
            return None
        assert isinstance(name, str) and isinstance(track, str) and isinstance(type_, str)
        assert _is_int(grade)
        return ValidatedSubject(name=name.strip(), grade=grade, track=track.strip(), type=type_.strip())

    def _validate_str_list(self, raw: object, path: str, *, required: bool) -> list[str] | None:
        if raw is None:
            if required:
                self._add(path, "is required")
            return None
        if not isinstance(raw, list):
            self._add(path, "must be a list of strings")
            return None
        out: list[str] = []
        seen: set[str] = set()
        for i, item in enumerate(raw):
            if not _is_non_empty_str(item):
                self._add(f"{path}[{i}]", "must be a non-empty string")
                continue
            assert isinstance(item, str)
            value = item.strip()
            if value in seen:
                self._add(f"{path}[{i}]", f"duplicate value '{value}'")
                continue
            seen.add(value)
            out.append(value)
        return out

    # -- nodes ---------------------------------------------------------
    def _validate_nodes(self, raw: object, declared_types: list[str] | None) -> list[ValidatedNode]:
        if not isinstance(raw, list):
            self._add("$.nodes", "nodes must be a list with at least one node")
            return []
        if not raw:
            self._add("$.nodes", "at least one node is required")
            return []
        nodes: list[ValidatedNode] = []
        seen_keys: set[str] = set()
        sibling_orders: set[tuple[str | None, int]] = set()
        parent_of: dict[str, str | None] = {}
        for i, item in enumerate(raw):
            path = f"$.nodes[{i}]"
            if not isinstance(item, dict):
                self._add(path, "must be an object")
                continue
            self._unknown_keys(item, {"key", "type", "title", "code", "order", "parent", "meta"}, path)
            key = item.get("key")
            type_ = item.get("type")
            title = item.get("title")
            code = item.get("code", key)
            order = item.get("order")
            parent = item.get("parent")
            meta = item.get("meta", {})
            ok = True
            if not _is_non_empty_str(key):
                self._add(f"{path}.key", "must be a non-empty string"); ok = False
            elif key in seen_keys:
                self._add(f"{path}.key", f"duplicate node key '{key}'"); ok = False
            if not _is_non_empty_str(type_):
                self._add(f"{path}.type", "must be a non-empty string"); ok = False
            elif declared_types is not None and type_.strip() not in declared_types:
                self._add(f"{path}.type", f"unknown node type '{type_}' (declared: {declared_types})"); ok = False
            if not _is_non_empty_str(title):
                self._add(f"{path}.title", "must be a non-empty string"); ok = False
            if not _is_non_empty_str(code):
                self._add(f"{path}.code", "must be a non-empty string"); ok = False
            if not _is_int(order) or order < 0:
                self._add(f"{path}.order", "must be an integer >= 0"); ok = False
            if parent is not None and not _is_non_empty_str(parent):
                self._add(f"{path}.parent", "must be a node key or null"); ok = False
            if not isinstance(meta, dict):
                self._add(f"{path}.meta", "must be an object"); ok = False
            if not ok:
                continue
            assert isinstance(key, str) and isinstance(type_, str) and isinstance(title, str)
            assert isinstance(code, str) and _is_int(order) and isinstance(meta, dict)
            parent_key = parent.strip() if isinstance(parent, str) else None
            if (parent_key, order) in sibling_orders:
                self._add(f"{path}.order", f"duplicate order {order} under the same parent")
                continue
            sibling_orders.add((parent_key, order))
            seen_keys.add(key)
            parent_of[key] = parent_key
            nodes.append(ValidatedNode(key=key, type=type_.strip(), title=title.strip(),
                                       code=code.strip(), order=order, parent_key=parent_key, meta=meta))

        # Cross-node checks: parent existence + cycles.
        by_key = {n.key: n for n in nodes}
        for node in nodes:
            if node.parent_key is not None and node.parent_key not in by_key:
                self._add(f"$.nodes[key={node.key}].parent",
                          f"unknown parent node key '{node.parent_key}'")
        for node in nodes:
            chain = [node.key]
            current = node.parent_key
            while current is not None and current in by_key:
                if current in chain:
                    chain.append(current)
                    self._add(f"$.nodes[key={node.key}]",
                              f"cycle detected: {' -> '.join(chain)}")
                    break
                chain.append(current)
                current = by_key[current].parent_key
        return nodes

    # -- test sets -----------------------------------------------------
    def _validate_test_sets(self, raw: object, node_keys: set[str]) -> list[ValidatedTestSet]:
        if not isinstance(raw, list):
            self._add("$.test_sets", "test_sets must be a list")
            return []
        out: list[ValidatedTestSet] = []
        seen: set[str] = set()
        for i, item in enumerate(raw):
            path = f"$.test_sets[{i}]"
            if not isinstance(item, dict):
                self._add(path, "must be an object")
                continue
            self._unknown_keys(item, {"key", "title", "test_type", "node", "meta"}, path)
            key = item.get("key")
            title = item.get("title")
            test_type = item.get("test_type")
            node = item.get("node")
            meta = item.get("meta", {})
            ok = True
            if not _is_non_empty_str(key):
                self._add(f"{path}.key", "must be a non-empty string"); ok = False
            elif key in seen:
                self._add(f"{path}.key", f"duplicate test set key '{key}'"); ok = False
            if not _is_non_empty_str(title):
                self._add(f"{path}.title", "must be a non-empty string"); ok = False
            if test_type not in ALLOWED_TEST_TYPES:
                self._add(f"{path}.test_type",
                          f"must be one of {list(ALLOWED_TEST_TYPES)}"); ok = False
            if node is not None:
                if not _is_non_empty_str(node):
                    self._add(f"{path}.node", "must be a node key or null"); ok = False
                elif node.strip() not in node_keys:
                    self._add(f"{path}.node", f"unknown node key '{node}'"); ok = False
            if not isinstance(meta, dict):
                self._add(f"{path}.meta", "must be an object"); ok = False
            if not ok:
                continue
            assert isinstance(key, str) and isinstance(title, str) and isinstance(test_type, str)
            assert isinstance(meta, dict)
            seen.add(key)
            out.append(ValidatedTestSet(key=key, title=title.strip(), test_type=test_type,
                                        node_key=node.strip() if isinstance(node, str) else None,
                                        meta=meta))
        return out

    # -- questions -----------------------------------------------------
    def _validate_questions(
        self,
        raw: object,
        book: ValidatedBook | None,
        test_sets: dict[str, ValidatedTestSet],
        node_keys: set[str],
        declared_difficulties: list[str] | None,
    ) -> list[ValidatedQuestion]:
        if not isinstance(raw, list):
            self._add("$.questions", "questions must be a list")
            return []
        out: list[ValidatedQuestion] = []
        seen_stable: set[str] = set()
        last_seq_per_set: dict[str, int] = {}
        for i, item in enumerate(raw):
            path = f"$.questions[{i}]"
            if not isinstance(item, dict):
                self._add(path, "must be an object")
                continue
            self._unknown_keys(item, {"test_set", "sequence_no", "stable_key", "answer_key",
                                      "answer_type", "difficulty", "topics", "meta"}, path)
            ts_key = item.get("test_set")
            seq = item.get("sequence_no")
            stable = item.get("stable_key")
            answer = item.get("answer_key")
            answer_type = item.get("answer_type", "choice")
            difficulty = item.get("difficulty")
            topics = item.get("topics")
            meta = item.get("meta", {})
            ok = True
            if not _is_non_empty_str(ts_key) or (isinstance(ts_key, str) and ts_key.strip() not in test_sets):
                self._add(f"{path}.test_set", f"unknown test set key '{ts_key}'"); ok = False
            if not _is_int(seq) or seq < 1:
                self._add(f"{path}.sequence_no", "must be an integer >= 1"); ok = False
            if stable is not None and not _is_non_empty_str(stable):
                self._add(f"{path}.stable_key", "must be a non-empty string"); ok = False
            if answer is not None and not _is_non_empty_str(answer):
                self._add(f"{path}.answer_key", "must be a non-empty string or null"); ok = False
            if not _is_non_empty_str(answer_type):
                self._add(f"{path}.answer_type", "must be a non-empty string"); ok = False
            if difficulty is not None:
                if not _is_non_empty_str(difficulty):
                    self._add(f"{path}.difficulty", "must be a non-empty string or null"); ok = False
                elif declared_difficulties is not None and difficulty.strip() not in declared_difficulties:
                    self._add(f"{path}.difficulty",
                              f"unknown difficulty '{difficulty}' (declared: {declared_difficulties})"); ok = False
            topic_keys: list[str] = []
            if topics is None:
                ts = test_sets.get(ts_key.strip()) if isinstance(ts_key, str) else None
                if ts is not None and ts.node_key is not None:
                    topic_keys = [ts.node_key]
            elif not isinstance(topics, list):
                self._add(f"{path}.topics", "must be a list of node keys"); ok = False
            else:
                for t in topics:
                    if not _is_non_empty_str(t):
                        self._add(f"{path}.topics", "every topic must be a non-empty node key"); ok = False
                        break
                    assert isinstance(t, str)
                    if t.strip() not in node_keys:
                        self._add(f"{path}.topics", f"unknown node key '{t}'"); ok = False
                        break
                    if t.strip() not in topic_keys:
                        topic_keys.append(t.strip())
            if not isinstance(meta, dict):
                self._add(f"{path}.meta", "must be an object"); ok = False
            if not ok:
                continue
            assert isinstance(ts_key, str) and _is_int(seq) and isinstance(answer_type, str)
            assert isinstance(meta, dict)
            ts_name = ts_key.strip()
            # Unique + ASCENDING sequence per test set (spec 13).
            if ts_name in last_seq_per_set and seq <= last_seq_per_set[ts_name]:
                self._add(f"{path}.sequence_no",
                          f"must be ascending within test set '{ts_name}' "
                          f"(got {seq} after {last_seq_per_set[ts_name]})")
                continue
            last_seq_per_set[ts_name] = seq
            book_key = book.stable_key if book is not None else "?"
            stable_key = stable.strip() if isinstance(stable, str) else f"{book_key}:{ts_name}:{seq}"
            if stable_key in seen_stable:
                self._add(f"{path}.stable_key", f"duplicate question stable_key '{stable_key}'")
                continue
            seen_stable.add(stable_key)
            if not topic_keys:
                self._add(path, "question maps to no topic: set 'topics' or give its test set a 'node'")
                continue
            out.append(ValidatedQuestion(
                test_set_key=ts_name, sequence_no=seq, stable_key=stable_key,
                answer_key=answer.strip() if isinstance(answer, str) else None,
                answer_type=answer_type.strip(),
                difficulty=difficulty.strip() if isinstance(difficulty, str) else None,
                topic_keys=tuple(topic_keys), meta=meta,
            ))
        return out


def validate_book_config(config: object) -> ValidatedConfig:
    """Validate + normalize a raw book config dict. Raises BookConfigError."""
    return _Validator(config).validate()
