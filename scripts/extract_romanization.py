#!/usr/bin/env python3
"""extract_romanization — pull RTGS, Paiboon and IPA out of the wiktextract dump.

The bridge file's `tr` turned out to be English translation, so the lexicon had
no romanisation source and fell back to a character walk. This is the real one:
Wiktionary's Thai entries carry the Royal Institute transcription as a tagged
`sounds` entry, alongside Paiboon and IPA. One pass over the 70MB dump builds a
lookup the ingest can use, so no entry has to guess.

    python3 scripts/extract_romanization.py
    -> data/lexicon/romanization.json  {word: {rtgs, paiboon, ipa, syl}}
"""
from __future__ import annotations

import gzip
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
DUMP = (HERE.parent / "thairoots" /
        "_downloads drop 2026-08-17 (builds + dictionary dumps)" /
        "raw-wiktextract-data.jsonl.gz")
OUT = HERE / "data" / "lexicon" / "romanization.json"


def main():
    table, n, seen = {}, 0, 0
    with gzip.open(DUMP, "rt", encoding="utf-8") as fh:
        for line in fh:
            n += 1
            if '"th"' not in line:
                continue
            try:
                d = json.loads(line)
            except Exception:
                continue
            if d.get("lang_code") != "th":
                continue
            w = d.get("word")
            if not w:
                continue
            seen += 1
            rec = table.setdefault(w, {})
            for s in d.get("sounds", []) or []:
                tags = s.get("tags") or []
                if "romanization" in tags and s.get("roman"):
                    if "Royal-Institute" in tags:
                        rec.setdefault("rtgs", s["roman"])
                    elif "Paiboon" in tags:
                        rec.setdefault("paiboon", s["roman"])
                if s.get("ipa"):
                    rec.setdefault("ipa", s["ipa"])
                # the respelling line: พด-จะ-นา-นุ-กฺรม — a real syllable count
                if s.get("other") and "-" in s["other"]:
                    rec.setdefault("syl", s["other"])
    table = {k: v for k, v in table.items() if v}
    OUT.write_text(json.dumps(table, ensure_ascii=False), "utf-8")
    r = sum(1 for v in table.values() if "rtgs" in v)
    i = sum(1 for v in table.values() if "ipa" in v)
    print(f"lines {n} · Thai entries {seen} · words with any sound data {len(table)}")
    print(f"  with RTGS {r} · with IPA {i}")
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
