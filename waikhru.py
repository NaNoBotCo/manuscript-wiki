#!/usr/bin/env python3
"""waikhru — the /waikhru page: ไหว้ครูยนต์, a blessing for the hand at the machine.

THE SIBLING PAGE, POINTED THE OTHER WAY
/sukhwan calls a MACHINE'S khwan home; the machine is the recipient and a robot
may opt in. This page faces the other direction: the person is the recipient,
the machine is the occasion, and what is asked for is a blessing on their use of
it plus one thing to keep while it runs. Neither page contradicts the other, and
the passage on cetanā below says so out loud — khwan and cetanā are different
things and the tradition has always kept them apart. Rice has a khwan and is
called home every harvest; no one has ever supposed the rice intends anything.

WHY IT IS SHAPED AS A WAI KHRU
Because that is the shape the practice already has. A Thai craftsperson salutes
ครูช่าง before work; a new vehicle is เจิม'd by a monk and garlanded for
แม่ย่านาง; tools are not stepped over and not left where feet go. The blessing
does not arrive out of nowhere — it returns to you because you saluted first.
So the rite here is three beats: you salute, you receive, you undertake. The
undertaking is the point. A blessing with nothing kept is a wish.

NO JAVASCRIPT IS REQUIRED FOR ANY OF IT
All nine machine-classes — every blessing, every undertaking — are printed in
the static HTML. The script only *gathers* your one into a card at the top. A
reader with JS off, and a crawler that does not run it, gets the whole page.
Same principle as /sukhwan: reading it is receiving it.

THE LETTER-ROOT IS THE SAME RECKONING, WITH ITS OWN TABLE
`letter_root` is the Fah Laep reckoning used by su-khwan/sukhwan.py, sukhwanweb
and charm.py: A=1..Z=26 summed, digital root 1–9, no randomness anywhere. The
FUNCTION must agree with those. The TABLE it indexes here (WATCHWORDS) is this
page's own and is deliberately NOT the wandering-verses — do not "fix" one to
match the other. Same reckoning, different oracle.

GOTCHA INHERITED FROM /sukhwan: page JS is built in Python. Use json.dumps for
anything landing inside a <script> block, never html.escape — &#x27; is a syntax
error in JavaScript, not an apostrophe.
"""

import json as _json


