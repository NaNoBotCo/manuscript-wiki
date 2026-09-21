#!/usr/bin/env python3
"""poppy — the /poppy page: ฝิ่น, the highland agricultural year, and what
happened to it when coffee took the poppy's place.

WHAT THIS PAGE IS
Every other page on this site reads a year off a manuscript — the twelve-year
cycle of the phrommachat, the horā almanac's lucky days, the moon's own
complication. This one reads a year off a hillside. It is the same subject seen
from the other end: not how time was *reckoned* in the Lanna north, but how it
was *spent*, month by month, by the people farming above 1,000 m — Hmong, Akha,
Lisu, Lahu, Iu Mien, Karen, Lua — in the century when the cash crop up there was
opium and in the decades after, when it became coffee.

The thing worth seeing is that the ceremonies are not decoration laid over the
work. They are cut into the same grid. The Akha Swinging Ceremony takes four
days in the tenth lunar month and NOBODY GOES TO THE FIELDS — that is the
ethnographer's sentence, not a gloss (Chob Kacha-ananda, JSS 59.1, 1971, twice).
The Hmong New Year is called noj peb caug, "eat thirty", and it sits in the one
gap the crop calendar leaves. Lahu New Year runs twelve days and has no fixed
date at all: it happens when the harvest is finished. A festival that long is
only affordable at a particular point in the year, and each of these lands on
one.

THE SOURCING MARKS ARE THE SAME AS THE ARTICLES'
Plain prose = from a named source, cited on the page. *Inference —* = my
reasoning across those sources. *Tradition holds —* = general background, hedged.
See content/entity-*.md for the same convention in the manuscript articles. The
one difference here: nothing on this page comes from catalog.db, because the
palm-leaf corpus does not cover highland swidden agriculture at all. That
absence is itself stated on the page rather than papered over.

TWO THINGS ARE DELIBERATELY LEFT OPEN, NAMED, WITH A WAY TO CLOSE THEM
1. THE RAT-CATCHING SEASON. Nan saw a hand-drawn year-wheel at the House of
   Opium in Sop Ruak with festival months and a rat-catching season marked on
   it. Her observation is the source and is cited as such. I could not find a
   published hill-tribe calendar that labels a rat block, so the page says what
   the literature DOES support (bamboo masting drives rodent irruptions in
   upland rice; rice-field rats are trapped with bamboo bow and deadfall traps
   at harvest) and names the missing piece. Closing it needs a photograph of the
   panel, or the Tribal Research Institute publication it was probably drawn
   from. DO NOT quietly upgrade this to a fact if a later session finds the
   panel plausible — find the panel.
2. THE AKHA TWELVE-DAY CYCLE HAS NO RAT IN IT. The JSS list, printed verbatim
   below, opens with the ANT and contains a termite, a mule and a giraffe. That
   is what the 1971 article prints. The obvious reading — a Tibeto-Burman
   reworking of the Sino twelve — is marked as inference, not asserted, and the
   giraffe is flagged as wanting a check against Akha-language sources. The OCR
   of that PDF also renders the female ancestor's name three ways (Umsahyeh /
   Umsahyee / Umsahyeb); the page says so rather than picking one silently.

NAMES
"Hill tribe" (ชาวเขา chao khao) is a Thai administrative category, not a people.
The page says that once, then uses the actual names. This is not delicacy — the
calendars differ between them, and a page about calendars that flattens the
peoples into one word cannot show the differences it exists to show.

ACCESSIBILITY IS WHY THE TABLE EXISTS
The wheel is the centrepiece, but it is never the only carrier: every band on it
is repeated in the month table below it, which is what a screen reader, a
crawler, and anyone who cannot resolve a 30° sector will read. Large type, high
contrast, no text rotated around the rim.
"""


# ---------------------------------------------------------------------------
# THE YEAR, AS FOUR CROPS AND A CEREMONY RING.
#
# Months are 0=January .. 11=December. Each band is (first_month, last_month,
# label) INCLUSIVE, and wraps if last < first (the poppy's lancing runs Dec–Feb).
#
# Sources for each ring are on the page itself, under "Where this comes from".
# Anything I could not pin to a named source is prefixed "~" — the same
# unverified mark this household uses on calendars everywhere else.
# ---------------------------------------------------------------------------

RICE = [
    (2, 3, "cut & dry the swidden"),
    (3, 4, "burn, then sow"),
    (4, 6, "weeding"),
    (8, 9, "HARVEST"),
    (10, 10, "thresh & store"),
]

MAIZE = [
    (3, 3, "plant"),
    (4, 5, "weeding"),
    (6, 7, "cobs in"),
    (7, 7, "stalks hoed under"),
]

POPPY = [
    (7, 7, "field prepared"),
    (8, 9, "SOWING"),
    (10, 11, "weeding seedlings"),
    (11, 0, "flowering"),
    (0, 1, "LANCING"),
]

COFFEE = [
    (1, 1, "flowering"),
    (3, 9, "cherries filling"),
    (10, 1, "PICKING"),
    (2, 3, "prune & mulch"),
]

# The ceremony ring. Each is (first, last, label, certain) — certain=False
# prints the ~ mark and is said to be unverified in the table too.
CEREMONY = [
    (7, 7, "Akha Swinging Ceremony · 4 days", True),
    (9, 9, "Akha rite to drive out sickness", False),
    (10, 11, "Hmong New Year · noj peb caug", True),
    (0, 1, "Lisu & Lahu New Year", True),
]

RINGS = [
    ("ceremony", "Ceremonies", CEREMONY, 262, 300, "#1F4E4A"),
    ("rice", "Upland rice", RICE, 216, 254, "#8a6a12"),
    ("maize", "Maize", MAIZE, 178, 208, "#b07a2a"),
    ("poppy", "Opium poppy", POPPY, 132, 170, "#9c3b4c"),
    ("coffee", "Coffee (from 1969)", COFFEE, 86, 124, "#4b3826"),
]

MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
          "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

# The month table under the wheel — the same information, in reading order,
# for anyone the wheel does not serve. Each row: month, rice, maize, poppy,
# coffee, ceremony.
TABLE = [
    ("January",   "—", "—", "lancing and collecting", "picking", "Lisu New Year (lunar) · Lahu New Year, twelve days, no fixed date"),
    ("February",  "—", "—", "lancing ends; field cleared", "picking ends · flowering", "Lisu & Lahu New Year"),
    ("March",     "cut and dry the swidden", "—", "—", "prune, mulch", "—"),
    ("April",     "burn, then sow", "plant", "—", "prune · cherries set", "—"),
    ("May",       "sow, first weeding", "weeding", "—", "cherries filling", "—"),
    ("June",      "weeding", "weeding", "—", "cherries filling", "—"),
    ("July",      "weeding", "first cobs", "—", "cherries filling", "—"),
    ("August",    "rice maturing", "cobs in; stalks hoed under", "field prepared in the maize plot", "cherries filling", "Akha Swinging Ceremony — four days, nobody works the fields"),
    ("September", "HARVEST", "—", "SOWING", "cherries filling", "—"),
    ("October",   "harvest ends", "—", "sowing must be finished", "cherries ripening", "~Akha rite to drive out sickness"),
    ("November",  "thresh and store", "—", "weeding seedlings", "PICKING BEGINS", "Hmong New Year — noj peb caug, after the harvest"),
    ("December",  "—", "—", "weeding; flowering begins", "picking", "Hmong New Year"),
]

# The Akha twelve, exactly as printed in Chob Kacha-ananda, JSS 59.1 (1971),
# footnote 4. Do not "correct" this list toward the Chinese zodiac — the whole
# point of printing it is that it is not that list.
AKHA_TWELVE = ["ant", "buffalo", "tiger", "horse", "rabbit", "termite",
               "mule", "giraffe", "monkey", "chicken", "dog", "pig"]


import math

# ---------------------------------------------------------------------------
# THE WHEEL.
#
# Drawn, not charted. The wobble is one feTurbulence/feDisplacementMap filter on
# the band group — no library, nothing fetched, and it degrades to clean arcs if
# a renderer skips the filter. Everything the wheel says is repeated in the
# table below it, because a 30° sector is not a reading surface for everyone.
# ---------------------------------------------------------------------------

CX = CY = 380.0


def _pt(r, deg):
    """Polar → cartesian, 0° at twelve o'clock, clockwise."""
    a = math.radians(deg - 90.0)
    return CX + r * math.cos(a), CY + r * math.sin(a)


def _band_path(m0, m1, r_in, r_out, pad=1.4):
    """Annular sector spanning months m0..m1 inclusive, wrapping past December."""
    span = (m1 - m0) % 12 + 1
    a0 = m0 * 30.0 + pad
    a1 = m0 * 30.0 + span * 30.0 - pad
    large = 1 if (a1 - a0) > 180.0 else 0
    x0, y0 = _pt(r_out, a0)
    x1, y1 = _pt(r_out, a1)
    x2, y2 = _pt(r_in, a1)
    x3, y3 = _pt(r_in, a0)
    return (f"M{x0:.1f},{y0:.1f} A{r_out:.0f},{r_out:.0f} 0 {large} 1 {x1:.1f},{y1:.1f} "
            f"L{x2:.1f},{y2:.1f} A{r_in:.0f},{r_in:.0f} 0 {large} 0 {x3:.1f},{y3:.1f} Z")


def _peak(label):
    """The all-hands windows are spelled in capitals in the band tables above,
    so the tables stay the single place the distinction is declared."""
    return label.isupper() or label.split(" ")[0].isupper()


def _slots(bands, ceremony=False):
    """Collapse a ring's bands into twelve month slots of (intensity, labels).

    Bands overlap on purpose in the tables — the poppy flowers in December and
    January and is lanced in January and February — and drawing them as separate
    translucent shapes double-paints the shared month, which reads as a third,
    accidental intensity. Resolving to one value per month first means every
    block on the wheel is exactly one of two densities, which is the whole
    grammar of the picture."""
    slots = [[0, []] for _ in range(12)]
    for band in bands:
        if ceremony:
            m0, m1, label, certain = band
            level = 2 if certain else 1
        else:
            m0, m1, label = band
            level = 2 if _peak(label) else 1
        for k in range((m1 - m0) % 12 + 1):
            slot = slots[(m0 + k) % 12]
            slot[0] = max(slot[0], level)
            if label not in slot[1]:
                slot[1].append(label)
    return slots


def _runs(slots):
    """Contiguous months of equal intensity → (first, last, level, label).
    Walks from the first month whose intensity differs from December's, so a run
    that wraps the year end (the lancing, the picking) is drawn as one arc
    rather than sliced at January."""
    if all(s[0] == 0 for s in slots):
        return []
    start = next(i for i in range(12) if slots[i][0] != slots[i - 1][0])
    out, i = [], 0
    while i < 12:
        m0 = (start + i) % 12
        level = slots[m0][0]
        n = 1
        while n < 12 - i and slots[(start + i + n) % 12][0] == level:
            n += 1
        if level:
            labels = []
            for k in range(n):
                for lab in slots[(start + i + k) % 12][1]:
                    if lab not in labels:
                        labels.append(lab)
            out.append((m0, (start + i + n - 1) % 12, level, ", ".join(labels)))
        i += n
    return out


