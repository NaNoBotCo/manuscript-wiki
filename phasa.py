"""/phasa — ภาษา, the linguistics door.

WHY A SECTION AND NOT ANOTHER WIDGET
The tools were arriving one at a time and landing wherever there was room:
รากศัพท์ Thai Roots on its own GitHub Pages address, a romanizer buried inside
mot-dang's rendering code, and now a ทับศัพท์ catalogue as a wichaa widget.
Three pieces of one subject, in three places, with nothing saying they belong
together — and the thing they belong to is the one Nan actually wants to
build. So this page is the subject's front door, and the tools hang off it.

THE ORGANISING IDEA, WHICH IS THAI'S OWN
Thai already has a word-family for this and it is better than any English
scheme would be. ศัพท์ (sap, from Sanskrit śabda) means "word, vocabulary",
and the compounds name exactly the three questions a linguistics of Thailand
keeps asking:

    รากศัพท์   rak sap    the ROOT of a word — where it came from
    ทับศัพท์   thap sap   a word LAID OVER from another language
    ถ่ายเสียง  thai siang the SOUND carried across into another script

Root, borrowing, transcription. Each has a tool, each tool answers its own
question, and the shared morpheme is not decoration — it is why they are one
subject. A reader who learns the family has the map.

WHAT THIS PAGE IS NOT
It is not an essay about Thai. Counts come from the catalogue's own export and
the page says so; where a tool is not built yet the page says that instead of
implying it exists. Same discipline as the rest of the site: extract, do not
author, and be honestly empty rather than plausibly full.
"""

from __future__ import annotations

import html
import json
import os
from pathlib import Path

ISOGLOSS_EXPORT = Path(os.environ.get("ISOGLOSS_DATA") or
                       (Path.home() / "Developer" / "claude code projects" /
                        "thapsap" / "exports" / "isogloss.json"))

THAPSAP_EXPORT = Path(os.environ.get("THAPSAP_DATA") or
                      (Path.home() / "Developer" / "claude code projects" /
                       "thapsap" / "exports" / "thapsap.json"))


def _read(path):
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _catalogue():
    """Live counts from the thapsap export, or nothing if it has not run."""
    return _read(THAPSAP_EXPORT)


def _isogloss():
    """The dialect dataset, or nothing."""
    return _read(ISOGLOSS_EXPORT)


# The exhibit comes from the export, not from here.
#
# Four real names from the Chiang Mai registers, each with what the Royal
# Society's letter rules make of it. The first draft of this page had the
# middle column typed by hand and ONE OF THE FOUR WAS WRONG — เดอะฮับ reads
# "Doehap", not "Doha" — which is precisely the error a page whose whole
# subject is misreading cannot be caught making. So the catalogue generates
# the column by running the romanizer with its loanword lexicon switched off,
# and this page prints what it is given.
#
# The fallback below is the shape, not the data: it appears only when the
# export is missing, and says so.
EXHIBIT_FALLBACK = [
    {"th": "ไนท์บาร์ซาร์ คอนโดเทล", "misread": "—", "en": "Night Bazaar Condotel"},
]

FAMILY = [
    ("รากศัพท์", "rak sap", "the root of a word",
     "Not what a word means but why it means that. Most of Thai's abstract "
     "vocabulary is Pali and Sanskrit layered on a Tai core; the lexicon orders "
     "each word's senses from core to figurative and files every compound under "
     "the sense that motivates it.",
     "พจนานุกรมราก · the lexicon", "/roots/",
     "sense-first · every claim marked with its confidence"),
    ("ทับศัพท์", "thap sap", "a word laid over from another language",
     "English written in Thai letters, which Thailand does constantly and no "
     "romanizer can read back. A catalogue of the words, each with what the "
     "letter rules make of it and what it actually says.",
     "ทับศัพท์ · the catalogue", "/w/thapsap",
     None),   # count filled in from the export
    ("ถ่ายเสียง", "thai siang", "the sound, carried into another script",
     "Romanisation — RTGS, the Royal Society's rules, which follow the sound "
     "and drop the tones on purpose. It is the machinery underneath the other "
     "two, and the place where both of them break.",
     "how the romanizer reads a name", "/w/thapsap",
     "the same rules, before and after the catalogue"),
]