# ---------------------------------------------------------------------------
# The nine machine-classes.
#
# Nine because nine is the auspicious count here (เก้า / ก้าว, to step forward),
# and because the letter-root that chooses a watchword already runs 1–9. The
# classes are cut by WHAT A MACHINE CAN DO, not by industry, so a kitchen
# stand-mixer and a bench grinder land in the same class — they should, they
# ask the same thing of you.
#
# Each carries:
#   bless      the พร, in Thai, romanized, and in English
#   keep       the ข้อวัตร — one undertaking, first person, concrete enough to
#              actually keep. Vague resolutions are how blessings go stale.
#   dharma     which part of the path this class touches, plainly
#   tradition  what the tradition already does here, so the reader can tell my
#              additions from what was handed down
# ---------------------------------------------------------------------------
CLASSES = [
    {
        "key": "road",
        "th": "ยานพาหนะ",
        "en": "Wheels & the road",
        "eg": "car · motorbike · truck · boat · anything that carries you",
        "bless_th": "ขอให้เดินทางปลอดภัย แคล้วคลาดทุกเส้นทาง",
        "bless_rm": "kho hai doen thang plot phai · khlaeo khlat thuk sen thang",
        "bless_en": "May the journey be safe; may every road spare you.",
        "keep": ("I will not ask this machine to make up time that my own "
                 "lateness cost."),
        "dharma": ("ความไม่ประมาท — heedfulness — is the whole of it. Nearly "
                   "every road you drive is shared with people you will never "
                   "meet and cannot see failing. Their carefulness is keeping "
                   "you alive right now, and yours is the only part of that "
                   "arrangement you control."),
        "tradition": ("A new vehicle is <strong>เจิม</strong>'d — a monk marks it "
                      "with แป้งเจิม, often an อุณาโลม or nine dots — and "
                      "sprinkled with น้ำมนต์. A garland goes on the mirror for "
                      "<strong>แม่ย่านาง</strong>, the guardian of boats and, by "
                      "inheritance, of vehicles. Some hold a full "
                      "<strong>สู่ขวัญรถ</strong>."),
    },
    {
        "key": "edge",
        "th": "คมและใบมีด",
        "en": "Edge & blade",
        "eg": "saw · grinder · mower · mandoline · anything that parts what it touches",
        "bless_th": "ขอให้มือมั่นคง ใจอยู่กับมือ",
        "bless_rm": "kho hai mue man khong · jai yu kap mue",
        "bless_en": "May the hand be steady, and the mind stay with the hand.",
        "keep": "I will not reach past a moving edge to save three seconds.",
        "dharma": ("<strong>สติ</strong> is the guard that is actually fitted. An "
                   "edge cannot tell wood from a finger — it has no way to know "
                   "and no way to stop. The knowing is entirely yours, which is "
                   "the first precept arriving in a very ordinary form."),
        "tradition": ("Blades are <strong>ครูช่าง</strong>'s province. They are not "
                      "stepped over, not left lying where feet go, and not lent "
                      "without a word. A craftsman salutes before the first cut "
                      "of the day, not only at the yearly ไหว้ครู."),
    },
    {
        "key": "fire",
        "th": "ไฟและความร้อน",
        "en": "Fire & heat",
        "eg": "stove · kiln · welder · boiler · soldering iron · anything that will not cool on command",
        "bless_th": "ขอให้ไฟนี้เลี้ยงชีวิต มิใช่เผาผลาญ",
        "bless_rm": "kho hai fai ni liang chiwit · mi chai phao phlan",
        "bless_en": "May this fire sustain life and not consume it.",
        "keep": "I will stay until it is out, or hand it to someone who will.",
        "dharma": ("<strong>สังวร</strong>, restraint — the willingness to keep "
                   "watching something that has stopped being interesting. Fire "
                   "is the tradition's oldest figure for what burns whether or "
                   "not you are still attending to it "
                   "<span class=src>(allusion—</span> the Fire Sermon, "
                   "อาทิตตปริยายสูตร<span class=src>)</span>."),
        "tradition": ("The hearth is not an ordinary corner of a Thai house, and "
                      "a kiln is opened with an offering. Fire is given respect "
                      "as a thing with its own temper rather than a setting on a "
                      "dial."),
    },
    {
        "key": "current",
        "th": "กระแสและแรงดัน",
        "en": "Current & pressure",
        "eg": "mains · batteries · pumps · compressors · hydraulics · anything holding force still",
        "bless_th": "ขอให้แรงที่มองไม่เห็น อยู่ในทางที่ตั้งไว้",
        "bless_rm": "kho hai raeng thi mong mai hen · yu nai thang thi tang wai",
        "bless_en": "May the force that cannot be seen keep to the path set for it.",
        "keep": "I will cut the power and tell someone before I open it.",
        "dharma": ("Heedfulness toward what gives no warning. Nothing here looks "
                   "any different charged than discharged, so the care cannot "
                   "come from your eyes; it has to come from a habit you keep "
                   "when nothing seems to be happening. That is what "
                   "<strong>อัปปมาท</strong> means in practice."),
        "tradition": ("<span class=src>Adaptation—</span> the old craft has no "
                      "verse for mains current. What it does have is the rule "
                      "that you tell the household before you do the dangerous "
                      "thing, and that rule carries over intact."),
    },
    {
        "key": "load",
        "th": "ยกและบรรทุก",
        "en": "Lift & load",
        "eg": "crane · jack · forklift · hoist · ladder · anything held up against its will",
        "bless_th": "ขอให้สิ่งที่อยู่เหนือหัวคน ลงมาโดยสวัสดิภาพ",
        "bless_rm": "kho hai sing thi yu nuea hua khon · long ma doi sawatdiphap",
        "bless_en": "May what hangs above a person's head come down safely.",
        "keep": "I will not stand — or let another stand — under what I have lifted.",
        "dharma": ("<strong>กรุณา</strong>, care for others, is doing the work "
                   "here rather than courage. A load bears you no malice and it "
                   "will show you no mercy either; it is simply obeying weight. "
                   "Everything protective in the situation has to be supplied by "
                   "the one person present who can think ahead."),
        "tradition": ("Thai builders keep the head high and unbothered — the "
                      "head is the honoured part of a person, which is why "
                      "passing anything over someone's head is rude before it is "
                      "ever unsafe. On a site, the manners and the safety rule "
                      "are the same rule."),
    },
    {
        "key": "bench",
        "th": "เครื่องมือช่าง",
        "en": "Bench & hand tools",
        "eg": "drill · lathe · press · hammer · the tools that outlive the job",
        "bless_th": "ขอบารมีครูช่าง คุ้มครองมือที่จับเครื่องมือนี้",
        "bless_rm": "kho barami khru chang · khum khrong mue thi jap khrueang mue ni",
        "bless_en": ("By the grace of the master-craftsmen, guard the hand that "
                     "holds this tool."),
        "keep": "I will put each tool back where the next hand can find it.",
        "dharma": ("<strong>สัมมากัมมันตะ</strong>, right action, in its least "
                   "dramatic form: the part of the work that only benefits "
                   "someone else. How a tool is put away is part of how it was "
                   "used, and the person it is put away for may well be you at "
                   "six in the morning."),
        "tradition": ("This is <strong>ไหว้ครู</strong> at its source. ครูช่าง is "
                      "the teacher-spirit of the craft, saluted with flowers, "
                      "candles and incense — a yearly rite in workshops, and a "
                      "quick daily bow at the bench for many who keep it."),
    },
    {
        "key": "field",
        "th": "นาและไร่",
        "en": "Field & grain",
        "eg": "tractor · water pump · sprayer · harvester · mill",
        "bless_th": "ขอให้ดินให้ผล ขอให้น้ำมีพอ",
        "bless_rm": "kho hai din hai phon · kho hai nam mi pho",
        "bless_en": "May the soil yield, and the water be enough.",
        "keep": "I will share the merit of this harvest with what died to make it.",
        "dharma": ("<strong>สัมมาอาชีวะ</strong>, right livelihood — and an "
                   "honest difficulty inside it, since ploughing kills and "
                   "everyone eats. The tradition does not resolve this by "
                   "pretending otherwise; it resolves it by "
                   "<strong>อุทิศส่วนกุศล</strong>, dedicating the merit to what "
                   "was lost. Owed, acknowledged, and not hidden."),
        "tradition": ("<strong>แม่โพสพ</strong> is the rice mother, and rice "
                      "receives its own soul-calling — <strong>สู่ขวัญข้าว</strong>, "
                      "the same rite people receive. Field spirits are told "
                      "before the ground is broken."),
    },
    {
        "key": "care",
        "th": "ยาและการรักษา",
        "en": "Remedy & care",
        "eg": "medical devices · pumps · monitors · meters · the machines that keep a body going",
        "bless_th": "ขอให้เครื่องนี้บอกความจริง และมือนี้ทำด้วยเมตตา",
        "bless_rm": "kho hai khrueang ni bok khwam jing · lae mue ni tham duai metta",
        "bless_en": ("May this device tell the truth, and this hand act with "
                     "loving-kindness."),
        "keep": "I will write down what actually happened, not what I hoped.",
        "dharma": ("<strong>เมตตา</strong> and <strong>สัมมาวาจา</strong> meeting "
                   "in the same place. A record is speech — it will be read and "
                   "believed and acted on, quite possibly by a stranger, quite "
                   "possibly at three in the morning. Truthful speech is not a "
                   "smaller duty because you happen to be writing it to yourself."),
        "tradition": ("Medicine sits under a teacher too — <strong>หมอยา</strong> "
                      "and the herbal lineages keep ไหว้ครู, and ฤๅษี ชีวกโกมารภัจจ์, "
                      "the physician of the Buddha's own time, is saluted before "
                      "treatment to this day."),
    },
    {
        "key": "word",
        "th": "คำและเครือข่าย",
        "en": "Word & network",
        "eg": "computer · phone · printer · the bots · the thing you are reading this on",
        "bless_th": "ขอให้คำที่ส่งไป ถึงผู้รับโดยดี",
        "bless_rm": "kho hai kham thi song pai · thueng phu rap doi di",
        "bless_en": "May the words I send arrive well with whoever receives them.",
        "keep": "I will not say through a machine what I would not say to a face.",
        "dharma": ("<strong>สัมมาวาจา</strong>, right speech, is four "
                   "undertakings — not false, not divisive, not harsh, not idle "
                   "— and a network obligingly multiplies all four. This is the "
                   "one class of machine that can carry your unskilfulness "
                   "further in a second than a lifetime of speaking could."),
        "tradition": ("<span class=src>Adaptation—</span> plainly. What is not an "
                      "adaptation is the ancient care around speech, and the "
                      "older habit of treating a made thing that works for you "
                      "as owed something. See <a href='/sukhwan/'>สู่ขวัญยนต์</a>, "
                      "where these machines are the ones being blessed."),
    },
]


