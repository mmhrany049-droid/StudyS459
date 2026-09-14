"""Authoring aid: inject deterministic SAMPLE questions into a book config.

Runtime NEVER uses this — the importer only reads the resulting JSON files.
Re-running with the same plan reproduces the same file (seeded RNG).

Plan shape:
    {
      "config": "chem2_mobtakeren.json",
      "seed": 45901,
      "specs": [
        {"test_set": "ch1_check1", "count": 12, "topics": ["ch1_t1", "ch1_t2"]},
        {"test_set": "concours1404", "count": 15,
         "topics_cycle": [["ch1"], ["ch2"], ["ch3"]]},
        {"test_set": "sec_drill", "count": 10, "difficulty": "L1x4,L2x3,L3x3"}
      ]
    }

- "topics" omitted      -> importer default (test set's node) applies.
- "topics_cycle"        -> rotate topic lists per question (1-based sequence).
- "difficulty" omitted  -> no difficulty tag. "L1x4,L2x3" expands in order;
                           "cycle:L1,L2" rotates; "L2" fills all.
- answer_key            -> seeded random choice of "1".."4" (SAMPLE ONLY).

Usage:
    python devtools/gen_samples.py devtools/plans/chem2.plan.json
"""

import json
import random
import sys
from pathlib import Path


def _parse_difficulty(pattern: str, count: int, where: str) -> list[str]:
    if pattern.startswith("cycle:"):
        cycle = [p.strip() for p in pattern[len("cycle:"):].split(",") if p.strip()]
        if not cycle:
            raise ValueError(f"{where}: empty cycle")
        return [cycle[i % len(cycle)] for i in range(count)]
    if "x" in pattern or "," in pattern:
        out: list[str] = []
        for chunk in pattern.split(","):
            chunk = chunk.strip()
            if "x" in chunk:
                level, _, times = chunk.partition("x")
                out.extend([level.strip()] * int(times))
            else:
                out.append(chunk)
        if len(out) != count:
            raise ValueError(f"{where}: difficulty pattern yields {len(out)}, expected {count}")
        return out
    return [pattern] * count


def _dump_config(config: dict) -> str:
    """indent=2 everywhere, but one compact line per question."""
    questions = config.get("questions", [])
    head = {k: v for k, v in config.items() if k != "questions"}
    text = json.dumps(head, ensure_ascii=False, indent=2).rstrip()
    assert text.endswith("}")
    text = text[:-1].rstrip()
    if not questions:
        return text + ',\n  "questions": []\n}\n'
    lines = ",\n".join("    " + json.dumps(q, ensure_ascii=False) for q in questions)
    return text + ',\n  "questions": [\n' + lines + "\n  ]\n}\n"


def main(plan_path: str) -> None:
    plan_file = Path(plan_path)
    plan = json.loads(plan_file.read_text(encoding="utf-8"))
    configs_dir = Path(__file__).resolve().parent.parent / "book_configs"
    config_path = configs_dir / plan["config"]
    config = json.loads(config_path.read_text(encoding="utf-8"))

    seed = int(plan.get("seed", 459))
    questions: list[dict] = []
    for spec in plan["specs"]:
        ts = spec["test_set"]
        count = int(spec["count"])
        rng = random.Random(f"{seed}:{ts}")
        topics = spec.get("topics")
        topics_cycle = spec.get("topics_cycle")
        diff_pattern = spec.get("difficulty")
        difficulties = (
            _parse_difficulty(diff_pattern, count, f"spec {ts}") if diff_pattern else [None] * count
        )
        for i in range(1, count + 1):
            q: dict = {
                "test_set": ts,
                "sequence_no": i,
                "answer_key": rng.choice(["1", "2", "3", "4"]),
            }
            if topics is not None:
                q["topics"] = topics
            elif topics_cycle is not None:
                q["topics"] = topics_cycle[(i - 1) % len(topics_cycle)]
            if difficulties[i - 1] is not None:
                q["difficulty"] = difficulties[i - 1]
            questions.append(q)

    config["questions"] = questions
    config_path.write_text(_dump_config(config), encoding="utf-8")
    print(f"wrote {len(questions)} sample questions -> {config_path.name}")


if __name__ == "__main__":
    main(sys.argv[1])
