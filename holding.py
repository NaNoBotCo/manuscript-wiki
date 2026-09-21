#!/usr/bin/env python3
"""holding — /holding, "ถืออยู่ในมือ · I'm holding an amulet".

/need starts from a want and walks toward objects; this page starts from the
OBJECT — the unknown thing already in the reader's hand — and walks toward what
it might be and what it asks of its keeper. The reader answers the questions a
sian would ask, in the sian's order (เนื้อ first, then what the eye sees), by
TAPPING — no typing anywhere, big targets, because the person this page serves
is holding an amulet in one hand and a phone in the other.

What makes it wichaa's page and not a price guide: every candidate kind leads
with its CLASS — the one fact a sale listing almost never states — read at
build time from the vault vocabulary (classes.md): does anything live in this
vessel, what does the keeper owe it, and how much does its history matter.
The four kinds the vocabulary refuses to classify stay visibly unclassified;
recording that refusal is the point, not a gap.

Sourcing discipline, stated on the page: class facts and keeping come from the
vault vocabulary (Tradition); listing counts and prices from catalog.db
(Catalogue); the figure-and-material mapping that drives the picker is this
page's own curation (Inference) and says so.

Self-contained like glossary.py / yant_index.py: no wiki.py import, writes its
own HTML + api/holding.json. Declared in routes.py with built_by="holding.py";
run from publish_site.sh (step 2a-5) BEFORE site_meta so the sitemap sees it.

    python3 holding.py --docs ../nanobotco-lanna/docs --site-url https://wichaa.net

Writes  docs/holding/index.html  +  docs/api/holding.json
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sqlite3
import statistics
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
CRAWLER = HERE.parent / "manuscript-crawler"
VAULT_VOCAB = HERE.parent / "wichaa-vault" / "_meta" / "vocab" / "classes.md"
KEY_JSON = HERE / "data" / "holding_key.json"

# publish_site.sh points CATALOG_DB at its point-in-time snapshot; honour that
# first so this build reads the same frozen catalogue as everything else in the
# run (and can never trip over the live crawler's hot journal).
DB = Path(os.environ.get("CATALOG_DB") or (CRAWLER / "crawler" / "catalog.db"))


# ------------------------------------------------------------- vault vocabulary

# The keeper's answer to "can I set it down?", keyed by the vocabulary's own
# upkeep values. Phrasing is deliberate: each names a practice, none plants a
# fear — the page is about veneration, not suspicion (the /nuea rule).
UPKEEP_TH = {
    "none": "ไม่มีผู้อยู่ · ไม่ต้องเลี้ยง",
    "veneration": "ถวายความเคารพ",
    "feeding": "เลี้ยงดูอย่างคนในบ้าน",
    "feeding_and_closing": "เลี้ยง และปิดให้ถูกเมื่อวางมือ",
}
UPKEEP_EN = {
    "none": "nobody home — nothing owed, adopt freely",
    "veneration": "kept with respect: offerings and regard, not meals",
    "feeding": "kept as family: fed, named, spoken to",
    "feeding_and_closing": "a knower's keeping: fed, and closed properly when set down",
}
PROV_EN = {
    "low": "history is a price question, not a safety one",
    "medium": "worth asking who kept it",
    "high": "ask its whole story before it comes home",
}
RESIDENT_EN = {
    "none": "no resident",
    "deva": "a deva venerated through it",
    "raised_spirit": "a raised child-spirit lives in it",
    "ghost": "a ghost of untimely death, bound by rite",
    "animated": "an animation compelled to serve",
}

# Group order on the page: the impersonal tiers first (the classes the
# second-hand market is built on), then the tiers where someone is home, then
# the kinds the vocabulary leaves to a knower. Class-first IS the page.
CLASS_ORDER = ["phra_khrueang", "yantra_wattu", "khong_thammachat",
               "thep_thewada", "hun_phayon", "kuman", "prai", None]


def parse_classes(path: Path) -> dict:
    """The seven class entries out of the vault's classes.md yaml blocks.

    A hand parser on purpose (no yaml dependency in this repo), reading only
    the scalar fields this page renders. Refuses to continue if the vocabulary
    is missing or short — a build without the class layer would still render
    and would quietly be a price guide, which is the one thing this page must
    never be (same refusal search_index.py makes over the tags table).
    """
    if not path.is_file():
        sys.exit(f"holding: class vocabulary not found at {path} — "
                 f"refusing to build the page without its disclosure layer")
    entries: dict[str, dict] = {}
    cur = None
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.rstrip()
        m = re.match(r"^- key:\s*(\S+)", line)
        if m:
            cur = {"key": m.group(1)}
            entries[cur["key"]] = cur
            continue
        if cur is None:
            continue
        m = re.match(r"^  (term|roman|en_gloss|resident|upkeep|provenance_sensitivity|confidence):\s*(.+?)\s*$", line)
        if m:
            cur[m.group(1)] = m.group(2)
        elif line and not line.startswith(" ") and not line.startswith("-"):
            cur = None  # left the yaml block (prose, headings, fences)
    if len(entries) < 7:
        sys.exit(f"holding: parsed only {len(entries)} classes from {path} — "
                 f"the vocabulary should carry 7; fix the parse, not the page")
    return entries


# ------------------------------------------------------------------- catalogue

def survives(hay: str, term: str, excludes: list[str]) -> bool:
    """The axis_match rule: DELETE the excluded strings, then test — never
    reject a text merely for containing a collision, or a listing holding both
    a real ว่าน and a stray กว่าน is lost."""
    for ex in excludes:
        hay = hay.replace(ex, "")
    return term in hay


def market_facts(conn, kinds: list[dict]) -> None:
    """Mutates each kind with listings / priced / price stats from items.

    Titles only (Thai + English) — a title is the seller's own claim about what
    the thing IS; descriptions sweep in freebie mentions (แถมตะกรุด…) that
    would inflate every count.
    """
    rows = conn.execute(
        "SELECT COALESCE(title_thai,'') || ' ' || COALESCE(title_english,'') AS hay, "
        "       price_value "
        "FROM items WHERE kind='amulet'").fetchall()
    for k in kinds:
        terms, excludes = k["search"], k.get("excludes") or []
        n, prices = 0, []
        for hay, price in rows:
            if any(survives(hay, t, excludes) for t in terms):
                n += 1
                if price is not None and price > 0:
                    prices.append(price)
        k["market"] = {"listings": n, "priced": len(prices)}
        if len(prices) >= 5:
            qs = statistics.quantiles(prices, n=10)
            k["market"]["p10"] = int(qs[0])
            k["market"]["p90"] = int(qs[-1])
            k["market"]["median"] = int(statistics.median(prices))


def corpus_facts(conn, kinds: list[dict]) -> None:
    """How often the treatises themselves speak each kind's name — manuscripts
    whose TITLE carries it, and digested pages whose text does. The excludes
    rule applies here too (the corpus is where กว่าน actually bit)."""
    has_pages = True
    try:
        conn.execute("SELECT transcription, translation FROM pages LIMIT 1")
    except sqlite3.OperationalError:
        has_pages = False
    for k in kinds:
        terms, excludes = k["search"], k.get("excludes") or []
        mss = 0
        for (hay,) in conn.execute(
                "SELECT COALESCE(title_thai,'')||' '||COALESCE(title_translit,'')||' '||"
                "COALESCE(title_english,'') FROM manuscripts"):
            if any(survives(hay, t, excludes) for t in terms):
                mss += 1
        pages = 0
        if has_pages:
            like = " OR ".join(
                "transcription LIKE ? OR translation LIKE ?" for _ in terms)
            params = [x for t in terms for x in (f"%{t}%", f"%{t}%")]
            for row in conn.execute(
                    f"SELECT COALESCE(transcription,'')||' '||COALESCE(translation,'') "
                    f"FROM pages WHERE {like}", params):
                if any(survives(row[0], t, excludes) for t in terms):
                    pages += 1
        k["corpus"] = {"mss": mss, "pages": pages}


# --------------------------------------------------------------------- payload

def build_payload(key: dict, classes: dict) -> dict:
    kinds = key["kinds"]
    conn = sqlite3.connect(DB) if DB.is_file() else None
    if conn is None:
        print(f"holding: no catalogue at {DB} — market/corpus facts omitted",
              file=sys.stderr)
        for k in kinds:
            k["market"] = {"listings": 0, "priced": 0}
            k["corpus"] = {"mss": 0, "pages": 0}
    else:
        try:
            market_facts(conn, kinds)
            corpus_facts(conn, kinds)
        finally:
            conn.close()

    cls_out = {}
    for ckey, c in classes.items():
        cls_out[ckey] = {
            "term": c.get("term", ckey), "roman": c.get("roman", ""),
            "gloss": c.get("en_gloss", ""),
            "resident": c.get("resident", ""), "upkeep": c.get("upkeep", ""),
            "sensitivity": c.get("provenance_sensitivity", ""),
            "upkeep_th": UPKEEP_TH.get(c.get("upkeep", ""), ""),
            "upkeep_en": UPKEEP_EN.get(c.get("upkeep", ""), ""),
            "resident_en": RESIDENT_EN.get(c.get("resident", ""), ""),
            "prov_en": PROV_EN.get(c.get("provenance_sensitivity", ""), ""),
        }

    return {
        "materials": key["materials"],
        "figures": key["figures"],
        "classes": cls_out,
        "classOrder": [c for c in CLASS_ORDER if c is None or c in cls_out],
        "kinds": kinds,
        "count": len(kinds),
        "marketTotal": sum(k["market"]["listings"] for k in kinds),
    }


# ------------------------------------------------------------------ page render

def esc(s) -> str:
    return (str(s).replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;").replace('"', "&quot;"))


def baht(n) -> str:
    return "฿{:,}".format(int(n))


def kind_card(k: dict, classes: dict) -> str:
    """One candidate kind, rendered as real static HTML (the page works with no
    JavaScript at all: every kind visible, grouped by class — JS only filters)."""
    figs = " ".join(k["figures"])
    mats = " ".join(k["materials"])
    mk = k["market"]
    market_line = ""
    if mk["listings"]:
        bits = [f"{mk['listings']:,} listings in the living market"]
        if mk.get("median") is not None:
            bits.append(f"{baht(mk['p10'])}–{baht(mk['p90'])} typical")
            bits.append(f"median {baht(mk['median'])}")
        market_line = " · ".join(bits)
    else:
        market_line = "kept in the tradition; not seen in this market crawl"
    co = k["corpus"]
    corpus_bits = []
    if co["mss"]:
        corpus_bits.append(f"{co['mss']} manuscript title{'s' if co['mss'] != 1 else ''}")
    if co["pages"]:
        corpus_bits.append(f"named on {co['pages']} treatise page{'s' if co['pages'] != 1 else ''}")
    corpus_line = " · ".join(corpus_bits)
    q = k["search"][0]
    links = [f'<a href="/browse?q={esc(q)}">in the corpus</a>',
             '<a href="/market">the living market</a>']
    if k["cls"] == "hun_phayon":
        links.append('<a href="/hun">forge one at /hun</a>')
    fuzzy = (f'<p class="fuzzy">✳ {esc(k["fuzzy"])}</p>' if k.get("fuzzy") else "")
    src_tag = {"vocab": "Tradition · vault vocabulary",
               "curated": "Inference · this page's curation"}[k["src"]]
    return f"""<article class="kind" data-f="{esc(figs)}" data-m="{esc(mats)}" id="k-{esc(k['roman']).replace(' ', '-')}">
  <h3 class="kth">{esc(k['term'])}</h3>
  <p class="ktr">{esc(k['roman'])} · {esc(k['gloss'])}</p>
  <p class="kwhat">{esc(k['what'])}</p>
  {fuzzy}
  <p class="kmarket">{esc(market_line)}</p>
  {f'<p class="kcorpus">{esc(corpus_line)}</p>' if corpus_line else ''}
  <p class="klinks">{' · '.join(links)} <span class="ksrc">{esc(src_tag)}</span></p>