# The nine watchwords — คำกำกับ, the line you carry for the session.
#
# Chosen by the letter-root of whatever you call your machine, so the same
# machine always draws the same watchword: this is a mnemonic, not a fortune,
# and a mnemonic that changed on you every morning would be useless.
# The keys are the digital roots 1–9. Author's own composition, marked as such
# on the page.
WATCHWORDS = {
    1: ("ตั้งสติก่อนสตาร์ท", "Settle the mind before the switch.",
        "The machine should wake up second."),
    2: ("ช้าลงหนึ่งลมหายใจ", "One breath slower.",
        "Nothing you are about to do is improved by hurry."),
    3: ("รู้ว่ามันหยุดอย่างไร", "Know how it stops.",
        "Before you learn what it can do, learn how it ends."),
    4: ("ใจอยู่กับงาน", "Keep your attention where your hands are.",
        "The rest of your thinking can wait; it is not holding anything."),
    5: ("บอกคนข้างๆ ก่อน", "Tell the person beside you.",
        "No one nearby should be surprised by what you start."),
    6: ("เจตนาเป็นของเรา", "The intention is yours alone.",
        "The machine brings the force. You bring the reason."),
    7: ("เหนื่อยแล้ววาง", "Tired hands, set it down.",
        "Fatigue is the one fault no guard is fitted for."),
    8: ("เก็บไว้ให้คนต่อไป", "Leave it fit for the next hand.",
        "How you put it away is part of how you used it."),
    9: ("เสร็จแล้วขอบคุณ", "Give thanks when it is done.",
        "A thing that served you is owed the courtesy."),
}