def _bracket(m0, m1, r, why):
    """A dashed arc sitting OUTSIDE every ring, with a tick at each end — the way
    a margin annotation brackets lines of text. An earlier draft outlined the
    whole sector from hub to rim; it crossed all five rings and the hub and read
    as clutter over the thing it was pointing at."""
    span = (m1 - m0) % 12 + 1
    a0, a1 = m0 * 30.0 + 1.0, m0 * 30.0 + span * 30.0 - 1.0
    large = 1 if (a1 - a0) > 180.0 else 0
    x0, y0 = _pt(r, a0)
    x1, y1 = _pt(r, a1)
    ticks = "".join(
        "<line x1='{:.1f}' y1='{:.1f}' x2='{:.1f}' y2='{:.1f}'/>".format(
            *_pt(r - 9, a), *_pt(r + 9, a))
        for a in (a0, a1))
    return (f"<g class=hl><title>{why}</title>"
            f"<path d='M{x0:.1f},{y0:.1f} A{r:.0f},{r:.0f} 0 {large} 1 {x1:.1f},{y1:.1f}'/>"
            f"{ticks}</g>")


def year_wheel_svg():
    parts = [
        "<svg class=wheel viewBox='0 0 760 760' xmlns='http://www.w3.org/2000/svg' "
        "role='img' aria-labelledby='wtitle wdesc'>",
        "<title id=wtitle>The highland agricultural year</title>",
        "<desc id=wdesc>A twelve-month wheel, January at the top, running "
        "clockwise. Reading outward from the centre: coffee, opium poppy, maize, "
        "upland rice, and the ceremony ring. The poppy is sown in September and "
        "October, the same weeks the rice is harvested, and lanced in January and "
        "February. Coffee is picked from November to February — the same slot the "
        "poppy harvest occupied. The two bracketed spans mark those windows. The "
        "full month-by-month table follows below.</desc>",
        "<defs>"
        "<filter id='rough' x='-8%' y='-8%' width='116%' height='116%'>"
        "<feTurbulence type='fractalNoise' baseFrequency='0.017' numOctaves='3' "
        "seed='7' result='n'/>"
        "<feDisplacementMap in='SourceGraphic' in2='n' scale='4' "
        "xChannelSelector='R' yChannelSelector='G'/></filter>"
        "</defs>",
    ]

    parts.append("<g class=spokes>")
    for m in range(12):
        x1, y1 = _pt(78, m * 30.0)
        x2, y2 = _pt(304, m * 30.0)
        parts.append(f"<line x1='{x1:.1f}' y1='{y1:.1f}' x2='{x2:.1f}' y2='{y2:.1f}'/>")
    parts.append("</g>")

    parts.append("<g filter='url(#rough)'>")
    for key, _label, bands, r_in, r_out, colour in RINGS:
        parts.append(f"<g class='ring ring-{key}'>")
        parts.append(
            f"<circle cx='{CX}' cy='{CY}' r='{(r_in + r_out) / 2:.0f}' fill='none' "
            f"stroke='{colour}' stroke-opacity='.07' stroke-width='{r_out - r_in}'/>")
        for m0, m1, level, label in _runs(_slots(bands, ceremony=(key == "ceremony"))):
            op = "1" if level == 2 else ".42"
            parts.append(
                f"<path d='{_band_path(m0, m1, r_in, r_out)}' fill='{colour}' "
                f"fill-opacity='{op}'><title>{MONTHS[m0]}"
                + (f"&ndash;{MONTHS[m1]}" if m1 != m0 else "")
                + f": {label}</title></path>")
        parts.append("</g>")
    parts.append("</g>")

    parts.append(_bracket(8, 9, 316,
                          "September\u2013October: rice in and poppy down, "
                          "the same weeks"))
    parts.append(_bracket(11, 1, 316,
                          "December\u2013February: the harvest slot the poppy "
                          "held and coffee took"))

    parts.append("<g class=mlab>")
    for m, name in enumerate(MONTHS):
        x, y = _pt(344, m * 30.0 + 15.0)
        parts.append(f"<text x='{x:.1f}' y='{y + 7:.1f}'>{name}</text>")
    parts.append("</g>")

    parts.append(
        f"<circle class=hub cx='{CX}' cy='{CY}' r='74'/>"
        f"<text class='hub-th' x='{CX}' y='{CY - 14}'>ฝิ่น</text>"
        f"<text class='hub-th' x='{CX}' y='{CY + 26}'>กาแฟ</text>"
        f"<line class=hubrule x1='{CX - 34}' y1='{CY - 1}' x2='{CX + 34}' y2='{CY - 1}'/>")

    parts.append("</svg>")
    return "".join(parts)


def strip_svg():
    """The handover, straightened out: two twelve-month strips, poppy above and
    coffee below, so the vacated September and the shared cold-months harvest are
    visible without reading a wheel."""
    W, X0, TOP, H, GAP = 52.0, 96.0, 40.0, 58.0, 38.0
    out = ["<svg class=strip viewBox='0 0 760 262' xmlns='http://www.w3.org/2000/svg' "
           "role='img' aria-label='Poppy year and coffee year compared, month by "
           "month. The poppy needs September and October for sowing and January "
           "and February for lancing; coffee needs nothing in September or "
           "October and is picked from November to February.'>"]
    for m, name in enumerate(MONTHS):
        out.append(f"<text class=sm x='{X0 + m * W + W / 2:.0f}' y='28' "
                   f"text-anchor='middle'>{name}</text>")
    rows = [("Poppy", POPPY, "#9c3b4c", TOP), ("Coffee", COFFEE, "#4b3826", TOP + H + GAP)]
    for title, bands, colour, y in rows:
        out.append(f"<text class=rowlab x='88' y='{y + 37:.0f}' text-anchor='end'>{title}</text>")
        for m0, m1, level, label in _runs(_slots(bands)):
            for k in range((m1 - m0) % 12 + 1):
                m = (m0 + k) % 12
                op = "1" if level == 2 else ".40"
                out.append(f"<rect x='{X0 + m * W + 2:.0f}' y='{y + 2:.0f}' "
                           f"width='{W - 4:.0f}' height='{H - 4:.0f}' fill='{colour}' "
                           f"fill-opacity='{op}' rx='4'><title>{MONTHS[m]}: {label}"
                           f"</title></rect>")
        out.append(f"<rect class=trough x='{X0}' y='{y:.0f}' width='{12 * W:.0f}' "
                   f"height='{H:.0f}' rx='6'/>")
    y2 = TOP + H + GAP
    out.append(f"<rect class=gap x='{X0 + 8 * W - 4:.0f}' y='{TOP - 10:.0f}' "
               f"width='{2 * W + 8:.0f}' height='{y2 + H + 10 - (TOP - 10):.0f}' rx='8'/>")
    out.append(f"<text class=sm x='{X0 + 9 * W:.0f}' y='{y2 + H + 30:.0f}' "
               "text-anchor='middle'>peak above, nothing below</text>")
    out.append("</svg>")
    return "".join(out)


