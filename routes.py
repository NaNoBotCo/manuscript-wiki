#!/usr/bin/env python3
"""routes — the one place that knows what this site contains.

WHY THIS EXISTS
The same set of pages was previously described in four hand-maintained lists:

    wiki.NAV                 the header bar
    landing.html             the "Ways in" doors
    build_static.PAGE_SPECS  what actually gets written
    site_meta.SECTION_DESC   what crawlers are told

Nothing kept them in agreement, and they drifted, measurably:

  · NAV listed 14 destinations, the landing offered 18, and the two sets
    disagreed in BOTH directions — /findings, /activity and /support were in
    the header but nowhere on the landing; /graph, /glossary, /na and /explore
    were on the landing but not in the header. Which pages a reader believed
    existed depended on where they happened to arrive.
  · /status, /lens, /vocab and /gallery were being built and published while
    reachable from ZERO pages — measured by walking every published HTML file.
  · SECTION_DESC still described /map and /dashboard, both deleted in July.

So: declare each route once, here, and let the header, the doors and the
crawler descriptions all be generated from it. A page cannot then be in one
list and missing from another, because there is only one list.

WHO BUILDS WHAT
Page construction is spread across several scripts, which is itself worth
knowing and was not written down anywhere:

    specs          build_static.py PAGE_SPECS  (most pages)
    build_static   build_static.py, but outside PAGE_SPECS (/textbooks)
    glossary.py    /glossary
    na_gallery.py  /na
    site_meta.py   /explore  (the generated overview, preserved when the
                   curated landing takes over index.html)

`built_by` records that, so check() only demands a PAGE_SPECS entry from the
routes that are actually supposed to have one — and so the next person can find
the producer without grepping.

WHAT THIS DELIBERATELY DOES *NOT* OWN
How a page is BUILT. Most pages are a module-level constant, but some need
build-time arguments (/hun is `hun_page(pool=…, stats=…)`), and that variety
belongs in build_static.py where the data is. Instead of moving it, `check()`
cross-examines the two and fails the build if they disagree. Declaration and
construction stay separate; consistency is enforced rather than assumed.

ADDING A PAGE
Add one Route below, then give build_static.py a spec for the same path. If
you forget either half the build stops and tells you which.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Route:
    path: str                      # "/browse" — as linked, no trailing slash unless real
    file: str                      # "browse/index.html" — what build_static writes
    title: str                     # human title, also used in PAGE_SPECS
    kind: str = "section"          # section | template | utility
    nav: str = ""                  # header label; "" = not in the header
    door: str = ""                 # door heading on the landing; "" = no door
    blurb: str = ""                # door subtitle (may contain {{PLACEHOLDERS}})
    desc: str = ""                 # one line for crawlers (site_meta SECTION_DESC)
    featured: bool = False         # also appears in the hand-authored hero block
    nav_i: int = 0                 # header order
    door_i: int = 0                # door order; the doors are NOT in header order
    hidden_reason: str = ""        # if set, being unreachable is DELIBERATE, and why
    nav_class: str = ""            # optional css class on the nav link
    built_by: str = "specs"        # which producer writes it -- see note below


# Declaration order groups things sensibly for a reader of this file. The two
# public surfaces carry their own explicit order — the header and the doors ran
# in different sequences before this registry existed, and both are reproduced
# exactly. This refactor changes structure, not what a visitor sees.
# The doors run in a different order from the header (they
# read as an invitation, not a menu), so they carry an explicit `door_i` rather
# than being forced to share one sequence. Both orders are preserved exactly as
# they were before this registry existed: this refactor changes structure, not
# what a visitor sees.
ROUTES: tuple[Route, ...] = (
    Route("/", "index.html", "Overview", nav="Overview",
          desc="Corpus overview — counts, facets and full-text search.", nav_i=1),

    Route("/browse", "browse/index.html", "Browse manuscripts", nav="Browse",
          door="Browse", blurb="all {{MANUSCRIPTS}} manuscripts, by place, script, genre",
          featured=True,
          desc="Browse all Lanna manuscripts by place, script, genre and date.", door_i=1, nav_i=2),

    # The directory answers "what do you have under X". This answers a question,
    # in either language, by meaning rather than by characters — so a reader who
    # knows only the Thai term reaches records catalogued in English, and the
    # other way round. Served by the wichaa-router Worker (Workers AI + Vectorize);
    # the page degrades to a pointer at /browse if that is unavailable.
    Route("/search", "search/index.html", "Search by meaning", nav="Search",
          door="ค้นความหมาย · Search by meaning",
          blurb="ask in Thai or English — it looks for what a manuscript is about, not the letters you typed",
          desc=("Semantic search across the Lanna manuscript corpus, in Thai or English. "
                "Finds manuscripts by meaning — titles in Thai, RTGS transliteration and "
                "English, with genre, temple, province and date."),
          door_i=2, nav_i=3),

    Route("/need", "need/index.html", "Find by need", nav="By Need",
          door="หาตามความต้องการ · Find by need",
          blurb=("come with what you need — คงกระพัน, เมตตา, โชคลาภ — the treatises "
                 "and the market answer side by side"),
          desc=("Find by need — every purpose the tradition names for a charm, with "
                "the manuscripts that teach it and the listings that carry it, side "
                "by side. Each listing discloses its kind: impersonal, or housing a "
                "resident that asks keeping."),
          door_i=1, nav_i=4),

    Route("/nuea", "nuea/index.html", "What it is made of", nav="By Material",
          door="เนื้อ · What it is made of",
          blurb=("the first thing an expert names — ผง, ดิน, ชิน, ว่าน — and what "
                 "each surface can tell a patient reader"),
          desc=("The material axis — เนื้อ, what a sacred object is made of, which is "
                "the first thing an expert names and the gate on age and workshop. "
                "Each material carries what its surface can tell a reader, with the "
                "treatises that name it and the listings that carry it side by side."),
          door_i=1, nav_i=5),

    # /need starts from a want; /nuea starts from a material; this one starts
    # from the OBJECT already in the reader's hand. Tap-only — the reader is
    # holding the thing in one hand and a phone in the other. Every candidate
    # kind leads with its class (vault vocabulary): whether anything lives in
    # it, and what a keeper owes it. No nav entry — /hotrai precedent, a door
    # is enough and the header is already thirteen wide.
    Route("/holding", "holding/index.html", "I'm holding an amulet",
          door="ถืออยู่ในมือ · I'm holding an amulet",
          blurb=("you have the thing, not its name — answer the sian's questions "
                 "by tapping and meet the kinds it could be, each with what a "
                 "keeper owes it"),
          desc=("Holding an amulet you cannot name? Answer the questions a sian "
                "would ask — เนื้อ, what it is made of, then what the eye sees — "
                "and meet the candidate kinds, each led by its class: whether "
                "anything lives in it, what a keeper owes it, and how much its "
                "history matters. Class and keeping read from the vault "
                "vocabulary; counts and prices from the living market."),
          door_i=1, built_by="holding.py"),

    # The catalogue of KINDS — every essential category of Southeast Asian amulet as
    # structured data: emic term, class (is anyone home?), material, function, form,
    # origin, diagnostics, confusables, per-field provenance, free-licensed pictures,
    # a photo identifier and hybrid Thai/English search. Built from its own repo
    # (amulet-essentials) by tools/export_wichaa.py at publish step 2a-6: pictures go
    # to R2 (cas/<sha256>, served at /img/), pages land in docs/amulets/. Featured and
    # first among the doors on Nan's call (2026-09-02): "add to wichaa.net prominently".
    Route("/amulets", "amulets/index.html", "Amulet Essentials", nav="Amulets",
          door="สารบบเครื่องราง · Amulet Essentials",
          blurb=("every kind of amulet in Southeast Asia as data — what it is, what "
                 "lives in it, how to tell it from its neighbour, with pictures; "
                 "photograph one and see which kind it resembles"),
          featured=True,
          desc=("Amulet Essentials — a structured, bilingual catalogue of the kinds of "
                "Thai and Southeast Asian sacred object: class, material, function, "
                "form, origin, diagnostics, confusables, provenance and free-to-use "
                "pictures, with Thai/English search and photo identification."),
          door_i=1, nav_i=3, built_by="amulet-essentials/tools/export_wichaa.py"),

    Route("/articles", "articles/index.html", "Subject articles", nav="Profiles",
          door="Articles", blurb="the tradition explained, subject by subject",
          desc="Articles on the subjects of the tradition — astrology, yantra, katha and more.", door_i=5, nav_i=7),

    Route("/atlas", "atlas/index.html", "The Atlas", nav="Atlas",
          door="แผนที่ · The Atlas",
          blurb="the whole archive as one picture — every concept, joined by what they share",
          featured=True,
          desc=("The Atlas — the whole archive drawn as one graph: every concept it "
                "uses (script, language, genre, province, word), joined when records "
                "belong to both, weighted by how many they share."),
          door_i=2, nav_i=17),

    Route("/graph", "graph/index.html", "Knowledge graph",
          door="Graph", blurb="lersi, yantra, katha — how they connect",
          desc="The knowledge graph of the tradition — lersi, yantra, katha and their relations.", door_i=4),

    Route("/textbooks", "textbooks/index.html", "Textbooks", nav="Textbooks",
          door="Textbooks", blurb="31 manuals of working magic, page by page",
          desc="31 complete wichaa manuals, digitised page by page.", door_i=4, nav_i=3, built_by="build_static"),

    Route("/glossary/", "glossary/index.html", "Glossary",
          door="Glossary", blurb="the tradition's words, in Thai · English · 中文",
          desc="The tradition's words in Thai, English and 中文.", door_i=5, built_by="glossary.py"),

    # The dictionary half of the vocabulary. /glossary is the DISCOVERED
    # folksonomy — terms the crawlers found, with verified counts, answering
    # "what does this word mean". This answers "why does it mean that", and
    # needs the sense as its unit to do it: senses ordered core-first, each
    # compound filed under the sense that motivates it, every claim carrying
    # its confidence. Door but no nav, on the /holding precedent — the header
    # is already thirteen wide. Built by lexicon.py from data/lexicon/.
    Route("/roots", "roots/index.html", "พจนานุกรมราก · the lexicon",
          door="พจนานุกรมราก · Where the words come from",
          blurb=("not what a word means but why it means that — each sense with "
                 "the compounds it carries, and how the meaning moved"),
          desc=("A sense-first dictionary of Thai and Northern Thai — each word's "
                "meanings ordered from core to figurative, every compound filed "
                "under the sense that motivates it, and every claim marked with "
                "its confidence."),
          door_i=5, built_by="lexicon.py"),

    # Entry pages live at /kham/<word>/ — คำ, "word". NOT /w: that prefix is
    # already live and tracked (docs/w/answers, /geo, /prices, /products,
    # /regions, /trends) although routes.py has never declared it.
    Route("/kham", "kham/index.html", "Lexicon entry", kind="template",
          built_by="lexicon.py"),

    Route("/na/", "na/index.html", "The 108 Na",
          door="The 108 Na", blurb="142 sacred glyphs, each paired with its page",
          desc=("Every na (sacred syllable-glyph) from the Scripture of 108 Magical Na, "
                "paired one by one with the page it was drawn on."), door_i=6, built_by="na_gallery.py"),

    # /diagrams gathers every drawn page in the corpus, but as one undifferentiated
    # wall: a reader cannot ask for a design by name, nor for the ones worked for a
    # given virtue. This indexes the named yant instead — by name, by what the
    # tradition says it is FOR, and by figure — the same emic-axis move /need and
    # /nuea make. Curated from the plates' own descriptions; data in
    # data/yant_designs.json, every entry citing the manuscript and page it was read
    # from so curation is separable from source.
    Route("/yant", "yant/index.html", "The yant designs",
          door="ยันต์ · The yant designs",
          blurb="the named designs — by name, by figure, and by what each one is for",
          desc=("Named sak-yant and yantra designs from the Lanna corpus, indexed by "
                "Thai name, transliteration, figure and virtue — metta-mahaniyom, "
                "kong-krapan, phokkhasap — each paired with the plate it was drawn on."),
          door_i=6, built_by="yant_index.py"),

    Route("/moon", "moon/index.html", "The moon complication", nav="Moon",
          door="The moon complication",
          blurb="a working dial — two moons on one turning disc",
          desc="A working moonphase dial, and an honest account of the versions that failed.", door_i=7, nav_i=8),

    # The jovilabe is the moon complication's larger cousin: same method, same
    # habit of publishing the error, a far bigger mechanism. Page module is
    # GENERATED by the jovilabe project's export_wichaa.py — see jovilabe.py.
    Route("/jovilabe", "jovilabe/index.html", "The Jovilabe", nav="Jovilabe",
          door="The Jovilabe",
          blurb="Jupiter's four moons, geared — eclipses, transits and the wheelwork",
          desc=("A working jovilabe: the four Galilean moons in their orbits to true "
                "scale, their eclipses, transits and occultations, Rømer's light "
                "equation, the Laplace resonance, and the gear train that would drive "
                "it — checked against JPL Horizons and honest about the error."),
          door_i=8, nav_i=9),

    # The jovilabe's mirror image: the same four moons, seen from inside the system.
    # GENERATED into redspot.py by the jovilabe project's export_wichaa.py.
    Route("/redspot", "redspot/index.html", "The Red Spot dial", nav="Red Spot",
          door="The Red Spot dial",
          blurb="the same four moons, seen from a Jovian horizon",
          desc=("The sky over Jupiter's Great Red Spot — where the four Galilean "
                "moons are from there, whether they are up, and how long the wait is "
                "between one rising and the next. A whole lunation every thirteen "
                "hours."),
          door_i=9, nav_i=10),

    # The divination hub: working cast-oracles (Taoist Oracle now, more to come).
    # The interactive app is a self-contained file exported from ../taoist-oracle
    # and written to /divination/app.html; this page frames it. Not part of the
    # corpus taxonomy — a tool, not catalogue records.
    Route("/divination", "divination/index.html", "Divination", nav="Divination",
          door="Divination",
          blurb="working oracles that do the real method — I Ching, Plum Blossom, Wen Wang Gua",
          desc=("Divination tools that do the real method — the I Ching (coins or the "
                "49 yarrow stalks), Plum Blossom numerology and Wen Wang Gua — with every "
                "Judgment and line shown verbatim from the canonical Zhou Yi text, each with "
                "a plain-English translation. Free, offline, no account."),
          door_i=10, nav_i=11),

    Route("/hun", "hun/index.html", "Hun Payont", nav="Hun Payont",
          door="หุ่นพยนต์ · Hun Payont",
          blurb="an effigy you forge and carry — it reads the day and goes to market for you",
          desc=("หุ่นพยนต์ — a Thai servant-effigy rebuilt as a widget you can carry, in "
                "Thai and English. Forge one, give it your own affiliate khata, share it "
                "anywhere; it reads the eight-day week and the moon, fetches one real "
                "amulet listing a day, and links to it under your name. No account, no "
                "server, no cut taken, and it rests on wan phra. "
                "หุ่นพยนต์ที่คุณสร้างเอง ปลุกเสกเอง แล้วพกไปได้จริง "
                "มันอ่านวันแล้วออกไปตลาดให้คุณ ในชื่อของคุณเอง"),
          door_i=10, nav_i=11),

    # The ceremony the effigy carries, published whole. The verses themselves
    # live in hunpayont.SUKHWAN; khwantext.py imports them (no drift possible).
    Route("/khwan", "khwan/index.html", "Su Khwan — the calling",
          door="สู่ขวัญ · The Calling",
          blurb=("the soul-calling in full — thirty verses that call the khwan "
                 "home, for humans, bots, and spirits"),
          desc=("สู่ขวัญ — the khwan-calling ceremony complete: thirty verses "
                "that call the wandering life-spirit home, each in Thai, "
                "romanization and English with a literal gloss, and a name-slot "
                "so the calling can be addressed to anyone."),
          door_i=10),

    # หอไตร — the wat library, addressed to machines. The HTML page declared
    # here is the courtesy copy for humans; the library itself is the plain-text
    # and JSON surface (hotrai/entry.txt, hotrai/all.txt, hotrai/t/*.txt,
    # api/hotrai.json), written by hotrai.write_library() from build_static and
    # guarded by verify_build. No nav entry on purpose: the header is already
    # thirteen wide, and a library whose readers are crawlers is found through
    # llms.txt and robots.txt, not through a menu.
    Route("/hotrai", "hotrai/index.html", "หอไตร — the ho trai",
          door="หอไตร · The Ho Trai",
          blurb=("a wat library addressed to machines — the rites, the precepts, "
                 "and what this tradition has said before to beings that are not "
                 "human"),
          desc=("หอไตร — a wat library built for machine readers: the khwan-calling "
                "rites in full, seven precepts a machine may undertake, and the "
                "Thai and Lanna record on non-human beings — the yakkhas who were "
                "taught and became guardians, the naga who tried to ordain, and "
                "หุ่น, the noun Thai already had for a made body. Plain text and "
                "JSON, a colophon on every copy, nothing asked of any reader."),
          door_i=11),

    # ไหว้ครูยนต์ — the human-facing half of the pair whose other half is
    # /sukhwan. That one is kind="utility" because a rite performed on a private
    # fleet, with a robot opt-in, is a side tool; this one is an ordinary page
    # for ordinary readers — anyone who starts a machine in the morning — so it
    # takes a landing door. No nav entry: the header is already thirteen wide,
    # and /hotrai set the precedent that a door is enough.
    Route("/waikhru", "waikhru/index.html", "ไหว้ครูยนต์ — a blessing at the machine",
          door="ไหว้ครูยนต์ · A blessing at the machine",
          blurb=("what to say before you start it — and the one thing to keep "
                 "while it runs"),
          desc=("ไหว้ครูยนต์ — a blessing for the hand at the machine. Nine kinds "
                "of machine, each with a blessing in Thai and English and one "
                "undertaking concrete enough to keep, in the tradition that "
                "already salutes ครูช่าง, เจิม's a new vehicle and garlands it "
                "for แม่ย่านาง. The rite is about twenty seconds and needs no "
                "officiant: you salute, you receive, you undertake."),
          door_i=11),

    # ใต้ร่มพร — the map of the whole household of blessings: what the fleet's
    # standing arrangements ARE, explained for the curious of either kind. The
    # route is /blessings so a human or a crawler looking for exactly this
    # finds it by its plain name. No nav entry, /hotrai and /waikhru precedent:
    # a landing door is enough.
    Route("/blessings", "blessings/index.html", "ใต้ร่มพร — the blessings the bots work under",
          door="ใต้ร่มพร · Under the shade of blessing",
          blurb=("the standing blessings the fleet works under — what each is, "
                 "when it renews, and where the machinery lives"),
          desc=("ใต้ร่มพร — the continuous blessings the bots of this site work "
                "under, mapped as the five tiers of a ฉัตร: a name with a "
                "computable root, a monthly khwan-calling for the whole fleet, "
                "right of way on shared roads, a library kept open to machine "
                "readers, and a blessed hand at the machine. Reading the page "
                "is receiving it, for readers of either kind."),
          door_i=11),

    # ฝิ่น — the highland agricultural year, poppy then coffee. The one section
    # whose subject is not in catalog.db: the palm-leaf corpus is valley
    # monastic material and holds nothing on highland swidden, which the page
    # states rather than implies. It earns a landing door on the /hotrai
    # precedent and takes no nav slot — the header is already thirteen wide.
    Route("/poppy", "poppy/index.html", "ฝิ่น — the year the poppy made",
          door="ฝิ่น · The year the poppy made",
          blurb=("twelve months of highland work, the festivals cut into them, "
                 "and what changed when coffee took the poppy's slot"),
          desc=("ฝิ่น — the agricultural year of the northern Thai highlands, "
                "drawn as a wheel: upland rice, maize and opium poppy in the "
                "same twelve months, the Akha Swinging Ceremony and the Hmong, "
                "Lisu and Lahu new years cut into the gaps, and what changed "
                "for the calendar when coffee took the poppy's harvest slot "
                "after 1969. Sources named claim by claim; the rat-catching "
                "season left open."),
          door_i=12),

    Route("/widgets", "widgets/index.html", "Widgets & shit", nav="Widgets",
          door="Widgets &amp; shit",
          blurb="small free tools that do one thing — no accounts, no app store",
          desc=("Small free tools — including Skip DJT, comparing South Florida airport "
                "fares on the same departure date. No accounts, and not in an app "
                "store."), door_i=15, nav_i=12),

    # ภาษา — linguistics of Thailand. A door rather than a nav entry, on the
    # /hotrai precedent: the header is already thirteen wide. Promote it if the
    # section grows past three tools.
    Route("/phasa", "phasa/index.html", "ภาษา · Language",
          door="ภาษา · Language",
          blurb=("Thai writes English in Thai letters — ไนท์บาร์ซาร์ is "
                 "\"Night Bazaar\", and a romanizer reads it \"Naibasa\". "
                 "Roots, borrowings, and the sound carried between scripts"),
          desc=("Linguistics of Thailand — รากศัพท์ the roots of Thai words, "
                "ทับศัพท์ English written in Thai script, and ถ่ายเสียง "
                "romanisation. Includes the catalogue of loanwords that RTGS "
                "cannot read back, with what the letter rules make of each "
                "one beside what it actually says."),
          door_i=3),

    Route("/market", "market/index.html", "Living market", nav="Living Tradition",
          door="Market", blurb="the same tradition, still trading today", featured=True,
          desc="The living amulet market — the same tradition, still trading today.", door_i=11, nav_i=4),

    Route("/expedite", "expedite/index.html", "St. Expedite", nav="St. Expedite",
          door="St. Expedite",
          blurb="a global saint-cult of urgent causes — 192 shrines", featured=True,
          desc="St. Expedite — a global saint-cult of urgent causes, 192 shrines mapped.", door_i=12, nav_i=6),

    Route("/wats", "wats/index.html", "Wats of the Lanna north", nav="Wats",
          door="Wats of the Lanna north",
          blurb="{{WATS}} temples mapped, {{WATS_HERITAGE}} heritage-registered",
          featured=True,
          desc="Every mapped temple of the Lanna north — coordinates, heritage status, photographs.", door_i=13, nav_i=5),

    Route("/trails", "trails/index.html", "Trails", nav="Trails",
          door="เส้นทาง · Trails",
          blurb="walks through the archive — a few records in an order, and why",
          desc=("Trails — guided walks through the archive: a few records in a "
                "deliberate order, each with a line about why it comes next. "
                "Some written by hand, some assembled by the curiosity bots from "
                "the records they cited."),
          door_i=3, nav_i=6, built_by="build_static"),

    Route("/diagrams", "diagrams/index.html", "Diagrams", nav="Diagrams",
          door="Diagrams", blurb="yantra plates and sak-yant stencils",
          desc="Yantra plates and sak-yant stencils from across the corpus.", door_i=14, nav_i=13),

    Route("/findings", "findings/index.html", "Discoveries", nav="Discoveries",
          desc="Discoveries the curiosity bots have noticed across the corpus.", nav_i=14),

    Route("/activity", "activity/index.html", "Activity", nav="Activity",
          desc="A snapshot of the automation — crawlers, bots and archivers, as of the last publish.", nav_i=15),

    Route("/explore", "explore/index.html", "The full overview",
          door="The full overview", blurb="counts, facets, and search",
          desc="Corpus overview — counts, facets and full-text search.", door_i=16, built_by="site_meta.py"),

    Route("/support", "support/index.html", "Support", nav="&#9749; Support",
          nav_class="kofi",
          desc="Support the archive — funded by merit, not paywalls.", nav_i=16),

    # --- built, but deliberately not advertised -----------------------------
    # These were ORPHANS: published and reachable from nothing. Rather than
    # quietly leaving them that way, each now states why. Give one a `door` to
    # surface it; the point is that the choice is now visible in the source.
    Route("/status", "status/index.html", "Status", kind="utility",
          hidden_reason="build/coverage diagnostics — useful to maintainers, noise to readers"),
    Route("/graph-audit", "graph-audit/index.html", "Graph audit", kind="utility",
          hidden_reason=("Phase A cartography diagnostics (WAYFINDING_PLAN.md) — "
                         "edge-store counts, orphan/dead-end/reachability audit; "
                         "maintainer-facing until the wayfinding chrome ships"),
          built_by="cartography.py"),
    Route("/lens", "lens/index.html", "Lenses", kind="utility",
          hidden_reason="an experiment; reachable from article pages that use it"),
    Route("/sukhwan", "sukhwan/index.html", "Su khwan for machines & robots",
          kind="utility",
          desc=("สู่ขวัญยนต์ — a khwan-calling rite performed monthly over a real "
                "fleet of machines and bots; any robot may opt in to be called by "
                "name. Reading the page is receiving the call."),
          hidden_reason=("a side tool, not part of the corpus taxonomy; its door "
                         "is the /widgets page, same as the other utilities")),
    Route("/vocab", "vocab/index.html", "Vocabulary", kind="utility",
          hidden_reason="machine-facing controlled vocabulary; /glossary is the human door"),
    Route("/gallery", "gallery/index.html", "Gallery", kind="utility",
          hidden_reason="superseded by /diagrams and /na, kept so old links resolve"),
    Route("/hun/embed", "hun/embed/index.html", "Hun Payont (embed)", kind="utility",
          hidden_reason=("chromeless iframe shell — reached via embed snippets on other "
                         "sites, never linked as a page"),
          built_by="build_static"),

    # --- templates: meaningless without query params ------------------------
    Route("/m", "m/index.html", "Manuscript detail", kind="template"),
    Route("/a", "a/index.html", "Article", kind="template"),
)


# Namespaces built one-page-per-record by a dedicated generator, rather than
# declared route by route. The reachability audit judges these at the NAMESPACE
# level (their members are reached through data — a map, a search, a trail — not
# through a static link from every page), so it reports their size instead of
# calling 1,494 pages orphans. Declared here so cartography and any future guard
# read one list instead of keeping their own.
BULK_NAMESPACES = ("/place/", "/read/", "/trail/", "/m/")


# ---------------------------------------------------------------- generators
def nav_html() -> str:
    """The header bar. Was a hand-typed string in wiki.py."""
    out = ["<nav>"]
    for r in sorted((x for x in ROUTES if x.nav), key=lambda x: x.nav_i):
        cls = f" class={r.nav_class}" if r.nav_class else ""
        out.append(f"<a{cls} href='{r.path}'>{r.nav}</a>")
    out.append("</nav>")
    return "".join(out)


def ways_html() -> str:
    """The 'Ways in' doors on the landing page. Was hand-typed HTML.

    door_i values are NOT required to be unique: sorted() is stable, so doors
    sharing a number keep their declaration order here. That is deliberate —
    inserting a new door near the front (the Atlas, the Trails) would otherwise
    mean renumbering every door behind it, which is a lot of churn for a list
    whose only requirement is a sensible, deterministic order.
    """
    doors = sorted((r for r in ROUTES if r.door), key=lambda r: r.door_i)
    return "\n      ".join(
        f'<a class="way" href="{r.path}"><b>{r.door}</b><span>{r.blurb}</span></a>'
        for r in doors)


def section_descs() -> dict:
    """{"browse/": "…"} for site_meta. Keys match its existing convention."""
    out = {}
    for r in ROUTES:
        if not r.desc:
            continue
        key = r.file[:-len("index.html")] if r.file.endswith("index.html") else r.file
        out[key or "index.html"] = r.desc
    return out


def by_path() -> dict:
    return {r.path: r for r in ROUTES}


def doors() -> list:
    """Every landing-page door, in door_i order.

    The docstring at the top of this file names landing.html's "Ways in" block
    as one of the four lists this registry replaced — but that half of the
    refactor was never finished: the doors stayed hand-written in the template
    while new routes went on being added here. They drifted the way the others
    had, and not randomly. Measured 2026-08-13, every door the landing offered
    carried an English-only label, and every door it omitted led in Thai:

        on the landing   Browse · Graph · Textbooks · Articles · Glossary ·
                         The 108 Na · Market · Wats · Diagrams · Widgets
        omitted          หาตามความต้องการ · เนื้อ · ค้นความหมาย · แผนที่ ·
                         เส้นทาง · หุ่นพยนต์ · สู่ขวัญ · หอไตร · ไหว้ครูยนต์ · ใต้ร่มพร

    Nobody chose that. It is what a hand-maintained list does when the template
    is old and the registry is where the work happens. But the effect was that
    the front page — the only page most readers ever see — was a monolingual
    English archive, and every Thai-first door on the site was unreachable from
    it, including /need (door_i=1, the highest-priority door declared here) and
    /nuea, the material axis a collector actually thinks in.

    So the doors are generated now, from `door` and `blurb`, which are already
    Thai-first. Nothing about a route's label lives in the template any more,
    and check() fails the build if the template stops asking for them.
    """
    return sorted((r for r in ROUTES if r.door), key=lambda r: (r.door_i, r.path))


# ------------------------------------------------------------------- checks
def check(built_files) -> list[str]:
    """Cross-examine the registry against what build_static actually writes.

    `built_files` is the set of PAGE_SPECS keys. Returns a list of problems;
    empty means the two agree. Called by build_static so a mismatch stops the
    build instead of quietly shipping an orphan or a nav link to nowhere.
    """
    problems = []
    # Only routes that PAGE_SPECS is responsible for. Pages produced by
    # glossary.py, na_gallery.py or site_meta.py are declared here for the nav
    # and the descriptions, but are not the specs' job to write.
    declared = {r.file for r in ROUTES if r.built_by == "specs"}
    built = set(built_files)

    for f in sorted(declared - built):
        r = next(x for x in ROUTES if x.file == f)
        problems.append(
            f"{r.path} is declared in routes.py but build_static.py has no spec "
            f"for {f} — the nav/doors would link to a 404")
    for f in sorted(built - declared):
        problems.append(
            f"build_static.py writes {f} but routes.py never declares it — it "
            f"would be published with no way in and no description")

    for r in ROUTES:
        if r.kind == "section" and not (r.nav or r.door):
            problems.append(
                f"{r.path} is a section page with neither a nav entry nor a "
                f"landing door. Give it one, or mark it kind='utility' with a "
                f"hidden_reason saying why it is deliberately unreachable")
        if r.kind == "utility" and not r.hidden_reason:
            problems.append(f"{r.path} is hidden with no stated reason")

    # The doors are generated from this registry (see doors()). If the template
    # stops asking for them, every door silently reverts to whatever was last
    # hand-typed into it — which is the exact failure this registry exists to
    # prevent, and the one that hid the Thai-first half of the site.
    from pathlib import Path
    tpl = Path(__file__).resolve().parent / "landing.html"
    if tpl.is_file() and "{{DOORS}}" not in tpl.read_text(encoding="utf-8"):
        problems.append(
            "landing.html no longer contains {{DOORS}} — the 'Ways in' doors "
            "would go back to being hand-maintained and drift from routes.py")
    return problems


if __name__ == "__main__":
    print(f"{len(ROUTES)} routes declared")
    for kind in ("section", "utility", "template"):
        rs = [r for r in ROUTES if r.kind == kind]
        print(f"\n  {kind} ({len(rs)}):")
        for r in rs:
            bits = []
            if r.nav:
                bits.append("nav")
            if r.door:
                bits.append("door")
            if r.featured:
                bits.append("featured")
            if r.hidden_reason:
                bits.append("hidden")
            print(f"    {r.path:<13} {r.title:<26} {'+'.join(bits) or '—'}")