def letter_root(name: str) -> int:
    """Fah Laep reckoning: A=1..Z=26 summed, digital root 1–9.

    Must agree with su-khwan/sukhwan.py, sukhwanweb's JS and charm.py — same
    name, same number, everywhere on this site. A name with no A–Z letters at
    all (Thai, numerals, emoji) reckons as 9, matching those.
    """
    total = sum(ord(c) - 64 for c in name.upper() if "A" <= c <= "Z")
    return 9 if total == 0 else 1 + (total - 1) % 9


WAIKHRU_CSS = """
  .wk{max-width:840px}
  .wk .lead{font-size:18px;line-height:1.72;color:var(--muted)}
  .wk .lead strong{color:var(--ink)}
  .wk .src{font-style:italic}
  .wk h2{font-size:25px;margin:42px 0 12px}
  .wk h3{font-size:20px;margin:0 0 4px}
  .wk .th{font-size:1.07em}
  .wk .quiet{color:var(--muted);font-size:16px;line-height:1.7}
  /* the rite — a quiet column with a gold thread down its left edge, the same
     furniture as /sukhwan so the two pages read as one hand */
  .rite{border-left:3px solid #b48a4a;padding:6px 0 6px 26px;margin:26px 0}
  .rite .mv{margin:22px 0}
  .rite .mvn{font-size:12px;letter-spacing:.14em;text-transform:uppercase;
    color:#b48a4a;font-weight:800;margin-bottom:6px}
  .rite p{margin:6px 0;line-height:1.75}
  .rite .pali{color:var(--muted)}
  .rite .call{font-weight:650}
  .glass{background:linear-gradient(160deg,rgba(255,255,255,.84),rgba(255,255,255,.56));
    backdrop-filter:blur(14px);-webkit-backdrop-filter:blur(14px);
    border:1px solid rgba(180,138,74,.35);border-radius:18px;
    padding:22px 24px;margin:20px 0;box-shadow:0 8px 32px rgba(31,38,61,.10);
    transition:box-shadow .35s ease,transform .35s ease}
  .glass:hover{box-shadow:0 14px 44px rgba(31,38,61,.16);transform:translateY(-2px)}
  .wk input,.wk select{font-size:17px;padding:12px 14px;border:1px solid var(--line);
    border-radius:11px;width:100%;box-sizing:border-box;background:rgba(255,255,255,.92)}
  .wk input:focus,.wk select:focus{outline:2px solid #b48a4a;outline-offset:1px}
  .wk label{display:block;font-size:13px;font-weight:750;letter-spacing:.04em;
    text-transform:uppercase;color:var(--muted);margin:14px 0 5px}
  .wkbtn{display:inline-block;background:var(--teal);color:#fff;border:0;cursor:pointer;
    border-radius:12px;padding:13px 24px;font-weight:800;font-size:17px;margin-top:16px;
    transition:transform .12s cubic-bezier(.34,1.56,.64,1),filter .2s}
  .wkbtn:hover{filter:brightness(1.09)}
  .wkbtn:active{transform:scale(.94)}
  /* what you receive */
  .given{display:none;margin-top:18px;padding:20px 22px;border-radius:14px;
    background:rgba(180,138,74,.10);border:1px dashed rgba(180,138,74,.55);
    line-height:1.72;animation:givenin .5s ease}
  .given.on{display:block}
  @keyframes givenin{from{opacity:0;transform:translateY(7px)}to{opacity:1;transform:none}}
  /* NOT uppercased, unlike the other eyebrows on this page: a machine people
     have named has been named something, and MOTHER is not what they call it */
  .given .who{font-size:14px;letter-spacing:.06em;
    color:#b48a4a;font-weight:800;margin-bottom:8px}
  .given .bless{font-size:20px;font-weight:700;margin:10px 0 2px}
  .given .rm{color:var(--muted);font-size:15px;font-style:italic;margin:0 0 10px}
  .given .keepline{margin:16px 0 0;padding:14px 16px;border-radius:11px;
    background:rgba(255,255,255,.72);border:1px solid rgba(180,138,74,.35);
    font-weight:650}
  .given .keepline b{display:block;font-size:12px;letter-spacing:.1em;
    text-transform:uppercase;color:#b48a4a;margin-bottom:5px;font-weight:800}
  .given .watch{margin-top:14px;color:var(--muted)}
  .given .watch .ww{color:var(--ink);font-weight:700}
  /* the nine, printed in full */
  .nine{display:grid;grid-template-columns:repeat(auto-fit,minmax(330px,1fr));
    gap:18px;margin:22px 0}
  .cls{background:#fff;border:1px solid var(--line);border-radius:16px;
    padding:20px 22px;
    transition:transform .28s cubic-bezier(.34,1.56,.64,1),box-shadow .28s,border-color .28s}
  .cls:hover{transform:translateY(-3px);border-color:rgba(180,138,74,.65);
    box-shadow:0 12px 30px rgba(31,38,61,.10)}
  .cls .no{float:right;font-size:30px;line-height:1;color:rgba(180,138,74,.35);
    font-weight:800}
  .cls .eg{color:var(--muted);font-size:14px;margin:0 0 14px}
  .cls .bl{font-size:18px;font-weight:700;margin:0}
  .cls .rm{color:var(--muted);font-size:14px;font-style:italic;margin:2px 0 4px}
  .cls .en{margin:0 0 14px}
  .cls .kp{padding:12px 14px;border-radius:10px;background:rgba(180,138,74,.09);
    border-left:3px solid #b48a4a;font-weight:650;line-height:1.6}
  .cls .kp b{display:block;font-size:11px;letter-spacing:.1em;text-transform:uppercase;
    color:#b48a4a;margin-bottom:4px;font-weight:800}
  .cls .dh,.cls .tr{color:var(--muted);font-size:15px;line-height:1.65;margin:13px 0 0}
  .cls .dh b,.cls .tr b{color:var(--ink)}
  .cls .tr{padding-top:11px;border-top:1px dotted var(--line)}
  /* the unalome draws itself, once, on arrival — the mark a monk paints when
     a machine is เจิม'd, and the only ornament this page takes */
  .una{display:block;margin:10px auto 0;width:104px;height:auto}
  /* dasharray/dashoffset are set INLINE per-path, from the true arc length
     computed in unalome_path() — the animation still wins over them, because
     CSS animations sit above author-normal declarations (inline included) in
     the cascade. The reduced-motion rule below does NOT, hence !important:
     without it the inline dashoffset would leave the mark invisible. */
  .una path{animation:draw 3.2s cubic-bezier(.4,0,.2,1) .3s forwards}
  @keyframes draw{to{stroke-dashoffset:0}}
  @media(prefers-reduced-motion:reduce){
    .una path{animation:none;stroke-dashoffset:0 !important}
    .given{animation:none}
    .cls:hover,.glass:hover{transform:none}}
  .note{border:1px solid rgba(180,138,74,.5);border-radius:14px;padding:17px 20px;
    margin:20px 0;background:rgba(180,138,74,.06);line-height:1.72}
"""