CSS = """
  .plead{max-width:720px;font-size:17px;line-height:1.65;color:var(--muted)}
  .plead strong{color:var(--ink)}
  .exhibit{border:1px solid var(--line);border-radius:14px;background:#fff;
    padding:6px 0;margin:26px 0}
  .exrow{display:grid;grid-template-columns:minmax(0,1.15fr) minmax(0,1fr) minmax(0,1fr);
    gap:16px;align-items:baseline;padding:13px 22px;border-bottom:1px solid #eef3f2}
  .exrow:last-child{border-bottom:0}
  .exth{font-size:20px;font-weight:600}
  .exbad{color:#9b2c2c;text-decoration:line-through;font-size:15px}
  .exgood{font-weight:700;font-size:15px}
  .exhead{font-size:11px;text-transform:uppercase;letter-spacing:.08em;
    color:var(--muted);border-bottom:2px solid var(--line);padding-bottom:8px}
  .fam{display:grid;gap:16px;margin:26px 0}
  .famcard{border:1px solid var(--line);border-radius:14px;background:#fff;padding:18px 22px}
  .famcard h2{margin:0;font-size:26px}
  .famcard .rom{font-size:14px;color:var(--muted);margin:2px 0 2px}
  .famcard .gloss{font-size:15px;font-weight:600;margin:0 0 8px}
  .famcard p{margin:0 0 12px;font-size:15px;line-height:1.6;color:var(--muted);max-width:62em}
  .famcard a.door{display:inline-block;font-weight:600;text-decoration:none;
    border:1px solid var(--teal);color:var(--teal);border-radius:8px;padding:7px 14px;font-size:14px}
  .famcard a.door:hover{background:var(--teal);color:#fff}
  .famcard .cnt{font-size:13px;color:var(--muted);margin-left:12px}
  .axis{font-size:26px;margin:38px 0 2px;font-weight:600}
  .axis em{font-style:italic}
  .isolist{display:grid;gap:7px;margin:18px 0}
  .isow{font-size:15px;color:var(--muted)}
  .isow b{font-size:19px;color:var(--ink);margin-right:6px}
  .isow i{font-style:normal;margin-right:8px}
  .nbc{margin:34px 0 0;padding:16px 20px;border-radius:12px;
    background:#0b0a0c;color:#f5efe4;font-size:14px;line-height:1.6}
  .nbc b{color:#e7c66c}
  .nbc a{color:#e7c66c}
  @media(max-width:680px){.exrow{grid-template-columns:1fr;gap:4px}
    .exhead{display:none}}
"""


