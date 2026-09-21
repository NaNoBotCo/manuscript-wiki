# พจนานุกรมราก · the lexicon schema

## Why this is not the ThaiRoots schema

ThaiRoots (257 heads, 974 words) borrowed Hans Wehr's **filing system** — group
words under a shared root — but not his **content model**. Four consequences,
all measured in the v1.0.0 data:

* **No slot for a sense.** Derivative fields were `t r s g gth n c conf src reg
  posT ipa k f`. Nothing said *which meaning* a word belonged to, so `ตาข่าย`
  (net-mesh) and `ตาบอด` (blind) sat in one undifferentiated list under `ตา`.
  The family forks and the model could not show it.
* **Senses became punctuation.** 77 of 257 heads packed several meanings into
  one gloss string: `ตา` = `"eye; maternal grandfather"`, `√pā` = `"protect;
  drink"`. Wehr numbers those. Here they were a semicolon.
* **`ext` grouped by syllable, not morpheme.** Only 34.7% of `ext` entries even
  contained their root verbatim; under `ตา` sat `ตาย` (die), `เตา` (stove),
  `ตุ๊กตา` (doll), `ชะตา` (fate < Skt *jāta*). None contain the morpheme "eye".
  Grouping by shared sound is the exact failure the root-dictionary format
  exists to prevent.
* **`แก้ว` was not in it at all** — no head, no derivative. The selection
  criterion was "is it a root?", and `แก้ว` is not a root; it is a word with a
  large family. The most rewarding entry in Thai was filtered out by the spine.

The sense structure was never missing, only flattened: 43% of the Thai glosses
(524 of 1231) still carry the source's semicolon-delimited senses. `ตา` reads
`ส่วนหนึ่งของร่างกาย…ดวงตา ; ช่องที่เกิดจากเส้นหรือตอกขัดกัน เช่น ตาข่าย ตาตาราง ; พ่อของแม่, ผัวของยาย`
— three clean senses, sense 2 naming its own derivatives, concatenated on
import. Remodelling recovers material already held.

## The five rules

1. **The sense is the unit.** A word has senses; a sense carries its compounds;
   senses point at the senses they grew out of. `EXTENDS` with a `via` —
   metaphor, metonymy, specialisation — is the edge a reader navigates by, and
   the one that turns a list into a map.
2. **The word, not the root, is the head.** Thai has no root-and-pattern
   morphology. Indic roots are real for one stratum and a fiction for the rest;
   they become an *attribute* (`etymology`), never the spine.
3. **Every content field carries provenance and confidence.** `conf` is one of
   `verified · standard · probable · traditional · disputed · unverified`, and
   `src` names who says so. `needs_check` is a first-class field: a claim the
   entry makes but has not earned yet is written down as such, not quietly
   asserted.
4. **Asserted edges are marked apart from counted edges.** The atlas graph
   states that "nothing is modelled, inferred or scored; every line is a count
   you could go and verify." A lexicon edge is the opposite kind of thing — a
   claim about meaning. So every lexicon edge carries `kind: "asserted"` plus
   its own `conf`/`src`, and the projection into the atlas exports **only**
   structural edges. The two graphs stay honest about what they are.
5. **IDs are allocated once and frozen.** `registry.json` records every id ever
   issued. A slug collision appends `-2`, `-3` in issue order and never
   renumbers, so a link to a sense keeps meaning that sense.

## Node types

| id prefix | type | what it is |
|---|---|---|
| `w:` | word | a headword, compound, phrase or name |
| `w:…#n` | sense | one numbered meaning of a word |
| `e:` | etymon | a source form (`e:pali:ratana`, `e:pt:*kɛːwᶜ`) |
| `r:` | root | an Indic root, kept as an attribute-node (`r:√grah`) |
| `d:` | domain | semantic field (`d:religion`, `d:kinship`) |
| `reg:` | register | `reg:day`, `reg:elevated`, `reg:religious`, `reg:poetic`, `reg:slang`, `reg:archaic`, `reg:offensive` |
| `lang:` | language | for loans and cognates (`lang:nod` Northern Thai) |
| `k:` | soundkey | a ThaiRoots sound-change card (`k:K9`) |
| `src:` | source | provenance node (`src:rid`, `src:wikt`, `src:cur`) |