</article>"""


def class_section(ckey, cinfo: dict | None, cards: list[str]) -> str:
    if not cards:
        return ""
    if ckey is None:
        head_th, head_ro = "ยังไม่ชี้ขาด", "the vocabulary leaves these to a knower"
        strip = ("Real ambiguities, recorded rather than resolved: each of these "
                 "kinds is genuinely filed two ways by the tradition itself. "
                 "The uncertainty is the accurate answer.")
        chips = ""
    else:
        head_th, head_ro = cinfo["term"], f"{cinfo['roman']} · {cinfo['gloss']}"
        strip = f"{cinfo['resident_en'].capitalize()} · {cinfo['upkeep_en']} · {cinfo['prov_en']}"
        chips = f'<span class="uchip">{esc(cinfo["upkeep_th"])}</span>'
    return f"""<section class="clsgrp" data-cls="{esc(ckey or 'unplaced')}">
  <header class="clshead">
    <h2>{esc(head_th)} <span class="clsro">{esc(head_ro)}</span></h2>
    <p class="clsstrip">{esc(strip)} {chips}</p>
  </header>
  <div class="kgrid">{''.join(cards)}</div>
</section>"""


def render_page(payload: dict, site: str, has_card: bool) -> str:
    by_class: dict = {}
    for k in payload["kinds"]:
        by_class.setdefault(k["cls"], []).append(kind_card(k, payload["classes"]))
    sections = "".join(
        class_section(ckey, payload["classes"].get(ckey), by_class.get(ckey, []))
        for ckey in payload["classOrder"])

    def picker(items, kind):
        out = []
        for i, it in enumerate(items, 1):
            out.append(
                f'<button type="button" class="pick" data-kind="{kind}" data-key="{esc(it["key"])}" '
                f'aria-pressed="false"><span class="pn">{i}</span>'
                f'<span class="pth">{esc(it["th"])}</span>'
                f'<span class="pen">{esc(it["en"])}</span>'
                f'<span class="phint">{esc(it["hint"])}</span></button>')
        return "".join(out)

    desc = (f"Holding an amulet you cannot name? Answer the questions a sian would ask "
            f"— เนื้อ (what it is made of), then what the eye sees — and meet "
            f"{payload['count']} candidate kinds, each led by its class: whether anything "
            f"lives in it, what a keeper owes it, and how much its history matters.")
    ogimg = f"{site}/holding/card.png" if has_card else f"{site}/og.jpg"
    jsonld = json.dumps({
        "@context": "https://schema.org", "@type": "CollectionPage",
        "name": "I'm holding an amulet", "url": f"{site}/holding",
        "description": desc,
        "mainEntity": {"@type": "ItemList", "numberOfItems": payload["count"]},
    }, ensure_ascii=False)

    return (PAGE
            .replace("{{SITE}}", site)
            .replace("{{DESC}}", esc(desc))
            .replace("{{OGIMG}}", ogimg)
            .replace("{{JSONLD}}", jsonld)
            .replace("{{COUNT}}", str(payload["count"]))
            .replace("{{MARKET_TOTAL}}", f"{payload['marketTotal']:,}")
            .replace("{{PICK_M}}", picker(payload["materials"], "m"))
            .replace("{{PICK_F}}", picker(payload["figures"], "f"))
            .replace("{{SECTIONS}}", sections)
            .replace("{{DATA}}", json.dumps(
                {"materials": [m["key"] for m in payload["materials"]],
                 "figures": [f["key"] for f in payload["figures"]]},
                ensure_ascii=False)))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--docs", required=True, help="the published docs/ directory")
    ap.add_argument("--site-url", default="https://wichaa.net")
    a = ap.parse_args(argv)
    docs = Path(a.docs).expanduser().resolve()
    if not docs.is_dir():
        raise SystemExit(f"holding: docs directory not found: {docs}")
    if not KEY_JSON.is_file():
        raise SystemExit(f"holding: {KEY_JSON} not found")

    key = json.loads(KEY_JSON.read_text(encoding="utf-8"))
    classes = parse_classes(VAULT_VOCAB)
    missing = {k["cls"] for k in key["kinds"]} - set(classes) - {None}
    if missing:
        raise SystemExit(f"holding: kinds reference unknown class(es) {missing} — "
                         f"fix data/holding_key.json or the vocabulary")

    payload = build_payload(key, classes)
    (docs / "api").mkdir(parents=True, exist_ok=True)
    (docs / "api" / "holding.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
    out = docs / "holding"
    out.mkdir(parents=True, exist_ok=True)
    has_card = (HERE / "publishing" / "cards" / "holding.png").is_file()
    (out / "index.html").write_text(
        render_page(payload, a.site_url.rstrip("/"), has_card), encoding="utf-8")

    zero = [k["term"] for k in payload["kinds"] if not k["market"]["listings"]
            and not k["corpus"]["mss"] and not k["corpus"]["pages"]]
    print(f"holding: {payload['count']} kinds · {payload['marketTotal']:,} market echoes "
          f"· classes {len(payload['classes'])}")
    if zero:
        print(f"holding: NOTE — {len(zero)} kind(s) with zero corpus AND zero market echo: "
              f"{', '.join(zero)} (carried on the vocabulary's word alone; the page says so)")
    print(f"         -> {out / 'index.html'}")
    return 0


PAGE = r"""<!doctype html>
<html lang="en"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>ถืออยู่ในมือ · I'm holding an amulet · wichaa</title>
<meta name="description" content="{{DESC}}">
<link rel="canonical" href="{{SITE}}/holding">
<meta property="og:type" content="website">
<meta property="og:site_name" content="wichaa">
<meta property="og:title" content="ถืออยู่ในมือ · I'm holding an amulet · wichaa">
<meta property="og:description" content="{{DESC}}">
<meta property="og:url" content="{{SITE}}/holding">
<meta property="og:image" content="{{OGIMG}}">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="ถืออยู่ในมือ · I'm holding an amulet · wichaa">
<meta name="twitter:image" content="{{OGIMG}}">
<script type="application/ld+json">{{JSONLD}}</script>
<style>
 :root{--bg:#f4efe3;--panel:#fdfbf5;--ink:#26302a;--muted:#6d6455;--gold:#a8791e;
  --gold-soft:#c9a24a;--crimson:#8c3b2e;--line:#e5dcc7;--sage:#3f5b3a;
  --serif:"Sukhumvit Set","Noto Serif Thai",Thonburi,"Iowan Old Style","Palatino Linotype",Palatino,Georgia,serif;
  --sans:"Sukhumvit Set","Noto Sans Thai",Thonburi,-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;}
 *{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);
  font-family:var(--sans);font-size:18px;line-height:1.65}
 a{color:var(--crimson);text-decoration:none}a:hover{text-decoration:underline}
 .wrap{max-width:1180px;margin:0 auto;padding:0 24px}
 header.top{text-align:center;padding:48px 24px 8px}
 .mark{font-family:var(--serif);letter-spacing:.4em;color:var(--gold);font-size:13px}
 .mark a{color:var(--gold)}
 h1{font-family:var(--serif);font-size:clamp(30px,5vw,46px);margin:14px 0 6px}
 .sub{color:#3c463f;font-family:var(--serif);font-style:italic;font-size:19px;
  max-width:740px;margin:0 auto}
 .src{margin-top:12px;font-size:14.5px;color:var(--muted);max-width:740px;
  margin-left:auto;margin-right:auto}

 .ethic{margin:26px auto 0;max-width:860px;padding:18px 22px;border:1px solid var(--line);
  border-radius:16px;background:linear-gradient(150deg,#fdfbf5,#f6efdf);font-size:15.5px}
 .ethic b{font-family:var(--serif)}

 .step{margin:26px 0 0;padding:22px 24px;border:1px solid var(--line);border-radius:18px;
  background:linear-gradient(160deg,#fdfbf5f0,#f7f1e2cc);backdrop-filter:blur(6px);
  box-shadow:0 1px 0 #fff inset,0 8px 26px -20px #6d645599}
 .step h2{font-family:var(--serif);font-size:22px;margin:0 0 2px}
 .step .lead{margin:0 0 14px;font-size:15px;color:var(--muted)}
 .picks{display:grid;gap:12px;grid-template-columns:repeat(auto-fill,minmax(240px,1fr))}
 .pick{position:relative;text-align:left;font:inherit;cursor:pointer;min-height:56px;
  padding:13px 15px 13px 52px;border:1.5px solid var(--line);border-radius:14px;
  background:var(--panel);color:var(--ink);
  transition:transform .14s cubic-bezier(.34,1.56,.64,1),border-color .16s,box-shadow .16s,background .16s}
 .pick:hover{transform:translateY(-2px);border-color:var(--gold-soft);
  box-shadow:0 10px 22px -14px #8c3b2e66}
 .pick:active{transform:scale(.965)}
 .pick:focus-visible{outline:3px solid var(--gold);outline-offset:2px}
 .pick[aria-pressed="true"]{background:var(--crimson);border-color:var(--crimson);color:#fdfbf5}
 .pick[aria-pressed="true"] .pen,.pick[aria-pressed="true"] .phint{color:#fdfbf5cc}
 .pick[aria-pressed="true"] .pn{background:#fdfbf5;color:var(--crimson)}
 .pn{position:absolute;left:13px;top:14px;width:28px;height:28px;border-radius:999px;
  background:#f0e8d4;color:var(--crimson);font-weight:700;font-size:15px;
  display:flex;align-items:center;justify-content:center}
 .pth{display:block;font-family:var(--serif);font-size:19px;line-height:1.3}
 .pen{display:block;font-size:14px;color:var(--muted)}
 .phint{display:block;font-size:13px;color:var(--muted);margin-top:4px;line-height:1.45}

 .state{position:sticky;top:0;z-index:6;background:#f4efe3ee;backdrop-filter:blur(8px);
  border-bottom:1px solid var(--line);margin-top:22px;padding:10px 0}
 .state .wrap{display:flex;gap:12px;align-items:center;flex-wrap:wrap}
 #verdict{font-size:15.5px}
 #verdict b{font-family:var(--serif)}
 #reset{font:inherit;font-size:14.5px;color:var(--crimson);cursor:pointer;border:0;
  background:none;text-decoration:underline;padding:6px 4px;min-height:44px}

 .clsgrp{margin:30px 0 0}
 .clshead h2{font-family:var(--serif);font-size:24px;margin:0}
 .clsro{font-size:15px;color:var(--gold);font-style:italic;font-weight:400;margin-left:8px}
 .clsstrip{margin:4px 0 14px;font-size:15px;color:#4a4335;border-left:3px solid var(--gold-soft);
  background:#f7f1e2;padding:9px 13px;border-radius:0 10px 10px 0}
 .uchip{display:inline-block;margin-left:8px;padding:2px 11px;border-radius:999px;
  background:#efe6d0;color:#6b4a2e;font-size:13.5px;white-space:nowrap}
 .kgrid{display:grid;gap:18px;grid-template-columns:repeat(auto-fill,minmax(330px,1fr))}
 .kind{background:var(--panel);border:1px solid var(--line);border-radius:16px;
  padding:18px 20px;display:flex;flex-direction:column;
  transition:transform .18s cubic-bezier(.34,1.4,.64,1),border-color .18s,box-shadow .18s}
 .kind:hover{transform:translateY(-3px);border-color:var(--gold-soft);
  box-shadow:0 16px 30px -22px #26302abb}
 .kth{font-family:var(--serif);font-size:26px;margin:0;line-height:1.25}
 .ktr{color:var(--gold);font-size:14.5px;font-style:italic;margin:3px 0 0}
 .kwhat{font-size:14.5px;color:#3c473f;margin:10px 0 0}
 .fuzzy{font-size:13.5px;color:#6b4a2e;background:#f7f1e2;border-radius:10px;
  padding:9px 12px;margin:10px 0 0}
 .kmarket{font-size:14px;margin:12px 0 0;color:var(--sage)}
 .kcorpus{font-size:14px;margin:3px 0 0;color:var(--muted)}
 .klinks{margin:12px 0 0;padding-top:11px;border-top:1px dotted var(--line);
  font-size:13.5px;color:var(--muted)}
 .klinks a{padding:6px 2px}
 .ksrc{float:right;font-size:12px;color:var(--muted);opacity:.85}
 .kind.dim{display:none}
 .clsgrp.dim{display:none}

 footer{border-top:1px solid var(--line);margin-top:56px;padding:26px 0 60px;
  text-align:center;font-size:14.5px;color:var(--muted)}
 @media (max-width:640px){body{font-size:17px}.picks{grid-template-columns:1fr 1fr}
  .phint{display:none}.pick{padding:12px 13px 12px 50px;min-height:52px}}
 @media (prefers-reduced-motion:reduce){*{transition:none!important}}
</style>
</head><body>

<header class="top">
  <div class="mark"><a href="/">WICHAA</a></div>
  <h1>ถืออยู่ในมือ · I'm holding an amulet</h1>
  <p class="sub">You have the thing; you don't have its name. Answer the questions a
     sian would ask — in the sian's order — and meet the kinds it could be.</p>
  <p class="src">{{COUNT}} kinds · {{MARKET_TOTAL}} listing-echoes in the living market ·
     class and keeping read from the vault vocabulary · the ways in:
     <a href="/nuea">by material</a> · <a href="/need">by need</a> ·
     <a href="/market">the market</a></p>
</header>

<div class="wrap">
  <div class="ethic"><b>Why class comes first.</b> A sale listing flattens every kind on
    this page to “amulet.” The one thing it almost never states is the first thing the
    tradition asks: <b>is anyone home?</b> A พระสมเด็จ and a กุมารทอง trade on the same
    page, in the same price band — and one is impersonal blessing you may adopt blind,
    while the other is a raised spirit whose history should travel with it. Class facts
    and keeping below come from the vault vocabulary (<i>Tradition</i>); counts and
    prices from the catalogue (<i>Catalogue</i>); the material-and-figure mapping that
    drives the picker is this page's own curation (<i>Inference</i>), and each card
    signs which it is.</div>

  <section class="step" id="step-m">
    <h2>๑ · เนื้อ — what is it made of?</h2>
    <p class="lead">The sian's first question, because material gates age and workshop.
       Surfaces and what they can tell a patient reader have their own page:
       <a href="/nuea">เนื้อ · by material</a>.</p>
    <div class="picks">{{PICK_M}}</div>
  </section>

  <section class="step" id="step-f">
    <h2>๒ · what does the eye see?</h2>
    <p class="lead">The figure or form — tap the nearest. “Can't tell” keeps every door open.</p>
    <div class="picks">{{PICK_F}}</div>
  </section>
</div>

<div class="state"><div class="wrap">
  <span id="verdict">Every kind is on the table — answer either question to narrow.</span>
  <button id="reset" hidden>แสดงทั้งหมด · show all</button>
</div></div>

<div class="wrap" id="results">
{{SECTIONS}}
</div>

<footer><div class="wrap">
  Nothing here authenticates an object or names a price — this page tells you what a
  thing of this kind <i>is</i>, and what the tradition says a keeper owes it.
  · <a href="/nuea">เนื้อ by material</a>
  · <a href="/need">หาตามความต้องการ by need</a>
  · <a href="/yant">the yant designs</a>
  · <a href="/browse">the whole corpus</a>
</div></footer>

<script>
var DATA = {{DATA}};
var state = {m: null, f: null};
var picks = [].slice.call(document.querySelectorAll('.pick'));
var kinds = [].slice.call(document.querySelectorAll('.kind'));
var groups = [].slice.call(document.querySelectorAll('.clsgrp'));
var verdict = document.getElementById('verdict');
var reset = document.getElementById('reset');

function apply(){
  var shown = 0;
  kinds.forEach(function(k){
    var fs = k.getAttribute('data-f').split(' ');
    var ms = k.getAttribute('data-m').split(' ');
    var ok = (!state.f || fs.indexOf(state.f) >= 0) &&
             (!state.m || ms.indexOf(state.m) >= 0);
    k.classList.toggle('dim', !ok);
    if (ok) shown++;
  });
  groups.forEach(function(g){
    var any = [].slice.call(g.querySelectorAll('.kind')).some(function(k){
      return !k.classList.contains('dim'); });
    g.classList.toggle('dim', !any);
  });
  picks.forEach(function(b){
    var on = state[b.getAttribute('data-kind')] === b.getAttribute('data-key');
    b.setAttribute('aria-pressed', on ? 'true' : 'false');
  });
  var filtered = state.m || state.f;
  verdict.innerHTML = filtered
    ? (shown === 1 ? '<b>1</b> kind answers to that'
                   : '<b>' + shown + '</b> kinds answer to that')
      + ' — grouped by what each asks of a keeper.'
    : 'Every kind is on the table — answer either question to narrow.';
  reset.hidden = !filtered;
  var h = [];
  if (state.m) h.push('m=' + state.m);
  if (state.f) h.push('f=' + state.f);
  history.replaceState(null, '', location.pathname + (h.length ? '#' + h.join('&') : ''));
}

picks.forEach(function(b){
  b.addEventListener('click', function(){
    var kind = b.getAttribute('data-kind'), key = b.getAttribute('data-key');
    if (key === 'unsure') key = null;
    state[kind] = (state[kind] === key) ? null : key;
    apply();
    if (state.m || state.f)
      document.getElementById('results').scrollIntoView({behavior: 'smooth', block: 'start'});
  });
});
reset.addEventListener('click', function(){ state.m = state.f = null; apply();
  window.scrollTo({top: 0, behavior: 'smooth'}); });

(function fromHash(){
  var m = location.hash.match(/m=([a-z_]+)/), f = location.hash.match(/f=([a-z_]+)/);
  if (m && DATA.materials.indexOf(m[1]) >= 0) state.m = m[1];
  if (f && DATA.figures.indexOf(f[1]) >= 0) state.f = f[1];
  if (state.m || state.f) apply();
})();
</script>
</body></html>
"""


if __name__ == "__main__":
    raise SystemExit(main())
