#!/usr/bin/env python3
"""Bridge the two wat universes. Zero network.

THE PROBLEM
This stack holds temples twice and joins them nowhere.

  wat-registry/registry.db   43,858 temples, permanent รหัสวัด, nikaya, rank,
                             founding year, ตำบล/อำเภอ/จังหวัด — and 98
                             coordinates in the whole country.
  wichaa-vault/places/       1,459 wats, every one with a coordinate, photos,
                             heritage marks, Wikipedia articles — and no code.

6,203 manuscripts already carry a `wat_code`. 1,494 place pages already exist.
Neither knows about the other, so no page can say the one thing a reader of a
temple page most wants to know: **what this temple holds.**

WHAT THIS WRITES
  data/wat_bridge.json   {place_id: {wat_code, name_th, matched_how, manuscripts}}
  cache/wat_bridge_review.txt   the ones a person has to settle

HOW THE JOIN WORKS
Only temples the catalogue actually cites are worth bridging — the register's
other 42,000 have nothing to hold. So the candidate set is the 113 distinct
`wat_code` values already stamped on manuscripts, and the question is only
which vault place each one is.

  1. narrow the register row to its จังหวัด, mapped to the vault's province
  2. compare thairom match keys against the place's name and its aliases
  3. accept only an unambiguous winner inside that province
  4. everything else is reported, never guessed

It fails closed: a temple with no confident vault place simply keeps its
manuscripts and gets no map pin, which is the truth about what we know.
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
PROJECTS = HERE.parent
REGISTRY_DB = PROJECTS / "wat-registry" / "registry.db"
CATALOG_DB = Path(__import__("os").environ.get(
    "CATALOG_DB", PROJECTS / "manuscript-crawler" / "crawler" / "catalog.db"))
WATS_GEOJSON = HERE / "data" / "wats.geojson"

sys.path.insert(0, str(PROJECTS / "wat-registry"))
from thairom import matchkey, similarity  # noqa: E402

# The register writes จังหวัด in Thai; the vault writes province in English.
CHANGWAT_EN = {
    "เชียงใหม่": "Chiang Mai", "เชียงราย": "Chiang Rai", "ลำพูน": "Lamphun",
    "ลำปาง": "Lampang", "แพร่": "Phrae", "น่าน": "Nan", "พะเยา": "Phayao",
    "แม่ฮ่องสอน": "Mae Hong Son", "อุตรดิตถ์": "Uttaradit", "ตาก": "Tak",
}
THRESHOLD = 0.86
# Two records of one name this close together are one temple written twice.
SAME_GROUND_M = 250


def _same_ground(places) -> bool:
    """True when every candidate stands within SAME_GROUND_M of the first."""
    import math
    pts = [(p.get("lat"), p.get("lng")) for p in places]
    if any(a is None or b is None for a, b in pts):
        return False
    (la0, ln0) = pts[0]
    for la, ln in pts[1:]:
        dx = (ln - ln0) * 111320 * math.cos(math.radians(la0))
        dy = (la - la0) * 110540
        if math.hypot(dx, dy) > SAME_GROUND_M:
            return False
    return True


def catalog_codes() -> dict[str, int]:
    """{wat_code: manuscripts held} — only temples the corpus actually cites."""
    con = sqlite3.connect(f"file:{CATALOG_DB}?mode=ro&immutable=1", uri=True)
    try:
        rows = con.execute(
            "SELECT wat_code, COUNT(*) FROM manuscripts "
            "WHERE wat_code IS NOT NULL AND wat_code <> '' "
            "GROUP BY wat_code").fetchall()
    finally:
        con.close()
    return {c: n for c, n in rows}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true", help="write data/wat_bridge.json")
    args = ap.parse_args()

    if not REGISTRY_DB.exists() or not WATS_GEOJSON.exists():
        print("register or vault snapshot missing — nothing to bridge")
        return

    held = catalog_codes()
    con = sqlite3.connect(f"file:{REGISTRY_DB}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    qmarks = ",".join("?" * len(held))
    temples = [dict(r) for r in con.execute(
        f"SELECT * FROM temples WHERE code IN ({qmarks}) ORDER BY code",
        list(held))]
    con.close()

    places = json.loads(WATS_GEOJSON.read_text())["wats"]
    by_province: dict[str, list] = {}
    for p in places:
        by_province.setdefault(p.get("province") or "", []).append(p)

    bridge, review, duplicates = {}, [], []
    for t in temples:
        prov_en = CHANGWAT_EN.get(t.get("changwat_th") or "", "")
        pool = by_province.get(prov_en) or []
        key = matchkey(t["name_th"])
        if not pool:
            review.append(
                f'{t["code"]}  {t["name_th"]}  ({t.get("changwat_th")})\n'
                f'    {held[t["code"]]} manuscript(s); the vault holds no place '
                f'in this province.\n')
            continue
        exact = [p for p in pool
                 if any(matchkey(n) == key
                        for n in [p.get("name"), p.get("nameRoman")] + (p.get("aliases") or []) if n)]
        cands = exact or [
            p for p in pool
            if max((similarity(key, matchkey(n)) for n in
                    [p.get("name"), p.get("nameRoman")] + (p.get("aliases") or []) if n),
                   default=0.0) >= THRESHOLD]
        # Two candidates of one name standing on the same ground are not two
        # temples — they are one temple the vault recorded twice, once from a
        # curated note and once from an OSM node. That is a duplicate to fix at
        # source, not an ambiguity to refuse: identity is not in doubt, only
        # which row carries it. The curated slug wins because it is the one a
        # person wrote and the one the URL should keep.
        dup = ""
        if len(cands) > 1 and _same_ground(cands):
            dup = " · ".join(p["id"] for p in cands)
            cands = sorted(cands, key=lambda p: (p["id"].startswith("osm-"), p["id"]))[:1]
            duplicates.append(f'    {t["name_th"]}: {dup}\n')
        if len(cands) == 1:
            p = cands[0]
            bridge[p["id"]] = {
                "wat_code": t["code"], "name_th": t["name_th"],
                    "matched_how": ("province+exact" if exact else "province+fuzzy")
                + ("+vault-duplicate" if dup else ""),
                "manuscripts": held[t["code"]],
                "sect": t.get("sect") or "", "rank": t.get("rank") or "",
                "founded_ce": t.get("founded_ce"),
                "tambon_th": t.get("tambon_th") or "",
                "amphoe_th": t.get("amphoe_th") or "",
            }
            continue
        review.append(
            f'{t["code"]}  {t["name_th"]}  ({t.get("changwat_th")})  '
            f'{held[t["code"]]} manuscript(s)\n'
            + ("".join(f'      {p["id"]}  {p.get("name")}\n' for p in cands[:6])
               if cands else "      no vault place answers to this name\n"))

    if args.write:
        out = {
            "note": ("Generated by scripts/bridge_wat_registry.py. Joins the "
                     "ONAB register code carried on 6,203 manuscripts to the "
                     "vault place that stands in the landscape. Rewritten "
                     "wholesale; ambiguous temples are in "
                     "cache/wat_bridge_review.txt and deliberately absent."),
            "source": ("ONAB temple register (B.E. 2567, Open Government Data "
                       "of Thailand) × wichaa-vault places"),
            "places": dict(sorted(bridge.items())),
        }
        (HERE / "data" / "wat_bridge.json").write_text(
            json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")

    cache = HERE / "cache"
    cache.mkdir(exist_ok=True)
    (cache / "wat_bridge_review.txt").write_text(
        f"{len(review)} temple(s) the catalogue cites that no single vault place "
        f"answers to.\nNothing here is guessed into data/wat_bridge.json.\n\n"
        + "\n".join(review), encoding="utf-8")

    if duplicates:
        (cache / "wat_vault_duplicates.txt").write_text(
            f"{len(duplicates)} temple(s) the vault holds twice — one curated "
            f"note and one OSM-derived record for the same ground.\nThe bridge "
            f"keeps the curated slug. Folding these at source would tidy "
            f"/wats and the place pages.\n\n" + "".join(duplicates),
            encoding="utf-8")

    ms = sum(v["manuscripts"] for v in bridge.values())
    print(f"wat bridge: {len(bridge)} of {len(temples)} cited temples matched "
          f"to a vault place ({ms:,} manuscripts reachable from a place page)")
    print(f"  {Counter(v['matched_how'] for v in bridge.values())}")
    print(f"  {len(review)} for review → cache/wat_bridge_review.txt")
    if not args.write:
        print("  (report only — pass --write)")


if __name__ == "__main__":
    main()