## Edge types

**Structural** (no confidence needed; these project to the atlas):
`HAS_SENSE` · `COMPOUND_OF` (ordered constituents) · `IN_DOMAIN` ·
`HAS_REGISTER` · `FROM_ETYMON` · `SOUND_KEY`

**Asserted** (each carries `conf`, `src`, optional `note`):
`EXTENDS` (sense→sense, `via`: metaphor | metonymy | specialisation |
generalisation | euphemism | calque) · `HEADS` (sense→compound it motivates) ·
`CALQUES` (native word ↔ the Indic term it renders — the edge that finally
joins the native and indic strata) · `COGNATE_WITH` · `CLASSIFIED_BY` ·
`NEAR_SYNONYM` (carries `distinction`) · `ANTONYM` · `HYPERNYM` ·
`CONFUSABLE_WITH` (carries `why`: homophone | near-key | tone-only | sense) ·
`COLLOCATES` · `ATTESTED_IN` (word/sense → a manuscript or article in the
corpus)

`ATTESTED_IN` is why this belongs in wichaa rather than as a standalone app: a
lexicon entry can point at the manuscripts that actually use the word, and the
count is read from `catalog.db`, not asserted.

## Where it sits

`/glossary` is the discovered folksonomy — the words the crawlers found on
manuscripts and listings, with verified counts. `/roots` is the etymological
and semantic dictionary: fewer words, far deeper, and the place a reader goes
to ask *why does this word mean that*. A term may appear in both; the lexicon
links to the glossary entry rather than restating it.

## The shared vocabulary — every surface of meaning, one network

The linguistics content arrived in pieces and each grew its own shape: this
lexicon, a ทับศัพท์ catalogue of borrowings, a romanizer, a 65-term glossary of
wichaa vocabulary, twelve sound-change cards. `phasa_graph.py` emits all of them
into one node and edge vocabulary and joins them. `/phasa` already named the
organising idea, and it is Thai's own — **รากศัพท์** where a word came from,
**ทับศัพท์** a word laid over from another language, **ถ่ายเสียง** the sound
carried across scripts.

| prefix | class | source | answers |
|---|---|---|---|
| `w:` | word · compound | lexicon | รากศัพท์ |
| `w:…#n` | sense | lexicon | รากศัพท์ |
| `l:` | loanword | thapsap | ทับศัพท์ |
| `read:` | reading | thapsap | ถ่ายเสียง |
| `t:` | term | glossary | the tradition's own vocabulary |
| `k:` | soundkey | thairoots | ถ่ายเสียง |
| `e:` `src:` | etymon | either | รากศัพท์ |
| `d:` `reg:` | domain · register | any | facets |

**The join is the product.** `SAME_AS` fires on an exact Thai string in two
sources; `CONTAINS_HEAD` fires when a term on any surface is built round a head
this lexicon holds, so พระเครื่อง in the glossary is a door to เครื่อง and to
พระ. Exact matching alone joined 9 things. The morphological join makes 6,091,
and that is the difference between five lists side by side and one network.

**A borrowed word is never cut with Thai morphology.** The remainder test that
built the compound set passes on nonsense the moment the input is a loan: ราหู
is Sanskrit *rāhu* and split as หู "ear"; เมตตา is Pali *mettā* and split as ตา
"eye"; เพลส is the English "Place". This is the ตาย-under-ตา failure the whole
schema was built to avoid, resurfacing one layer up. A word whose etymology names
Pali, Sanskrit, Khmer, Chinese, Malay, Portuguese or English is refused — 1,095 of
them — and the longest head wins over the first found, so น้ำมันมนต์ is น้ำมัน +
มนต์ rather than มัน + น้ำมนต์.

**Every surface a portal.** `api/phasa/resolve.json` maps a Thai string to the
nodes describing it — 7,591 of them. Any page holding Thai text (a manuscript
title, a market listing, a place name, an article) can look a term up and make it
a door, without knowing which subsystem owns it.