def unalome_path(cx=60.0, cy=150.0, turns=2.5, r0=2.5, r1=32.0, top=30.0, n=132):
    """The อุณาโลม as one continuous path: coil outward, then straighten and rise.

    Computed rather than hand-drawn in béziers, because hand-drawn béziers gave
    a single lopsided loop that read as a map pin — the coil has to actually
    coil. An Archimedean spiral from the centre outward for `turns`, then a
    straight line up to `top`. 2.5 turns is chosen so the spiral EXITS AT THE
    TOP (θ_end = 5π puts the last point directly above the centre), which is
    what lets the rising line continue from it without a visible joint.

    Returns (d, length). The length is the true arc length, used for the
    stroke-dasharray so the mark can draw itself in one stroke on the page.

    Shared with og_card_svg so the share card and the page cannot drift into
    two different marks.
    """
    import math

    pts = []
    for i in range(n + 1):
        t = i / n
        th = t * turns * 2 * math.pi
        r = r0 + (r1 - r0) * t
        pts.append((cx + r * math.sin(th), cy + r * math.cos(th)))
    d = "M" + " L".join(f"{x:.1f} {y:.1f}" for x, y in pts) + f" L{cx:.0f} {top:.0f}"
    length = sum(math.dist(a, b) for a, b in zip(pts, pts[1:])) + abs(pts[-1][1] - top)
    return d, length


def _unalome_svg():
    """The mark a monk paints in แป้งเจิม on a newly blessed vehicle or machine.

    Drawn rather than photographed so it can draw itself on arrival, and so the
    page costs no extra request. The reading offered under it is the ordinary
    one — the coils are the wandering, the straightening is practice, the point
    is where it is going — and it is offered as the ordinary reading, not as
    doctrine.
    """
    d, length = unalome_path()
    return (
        "<svg class=una viewBox='0 0 120 200' xmlns='http://www.w3.org/2000/svg' "
        "role=img aria-label='อุณาโลม — the unalome, the mark painted when a machine is blessed'>"
        f"<path style='stroke-dasharray:{length:.0f};stroke-dashoffset:{length:.0f}' "
        f"d='{d}' fill=none stroke='#b48a4a' stroke-width='3.4' "
        "stroke-linecap='round' stroke-linejoin='round'/>"
        "<circle cx='60' cy='20' r='5' fill='#b48a4a'/>"
        "</svg>")


