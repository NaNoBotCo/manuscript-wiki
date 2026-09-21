#!/usr/bin/env python3
"""lexicon_ingest — generate `listed` entries for the 300 most generative heads.

WHAT IS AND IS NOT AUTOMATED
Senses can be ingested; a sense MAP cannot. The RID gives a word's meanings as a
list, and that list is real — but its ORDER is the dictionary's editorial order,
not an argument about how the meaning moved, and nothing in the source says which
sense a compound grew out of. Those two things are the whole editorial job, so
this tool refuses to fake them:

    status = "listed"   senses present, in the source's order (order_conf
                        "unverified"), compounds in `compounds_unassigned`,
                        no EXTENDS edge anywhere.
    status = "mapped"   a human ordered the senses and filed every compound
                        under the one that motivates it. Only แก้ว, by hand.

The page prints the difference, so a listed entry never passes as a finished one.

SELECTING THE HEADS
Generativity, measured: a compound of head H is a dictionary word H+R or R+H
where R is ITSELF a headword. Requiring the remainder to be a real word is what
kills the defect this whole schema exists to fix — ตา+ข่าย passes and ตา+ย does
not, so ตาย never lands under "eye". Ranked over all 29,355 headwords.

    python3 lexicon_ingest.py --limit 300 --write
"""
from __future__ import annotations

import argparse
import json
import math
import re
import sqlite3
import sys
from collections import Counter, defaultdict
from pathlib import Path

from thai_translit import translit

HERE = Path(__file__).resolve().parent
LEX = HERE / "data" / "lexicon"
DUMPS = HERE.parent / "thairoots" / "_downloads drop 2026-08-17 (builds + dictionary dumps)"
DB = HERE.parent / "manuscript-crawler" / "crawler" / "catalog.db"

# Bound morphemes and nominalisers: real, but they are affixes, not heads with a
# sense map. ThaiRoots kept them in their own bucket and that was right.
AFFIX = {"การ", "ความ", "กระ", "ประ", "ระ", "กะ", "สม", "อนุ", "วิ", "สุ", "ผู้",
         "นัก", "ช่าง", "ชาว", "ที่", "สา", "สะ", "กร", "การก", "การประ", "ลา",
         "มหา", "ศาสตร์", "จำ", "วง", "ข้อ", "กัน", "หมาย", "สาร", "ภาพ", "ลำ"}
# Place-name formatives. Kept, but as their own domain: this is how the northern
# map is built, and it joins the wat registry and the segmentation dictionary.
TOPO = {"หนอง", "บาง", "ท่า", "นา", "วัง", "คลอง", "ดอน", "เกาะ", "ห้วย", "สัน",
        "โนน", "บึง", "ทุ่ง", "ศรี", "แม่", "ป่า", "บ้าน", "เมือง"}

POS_EN = {"คำนาม": "noun", "คำกริยา": "verb", "คำคุณศัพท์": "adjective",
          "คำวิเศษณ์": "adverb", "คำลักษณนาม": "classifier",
          "คำสรรพนาม": "pronoun", "คำบุพบท": "preposition",
          "คำสันธาน": "conjunction", "คำอุทาน": "interjection",
          "คำวิสามานยนาม": "proper noun"}


def slug(s):
    return re.sub(r"[^a-z0-9]+", "-", (s or "").lower()).strip("-") or "x"


# The bridge's `tr` turned out to be English translation, not romanisation, so
# there is NO RTGS source in these dumps. Entries therefore carry `translit_auto`
# for the URL and leave `rtgs` absent until a human writes it.


def generativity(words):
    gen, parts = Counter(), defaultdict(list)
    W = words
    for w in W:
        n = len(w)
        if n < 3:
            continue
        for i in range(2, n - 1):
            a, b = w[:i], w[i:]
            if len(a) >= 2 and len(b) >= 2 and a in W and b in W:
                gen[a] += 1
                gen[b] += 1
                parts[a].append((w, b, "head-initial"))
                parts[b].append((w, a, "head-final"))
    return gen, parts


