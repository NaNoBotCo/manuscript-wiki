#!/usr/bin/env python3
"""glossary — a multilingual glossary of the discovered wichaa terms.

The crawlers surface a folksonomy: the words the tradition actually uses, tagged on
manuscripts and on market listings. This turns the meaningful ones into a real
glossary — each term in Thai, romanised, and glossed in English and 中文 (Chinese),
with the *verified* count of how many manuscripts and how many listings carry it.

Multilingual by design (Singapore is a core audience): every entry is a dict of
language → gloss, so Malay (ms) and Tamil (ta) slot in later without a rewrite; the
page shows whatever languages are present. The glosses are editorial — careful, but
refinements from readers who know the tradition better are welcome. The counts are
not editorial: they are read straight from the catalogue.

    python3 glossary.py --docs ../nanobotco-lanna/docs --site-url https://wichaa.net
Writes  docs/api/glossary.json  +  docs/glossary/index.html .
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
_db = HERE.parent / "manuscript-crawler" / "crawler" / "catalog.db"

# term (Thai) → {roman, domain, glosses:{lang:text}}. English is authoritative;
# Chinese is a careful editorial gloss. Domains group the glossary into desire paths.
GLOSS = {
 "ยันต์": {"roman":"yan · yantra","domain":"yantra","en":"A sacred diagram of letters, syllables and lines — drawn, inscribed or tattooed to protect, empower, or attract. The north's core visual magic.","zh":"符 · 護身法陣 — 由聖字、音節與線條構成的幾何圖，用以護身、加持或招引。"},
 "ผ้ายันต์": {"roman":"pha yant","domain":"yantra","en":"A yantra inked onto cloth — a protective banner or wearing-cloth carrying the diagram.","zh":"符布 — 繪有法陣的護身布或旗。"},
 "คาถา": {"roman":"katha","domain":"katha","en":"A Pali incantation — verses of power, recited to activate a charm, ward danger, or draw fortune.","zh":"咒語 — 巴利語的靈驗偈頌，誦唸以啟動法物、驅邪或招福。"},
 "นะ": {"roman":"na","domain":"katha","en":"The sacred syllable นะ — a seed-letter at the heart of countless katha and yantra; the tradition counts 108 of its forms.","zh":"「那」聖音字 — 眾多咒與符的種子字，傳有一百零八變化。"},
 "ตะกรุด": {"roman":"takrut","domain":"amulet","en":"A spell inscribed on a thin metal scroll, rolled tight and empowered — worn for protection, invulnerability, or love.","zh":"符管 — 刻於薄金屬並捲緊加持的經文護符，用於護身、刀槍不入或招情。"},
 "เครื่องราง": {"roman":"khrueang rang","domain":"amulet","en":"Talisman or charm, in the broad sense — any empowered object worn or carried for its power.","zh":"護身符（廣義）— 一切經加持、隨身佩帶以求靈力的物件。"},
 "พระเครื่อง": {"roman":"phra khrueang","domain":"amulet","en":"A Buddhist amulet, usually a small moulded image of a Buddha or revered monk.","zh":"佛牌 — 多為佛陀或高僧的小型模製聖像護符。"},
 "วัตถุมงคล": {"roman":"watthu mongkhon","domain":"amulet","en":"Auspicious sacred objects — the umbrella category for amulets, charms and consecrated items.","zh":"聖物 · 吉祥物 — 佛牌、護符與開光物件的總稱。"},
 "พระสมเด็จ": {"roman":"phra somdet","domain":"amulet","en":"The Somdej amulet — among the most revered Thai amulet types, the 'king of amulets.'","zh":"崇迪佛牌 — 最受尊崇的泰國佛牌之一，有『佛牌之王』之稱。"},
 "จตุคาม": {"roman":"jatukham","domain":"amulet","en":"Jatukham Ramathep — a guardian-deity amulet cult that swept Thailand in the 2000s.","zh":"加都堪拉瑪贴 — 二〇〇〇年代風靡泰國的護法神護符。"},
 "เมตตา": {"roman":"metta","domain":"attraction","en":"Loving-kindness — as a magical quality, the power to draw goodwill and warmth from all who meet you.","zh":"慈心 — 作為法門的特質，能招來眾人的善意與愛戴。"},
 "เมตตามหานิยม": {"roman":"metta mahaniyom","domain":"attraction","en":"Loving-kindness + 'great popularity' — charm that makes one widely liked and favoured.","zh":"慈心廣受愛戴 — 使人緣廣結、備受喜愛的法門。"},
 "เสน่ห์": {"roman":"saneh","domain":"attraction","en":"Love-drawing allure — charms and rites to kindle desire and attraction.","zh":"魅惑 · 招情 — 引動愛慕與情緣的法術。"},
 "สีผึ้งเสน่ห์": {"roman":"si phueng saneh","domain":"attraction","en":"Enchanted lip-wax — a balm consecrated to lend the wearer allure.","zh":"招情蜂蠟 — 開光的唇蠟，增添佩者魅力。"},
 "คงกระพัน": {"roman":"kongkraphan","domain":"power","en":"Invulnerability — the classic martial protection, skin that blades cannot cut.","zh":"刀槍不入 — 經典的護體法門，刀刃不能傷。"},
 "ฤๅษี": {"roman":"lersi · ruesi","domain":"teachers","en":"The ascetic hermit-seers — the teacher-figures at the root of the tradition, patrons of yantra, katha and healing.","zh":"修行隱士 · 仙人 — 傳統根源的祖師，符、咒與醫術的守護者。"},
 "หลวงปู่ทวด": {"roman":"luang pu thuat","domain":"teachers","en":"A revered southern monk (16th–17th c.), whose amulets are believed to protect from harm and misfortune.","zh":"龍菩托祖師 — 受尊崇的南方高僧，其佛牌被信能護身避險。"},
 "ราหู": {"roman":"rahu","domain":"astrology","en":"The eclipse-deity — the shadow-planet that swallows sun and moon; propitiated to turn misfortune to fortune.","zh":"羅睺 — 食日月的影曜之神，供奉以轉厄為福。"},
 "โหราศาสตร์": {"roman":"horasat · hora","domain":"astrology","en":"Astrology — the reckoning of time, star and fate; the diviner's science of auspicious days and birth-charts.","zh":"占星術 — 推算時辰、星曜與命運，擇吉日、排命盤之學。"},
 "ยา": {"roman":"ya","domain":"medicine","en":"Medicine — herbal remedy and the medical manuals; healing sits inside wichaa, not apart from it.","zh":"藥 · 草藥 — 醫方與醫書；療癒本屬 wichaa 之內，不與其分。"},
 "กุมารทอง": {"roman":"kuman thong","domain":"spirits","en":"The 'golden boy' — a child-spirit effigy kept and fed for luck, wealth and protection.","zh":"金童 — 供養以求財、護佑的靈童造像。"},
 "นางกวัก": {"roman":"nang kwak","domain":"spirits","en":"The beckoning lady — her raised hand calls in customers and wealth; the merchant's charm.","zh":"招財女神 — 舉手招客招財，商家的守護。"},
 "ไอ้ไข่": {"roman":"ai khai","domain":"spirits","en":"Ai Khai — the boy-spirit of Wat Chedi, famed for granting luck and answered wishes.","zh":"艾蓋童子 — 柴迪寺的靈童，以賜運、有求必應聞名。"},
 "ท้าวเวสสุวรรณ": {"roman":"thao wessuwan","domain":"deities","en":"Vaishravana — guardian king of the north, giant lord of yakṣas, who wards off ghosts and evil.","zh":"多聞天王（毗沙門）— 北方護法天王，夜叉之主，驅鬼辟邪。"},
 "ปลัดขิก": {"roman":"palad khik","domain":"material","en":"A phallic amulet — carved for protection, virility and warding of harm.","zh":"陽形護符 — 雕製以護身、旺陽、避害。"},
 "เขี้ยวเสือ": {"roman":"khiao suea","domain":"material","en":"Tiger fang — worn for authority, command over others and protection.","zh":"虎牙 — 佩以增威權、懾眾、護身。"},
 "พญาเต่าเรือน": {"roman":"phaya tao ruean","domain":"material","en":"The turtle amulet — for longevity and steady, sheltering wealth.","zh":"龜將軍 — 象徵長壽與穩固招財。"},
 "เบี้ยแก้": {"roman":"bia kae","domain":"material","en":"A cowrie-shell remedy charm — the classic guard against black magic and curse.","zh":"解厄寶螺 — 對治邪術與詛咒的傳統寶貝護符。"},
 "มีดหมอ": {"roman":"mit mo","domain":"ritual","en":"The ritual master's knife — for exorcism, cutting malign influence, and consecrating charms.","zh":"法師刀 — 用於驅邪、斬煞與開光法物。"},
 "น้ำมันมนต์": {"roman":"nam man mon","domain":"ritual","en":"Enchanted oil — consecrated for love, luck or persuasion, anointed on skin or object.","zh":"法油 · 咒油 — 為招情、招運或說服而開光，塗於身或物。"},
 "ผงพุทธคุณ": {"roman":"phong phutthakhun","domain":"ritual","en":"Sacred powder of Buddha-virtue — ground from consecrated materials and pressed into amulets.","zh":"佛粉（聖粉）— 由開光材料研磨，壓入佛牌之中。"},
 "ชานหมาก": {"roman":"chan mak","domain":"ritual","en":"Chewed betel-quid — spat and worked into folk blessing, healing and love magic.","zh":"檳榔渣 — 用於民間祝福、療癒與情術。"},
 "กะลาตาเดียว": {"roman":"kala ta diao","domain":"material","en":"A rare one-eyed coconut shell — a single natural sprout-hole makes it a powerful protective charm.","zh":"獨眼椰殼 — 天然僅一芽孔的稀有椰殼，為強力護符。"},

 # ---- The katha vocabulary itself — batch glossed 2026-08-19 ---------------------
 # Source: manuscript-crawler/term_scout.py (the Enrich-tier gap finder). After the
 # translated corpus grew to 4,592 pages, the scout's leaderboard — ordered by how
 # many manuscripts a term appears in — was the liturgy the manuscripts are made of:
 # the namo and refuge formulae, the heart-syllables, the Itipiso words, and the
 # verbs and units of the rite (เสก, คาบ, ภาวนา). None had a glossary entry.
 # These are dictionary-grade Pali/Thai terms, not interpretations; where a reading
 # is the tradition's own (นะโมพุทธายะ = the five Buddhas) it is marked as such.
 # `src` is provenance (ignored by the renderer); the per-manuscript spread quoted in
 # it is the scout's doc_count at glossing time. Each term's vocab_candidates row was
 # set status='glossed' the same day, per the scout's contract.
 "นะโม": {"roman":"namo","domain":"katha","en":"'Homage' — the first word of the salutation (namo tassa bhagavato…), and the word with which a katha, a recipe, or a rite begins.","zh":"南無 · 禮敬 — 禮敬文（namo tassa bhagavato…）的首字；咒語、藥方與法事皆以此開頭。","src":"term-scout 2026-08-19 · 17 mss"},
 "นะโมพุทธายะ": {"roman":"namo buddhaya","domain":"katha","en":"'Homage to the Buddha' — the five-syllable formula na-mo-phut-tha-ya, the commonest katha in the corpus. Tradition holds each syllable stands for one of the five Buddhas of this aeon (พระเจ้าห้าพระองค์); inscribed in yantra as a 5-cell row, rotated and reversed in consecration.","zh":"南無佛陀耶 — 五音節咒 na-mo-phut-tha-ya，全藏書中最常見的咒語。傳統以每一音對應本劫五佛（พระเจ้าห้าพระองค์）；常以五格書入符陣，順逆輪轉以加持。","src":"term-scout 2026-08-19 · 16 mss, 277 occurrences"},
 "นะมะพะทะ": {"roman":"na ma pha tha","domain":"katha","en":"The four-syllable 'heart of the elements' — na, ma, pha, tha, one for each of earth, water, fire and wind. Written into 4×4 yantra squares and read forward and backward (anuloma / patiloma) while a charm is empowered.","zh":"四大心咒 — na·ma·pha·tha 四音，對應地、水、火、風四大。書於四乘四符陣，加持時順讀、逆讀。","src":"term-scout 2026-08-19 · 13 mss"},
 "มะอะอุ": {"roman":"ma a u","domain":"katha","en":"The three syllables ma-a-u — the 'heart of the Triple Gem' (Buddha, Dhamma, Sangha) in Thai esoteric use; the same three sounds as Om (a-u-ma), reordered.","zh":"三音「麻·阿·烏」— 泰國密法中的三寶心咒（佛·法·僧）；與「唵」（a-u-ma）同音而異序。","src":"term-scout 2026-08-19 · 13 mss"},
 "อิติปิโส": {"roman":"itipiso","domain":"katha","en":"Itipiso — the opening of the recollection of the Buddha's qualities (itipi so bhagavā arahaṃ sammāsambuddho…). The katha tradition recites it, reverses it, counts it (Itipiso 108) and lays its syllables out as yantra.","zh":"伊諦比索 — 佛德憶念文（itipi so bhagavā arahaṃ…）的起句。咒法傳統誦之、倒讀之、計數之（伊諦比索一〇八），並將其音節排為符陣。","src":"term-scout 2026-08-19 · 14 mss"},
 "ภะคะวา": {"roman":"bhagava","domain":"katha","en":"Bhagavā, 'the Blessed One' — the Buddha's epithet and the second word of the Itipiso; often stands alone in a yantra cell as a seed-word.","zh":"薄伽梵（世尊）— 佛之尊號，Itipiso 的第二字；常單獨置於符格作種子字。","src":"term-scout 2026-08-19 · 13 mss"},
 "ภะคะวะโต": {"roman":"bhagavato","domain":"katha","en":"'Of the Blessed One' — the form heard in the salutation namo tassa bhagavato arahato sammāsambuddhassa.","zh":"世尊（屬格）— 見於禮敬文 namo tassa bhagavato arahato sammāsambuddhassa。","src":"term-scout 2026-08-19 · 12 mss"},
 "อะระหัง": {"roman":"arahang","domain":"katha","en":"Arahaṃ, 'the Worthy One' — first of the nine qualities of the Buddha; also breathed as a two-beat meditation word (a-ra-haṃ) and used as a seed in protective katha.","zh":"阿羅漢（應供）— 佛九德之首；亦作兩拍呼吸禪修詞（a-ra-haṃ），並為護身咒的種子音。","src":"term-scout 2026-08-19 · 14 mss"},
 "พุทโธ": {"roman":"buddho","domain":"katha","en":"Buddho, 'the Awakened One' — the commonest meditation word of the Thai forest tradition (bud- on the in-breath, -dho on the out-breath) and a seed-word in katha; with dhammo and saṅgho it makes the Triple-Gem triad.","zh":"佛陀（覺者）— 泰國森林傳統最常用的禪修念誦詞（入息 bud-、出息 -dho），亦為咒語種子；與 dhammo、saṅgho 合為三寶三聯。","src":"term-scout 2026-08-19 · 21 mss"},
 "ธัมโม": {"roman":"dhammo","domain":"katha","en":"Dhammo, 'the Teaching' — recited as the second of the Triple-Gem triad (buddho dhammo saṅgho).","zh":"達摩（法）— 三寶三聯之第二（buddho dhammo saṅgho）。","src":"term-scout 2026-08-19 · 15 mss"},
 "สังโฆ": {"roman":"sangho","domain":"katha","en":"Saṅgho, 'the Community' — third of the Triple-Gem triad.","zh":"僧伽（僧）— 三寶三聯之第三。","src":"term-scout 2026-08-19 · 12 mss"},
 "พุทธัง": {"roman":"buddhang","domain":"katha","en":"Buddhaṃ — 'the Buddha' as the object of the refuge formula: buddhaṃ saraṇaṃ gacchāmi, 'I go to the Buddha for refuge'. The three refuge lines open almost every rite in the corpus.","zh":"佛陀（受格）— 皈依文之對象：buddhaṃ saraṇaṃ gacchāmi「我皈依佛」。三皈依幾乎開啟藏書中每一場法事。","src":"term-scout 2026-08-19 · 19 mss"},
 "ธัมมัง": {"roman":"dhammang","domain":"katha","en":"Dhammaṃ — 'the Dhamma' in the second refuge line: dhammaṃ saraṇaṃ gacchāmi.","zh":"法（受格）— 第二句皈依文：dhammaṃ saraṇaṃ gacchāmi。","src":"term-scout 2026-08-19 · 19 mss"},
 "สังฆัง": {"roman":"sanghang","domain":"katha","en":"Saṅghaṃ — 'the Sangha' in the third refuge line: saṅghaṃ saraṇaṃ gacchāmi.","zh":"僧（受格）— 第三句皈依文：saṅghaṃ saraṇaṃ gacchāmi。","src":"term-scout 2026-08-19 · 19 mss"},
 "สะระณัง": {"roman":"saranang","domain":"katha","en":"Saraṇaṃ, 'refuge' — the word at the centre of each refuge line.","zh":"皈依（saraṇaṃ）— 每句皈依文的中心詞。","src":"term-scout 2026-08-19 · 14 mss"},
 "คัจฉามิ": {"roman":"gacchami","domain":"katha","en":"Gacchāmi, 'I go' — the verb that closes each refuge line.","zh":"我去 · 我往（gacchāmi）— 結束每句皈依文的動詞。","src":"term-scout 2026-08-19 · 12 mss"},
 "สัพเพ": {"roman":"sabbe","domain":"katha","en":"Sabbe, 'all' — opens the loving-kindness and protective formulae (sabbe sattā… 'may all beings…'), which the manuscripts recite over water, oil and the body.","zh":"一切（sabbe）— 慈心與護身文之首字（sabbe sattā…「願一切眾生…」），藏書中常對水、油與身體誦之。","src":"term-scout 2026-08-19 · 13 mss"},
 "เอหิ": {"roman":"ehi","domain":"katha","en":"Ehi, 'come!' — the summoning imperative that opens katha of calling: customers, lovers, spirits, fortune (ehi… piyaṃ mama).","zh":"來（ehi）— 召喚式命令語，開啟招客、招情、召靈、招財之咒（ehi… piyaṃ mama）。","src":"term-scout 2026-08-19 · 13 mss"},
 "สิทธิการิยะ": {"roman":"sitthikariya","domain":"katha","en":"'May it be accomplished' — the auspicious word with which a Thai manuscript, recipe or formula opens; the scribe's invocation, and the marker that a new text is beginning.","zh":"悉地迦利耶（願得成就）— 泰文古籍、藥方或咒法起首的吉祥語；書者之祈請，亦是新篇開始的標記。","src":"term-scout 2026-08-19 · 13 mss, 205 occurrences"},
 "สิทธิกิจจัง": {"roman":"sitthikitchang","domain":"katha","en":"'May the task succeed' — from the success-blessing siddhikiccaṃ siddhikammaṃ siddhikāriya tathāgato, recited to seal a rite or a making.","zh":"願事成就（siddhikiccaṃ）— 出自成就祝文 siddhikiccaṃ siddhikammaṃ siddhikāriya tathāgato，誦以封印法事或製作。","src":"term-scout 2026-08-19 · 12 mss"},
 "นะมามิหัง": {"roman":"namamihang","domain":"katha","en":"Namāmihaṃ, 'I pay homage' — the closing word of many salutation-katha (… namāmihaṃ).","zh":"我禮敬（namāmihaṃ）— 眾多禮敬咒的結尾詞。","src":"term-scout 2026-08-19 · 11 mss"},
 "ทุกขัง": {"roman":"dukkhang","domain":"katha","en":"Dukkhaṃ, 'suffering' — with aniccaṃ (impermanence) and anattā (not-self) one of the three marks; recited as a contemplation formula and used as a seed in katha.","zh":"苦（dukkhaṃ）— 與無常、無我合為三法印；作觀修文誦之，亦為咒語種子。","src":"term-scout 2026-08-19 · 12 mss"},
 "อนัตตา": {"roman":"anatta","domain":"katha","en":"Anattā, 'not-self' — third of the three marks (aniccaṃ dukkhaṃ anattā).","zh":"無我（anattā）— 三法印之第三。","src":"term-scout 2026-08-19 · 11 mss"},
 "กรุณา": {"roman":"karuna","domain":"katha","en":"Karuṇā, 'compassion' — second of the four brahmavihāra (mettā karuṇā muditā upekkhā), recited in sequence as a blessing and named among the qualities a charm bestows.","zh":"悲（karuṇā）— 四梵住之第二（慈悲喜捨），依序誦為祝福，亦列於法物所賜之德。","src":"term-scout 2026-08-19 · 13 mss"},
 "มุทิตา": {"roman":"mudita","domain":"katha","en":"Muditā, 'sympathetic joy' — third of the four brahmavihāra.","zh":"喜（muditā）— 四梵住之第三。","src":"term-scout 2026-08-19 · 12 mss"},
 "อุเบกขา": {"roman":"upekkha","domain":"katha","en":"Upekkhā, 'equanimity' — fourth of the four brahmavihāra.","zh":"捨（upekkhā）— 四梵住之第四。","src":"term-scout 2026-08-19 · 14 mss"},
 "ภาวนา": {"roman":"phawana","domain":"ritual","en":"To cultivate by recitation — repeating a katha, in the mind or aloud, a set number of times to charge a charm or oneself; the manuscripts' verb for 'recite / meditate on'.","zh":"修念 · 持誦（bhāvanā）— 以心或口反覆誦咒若干遍，以加持法物或自身；藏書中「誦／觀修」之動詞。","src":"term-scout 2026-08-19 · 14 mss"},
 "เสก": {"roman":"sek","domain":"ritual","en":"To consecrate by spell — breathe a katha over water, oil, wax, powder or an amulet to empower it. The central verb of the craft.","zh":"咒加持 — 對水、油、蠟、粉或護符誦咒吹氣以賦靈；法門的核心動詞。","src":"term-scout 2026-08-19 · 12 mss, 194 occurrences"},
 "คาบ": {"roman":"khap","domain":"ritual","en":"A count of recitations — 'recite 3 คาบ, 7 คาบ, 108 คาบ'; the unit in which the manuscripts measure a katha's work.","zh":"遍（誦咒計數單位）—「誦三遍、七遍、一〇八遍」；藏書衡量咒功之單位。","src":"term-scout 2026-08-19 · 12 mss, 495 occurrences"},
 "ธูป": {"roman":"thup","domain":"ritual","en":"Incense stick — counted out in set numbers (3, 5, 9, 16…) as the offering that opens a rite and honours the teacher-line.","zh":"香 — 以定數（三、五、九、十六…）供奉，開啟法事並敬師承。","src":"term-scout 2026-08-19 · 11 mss"},
 "เทียน": {"roman":"thian","domain":"ritual","en":"Candle — offering and instrument both: candles of set weight and number open the rite, and their flame or dripping wax carries the consecration.","zh":"蠟燭 — 既是供品也是法器：定重定數之燭開啟法事，其火與蠟滴承載加持。","src":"term-scout 2026-08-19 · 13 mss"},
 "ศีล": {"roman":"sin · sila","domain":"ritual","en":"The precepts (sīla — five or eight) — the moral discipline the manuscripts set alongside recitation as its condition.","zh":"戒（sīla，五戒或八戒）— 藏書與持誦並列、作為其條件的道德律儀。","src":"term-scout 2026-08-19 · 13 mss"},
}

DOMAIN_LABEL = {
 "yantra":"Yantra — sacred diagrams","katha":"Katha — spells & sacred sound",
 "amulet":"Amulets","attraction":"Love & attraction","power":"Powers of the body",
 "teachers":"Teachers & lineage","astrology":"Astrology & fate","medicine":"Medicine",
 "spirits":"Spirits & effigies","deities":"Deities & guardians","material":"Materials & bodies",
 "ritual":"Ritual craft",
}
LANGS = [("en","English"),("zh","中文"),("th","ไทย")]


def counts(conn):
    out = {}
    for r in conn.execute(
        "SELECT term_raw, COUNT(DISTINCT manuscript_id) ms, COUNT(DISTINCT item_id) mkt "
        "FROM tags GROUP BY term_raw"):
        out[r["term_raw"]] = (r["ms"] or 0, r["mkt"] or 0)
    # A term the taggers never tagged can still be counted — term_scout.py keeps,
    # per Thai token, the number of distinct manuscripts whose TRANSCRIPTIONS
    # contain it (vocab_candidates.doc_count). The katha vocabulary glossed
    # 2026-08-19 lives in page text, not in title tags, so without this the
    # glossary would say "0 manuscripts" beside a word found in 21 of them. Still
    # a catalogue count, not an editorial one; tags win where both exist. The
    # table may be absent on an old catalogue — then there is simply no fallback.
    try:
        for r in conn.execute(
            "SELECT term, doc_count FROM vocab_candidates WHERE doc_count > 0"):
            if r["term"] not in out or out[r["term"]][0] == 0:
                mkt = out.get(r["term"], (0, 0))[1]
                out[r["term"]] = (r["doc_count"] or 0, mkt)
    except sqlite3.OperationalError:
        pass
    return out


def build_data(db: Path):
    conn = sqlite3.connect(str(db)); conn.row_factory = sqlite3.Row
    try:
        c = counts(conn)
    finally:
        conn.close()
    entries = []
    for th, g in GLOSS.items():
        ms, mkt = c.get(th, (0, 0))
        gl = {"en": g["en"]}
        if g.get("zh"): gl["zh"] = g["zh"]
        gl["th"] = ""  # the headword itself is the Thai; per-lang gloss optional
        entries.append({
            "term": th, "roman": g["roman"], "domain": g["domain"],
            "domainLabel": DOMAIN_LABEL.get(g["domain"], g["domain"]),
            "glosses": gl, "manuscripts": ms, "listings": mkt,
        })
    entries.sort(key=lambda e: (e["domain"], -(e["manuscripts"] + e["listings"])))
    return {"kind": "glossary", "note": "Glosses are editorial (English authoritative, "
            "中文 careful); manuscript & listing counts are read from the catalogue.",
            "languages": [l[0] for l in LANGS], "count": len(entries), "entries": entries}


def render_page(data, site):
    entries_json = json.dumps(data["entries"], ensure_ascii=False)
    langs_json = json.dumps(LANGS, ensure_ascii=False)
    jsonld = json.dumps({
        "@context": "https://schema.org", "@type": "DefinedTermSet",
        "name": "Glossary of wichaa", "url": f"{site}/glossary/",
        "description": ("A multilingual glossary of Northern Thai wichaa — the terms of "
                        "the tradition, in Thai, English and 中文."),
        "hasDefinedTerm": [
            {"@type": "DefinedTerm", "name": e["term"], "alternateName": e["roman"],
             "description": e["glosses"].get("en", ""), "inDefinedTermSet": f"{site}/glossary/"}
            for e in data["entries"]
        ],
    }, ensure_ascii=False)
    return PAGE.replace("{{SITE}}", site).replace("{{COUNT}}", str(data["count"]))\
        .replace("{{JSONLD}}", jsonld)\
        .replace("{{ENTRIES}}", entries_json).replace("{{LANGS}}", langs_json)


PAGE = r"""<!doctype html>
<html lang="en"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Glossary · wichaa</title>
<meta name="description" content="A multilingual glossary of Northern Thai wichaa — the terms of the tradition, in Thai, English and 中文, each with how many manuscripts and market listings carry it.">
<meta name="keywords" content="wichaa glossary, Thai amulet terms, Thai magic glossary, yantra, katha, takrut, kuman thong, metta, sak yant, Northern Thai, 泰国佛牌, 泰国法术, Chinese, multilingual">
<link rel="canonical" href="{{SITE}}/glossary/">
<meta property="og:type" content="website">
<meta property="og:title" content="Glossary — the words of wichaa · Thai · English · 中文">
<meta property="og:description" content="The tradition's own vocabulary — takrut, kuman thong, metta, rahu — glossed in Thai, English and Chinese, each with the manuscripts and market listings that carry it.">
<meta property="og:url" content="{{SITE}}/glossary/">
<meta property="og:image" content="{{SITE}}/og.jpg">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:image" content="{{SITE}}/og.jpg">
<script type="application/ld+json">{{JSONLD}}</script>
<style>
 :root{--bg:#f4efe3;--panel:#fdfbf5;--ink:#26302a;--muted:#6d6455;--gold:#a8791e;
  --gold-soft:#c9a24a;--crimson:#8c3b2e;--line:#e5dcc7;
  --serif:"Sukhumvit Set","Noto Serif Thai",Thonburi,"Iowan Old Style","Palatino Linotype",Palatino,Georgia,serif;
  --sans:"Sukhumvit Set","Noto Sans Thai",Thonburi,-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;}
 *{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);
  font-family:var(--sans);font-size:18px;line-height:1.6}
 a{color:var(--crimson);text-decoration:none}a:hover{text-decoration:underline}
 .wrap{max-width:1000px;margin:0 auto;padding:0 24px}
 header{text-align:center;padding:52px 24px 20px}
 .mark{font-family:var(--serif);letter-spacing:.4em;color:var(--gold);font-size:13px}
 h1{font-family:var(--serif);font-size:clamp(30px,5vw,46px);margin:14px 0 8px}
 .sub{color:#3c463f;font-family:var(--serif);font-style:italic;font-size:20px;max-width:640px;margin:0 auto}
 .controls{position:sticky;top:0;background:var(--bg);border-bottom:1px solid var(--line);
  padding:16px 0;z-index:5;margin-top:22px}
 .controls .wrap{display:flex;gap:14px;flex-wrap:wrap;align-items:center;justify-content:center}
 #q{flex:1 1 260px;max-width:420px;padding:11px 16px;border:1.5px solid var(--line);
  border-radius:999px;font-size:16px;background:var(--panel);color:var(--ink)}
 .lang{display:flex;gap:6px}
 .lang button{padding:8px 15px;border:1.5px solid var(--gold);background:transparent;
  color:var(--ink);border-radius:999px;font-size:15px;font-weight:600;cursor:pointer}
 .lang button.on{background:var(--ink);color:#f6f1e4;border-color:var(--ink)}
 h2.dom{font-family:var(--serif);font-size:23px;color:var(--gold);
  border-bottom:1px solid var(--line);padding-bottom:8px;margin:38px 0 4px}
 .grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));gap:16px;margin-top:16px}
 .card{background:var(--panel);border:1px solid var(--line);border-radius:13px;padding:18px 20px}
 .card .th{font-family:var(--serif);font-size:26px;color:var(--ink);line-height:1.2}
 .card .rm{color:var(--gold);font-size:15px;font-style:italic;margin-bottom:8px}
 .card .gl{font-size:16px;color:#3c473f;line-height:1.55}
 .card .cnt{margin-top:12px;font-size:13.5px;color:var(--muted);display:flex;gap:14px;flex-wrap:wrap}
 .card .cnt a{color:var(--muted)}.card .cnt b{color:var(--ink)}
 footer{border-top:1px solid var(--line);margin-top:50px;padding:30px 0 60px;text-align:center;
  color:var(--muted);font-size:15px}
 .empty{text-align:center;color:var(--muted);padding:40px}
</style>
<script src="/phasa/portal.js" defer></script></head><body>
<header><div class="mark">wichaa · วิชา</div>
 <h1>Glossary</h1>
 <p class="sub">The words the tradition actually uses — in Thai, English and 中文 — each
   with how many manuscripts and how many market listings carry it.</p>
 <p style="margin-top:14px"><a href="/">← wichaa.net</a></p></header>
<div class="controls"><div class="wrap">
  <input id="q" type="search" placeholder="Search a term, meaning, or sound…">
  <div class="lang" id="lang"></div>
</div></div>
<main class="wrap" id="main"></main>
<footer><div class="wrap">
  Glosses are editorial — English authoritative, 中文 a careful reading; refinements welcome.
  Counts come straight from the catalogue. Malay &amp; Tamil to follow.<br>
  Open under <a href="/LICENSE">CC-BY 4.0</a> · <a href="/api/glossary.json">glossary.json</a>
</div></footer>
<script>
var ENTRIES={{ENTRIES}}, LANGS={{LANGS}}, SITE="{{SITE}}", lang="en";
function esc(s){var d=document.createElement('div');d.textContent=s||'';return d.innerHTML;}
function gloss(e){return e.glosses[lang]||e.glosses.en||'';}
function draw(){
 var q=(document.getElementById('q').value||'').toLowerCase().trim();
 var list=ENTRIES.filter(function(e){
   if(!q)return true;
   return (e.term+' '+e.roman+' '+e.glosses.en+' '+(e.glosses.zh||'')).toLowerCase().indexOf(q)>=0;
 });
 var main=document.getElementById('main');
 if(!list.length){main.innerHTML='<p class="empty">No term matches that.</p>';return;}
 var html='', dom=null;
 list.forEach(function(e){
   if(e.domain!==dom){
     if(dom!==null)html+='</div>';   // close the PREVIOUS domain's grid before opening the next
     dom=e.domain;html+='<h2 class="dom">'+esc(e.domainLabel)+'</h2><div class="grid">';
   }
   var links=[];
   if(e.manuscripts)links.push('<a href="/browse">▦ <b>'+e.manuscripts+'</b> manuscripts</a>');
   if(e.listings)links.push('<a href="/market">◈ <b>'+e.listings+'</b> listings</a>');
   html+='<div class="card"><div class="th">'+esc(e.term)+'</div>'+
     '<div class="rm">'+esc(e.roman)+'</div>'+
     '<div class="gl">'+esc(gloss(e))+'</div>'+
     '<div class="cnt">'+(links.join('')||'<span>—</span>')+'</div></div>';
 });
 // close the final domain's grid
 main.innerHTML=html+(list.length?'</div>':'');
}
var lc=document.getElementById('lang');
LANGS.forEach(function(l){var b=document.createElement('button');b.textContent=l[1];
 if(l[0]===lang)b.className='on';b.onclick=function(){lang=l[0];
 [].forEach.call(lc.children,function(c){c.className='';});b.className='on';draw();};
 lc.appendChild(b);});
document.getElementById('q').addEventListener('input',draw);
draw();
</script></body></html>"""


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Build the multilingual wichaa glossary")
    ap.add_argument("--db", default=str(_db))
    ap.add_argument("--docs", default=str(HERE.parent / "nanobotco-lanna" / "docs"))
    ap.add_argument("--site-url", default="https://wichaa.net")
    a = ap.parse_args(argv)
    db = Path(a.db); docs = Path(a.docs)
    if not db.is_file():
        print(f"glossary: catalog.db not found at {db}", file=sys.stderr); return 1
    if not (docs / "api").is_dir():
        print(f"glossary: no built site at {docs} (run build_static.py first)", file=sys.stderr); return 1
    data = build_data(db)
    (docs / "api" / "glossary.json").write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    gdir = docs / "glossary"; gdir.mkdir(exist_ok=True)
    (gdir / "index.html").write_text(render_page(data, a.site_url.rstrip("/")), encoding="utf-8")
    withzh = sum(1 for e in data["entries"] if e["glosses"].get("zh"))
    print(f"glossary: {data['count']} terms ({withzh} with 中文) → "
          f"api/glossary.json + glossary/index.html")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
