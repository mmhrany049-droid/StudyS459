# Book Configs (Phase 1 — config-driven, spec 05)

Every book is defined by ONE JSON file. The importer (`POST /books/import`)
is fully generic: it has **zero per-book conditions** (spec 03 forbids them).
Any hierarchy, any node types, any depth.

> ⚠️ **SAMPLE DATA**: the three shipped configs contain illustrative
> structures and *generated* answer keys. They exist to prove the three
> different hierarchies load (spec 17) and to exercise Phase 2+.
> Replace them with real book content before real use.

## Files

| file | book | hierarchy | notes |
|---|---|---|---|
| `chem2_mobtakeren.json` | شیمی ۲ — مبتکران | chapter → title → subtitle? | checkups span titles (multi-topic), 2 chapter exams, book-end concours 1404 |
| `hesab1_olgoo.json` | حسابان ۱ — نشر الگو | chapter → lesson → section | one drill set per section with `L1/L2/L3` difficulties, concours per lesson |
| `phys2_kheilisabz.json` | فیزیک ۲ — خیلی سبز | chapter → section → subsection | drills per section + chapter exams |

## Schema

```json
{
  "book": {
    "stable_key": "chem2_mobtakeren",   // required, unique, never reused
    "title": "شیمی ۲",                    // required
    "publisher": "مبتکران",               // required
    "grade": 11, "track": "mathematics", // required
    "edition": "1404",                   // required
    "config_version": 1,                 // required, int >= 1
    "subject": {"name": "شیمی", "type": "specialized"}
      // name+type required; grade/track default to the book's
  },
  "node_types": ["chapter", "title", "subtitle"],  // optional declaration;
      // if present, every node.type must be in it (typo guard)
  "difficulty_levels": ["L1", "L2", "L3"],         // optional, same idea
  "nodes": [
    {"key": "ch1", "type": "chapter", "title": "...", "order": 1,
     "code": "1",            // optional, defaults to key
     "parent": "ch1",        // optional (null = root)
     "meta": {}}             // optional object
  ],
  "test_sets": [
    {"key": "ch1_check1", "title": "...", "test_type": "checkup",
     "node": "ch1",          // optional anchor node
     "meta": {}}
  ],
  "questions": [
    {"test_set": "ch1_check1", "sequence_no": 1,
     "stable_key": "...",    // optional, auto: book:set:seq
     "answer_key": "2",      // optional (null = pending-correction flow)
     "answer_type": "choice",// optional, default "choice"
     "difficulty": "L1",     // optional
     "topics": ["ch1_t1"],   // optional, defaults to the test set's node;
                             // MUST resolve to >= 1 topic (multi-topic ok)
     "meta": {}}
  ],
  "sample_data": true,       // optional marker
  "notes": "..."             // optional string
}
```

`test_type` vocabulary (spec 02): `normal | checkup | chapter_exam |
comprehensive | concours | mock | custom`.

## Validation rules (spec 13)

- `stable_key` unique (book globally, question per book).
- No tree cycles; parent must exist and belong to the same book (by construction).
- Sibling `order` unique; `sequence_no` unique **and ascending** per test set.
- Unknown keys are rejected (catches typos like `"test_set"` vs `"test_sets"`).
- JSON `true` is NOT accepted where an int is expected.
- Every question must map to ≥ 1 topic (`topics`, or the test set's `node`).

## Import behavior

- First import → `201 {"status": "imported", ...}` (book auto-activates).
- Same file again → `200 {"status": "unchanged", ...}` (hash-verified, no duplicates).
- Same `stable_key`, different content → `409 book_already_imported`
  (v1 has no structural re-import/update; history-safe by design).
- Invalid file → `422 invalid_book_config` with `details.issues: [{path, message}]`.

```bash
curl -s -X POST localhost:8000/books/import -H 'Content-Type: application/json' \
  -d @book_configs/chem2_mobtakeren.json
```

## Authoring sample questions (dev only)

`devtools/gen_samples.py` + `devtools/plans/*.plan.json` generate the
deterministic sample questions (seeded RNG). Runtime never uses them:

```bash
python devtools/gen_samples.py devtools/plans/chem2.plan.json
```