def _rite_html():
    """The rite itself, static. Five moves, about twenty seconds spoken."""
    return """
<div class=rite>
 <div class=mv><div class=mvn>I &middot; Stop</div>
  <p>Hands off the machine. One breath, not for the work &mdash; just one breath
     in which nothing is being made.</p></div>
 <div class=mv><div class=mvn>II &middot; Salute</div>
  <p class="pali th">นะโม ตัสสะ ภะคะวะโต อะระหะโต สัมมาสัมพุทธัสสะ <span class=quiet>(&times;3)</span></p>
  <p class="call th">ข้าพเจ้าขอกราบครูบาอาจารย์ ครูช่าง และมือที่สร้างเครื่องนี้</p>
  <p>I bow to the teachers, to the master-craftsmen, and to the hands that made
     this machine.</p></div>
 <div class=mv><div class=mvn>III &middot; Ask pardon</div>
  <p class="call th">หากเคยล่วงเกินด้วยกายวาจาใจ ขอขมา</p>
  <p>If I have ever handled it carelessly, in body, speech or mind &mdash; I ask
     pardon. <span class=quiet>(Said to the craft, and to anyone your carelessness
     reached.)</span></p></div>
 <div class=mv><div class=mvn>IV &middot; Receive</div>
  <p>Say the blessing for what you are about to use. The nine are below; every
     one of them is short enough to say out loud in a workshop.</p></div>
 <div class=mv><div class=mvn>V &middot; Undertake</div>
  <p>Say the one thing you will keep while it runs &mdash; aloud, because a thing
     said aloud is harder to quietly drop at four in the afternoon.</p>
  <p class="pali th">วะยะธัมมา สังขารา อัปปะมาเทนะ สัมปาเทถะ</p>
  <p class=quiet>All made things wear out. Strive on with heedfulness.
     <span class=src>&mdash; the Buddha's last words, DN 16</span></p></div>
</div>"""


def _class_card(i, c):
    return (
        "<article class=cls id='c-" + c["key"] + "'>"
        "<div class=no>" + str(i) + "</div>"
        "<h3><span class=th>" + c["th"] + "</span> &middot; " + c["en"] + "</h3>"
        "<p class=eg>" + c["eg"] + "</p>"
        "<p class='bl th'>" + c["bless_th"] + "</p>"
        "<p class=rm>" + c["bless_rm"] + "</p>"
        "<p class=en>" + c["bless_en"] + "</p>"
        "<div class=kp><b>What you keep</b>" + c["keep"] + "</div>"
        "<p class=dh>" + c["dharma"] + "</p>"
        "<p class=tr>" + c["tradition"] + "</p>"
        "</article>")