POPPY_CSS = """
.py{max-width:960px;margin:0 auto;padding:0 18px 60px}
.py .lead{font-size:19px;line-height:1.7;max-width:46em}
.py p{max-width:46em}
.py h2{font-family:var(--serif);font-size:27px;margin:44px 0 6px;
  border-bottom:2px solid var(--line);padding-bottom:8px}
.py h3{font-family:var(--serif);font-size:21px;margin:30px 0 4px}
.py .fig{margin:26px 0 8px;padding:18px 10px 10px;background:var(--card);
  border:1px solid var(--line);border-radius:14px;
  box-shadow:0 2px 14px rgba(0,0,0,.05)}
.py figcaption{font-size:15px;color:var(--muted);max-width:52em;margin:8px auto 2px;
  padding:0 10px;line-height:1.6}
svg.wheel,svg.strip{display:block;width:100%;height:auto;margin:0 auto;overflow:visible}
svg.wheel .spokes line{stroke:var(--line);stroke-width:1}
svg.wheel .mlab text{font-family:var(--serif);font-size:20px;font-weight:700;
  fill:var(--ink);text-anchor:middle}
svg.wheel .hub{fill:var(--card);stroke:var(--line);stroke-width:2}
svg.wheel .hub-th{text-anchor:middle;font-family:var(--serif);font-size:28px;fill:var(--teal)}
svg.wheel .hubrule{stroke:var(--line);stroke-width:1.5}
svg.wheel .hl{fill:none;stroke:var(--prio);stroke-opacity:.9;stroke-width:3;
  stroke-dasharray:8 6;stroke-linecap:round}
svg.wheel .hl line{stroke-dasharray:none}
svg.strip .trough{fill:none;stroke:var(--line);stroke-width:1.5}
svg.strip .gap{fill:none;stroke:var(--prio);stroke-width:2.5;stroke-dasharray:6 5}
svg.strip .sm{font-size:15px;fill:var(--muted)}
svg.strip .rowlab{font-family:var(--serif);font-size:19px;font-weight:700;fill:var(--ink)}
.py .key{display:flex;flex-wrap:wrap;gap:8px 20px;justify-content:center;
  margin:14px auto 2px;font-size:15px;max-width:52em}
.py .key span{display:inline-flex;align-items:center;gap:8px}
.py .key i{width:20px;height:14px;border-radius:4px;display:inline-block}
.py .vh{position:absolute;width:1px;height:1px;overflow:hidden;clip:rect(0 0 0 0);white-space:nowrap}
.py table{border-collapse:collapse;width:100%;margin:18px 0;font-size:15px}
.py th,.py td{border:1px solid var(--line);padding:8px 10px;text-align:left;
  vertical-align:top}
.py th{background:var(--teal);color:var(--teal-ink);font-weight:700}
.py tbody tr:nth-child(even){background:#00000006}
.py td.mo{font-weight:700;white-space:nowrap}
.py .peak{color:var(--prio);font-weight:700}
.py .note{background:var(--gold-bg);border-left:5px solid var(--gold);
  padding:14px 18px;border-radius:0 10px 10px 0;margin:22px 0;max-width:52em}
.py .open{background:var(--prio-bg);border-left:5px solid var(--prio);
  padding:14px 18px;border-radius:0 10px 10px 0;margin:22px 0;max-width:52em}
.py .mark{font-style:italic;color:var(--muted);font-weight:700}
.py .term{font-weight:700}
.py .term .sc{font-family:var(--serif)}
.py ul{max-width:46em;line-height:1.65}
.py li{margin:7px 0}
.py .twelve{display:flex;flex-wrap:wrap;gap:8px;margin:14px 0;max-width:52em;padding:0;
  list-style:none}
.py .twelve li{margin:0;border:1px solid var(--line);background:var(--card);
  border-radius:999px;padding:5px 14px;font-size:15px}
.py .twelve li b{color:var(--teal)}
.py .src{font-size:15px;line-height:1.6}
.py .src li{margin:10px 0;max-width:52em}
@media (max-width:700px){
  svg.wheel .mlab text{font-size:26px}
  svg.strip .sm{font-size:17px}
  .py h2{font-size:23px}
}
"""


def _wheel_key():
    return ("<div class=key>" + "".join(
        f"<span><i style='background:{c}'></i>{lab}</span>"
        for _k, lab, _b, _ri, _ro, c in RINGS) +
        "<span><i style='background:transparent;border:2px dashed var(--ink)'>"
        "</i>the two bracketed spans</span></div>")


def _month_table():
    head = ("<thead><tr><th>Month</th><th>Upland rice</th><th>Maize</th>"
            "<th>Opium poppy</th><th>Coffee</th><th>Ceremony</th></tr></thead>")
    rows = []
    for mo, rice, maize, pop, cof, cer in TABLE:
        cells = "".join(
            "<td>" + (f"<span class=peak>{c}</span>" if c.isupper() and c != "—" else c) + "</td>"
            for c in (rice, maize, pop, cof, cer))
        rows.append(f"<tr><td class=mo>{mo}</td>{cells}</tr>")
    return ("<table><caption class=vh>The highland year, month by month</caption>"
            + head + "<tbody>" + "".join(rows) + "</tbody></table>")


