#!/usr/bin/env python3
"""extract_senses — pull per-sense glosses, examples and tags out of wiktextract.

WHY THIS EXISTS
Filing 8,078 compounds under the sense each one belongs to looked like a job for
text similarity, and the two cheap signals in thai-full.json both turned out to be
too thin to carry it: the gloss names its own compound only 1.6% of the time, and
only 0.8% of senses carry the ปริยาย figurative marker. A similarity-only matcher
on one-line Thai glosses would have produced confident-looking guesswork.

Wiktionary's own sense entries solve it directly. Each sense carries `examples`,
and for Thai those examples are very often the COMPOUNDS of the headword — ใจ's
"breath" sense lists กลั้นใจ, อึดใจ, หายใจ. That is not an inference; it is the
dictionary filing the compound under the sense itself. Anything matched this way
is sourced, not proposed.

    python3 scripts/extract_senses.py
    -> data/lexicon/senses.json  {word: [{gloss, examples[], tags, topics, cls}]}
"""
from __future__ import annotations

import gzip
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
DUMP = (HERE.parent / "thairoots" /
        "_downloads drop 2026-08-17 (builds + dictionary dumps)" /
        "raw-wiktextract-data.jsonl.gz")
OUT = HERE / "data" / "lexicon" / "senses.json"


def main():
    table, n_ex = {}, 0
    with gzip.open(DUMP, "rt", encoding="utf-8") as fh:
        for line in fh:
            if '"th"' not in line:
                continue
            try:
                d = json.loads(line)
            except Exception:
                continue
            if d.get("lang_code") != "th" or not d.get("word"):
                continue
            rows = table.setdefault(d["word"], [])
            for s in d.get("senses", []) or []:
                g = s.get("glosses") or []
                if not g:
                    continue
                ex = [x.get("text", "") for x in (s.get("examples") or [])
                      if x.get("text")]
                n_ex += len(ex)
                rows.append({
                    "gloss": g[0],
                    "pos": d.get("pos"),
                    "examples": ex,
                    "tags": s.get("tags") or [],
                    "topics": s.get("topics") or [],
                    "cls": [c.get("classifier") for c in (s.get("classifiers") or [])
                            if c.get("classifier")],
                })
    table = {k: v for k, v in table.items() if v}
    OUT.write_text(json.dumps(table, ensure_ascii=False), "utf-8")
    withex = sum(1 for v in table.values() for s in v if s["examples"])
    tot = sum(len(v) for v in table.values())
    print(f"words {len(table)} · senses {tot} · senses carrying examples {withex}")
    print(f"example strings {n_ex}")
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