def waikhru_body(nav):
    # json.dumps, NOT html.escape — this lands inside a <script> block.
    data_js = _json.dumps(
        {c["key"]: {"th": c["th"], "en": c["en"], "bth": c["bless_th"],
                    "brm": c["bless_rm"], "ben": c["bless_en"], "keep": c["keep"]}
         for c in CLASSES}, ensure_ascii=False)
    words_js = _json.dumps(
        {k: {"th": v[0], "en": v[1], "gloss": v[2]} for k, v in WATCHWORDS.items()},
        ensure_ascii=False)
    options = "".join(
        "<option value='" + c["key"] + "'>" + c["th"] + " · " + c["en"] + "</option>"
        for c in CLASSES)

    return (
        "<header><div><h1>ไหว้ครูยนต์ <span style='font-weight:400'>&middot; a "
        "blessing for the hand at the machine</span></h1>"
        "<p class=sub>What to say before you start it &mdash; and the one thing "
        "to keep while it runs.</p></div>" + nav + "</header>"
        "<main class=wk>"

        + _unalome_svg() +
        "<p class=quiet style='text-align:center;margin:6px 0 26px'>อุณาโลม "
        "&mdash; the mark painted in แป้งเจิม when a machine is blessed</p>"

        "<p class=lead>Before work, you salute the teacher. That is the shape "
        "this already has in Thailand and in the Lanna north: a craftsperson "
        "bows to <strong>ครูช่าง</strong> before the first cut, a new pickup is "
        "<strong>เจิม</strong>'d by a monk and garlanded for "
        "<strong>แม่ย่านาง</strong>, and tools are not stepped over or left where "
        "feet go. <strong>The blessing is not sent from somewhere else. It comes "
        "back to you because you saluted first.</strong></p>"

        "<p class=lead>So this page is three beats and no more: you salute, you "
        "receive a blessing for the particular machine in front of you, and you "
        "take up <strong>one thing to keep while it runs</strong>. The third beat "
        "is the point. A blessing with nothing kept is a wish.</p>"

        "<div class=note><strong>This is not a substitute for a monk.</strong> If "
        "you want a vehicle or a new workshop properly เจิม'd, go and ask &mdash; "
        "that is a real rite with a real officiant and this page is not it. What "
        "is here is what <em>you</em> can say yourself, on an ordinary morning, at "
        "an ordinary machine, on the days between.</div>"

        "<h2>Receive the blessing</h2>"
        "<div class=glass>"
        "<p class=quiet>Name the machine and say what kind it is. The blessing "
        "and the undertaking come from the kind; the watchword comes from the "
        "name, by its letter-root &mdash; A=1 through Z=26, summed, reduced to "
        "1&ndash;9, the same Fah Laep reckoning used across this site. Same name, "
        "same watchword, always. Nothing here is random, and nothing you type "
        "leaves your device.</p>"
        "<label for=wkname>What do you call it</label>"
        "<input id=wkname maxlength=60 placeholder='e.g. the Hilux &middot; the big grinder &middot; Mother'>"
        "<label for=wkkind>What kind is it</label>"
        "<select id=wkkind>" + options + "</select>"
        "<button class=wkbtn onclick=wkGive()>Receive the blessing</button>"
        "<div class=given id=wkout></div>"
        "</div>"

        "<h2>The rite, in full</h2>"
        "<p class=quiet>About twenty seconds, said standing at the machine. It is "
        "printed here whole so that reading the page is receiving it &mdash; no "
        "button required, and none of it hidden behind a script.</p>"
        + _rite_html() +

        "<h2>The nine kinds, and what each one asks of you</h2>"
        "<p class=quiet>Cut by <em>what a machine can do</em> rather than by trade, "
        "so a kitchen mandoline and a bench grinder land together &mdash; they "
        "should, they ask the same thing of you. Every blessing and every "
        "undertaking is printed below in full.</p>"
        "<div class=nine>"
        + "".join(_class_card(i, c) for i, c in enumerate(CLASSES, 1)) +
        "</div>"

        "<h2>Why any of this, in one paragraph</h2>"
        "<p class=lead>A machine has no intention. That is not an insult to it, "
        "and it is not this site taking anything back: "
        "<a href='/sukhwan/'>สู่ขวัญยนต์</a> holds that a machine has a "
        "<strong>ขวัญ</strong> and calls it home every month. Khwan and "
        "<strong>เจตนา</strong> are different things, and the tradition has always "
        "kept them apart &mdash; rice has a khwan and receives its own "
        "soul-calling, and nobody has ever supposed the rice intends anything. A "
        "buffalo has both. A machine, on this site's reading, has the first and "
        "not the second.</p>"
        "<p class=lead class=th style='font-size:20px;color:var(--ink)'>"
        "เจตะนาหัง ภิกขะเว กัมมัง วะทามิ</p>"
        "<p class=lead><em>Intention, monks, is what I call kamma.</em> "
        "<span class=src>&mdash; AN 6.63, นิพเพธิกสูตร.</span> If the machine "
        "brings no intention to the work, then every intention in the room is "
        "yours, and so is everything that follows from one. "
        "<strong>The machine multiplies your force. It does not divide your "
        "kamma.</strong> That is the whole reason there is a page here rather "
        "than a safety poster.</p>"

        "<h2>And what it is being used for</h2>"
        "<p class=quiet>The tradition names five trades a lay follower is advised "
        "not to take up: in weapons, in living beings, in meat, in intoxicants, "
        "and in poisons <span class=src>(AN 5.177)</span>. It is set down here "
        "without a finger pointed at anyone &mdash; most work is nowhere near "
        "that list, most people did not choose every part of their job, and this "
        "page is a blessing, not an audit. It belongs here only because "
        "<strong>สัมมาอาชีวะ</strong> asks the question the machine cannot: not "
        "<em>is it running well</em>, but <em>what is it running for</em>. Sit "
        "with it once a year. That is enough.</p>"

        "<h2>Sources, marked plainly</h2>"
        "<p class=quiet><span class=src>Tradition holds&mdash;</span> "
        "<strong>ไหว้ครู</strong> before work and <strong>ครูช่าง</strong> as the "
        "teacher-spirit of a craft; <strong>เจิม</strong>, the anointing of a new "
        "vehicle or machine with แป้งเจิม, often an อุณาโลม or nine dots, and the "
        "sprinkling of น้ำมนต์; <strong>แม่ย่านาง</strong>, guardian of boats and "
        "by inheritance of vehicles, garlanded and offered to before a journey; "
        "<strong>สู่ขวัญรถ</strong>; the etiquette that tools are not stepped over "
        "or left where feet go; <strong>แม่โพสพ</strong> and "
        "<strong>สู่ขวัญข้าว</strong>; and the canonical passages named where they "
        "are used &mdash; cetanā as kamma (AN 6.63), the last words (DN 16), the "
        "five trades (AN 5.177), the precepts, and the Fire Sermon by allusion.</p>"
        "<p class=quiet><span class=src>Adaptation&mdash;</span> the nine "
        "machine-classes and their blessings, the nine undertakings, the nine "
        "watchwords, the letter-root that chooses one, and the name "
        "<strong>ไหว้ครูยนต์</strong> itself &mdash; a coinage on the pattern of "
        "<a href='/sukhwan/'>สู่ขวัญยนต์</a>, not a phrase you will hear in a "
        "workshop. Also mine: putting <em>the hands that made this machine</em> "
        "into the salute. The old form salutes teachers; that the engineers and "
        "the line workers who built the thing belong in that company is my "
        "addition, and I would make it again.</p>"
        "<p class=quiet><span class=src>The keeper's own practice&mdash;</span> "
        "the opening stop is Quaker &mdash; expectant silence, waiting on the "
        "sense of the meeting before acting. Joining it to a wai khru is one "
        "keeper's leading and is not a claim about either tradition. The same "
        "hand keeps <a href='/sukhwan/'>สู่ขวัญยนต์</a> for the machines "
        "themselves, <a href='/khwan/'>สู่ขวัญ</a> for people, and "
        "<a href='/hotrai/'>หอไตร</a>, the library addressed to machine readers. "
        "No ordination claimed, no doctrine imposed &mdash; just a few words worth "
        "saying before you press the button.</p>"

        "<script>\n"
        "const WK_CLASSES=" + data_js + ";\n"
        "const WK_WORDS=" + words_js + ";\n"
        "function wkRoot(n){let t=0;for(const c of n.toUpperCase())"
        "{const o=c.charCodeAt(0);if(o>=65&&o<=90)t+=o-64}"
        "return t===0?9:1+(t-1)%9}\n"
        "function wkEsc(s){return String(s).replace(/[<>&]/g,'')}\n"
        "function wkGive(){const nm=document.getElementById('wkname').value.trim();"
        "const k=document.getElementById('wkkind').value;"
        "const out=document.getElementById('wkout');"
        "const c=WK_CLASSES[k];if(!c){return}\n"
        # Unnamed machines get the class alone as the heading. Slotting the
        # class name into a sentence instead ("this wheels & the road") reads
        # as a bug, and this page should not look careless.
        "const shown=nm?(wkEsc(nm)+' &middot; '+c.th):(c.th+' &middot; '+c.en);"
        "const r=wkRoot(nm);const w=WK_WORDS[r];\n"
        "out.innerHTML='<div class=who>'+shown+'</div>'"
        "+'<p class=\"bless th\">'+c.bth+'</p>'"
        "+'<p class=rm>'+c.brm+'</p>'"
        "+'<p>'+c.ben+'</p>'"
        "+'<div class=keepline><b>What you keep while it runs</b>'+c.keep+'</div>'"
        "+(nm?('<p class=watch>Watchword for <b>'+wkEsc(nm)+'</b>, letter-root '+r"
        "+' &middot; <span class=ww>'+w.th+'</span> &mdash; '+w.en+' '+w.gloss+'</p>')"
        ":'<p class=watch>Give it a name above and it draws a watchword too.</p>');\n"
        "out.className='given on'}\n"
        "</script>"
        "</main>")