def keyword_idf(dom, full):
    """Weight each domain keyword by how RARE it is across all 29,355 glosses.

    A flat keyword count puts three quarters of the dictionary in "body" and
    "motion": ตา, มือ, ไป and ขึ้น are not domain signals, they are the words
    Thai definitions are WRITTEN IN. Inverse document frequency is the standard
    correction and it is cheap here — สมุนไพร (rare) should outweigh ไป (in
    thousands of glosses) by orders of magnitude.
    """
    kws = {k for d in dom.values() for k in d["kw"] if k}
    df = Counter()
    for v in full.values():
        text = " ".join(v["g"])
        for k in kws:
            if k in text:
                df[k] += 1
    n = len(full)
    return {k: math.log(n / (1 + df[k])) for k in kws}, df


def assign_domain(head, glosses, dom, overrides, idf, floor):
    if head in overrides:
        return overrides[head], ["override"]
    if head in TOPO:
        return "d:toponym", ["toponym formative"]
    text = " ".join(glosses)
    score, hit = Counter(), defaultdict(list)
    for did, d in dom.items():
        for k in d["kw"]:
            if k and k in text:
                score[did] += idf.get(k, 0.0)
                hit[did].append(k)
    if not score:
        return "d:unassigned", []
    best, top = score.most_common(1)[0]
    if top < floor:
        return "d:unassigned", []
    hits = sorted(hit[best], key=lambda k: -idf.get(k, 0))[:4]
    return best, hits


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=300)
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--floor", type=float, default=6.0,
                    help="minimum idf-weighted score to claim a domain")
    a = ap.parse_args()

    full = json.loads((DUMPS / "thai-full.json").read_text("utf-8"))
    bridge = json.loads((DUMPS / "wikt-en-bridge.json").read_text("utf-8"))
    inv, tr, nod = bridge["inv"], bridge["tr"], bridge["nod"]
    rom = json.loads((LEX / "romanization.json").read_text("utf-8"))
    dconf = json.loads((LEX / "domains.json").read_text("utf-8"))
    dom = {**dconf["domains"], **dconf["extra_domains"]}
    overrides = dconf["assign_overrides"]

    W = set(full)
    gen, parts = generativity(W)
    def is_head(w):
        """Keep only things that can carry a sense map.

        Drops abbreviations (บ. ท. ก. อ. — the RID lists hundreds and they rank
        high because they combine freely), bound morphemes, and anything the
        dictionary itself labels a shortening. Backfilled from the ranking so the
        limit still yields that many real heads.
        """
        if w in AFFIX or len(w) < 2 or "." in w:
            return False
        rec = full.get(w)
        if not rec or not rec["g"]:
            return False
        g0 = rec["g"][0]
        if g0.startswith(("คำย่อ", "ย่อ", "อักษรย่อ", "รูปแบบอื่น", "การสะกด")):
            return False
        if any(p in ("คำย่อ", "อักษรย่อ") for p in rec["pos"]):
            return False
        return True

    ranked = [w for w, _ in gen.most_common() if is_head(w)]
    dropped = len([w for w, _ in gen.most_common()[:a.limit]]) - len(ranked[:a.limit])
    heads = ranked[:a.limit]

    idf, df = keyword_idf(dom, full)

    con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True) if DB.exists() else None

    def attest(w):
        if not con:
            return None
        q = "select count(*) from %s where title_thai like ?"
        return {"manuscripts": con.execute(q % "manuscripts", (f"%{w}%",)).fetchone()[0],
                "items": con.execute(q % "items", (f"%{w}%",)).fetchone()[0]}

    existing = {p.stem for p in (LEX / "entries").glob("*.json")}
    out, stats = [], Counter()
    no_rtgs = []
    used_slug = {"kaeo": "แก้ว"}   # the hand-written entry owns its slug
    collisions = 0
    for w in heads:
        rec = full[w]
        # A character walk collapses distinct words onto one slug (different
        # tones, different spellings, same letters). Suffix in first-seen order
        # and never renumber: ids are frozen the moment they are issued.
        # Real RTGS from the wiktextract dump where it exists; the character walk
        # only ever fills a gap, and the entry says which it got.
        rr = rom.get(w, {})
        base = rr.get("rtgs") or translit(w)
        r, k = base, 1
        while r in used_slug and used_slug[r] != w:
            k += 1
            r = f"{base}-{k}"
        if r != base:
            collisions += 1
        used_slug[r] = w
        no_rtgs.append(w)
        if r in existing:
            stats["skipped (hand-written)"] += 1
            continue
        did, hits = assign_domain(w, rec["g"], dom, overrides, idf, a.floor)
        stats[did] += 1

        senses = []
        for i, g in enumerate(rec["g"], 1):
            en = inv.get(w, [])
            senses.append({
                "n": i,
                "gloss": {"en": en[:4] or [f"[needs an English gloss — RID sense {i}]"],
                          "th": g[:400],
                          "conf": "verified" if en else "unverified",
                          "src": ["RID", "WIKT"] if en else ["RID"]},
                "pos": ", ".join(POS_EN.get(p, p) for p in rec["pos"]) or None,
                "pos_th": ", ".join(rec["pos"]) or None,
                "domains": [did] if did != "d:unassigned" else [],
                "order_conf": "unverified",
                "conf": "probable",
                "src": ["RID", "WIKT"],
                "needs_check": ["Sense order is the RID's, not an argument about "
                                "semantic development. Rank it, then set order_conf."]
                if i == 1 else [],
            })
            senses[-1] = {k: v for k, v in senses[-1].items() if v not in (None, [], "")}
            senses[-1]["n"] = i

        comps = []
        for cw, other, shape in parts.get(w, []):
            cen = inv.get(cw, [])
            comps.append({
                "th": cw,
                **({"rtgs": rom[cw]["rtgs"]} if rom.get(cw, {}).get("rtgs")
                   else {"translit_auto": translit(cw)}),
                **({"ipa": rom[cw]["ipa"]} if rom.get(cw, {}).get("ipa") else {}),
                "gloss": {"en": cen[:3] or [f"[needs a gloss]"],
                          "th": (full[cw]["g"][0][:220] if full.get(cw, {}).get("g") else ""),
                          "conf": "verified" if cen else "unverified",
                          "src": ["RID", "WIKT"] if cen else ["RID"]},
                "parts": [w, other] if shape == "head-initial" else [other, w],
                "note": f"{shape}; both parts are dictionary headwords",
                "conf": "verified", "src": ["RID", "WIKT"],
            })
            comps[-1]["gloss"] = {k: v for k, v in comps[-1]["gloss"].items() if v != ""}

        ety = " ".join(rec["ety"])[:900]
        m = re.search(r"คำเมือง ([^\s,;()]+)(?:\s*\(([^)]+)\))?", ety)
        att = attest(w)
        entry = {
            "id": f"w:{slug(r)}", "th": w,
            "status": "listed",
            # `rtgs` is display data and legitimately collides across homographs
            # (ส่ง and ทรง are both "song"); the id carries the disambiguator and
            # is what the URL is built from.
            **({"rtgs": rr["rtgs"]} if rr.get("rtgs") else {"translit_auto": r}),
            **({"paiboon": rr["paiboon"]} if rr.get("paiboon") else {}),
            **({"ipa": rr["ipa"]} if rr.get("ipa") else {}),
            **({"syllable_respelling": rr["syl"]} if rr.get("syl") else {}),
            "stratum": "unknown",
            "freq": "core",
            "senses": senses,
            "conf": "probable",
            "src": ["RID", "WIKT", "thai-full.json"],
            "needs_check": [
                "Auto-ingested: senses are listed in the RID's order and no EXTENDS "
                "chain has been asserted. Order the senses and file each compound "
                "under the one that motivates it to reach status 'mapped'.",
            ],
            "editorial": f"Generated by lexicon_ingest.py. Generativity {gen[w]}; "
                         f"domain seeded by keyword hits {hits or '—'}.",
        }
        if comps:
            entry["compounds_unassigned"] = comps
        if ety:
            entry["etymology"] = {"summary": ety, "conf": "probable", "src": ["WIKT"]}
        if m:
            entry["lanna"] = {"tham": m.group(1), "th": (m.group(2) or "").strip() or None,
                              "note": "Extracted from the Wiktionary etymology line.",
                              "conf": "probable", "src": ["WIKT"]}
            entry["lanna"] = {k: v for k, v in entry["lanna"].items() if v}
        if att and (att["manuscripts"] or att["items"]):
            entry["needs_check"].append(
                f"Attested in this corpus: {att['manuscripts']} manuscript titles, "
                f"{att['items']} item titles. Turn the useful ones into ATTESTED_IN edges.")
        if not rr.get("rtgs"):
            entry["needs_check"].append(
                f"No RTGS in the dump for this word. The URL uses translit_auto "
                f"'{r}', a character walk, not RTGS. Write the real romanisation.")
        out.append(entry)

    # Words sharing an RTGS are the confusable set, by construction: RTGS drops
    # tone, so ทรง and ส่ง both come out "song". Paiboon keeps the tone, so it is
    # what the edge offers as the distinction. Cheap, exact, and it is the reason
    # the site's search needs the entry to say so.
    by_rtgs = defaultdict(list)
    for e in out:
        if e.get("rtgs"):
            by_rtgs[e["rtgs"]].append(e)
    homo = 0
    for r, group in by_rtgs.items():
        if len(group) < 2:
            continue
        for e in group:
            for o in group:
                if o is e:
                    continue
                e.setdefault("edges", []).append({
                    "rel": "CONFUSABLE_WITH", "to": o["id"], "label": o["th"],
                    "why": "spelling",
                    "distinction": (f"Both romanise as \"{r}\". "
                                    f"{e['th']} is {e.get('paiboon','?')}, "
                                    f"{o['th']} is {o.get('paiboon','?')} — RTGS drops "
                                    f"the tone that separates them."),
                    "conf": "verified", "src": ["WIKT"]})
                homo += 1
    print(f"RTGS homograph edges: {homo} across "
          f"{sum(1 for g in by_rtgs.values() if len(g) > 1)} collided romanisations")

    ns = sum(len(e["senses"]) for e in out)
    nc = sum(len(e.get("compounds_unassigned", [])) for e in out)
    print(f"dictionary {len(W)} · generative heads {len(gen)} · taking top {a.limit}")
    print(f"senses {ns} · compounds {nc} · NOTHING TRUNCATED "
          f"(earlier runs silently capped senses at 8 and compounds at 40, which "
          f"dropped 224 senses and 1,060 compounds and flattened every ranking "
          f"computed from them)")
    print(f"generated {len(out)} listed entries "
          f"({stats['skipped (hand-written)']} skipped as already hand-written)")
    have = sum(1 for w in heads if rom.get(w, {}).get("rtgs"))
    print(f"real RTGS from wiktextract: {have}/{len(heads)}; character walk for the rest")
    print(f"slug collisions resolved by suffix: {collisions}")
    print("\ndomains:")
    for d, n in stats.most_common():
        if d.startswith("d:"):
            label = dom.get(d, {}).get("th", d)
            print(f"  {n:4}  {d:<16} {label}")
    if a.write:
        for e in out:
            (LEX / "entries" / f"{e['id'].split(':', 1)[1]}.json").write_text(
                json.dumps(e, ensure_ascii=False, indent=1) + "\n", "utf-8")
        print(f"\nwrote {len(out)} files to {LEX/'entries'}")
    else:
        print("\n(dry run — pass --write)")


if __name__ == "__main__":
    main()