def poppy_body(nav):
    twelve = "".join(f"<li><b>{i + 1}</b> &nbsp;the day of the {a}</li>"
                     for i, a in enumerate(AKHA_TWELVE))

    return (
        "<header><div><h1>ฝิ่น <span style='font-weight:400'>&middot; the year "
        "the poppy made</span></h1>"
        "<p class=sub>Twelve months of highland work, the festivals cut into "
        "them, and what changed when coffee took the poppy's slot.</p></div>"
        + nav + "</header>"
        "<main class=py>"

        "<p class=lead>A year on a hillside above a thousand metres is not a "
        "season and a crop. It is a schedule with almost no slack in it. The "
        "same household grew upland rice, maize and opium poppy in the same "
        "twelve months, and two of the three wanted the same weeks. The "
        "festivals were not laid over that schedule as ornament. They were cut "
        "into it &mdash; four days here, twelve days there, in the gaps the "
        "crops left &mdash; and while one ran, nobody went to the fields.</p>"

        # ------------------------------------------------------------------
        "<h2>First, the names</h2>"

        "<p><span class=term><span class=sc>ชาวเขา</span></span> <em>chao khao</em> "
        "/chaaw kʰǎw/ &mdash; <span class=sc>ชาว</span> <em>chao</em> &ldquo;the "
        "folk of&rdquo; + <span class=sc>เขา</span> <em>khao</em> &ldquo;hill, "
        "mountain&rdquo; &mdash; is a Thai administrative category, not a people. "
        "It was the frame the state worked in: the 1971 study quoted throughout "
        "this page opens by placing the Akha among &ldquo;the six major tribal "
        "groups included within the research program of the Tribal Research "
        "Centre located in Chiang Mai&rdquo;. Six groups is an office's number, "
        "not a hillside's.</p>"

        "<p>So the peoples get their own names here: <strong>Hmong</strong> "
        "(<span class=sc>ม้ง</span>), <strong>Akha</strong> "
        "(<span class=sc>อาข่า</span>), <strong>Lisu</strong> "
        "(<span class=sc>ลีซู</span>), <strong>Lahu</strong> "
        "(<span class=sc>ลาหู่</span>), <strong>Iu Mien</strong> "
        "(<span class=sc>เมี่ยน</span>), <strong>Karen</strong> "
        "(<span class=sc>ปกาเกอะญอ</span>), <strong>Lua</strong> "
        "(<span class=sc>ลัวะ</span>). Their calendars are not the same "
        "calendar.</p>"

        "<p><span class=term><span class=sc>ฝิ่น</span></span> <em>fin</em> "
        "/fìn/ is the poppy and its gum both. <span class=mark>Tradition holds "
        "&mdash;</span> the word belongs to the Old-World chain that also gave "
        "English <em>opium</em>: Greek <span class=sc>ὄπιον</span> <em>ópion</em>, "
        "a diminutive of <span class=sc>ὀπός</span> <em>opós</em> &ldquo;plant "
        "sap&rdquo;, through Arabic and Persian "
        "<span class=sc>أفيون</span> <em>afyūn</em>. Which leg of the trade "
        "carried it into Thai, I have not pinned down and do not assert. "
        "<span class=term><span class=sc>กาแฟ</span></span> <em>kafae</em> "
        "/kaa-fɛɛ/ came the short way, from French <em>café</em>, itself from "
        "Arabic <span class=sc>قهوة</span> <em>qahwa</em>.</p>"

        # ------------------------------------------------------------------
        "<h2>The year, drawn</h2>"

        "<figure class=fig>" + year_wheel_svg() + _wheel_key() +
        "<figcaption>Reading outward from the centre: coffee, opium poppy, "
        "maize, upland rice, ceremonies. Solid blocks are the all-hands weeks; "
        "pale blocks are ordinary work. The two bracketed spans are the argument "
        "of this page. <strong>September&ndash;October</strong> is the crunch: "
        "the rice has to come in and the poppy has to go down in the same weeks, "
        "in different fields. <strong>December&ndash;February</strong> is the "
        "slot the poppy harvest held and coffee later took &mdash; hand work, "
        "repeated passes, the same cold dry end of the year. The poppy ring is "
        "the Hmong-type upland succession; the others farmed years that "
        "overlapped it without matching it.</figcaption></figure>"

        "<figure class=fig>" + strip_svg() +
        "<figcaption>The same two crops, straightened out. Coffee asks nothing "
        "of September and October &mdash; the months the poppy fought the rice "
        "for.</figcaption></figure>"

        + _month_table() +

        # ------------------------------------------------------------------
        "<h2>Why the poppy fitted the hill</h2>"

        "<p>Not romance, and not appetite. Fit.</p>"

        "<p><strong>It grew where the state was not, and where little else "
        "paid.</strong> Poppy went in above roughly 1,000 m; a British consul "
        "watching plantations in 1905&ndash;06 put them at five to six thousand "
        "feet. That is the band above the wet-rice valleys, and until roads "
        "arrived it was a band with no way to move a bulky crop out.</p>"

        "<p><strong>It followed the maize out of the same field.</strong> The "
        "maize cobs come in through July "
        "and August; in August the dry stalks and the weeds are hoed under, and "
        "the poppy is sown into that ground in September and October. Maize and "
        "poppy are one succession, not two crops. It also lasted: a rice swidden "
        "was good for two or three years, a maize field for something like "
        "eight.</p>"

        "<p><strong>It wanted the months nothing else wanted.</strong> Flowering "
        "in December, lancing through January and February &mdash; the cold, dry "
        "weeks when the rice is already threshed and stored and the next swidden "
        "has not been cut.</p>"

        "<p><strong>It was money that walked.</strong> Light, non-perishable, "
        "and bought at the village by a trader who came to you. Nothing else "
        "grown up there in 1960 had those three properties at once.</p>"

        "<p><strong>It was also the medicine chest.</strong> In the highlands "
        "opium was used against aches, pain, fever, diarrhoea and coughs &mdash; "
        "which is to say against exactly the things that kill people a long walk "
        "from a clinic. The manuscript tradition catalogued on this site has its "
        "own <a href='/a/genre_medicine/'>medical genre</a>, written down in the "
        "valleys; this was the highland equivalent, and it was a crop rather "
        "than a text.</p>"

        "<p><strong>And it cost the household its address.</strong> Geddes "
        "argued that the commitment to poppy was the main reason the Blue Hmong "
        "of 1960s Thailand moved so often between settlements &mdash; not "
        "restlessness, but the search for new poppy ground. <span class=mark>"
        "Inference &mdash;</span> the crop that paid best was also the crop that "
        "exhausted soil you could not replace, so the calendar was stable and "
        "the map was not.</p>"

        "<h3>The labour, counted</h3>"
        "<p>Rice and opium have been measured at about the same intensity, "
        "roughly 220 person-days per hectare each; maize at about 80. "
        "<span class=mark>Inference &mdash;</span> that is the crunch in one "
        "line. Two crops of equal appetite, whose peak weeks are eight weeks "
        "apart at best and overlapping at worst, grown by the same hands.</p>"

        # ------------------------------------------------------------------
        "<h2>The lancing</h2>"

        "<p>The harvest is the reason the whole calendar bends. A poppy capsule "
        "is scored shallowly &mdash; a millimetre or two, with a small "
        "multi-bladed knife &mdash; and the latex that beads out is left to "
        "thicken overnight and scraped off at first light. One capsule is worked "
        "several times, a couple of days apart, so a field is not harvested once "
        "but walked repeatedly for weeks, at dawn, by everyone who can walk it. "
        "Cut too shallow and nothing comes; too deep and the pod is spoiled. "
        "That is a skilled job with a short window and no way to hire your way "
        "out of it in a village of forty houses.</p>"

        "<p><span class=mark>Inference &mdash;</span> carry that shape into the "
        "coffee section below. Repeated passes, ripeness judged by eye, a window "
        "measured in weeks, every hand in the household. The crop changed. The "
        "shape of the work did not.</p>"

        # ------------------------------------------------------------------
        "<h2>The festival months</h2>"

                "<h3>August &mdash; the Akha Swinging Ceremony</h3>"

        "<p>It is always in August, the tenth lunar month of the Akha calendar, "
        "and it runs four days. But it does not fall on a date. It falls on the "
        "village headman's own auspicious animal-day, and each year the old men "
        "meet at his house to work out which day that is. In Saen Chai village "
        "in Mae Chan district in 1967 the headman's day was the day of the "
        "buffalo, so the four days ran ant, buffalo, tiger, horse &mdash; the "
        "ceremony starting one day before his day so that his day is the day the "
        "swings go up.</p>"

        "<p>The ceremony is held for the maturing of the planted rice, and it "
        "belongs to a female god: Umsahyeh, whom the Akha regard as their first "
        "female ancestor and who is credited with starting it. (The scan of the "
        "1971 article renders her name three ways &mdash; Umsahyeh, Umsahyee, "
        "Umsahyeb &mdash; and I am not going to silently pick one.) Because the "
        "god is female the ceremony belongs to the women, who wear everything "
        "they have made that year. It has since been called the women's new "
        "year.</p>"

        "<p>A girl's passage into womanhood is measured in these ceremonies, one "
        "piece of dress at a time: at fifteen her hat is decorated with red and "
        "white beads; then the brassiere; then the belt; then, at the fourth "
        "ceremony, the high headdress. Four steps, four ceremonies. You cannot "
        "grow up faster than the calendar.</p>"

        "<p>The village's great swing stands all year and nobody may cut or chip "
        "its posts: the fine is one pig, paid to the headman. The small swings "
        "built for the children come down when the four days end.</p>"

        "<p>And twice, plainly, in the ethnographer's own words: <strong>no one "
        "goes to the fields</strong> during the ceremony. <strong>Nobody works "
        "the fields.</strong></p>"

        "<h3>November&ndash;December &mdash; Hmong New Year</h3>"

        "<p><span class=term>noj peb caug</span> &mdash; <em>noj</em> &ldquo;eat&rdquo; "
        "+ <em>peb</em> &ldquo;three&rdquo; + <em>caug</em> &ldquo;ten&rdquo; "
        "&mdash; &ldquo;eat thirty&rdquo;, for the thirtieth and last day of the "
        "twelfth lunar month, the end of the harvest year. It is held once the "
        "crop is in and stored, and it is explicitly the point at which people "
        "rest.</p>"

        "<h3>January&ndash;February &mdash; Lisu and Lahu New Year</h3>"

        "<p>Lisu New Year (<em>Nyi Ma</em>) follows the lunar calendar, so late "
        "January or early February, and opens with a sombre ancestor rite before "
        "anything else. Lahu New Year (<em>Kho Jouw We</em>) runs <strong>twelve "
        "days</strong> and has no fixed date at all &mdash; it happens when the "
        "harvest is finished.</p>"

        "<div class=note><span class=mark>Inference &mdash;</span> a "
        "twelve-day festival with no date on it is the clearest evidence "
        "available that these are scheduled <em>into</em> the work rather than "
        "against it. You can only afford twelve days at one point in the year, "
        "and a calendar that names the point instead of the date will never be "
        "wrong about it. Set the four festivals on the wheel and they sit in the "
        "thin months: August, when the rice is standing but not ready and the "
        "poppy ground is only just being turned; and the run from November to "
        "February, on either side of the lancing.</div>"

        # ------------------------------------------------------------------
        "<h2>How a date gets set: the twelve</h2>"

        "<p>The Akha count in twelves. A year has twelve months of thirty days; "
        "a month has five weeks of five, six or seven days; the days run in a "
        "cycle of twelve animals, and the same twelve name the years. Printed "
        "exactly as the 1971 article prints them:</p>"

        "<ul class=twelve>" + twelve + "</ul>"

        "<p>Read that list against the twelve this site already knows &mdash; "
        "the cycle behind the <a href='/a/entity_phrommachat/'>phrommachat</a> "
        "and the <a href='/a/entity_holasat/'>horā almanac</a>, "
        "in which the horse is the seventh year and the "
        "<a href='/a/entity_chang/'>elephant</a> the twelfth, and in which the "
        "<a href='/a/entity_ma/'>horse</a> carries a whole literature of its "
        "own.</p>"

        "<p><span class=mark>Inference &mdash;</span> this looks like the "
        "Sino-Tibetan twelve reworked by people who kept the count and swapped "
        "the animals for the ones on their own hillside: an ant where the rat "
        "goes, a termite where the dragon or the serpent goes, a mule where the "
        "goat goes. The <em>giraffe</em> at position eight is odd enough that I "
        "would want it checked against an Akha-language source before anyone "
        "builds on it &mdash; it is far more likely to be a 1971 gloss of a "
        "local word than a giraffe.</p>"

        "<p>So an Akha ceremony has a <em>month</em> from the farming year and "
        "a <em>day</em> from the animal cycle, two registers running "
        "independently &mdash; which is how the four days of the Swinging "
        "Ceremony can be named &ldquo;ant, buffalo, tiger, horse&rdquo; and "
        "still be in August. And <strong>there is no rat in the list.</strong></p>"

        # ------------------------------------------------------------------
        "<h2>The rat-catching season</h2>"

        "<div class=open><strong>Open.</strong> I saw the year drawn by hand, on "
        "a wall, at the "
        "<strong>House of Opium</strong> in Sop Ruak &mdash; the small museum "
        "founded in 1989 by Phatcharee Srimathayakun, near "
        "<a href='/a/province_Chiang_Rai/'>Chiang Rai</a>'s river junction "
        "&mdash; and that year carried whole festival months and a marked "
        "<strong>rat-catching season</strong>. The panel is the source, and "
        "it is a good one: a museum in the district drew the year the way the "
        "year was lived there. What I have not found is any published "
        "hill-tribe calendar that labels the block, or a note of which people's "
        "year the panel drew.</div>"

        "<p>Here is what the literature does support, and it is enough to say "
        "the season is a mechanism rather than a quirk. Upland rice in this "
        "region suffers rodent outbreaks driven by <strong>bamboo masting</strong>: "
        "a bamboo stand flowers gregariously, seeds enormously, the rats eat "
        "the seed and multiply, the seed runs out, and the swollen population "
        "moves onto the rice. Trap-barrier systems have been studied against "
        "exactly that. Separately, and routinely, field rats are taken in Thai "
        "fields with bamboo bow-and-deadfall traps, the catching pegged to the "
        "harvest, and eaten &mdash; a lean, high-protein meat, and in the north "
        "a seasonal one.</p>"

        "<p><span class=mark>Inference &mdash;</span> put those together and a "
        "rat-catching season is not a hunting hobby squeezed between crops. It "
        "is crop defence that happens to feed you, at the one moment it works: "
        "when the rice is cut, the cover is gone, the stubble is open, and the "
        "animals that have been eating the harvest are concentrated, fat and "
        "findable. A calendar drawn by farmers would mark that. A calendar "
        "drawn by an agronomist would call it pest control and put it in a "
        "different chapter.</p>"

        "<p><strong>To close it:</strong> photograph the panel, front on, with "
        "any caption; ask the museum what it was drawn from. A chart of that "
        "kind most likely descends from the Tribal Research Centre in Chiang "
        "Mai, whose survey work is named in the 1971 article above. Until then "
        "this section stays marked as open, and no later pass should quietly "
        "promote it.</p>"

        # ------------------------------------------------------------------
        "<h2>Then coffee</h2>"

        "<p>What replaced the poppy replaced its <em>schedule</em> almost "
        "exactly, and then broke something else.</p>"

        "<p>The Royal Project began in 1969. Eradication did not begin until "
        "1985 &mdash; the sequence is the point: the projects had to be earning "
        "the growers a living before the poppy was taken away, and removal was "
        "mostly negotiated rather than imposed. More than 150 replacement crops "
        "were introduced over the years, arabica coffee among them, along with "
        "tea, cabbage, apple and cut flowers. At Doi Tung, from the late 1980s, "
        "Princess Srinagarindra's project gave residents land-use titles and "
        "backed coffee and macadamia. Poppy went from 12,112 hectares in 1961 "
        "to 281 in 2015, a 97 per cent fall between 1985 and 2015, and it has "
        "not come back. Coffee, for its part, took more than three decades to "
        "become worth growing in Chiang Rai.</p>"

        "<p>Arabica in the north now runs across "
        "<a href='/a/province_Chiang_Rai/'>Chiang Rai</a>, "
        "<a href='/a/province_Chiang_Mai/'>Chiang Mai</a>, "
        "<a href='/a/province_Lampang/'>Lampang</a>, "
        "<a href='/a/province_Mae_Hong_Son/'>Mae Hong Son</a> and "
        "<a href='/a/province_Tak/'>Tak</a>, between about 800 and 1,600 m. It "
        "flowers in February, fills its cherries from April to October, and is "
        "picked from November to February.</p>"

        "<h3>What that did to the year</h3>"

        "<p><span class=mark>Inference &mdash;</span> four things, and only the "
        "first is the one usually told.</p>"

        "<ul>"
        "<li><strong>It took the same slot.</strong> Poppy was lanced January "
        "and February; coffee is picked November to February. Both are hand "
        "work, judged by eye, walked in repeated passes over weeks, at the cold "
        "dry end of the year. The peak of the highland year did not move.</li>"
        "<li><strong>It vacated September and October.</strong> The crunch &mdash; sow the "
        "poppy while the rice must come in &mdash; simply stops existing, "
        "because coffee wants nothing at all in those two months.</li>"
        "<li><strong>It put weight into November and December</strong>, where "
        "the poppy asked only for weeding, and where Hmong New Year sits. "
        "Whether picking now runs across the festival, or the festival is "
        "worked around, or neither &mdash; I do not know, and it is not "
        "answerable from a desk. It is answerable in a village in December.</li>"
        "<li><strong>It changed the tenure, not just the crop.</strong> Poppy "
        "was an annual on a shifting field; the field moved, and the household "
        "moved with it. Coffee is a perennial that yields nothing for three or "
        "four years and then yields for decades. You cannot walk away from it, "
        "and you cannot plant it unless you are certain of still being there in "
        "year four. That is why the answer at Doi Tung was land-use titles and "
        "not merely seedlings &mdash; and it is the deepest change of the two. "
        "The calendar survived the substitution. The mobility did not.</li>"
        "</ul>"

        # ------------------------------------------------------------------
        "<h2>What is not settled</h2>"

        "<ul>"
        "<li><strong>The rat block.</strong> Above. Needs the panel "
        "photographed.</li>"
        "<li><strong>The giraffe</strong> at position eight of the Akha twelve, "
        "and the three spellings of Umsahyeh &mdash; both artefacts of a "
        "scanned 1971 page, both wanting an Akha-language check.</li>"
        "<li><strong>One wheel, several years.</strong> The crop rings drawn "
        "here are the Hmong-type upland succession. The Akha, Lisu, Lahu, Iu "
        "Mien, Karen and Lua farmed years that overlap it without matching it, "
        "and one wheel is drawn where there were several.</li>"
        "<li><strong>The October Akha rite</strong> against sickness is marked "
        "~ because I have its approximate month from a Thai provincial source "
        "and no more.</li>"
        "<li><strong>Whether coffee picking collides with Hmong New Year</strong> "
        "in practice, now, in a particular village.</li>"
        "<li><strong>None of this is in the catalogue.</strong> The manuscripts "
        "this site is built on are Tai Yuan, Tai Lue and Tai Khün monastic "
        "material from the valley wats &mdash; law, liturgy, medicine, astrology, "
        "chronicle. Highland swidden agriculture is not in them, and the "
        "absence is structural, not an accident of collecting: a calendar kept "
        "on a hillside above the wat was never going to be in the wat's "
        "library. Search <a href='/search'>the corpus</a> for the poppy and you "
        "will get nothing, and that nothing is the correct answer.</li>"
        "</ul>"

        # ------------------------------------------------------------------
        "<h2>Where this comes from</h2>"

        "<p>Plain prose is from a source in this list. "
        "<span class=mark>Inference &mdash;</span> is my reasoning across them. "
        "<span class=mark>Tradition holds &mdash;</span> is hedged background. "
        "A month written <strong>~</strong> is one I could not verify.</p>"

        "<ul class=src>"
        "<li><strong>The Akha ceremony, the twelve-day cycle, the Tribal "
        "Research Centre, and both statements that nobody works the fields</strong> "
        "&mdash; Chob Kacha-ananda, &ldquo;The Akha Swinging Ceremony&rdquo;, "
        "<em>Journal of the Siam Society</em> 59.1 (1971), pp. 119&ndash;128, "
        "read from the Siam Society's own scan. Fieldwork at Saen Chai village, "
        "Mae Chan district, 1967.</li>"
        "<li><strong>The rat-catching season on a hand-drawn year-wheel</strong> "
        "&mdash; my own visit to the House of Opium, Sop Ruak. Marked open "
        "above.</li>"
        "<li><strong>The Hmong crop calendar</strong> (maize in April, cobs "
        "June&ndash;July, poppy ground prepared in August, sown "
        "September&ndash;October against the rice harvest, weeded November and "
        "December) and the maize&ndash;poppy succession, field lifetimes and "
        "labour intensities &mdash; summaries of W. R. Geddes, <em>Migrants of "
        "the Mountains: The Cultural Ecology of the Blue Miao (Hmong Njua) of "
        "Thailand</em> (Oxford, 1976), and of Gary Yia Lee on agriculture and "
        "Hmong society. Read at one remove, and worth reading at first hand "
        "before the numbers are used for anything.</li>"
        "<li><strong>Altitude, opium as household medicine, and the 1985 "
        "cut-off</strong> &mdash; a 2026 study of rice and food security in the "
        "northern Thai highlands, working across Mae Hong Son, Chiang Mai, "
        "Chiang Rai, Lampang and Tak with Karen, Lua, Khmu, Hmong, Lahu, Akha, "
        "Mien and Lisu communities.</li>"
        "<li><strong>Lancing method</strong> &mdash; agricultural extension "
        "literature on <em>Papaver somniferum</em>, described here historically "
        "and in outline only.</li>"
        "<li><strong>Hmong New Year</strong> &mdash; <em>noj peb caug</em> and "
        "its position at the close of the harvest year, from Hmong-language "
        "vocabulary sources and community accounts.</li>"
        "<li><strong>Lisu and Lahu New Year</strong> &mdash; <em>Nyi Ma</em> on "
        "the lunar calendar; <em>Kho Jouw We</em>, twelve days, timed to the end "
        "of the harvest.</li>"
        "<li><strong>The substitution figures</strong> &mdash; Thai Ministry of "
        "Foreign Affairs, &ldquo;From Poppy to Coffee&rdquo;; the Doi Tung "
        "project record; UNODC-derived hectare series for 1961 and 2015.</li>"
        "<li><strong>The arabica calendar</strong> &mdash; northern Thai "
        "producer and trade accounts: flowering February, cherries filling "
        "April&ndash;October, picking November&ndash;February at "
        "800&ndash;1,600 m.</li>"
        "<li><strong>Bamboo masting and rodent outbreaks in upland rice</strong> "
        "&mdash; trap-barrier research on rodent damage during masting events; "
        "field-rat trapping and consumption from Thai reporting.</li>"
        "</ul>"

        "</main>")