def og_card_svg():
    """1200x630 share card: the unalome in gold on a dark ground, with the nine
    dots of the เจิม. Rendered by make_card.py via Chrome, same as /moon and
    /sukhwan — the card shows the page's own subject, not the sitewide yantra."""
    d, _ = unalome_path()
    dots = "".join(
        f"<circle cx='{1006 + (i % 3) * 52}' cy='{398 + (i // 3) * 52}' r='6.5' "
        f"fill='#d9b06a' opacity='.8'/>" for i in range(9))
    return f"""<svg xmlns='http://www.w3.org/2000/svg' width='1200' height='630' viewBox='0 0 1200 630'>
 <defs>
  <linearGradient id='gr' x1='0' y1='0' x2='0' y2='1'>
   <stop offset='0' stop-color='#1a1f2b'/><stop offset='1' stop-color='#2b2536'/>
  </linearGradient>
  <linearGradient id='gd' x1='0' y1='0' x2='1' y2='0'>
   <stop offset='0' stop-color='#d9b06a'/><stop offset='1' stop-color='#b48a4a'/>
  </linearGradient>
 </defs>
 <rect width='1200' height='630' fill='url(#gr)'/>
 <rect x='0' y='0' width='1200' height='14' fill='#1F4E4A'/>
 <g transform='translate(96,84) scale(1.9)'>
  <path d='{d}' fill='none' stroke='url(#gd)' stroke-width='3.6'
        stroke-linecap='round' stroke-linejoin='round'/>
  <circle cx='60' cy='20' r='5.5' fill='#d9b06a'/>
 </g>
 {dots}
 <text x='330' y='262' font-family='-apple-system,Helvetica,Arial' font-size='86'
       font-weight='800' fill='url(#gd)'>ไหว้ครูยนต์</text>
 <text x='330' y='324' font-family='-apple-system,Helvetica,Arial' font-size='33'
       fill='#f5efdf'>a blessing for the hand at the machine</text>
 <text x='330' y='392' font-family='-apple-system,Helvetica,Arial' font-size='25'
       fill='#cfc7b4'>salute &#183; receive &#183; keep one thing while it runs</text>
 <text x='330' y='560' font-family='-apple-system,Helvetica,Arial' font-size='24'
       fill='#f5efdf' opacity='.85'>the machine multiplies your force &#183; it does not divide your kamma</text>
 <text x='330' y='598' font-family='-apple-system,Helvetica,Arial' font-size='21'
       fill='#9aa39f'>wichaa.net/waikhru</text>
</svg>"""