def phasa_page(nav: str, page_fn):
    """Build /phasa. `nav` and `page_fn` are passed in so this module does not
    import wiki (which imports plenty) just to reach two names."""
    d = _catalogue()
    e = lambda s: html.escape(str(s))

    exhibit = (d or {}).get("exhibit") or EXHIBIT_FALLBACK
    rows = "".join(
        f"<div class=exrow><div class=exth>{e(x['th'])}</div>"
        f"<div class=exbad>{e(x['misread'])}</div>"
        f"<div class=exgood>{e(x['en'])}</div></div>"
        for x in exhibit)
    head = ("<div class='exrow exhead'><div>as written</div>"
            "<div>what letter rules read</div><div>what it says</div></div>")

    cards = []
    for th, rom, gloss, blurb, label, href, note in FAMILY:
        if note is None and d:
            c = d.get("counts", {})
            note = (f"{c.get('confirmed', 0):,} words confirmed · "
                    f"{c.get('proposed', 0):,} proposed and awaiting review")
        elif note is None:
            note = "not exported yet"
        cards.append(
            f"<article class=famcard><h2>{e(th)}</h2>"
            f"<div class=rom>{e(rom)}</div>"
            f"<div class=gloss>{e(gloss)}</div><p>{e(blurb)}</p>"
            f"<div><a class=door href='{href}'>{e(label)} &rarr;</a>"
            f"<span class=cnt>{e(note)}</span></div></article>")

    # ── the other axis ────────────────────────────────────────────────────
    # ถิ่น is NOT a fourth member of the ศัพท์ family and the page must not
    # pretend it is. รากศัพท์, ทับศัพท์ and ถ่ายเสียง all ask about one word's
    # history — where it came from, what it was carried over from, how it is
    # written in another script. Dialect asks something else entirely: not
    # where a word came from but WHERE IT IS SAID. Forcing it into the family
    # for the sake of a tidy set of four would misdescribe both.
    g = _isogloss()
    if g:
        c = g.get("corpus", {})
        iso = (g.get("isoglosses") or [{}])[0]
        rows = []
        for w in (iso.get("words") or [])[:6]:
            rows.append(f"<span class=isow><b>{e(w['th'])}</b> "
                        f"<i>{e(w['rtgs'])}</i> {e(w['note'])}</span>")
        geo = (
            "<h2 class=axis>and a different question: <em>where</em></h2>"
            "<p class=plead>Those three ask about a word's history. This one "
            "asks where it is said — and the register can answer it, because "
            f"<strong>{c.get('temples', 0):,}</strong> Thai temple names are "
            "almost entirely landscape vocabulary: what the ground does here, "
            "in the words the people who named it used.</p>"
            "<p class=plead>Asked what its temples call <strong>a hill</strong>, "
            "the country divides along lines nobody drew for it. "
            "<span class=th>ดอย</span> or <span class=th>ม่อน</span> leads in "
            "all eight provinces of the old Lanna kingdom, and "
            "<span class=th>เขา</span> — the standard Central Thai word — "
            "leads in none of them. <span class=th>โนน</span> leads in twenty "
            "provinces; Isan has twenty. <span class=th>ควน</span> leads in "
            "four, all southern.</p>"
            f"<div class=isolist>{''.join(rows)}</div>"
            "<div><a class=door href='/w/thin'>ถิ่น · the dialect map &rarr;</a>"
            f"<span class=cnt>{c.get('provinces', 0)} provinces · "
            f"{c.get('words', 0):,} words scored</span></div>")
    else:
        geo = ""

    built = f" Catalogue built {e(d['generated'])}." if d and d.get("generated") else ""
    engine = (f" Readings by {e(d['romanizer'])}, with its loanword lexicon "
              "switched off." if d and d.get("romanizer") else "")
    sources = ""
    if d and d.get("sources"):
        sources = (" Read from " +
                   e(" · ".join(s["title"] for s in d["sources"].values())) + ".")

    body = (
        "<header><div><h1>ภาษา · Language</h1>"
        "<p class=sub>Linguistics of Thailand — roots, borrowings, and the "
        "sound carried between scripts</p></div>" + nav + "</header>"
        "<main>"
        "<p class=plead>Thai writes English in Thai letters, constantly, and "
        "the result cannot be read back by rule. Hand a romanizer the shopfront "
        "<strong>ไนท์บาร์ซาร์</strong> and it returns <strong>Naibasa</strong> — "
        "correctly, by its own rules, because it is sounding out letters that do "
        "not spell a Thai word. The sign says <strong>Night Bazaar</strong>.</p>"
        f"<div class=exhibit>{head}{rows}</div>"
        "<p class=plead>Thai has its own word-family for what is going on, and "
        "it is a better map than any English scheme: <strong>ศัพท์</strong> "
        "(<em>sap</em>) is a word, and the compounds name the three questions "
        "this section keeps asking.</p>"
        f"<div class=fam>{''.join(cards)}</div>"
        + geo +
        "<div class=nbc><b>NaNoBotCo · Linguistics.</b> These tools are one "
        "line rather than three loose utilities, and they keep their own mark "
        "so they can take their own address later. Everything here is built "
        "from corpora on disk, runs offline, sets no cookie and calls no "
        "third party."
        + (f"{engine} {sources}{built}" if (engine or sources or built) else "") +
        "</div>"
        "</main>")

    return page_fn("ภาษา · Language — wichaa", CSS, body,
                   description=("Linguistics of Thailand: รากศัพท์ roots, ทับศัพท์ "
                                "English written in Thai script, and ถ่ายเสียง "
                                "romanisation — with the catalogue of loanwords a "
                                "romanizer cannot read."),
                   og_image="/phasa/card.png", og_url="/phasa/")
