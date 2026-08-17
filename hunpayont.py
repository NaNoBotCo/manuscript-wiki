#!/usr/bin/env python3
"""หุ่นพยนต์ · Hun Payont — an effigy you forge, consecrate and carry, which
walks to the market every morning and brings back one thing.

WHAT IT IS, MECHANICALLY
    A dependency-free widget. The bearer forges an effigy (a deterministic
    drawing seeded by their own name), breathes a KHATA into it — which here is
    literally the bearer's own affiliate-link template — and pastes the embed
    anywhere. Each day it reads the Thai day-reckoning (day-deva, colour, moon
    phase, wan phra, Rahu), picks one real listing out of the living-market
    corpus that suits that day, and links to it through the bearer's template.

    Whatever it earns is earned by the bearer's own affiliate account, paid by
    the bearer's own network, straight to the bearer. This site takes no cut,
    runs no server, sets no cookie and never sees a click. There is nothing to
    take a cut WITH: the whole thing is one static page.

WHY THE KHATA IS A TEMPLATE AND NOT A HARD-CODED NETWORK
    Deliberate. Lazada's link generation changed recently and some products are
    no longer deep-linkable at all; Involve Asia's wrapper grammar is not
    publicly documented. Hard-coding one network's URL shape would mean shipping
    a claim I cannot verify, into a page whose entire promise is that it works.
    So the bearer supplies the shape, the widget shows the EXACT url it will
    emit before anything is saved, and the bearer checks it against their own
    dashboard. One click to verify, and it survives any network changing its
    mind. It also happens to be the folklore: an effigy is inert until someone
    who knows the words says them over it.

WHY THE ERRAND IS FIXED FOR THE DAY
    The pick is hash(date + bearer) — the same all day, different per bearer.
    An errand that changes on every refresh is a slot machine, and reads as one.

WHY IT RESTS ON WAN PHRA
    On the four Buddhist holy days of each lunar month it shows the day and no
    product at all. That is what the tradition does, and a thing that will not
    sell on those days is more believable the rest of the month.

DRIFT WATCH
    `elong()` inside READING_JS is COPIED from moondial.py's DIAL_JS — the same
    compact series, checked there against JPL DE440 (worst 0.40°). If one
    changes, change both; a diff of the two functions takes ten seconds.

    The effigy exists in exactly ONE implementation (EFFIGY_JS, JavaScript).
    The share card renders it by running that same script in Chrome rather than
    redrawing it in Python, so a card cannot drift from the page.
"""

from __future__ import annotations

import html
import json

# ---------------------------------------------------------------- palette
# Same house as the moon dial, so the two look like they came from one workshop.
INK = "#1b2b28"
GOLD = "#9a7b32"
GOLD_LIGHT = "#c2a253"
PLATE = "#efe5d0"
BAMBOO = "#c8a86a"
BAMBOO_DARK = "#9c7d45"
CORD = "#7d5b32"
NIGHT = "#101f38"

# ---------------------------------------------------------------- the days
# The eight-day week of Thai reckoning: seven days, with Wednesday split into
# its daytime and its night, the night belonging to Rahu. Each day carries a
# graha, a colour, and a posture of the Buddha (พระประจำวันเกิด) — this part is
# standard and stable across sources.
#
# `theme` maps the day onto a term that is ACTUALLY IN THE CORPUS with a
# healthy count, so the errand is drawn from real listings and not from a
# category invented to fit. The mapping follows the graha's own documented
# domain — Budha/Wednesday is the graha of trade, so Wednesday fetches
# นางกวัก, the beckoning lady kept by shopkeepers; Shukra/Friday is the graha
# of love, so Friday fetches สีผึ้งมหาเสน่ห์, charm balm. Marked as
# interpretation on the page, because the pairing is mine.
DAYS = [
    {"i": 0, "en": "Sunday", "th": "อาทิตย์", "graha": "พระอาทิตย์",
     "grahaEn": "Surya", "colour": "#c8322b", "colourName": "red",
     "colourNameTh": "สีแดง",
     "pang": "ปางถวายเนตร", "pangEn": "gazing, unblinking",
     "domain": "standing in your own name",
     "domainTh": "การยืนหยัดในชื่อของตัวเอง", "theme": "authority"},
    {"i": 1, "en": "Monday", "th": "จันทร์", "graha": "พระจันทร์",
     "grahaEn": "Chandra", "colour": "#efdc9e", "colourName": "cream yellow",
     "colourNameTh": "สีเหลืองนวล",
     "pang": "ปางห้ามญาติ", "pangEn": "hand raised, quieting a quarrel",
     "domain": "safe passage, cooling a temper",
     "domainTh": "การเดินทางปลอดภัย และการระงับความโกรธ", "theme": "safety"},
    {"i": 2, "en": "Tuesday", "th": "อังคาร", "graha": "พระอังคาร",
     "grahaEn": "Mangala", "colour": "#e07a9a", "colourName": "pink",
     "colourNameTh": "สีชมพู",
     "pang": "ปางไสยาสน์", "pangEn": "reclining",
     "domain": "nerve, and the cheek to ask",
     "domainTh": "ความกล้า และความหน้าด้านพอที่จะเอ่ยปากขอ",
     "theme": "mischief"},
    {"i": 3, "en": "Wednesday", "th": "พุธ", "graha": "พระพุธ",
     "grahaEn": "Budha", "colour": "#2e8b57", "colourName": "green",
     "colourNameTh": "สีเขียว",
     "pang": "ปางอุ้มบาตร", "pangEn": "holding the alms bowl",
     "domain": "trade, and being spoken well of",
     "domainTh": "การค้าขาย และการมีคนพูดถึงในทางที่ดี", "theme": "trade"},
    {"i": 4, "en": "Thursday", "th": "พฤหัสบดี", "graha": "พระพฤหัสบดี",
     "grahaEn": "Brihaspati", "colour": "#e08a2e", "colourName": "orange",
     "colourNameTh": "สีส้ม",
     "pang": "ปางสมาธิ", "pangEn": "seated in meditation",
     "domain": "teachers — this is the day of wai khru",
     "domainTh": "ครูบาอาจารย์ — วันนี้คือวันไหว้ครู", "theme": "teacher"},
    {"i": 5, "en": "Friday", "th": "ศุกร์", "graha": "พระศุกร์",
     "grahaEn": "Shukra", "colour": "#7fb6d9", "colourName": "light blue",
     "colourNameTh": "สีฟ้า",
     "pang": "ปางรำพึง", "pangEn": "standing, arms folded, considering",
     "domain": "being wanted", "domainTh": "เสน่ห์ การเป็นที่ต้องการ",
     "theme": "charm"},
    {"i": 6, "en": "Saturday", "th": "เสาร์", "graha": "พระเสาร์",
     "grahaEn": "Shani", "colour": "#4b3a63", "colourName": "purple",
     "colourNameTh": "สีม่วง",
     "pang": "ปางนาคปรก", "pangEn": "sheltered by the naga's hood",
     "domain": "obstacles, and standing behind a door",
     "domainTh": "อุปสรรค และการเฝ้าอยู่หลังประตู",
     "theme": "protection"},
    {"i": 7, "en": "Wednesday night", "th": "พุธกลางคืน", "graha": "พระราหู",
     "grahaEn": "Rahu", "colour": "#24242a", "colourName": "black",
     "colourNameTh": "สีดำ",
     "pang": "ปางป่าเลไลยก์", "pangEn": "in the forest, attended by an "
     "elephant and a monkey",
     "domain": "swallowing what should be let go of",
     "domainTh": "การกลืนสิ่งที่ควรปล่อยวาง", "theme": "rahu"},
]

# theme key -> what it is, in both languages, and the corpus term it draws from.
# `term` is the ONLY field wiki.hun_pool() queries with; everything else is
# display. The Thai is not a translation of the English — for a Thai reader the
# object needs no explaining, so the Thai line says what it is FOR, which is the
# part that is actually useful.
THEMES = {
    "authority": {"en": "Authority", "th": "บารมี", "term": "จตุคาม",
                  "whyEn": "Jatukham Rammathep — the amulet of rank and reach.",
                  "whyTh": "จตุคามรามเทพ — ของเสริมบารมีและอำนาจ"},
    "safety":    {"en": "Safe passage", "th": "แคล้วคลาด", "term": "หลวงปู่ทวด",
                  "whyEn": "Luang Pu Thuat, whom people carry against accidents.",
                  "whyTh": "หลวงปู่ทวด — พกไว้กันอุบัติเหตุ แคล้วคลาดปลอดภัย"},
    "mischief":  {"en": "Nerve", "th": "กล้าได้กล้าเสีย", "term": "ไอ้ไข่",
                  "whyEn": "Ai Khai, the boy of Wat Chedi — asked bluntly, "
                           "answers bluntly.",
                  "whyTh": "ไอ้ไข่ วัดเจดีย์ — ขอตรงๆ ท่านก็ให้ตรงๆ"},
    "trade":     {"en": "Trade", "th": "ค้าขาย", "term": "นางกวัก",
                  "whyEn": "Nang Kwak, the beckoning lady, kept beside the till.",
                  "whyTh": "นางกวัก — ตั้งไว้ข้างลิ้นชักเงิน เรียกลูกค้า"},
    "teacher":   {"en": "The master's cloth", "th": "ของครู", "term": "ผ้ายันต์",
                  "whyEn": "Pha yant — the cloth a teacher draws on and gives "
                           "away.",
                  "whyTh": "ผ้ายันต์ — ผ้าที่ครูบาอาจารย์ลงอักขระแล้วมอบให้"},
    "charm":     {"en": "Charm", "th": "เมตตามหาเสน่ห์",
                  "term": "สีผึ้งมหาเสน่ห์",
                  "whyEn": "Si phueng — charm balm, worn on the lip.",
                  "whyTh": "สีผึ้ง — ป้ายริมฝีปาก เสริมเสน่ห์เมตตา"},
    "protection": {"en": "Protection", "th": "คุ้มครอง",
                   "term": "ท้าวเวสสุวรรณ",
                   "whyEn": "Thao Wessuwan, the guardian of the north, at the "
                            "gate.",
                   "whyTh": "ท้าวเวสสุวรรณ — ท้าวจตุโลกบาลประจำทิศเหนือ "
                            "ตั้งไว้หน้าประตู"},
    "rahu":      {"en": "Letting go", "th": "ปล่อยวาง", "term": "ราหู",
                  "whyEn": "Phra Rahu, who swallows and then must release.",
                  "whyTh": "พระราหู — ผู้กลืนแล้วก็ต้องคาย"},
    "growth":    {"en": "Growth", "th": "ค่อยเป็นค่อยไป",
                  "term": "พญาเต่าเรือน",
                  "whyEn": "Phaya Tao Ruean, the house-turtle — slow, and it "
                           "arrives.",
                  "whyTh": "พญาเต่าเรือน — ช้าๆ แต่ถึงแน่"},
    "binding":   {"en": "Binding", "th": "ผูกไว้", "term": "ตะกรุด",
                  "whyEn": "Takrut — a rolled sheet of inscribed metal, tied "
                           "shut.",
                  "whyTh": "ตะกรุด — แผ่นโลหะลงอักขระ ม้วนแล้วผูกไว้"},
    "self":      {"en": "Its own kind", "th": "พวกเดียวกัน",
                  "term": "หุ่นพยนต์",
                  "whyEn": "A hun payont, which is what this is. It fetches its "
                           "own kind once a month.",
                  "whyTh": "หุ่นพยนต์ — อย่างเดียวกับตัวมันเอง "
                           "เดือนละครั้งมันจะไปหาพวกเดียวกัน"},
}

# The order the pool is built and shipped in.
THEME_KEYS = list(THEMES.keys())

# How many listings per theme get baked into the page. 30 x 11 keeps the
# payload near 60 KB, which is the price of the widget working with the network
# unplugged — the portability contract every widget on this site is held to.
PER_THEME = 30


# ------------------------------------------------------------- su khwan katha
# A second, simpler mode on this same page: no effigy, no affiliate link, no
# forging — a visitor types one or more of their own names and gets a daily
# bilingual name-blessing, picked deterministically the same way the effigy's
# daily errand is (hash(date + names) % len(bank), see pickFor() in APP_JS).
#
# SOURCING, stated plainly because this draws on a real living rite: su khwan /
# บายศรีสู่ขวัญ ("calling the khwan back") is documented practice across Lao,
# Sipsong Panna, Lanna and Isaan communities — a mor soot leads a call-and-
# response ("มา เยอ ขวัญ เอย") around a tiered bai sri offering, then ties white
# string around the wrist to bind the 32 khwan back to the body. See
# https://www.thaifolk.com/doc/bysri_e.htm ,
# https://ccsenet.org/journal/index.php/ach/article/view/36412 ,
# https://link.springer.com/article/10.1007/s44282-025-00172-x .
# Every line below is ORIGINAL composition inspired by that structure — none is
# quoted or adapted from a specific published ritual text, and this page makes
# no claim to a mor soot's authority. It is a solitary, poetic echo of a
# communal rite, not a substitute for one performed with family present. The
# Thai lines are written directly in Thai, not translated from the English —
# same discipline as _essay_en/_essay_th.
#
# {name} is replaced client-side with whichever entered name is on duty that
# day (see the mode's pick logic in APP_JS) — never server-side, since this
# whole site is static and makes no request carrying anyone's name anywhere.
SUKHWAN = [
    {
        "en": "Khwan, come home. {name} is standing in the doorway with the light still on for you.",
        "th": "ขวัญเอย ขวัญของ {name} กลับมาเถิด ประตูยังเปิดรอ ไฟยังไม่ดับ",
        "translit": "Khwan oei, khwan khong {name}, klap ma theut. Pratu yang poet ror, fai yang mai dap.",
        "gloss": "Oh khwan, khwan of {name}, please come back. The door is still open and waiting, the fire is not yet out.",
    },
    {
        "en": "Wherever you wandered today, {name}'s khwan — come back now, and stay close to the hands and feet.",
        "th": "ไปไหนมาทั้งวัน ขวัญของ {name} กลับมาอยู่กับเนื้อกับตัวเสียที",
        "translit": "Pai nai ma thang wan, khwan khong {name} klap ma yu kap nuea kap tua sia thi.",
        "gloss": "Wherever you went all day, khwan of {name}, come back and stay with the body at last.",
    },
    {
        "en": "The thread is tied. {name} is bound to breath, to bone, to the ground underfoot.",
        "th": "ผูกด้ายไว้ที่ข้อมือ ไม่ใช่ผูกไว้ไม่ให้ไป แต่ผูกไว้ไม่ให้ขวัญหลงทางตอนหลับ",
        "translit": "Phuk dai wai thi kho meu, mai chai phuk wai mai hai pai, tae phuk wai mai hai khwan long thang ton lap.",
        "gloss": "The thread is tied at the wrist — not to keep you from leaving, but to keep the khwan from losing its way while sleeping.",
    },
    {
        "en": "Come, oh khwan, come — {name} calls you by name, and a name is a place to land.",
        "th": "มาเยอ ขวัญเอย เรียกชื่อ {name} เพราะชื่อคือที่ให้กลับมาลง",
        "translit": "Ma yoe, khwan oei, riak cheu {name} phro cheu khue thi hai klap ma long.",
        "gloss": "Come, oh spirit — I call the name {name}, because a name is the place to land upon returning.",
    },
    {
        "en": "Rest in {name}'s chest tonight. The door is shut against fright, and the lamp is lit.",
        "th": "คืนนี้ให้ {name} นอนอุ่น ขวัญอยู่ในอก ไม่หนีไปไหน",
        "translit": "Khuen ni hai {name} non un, khwan yu nai ok, mai ni pai nai.",
        "gloss": "Tonight let {name} sleep warm — the khwan stays in the chest, going nowhere.",
    },
    {
        "en": "Khwan that scattered at the loud noise, at the near miss, at the long road — return to {name} now.",
        "th": "ขวัญที่ตกใจ ขวัญที่วิ่งหนีเสียงดัง ขวัญที่หลงทางไกล กลับมาหา {name} เถิด",
        "translit": "Khwan thi tok jai, khwan thi wing ni siang dang, khwan thi long thang klai, klap ma ha {name} theut.",
        "gloss": "Khwan that was startled, khwan that ran from a loud sound, khwan that lost its way far off — come back to {name}.",
    },
    {
        "en": "{name}, your khwan is called home the way a boat is called back to shore before the tide turns.",
        "th": "{name} เรียกขวัญกลับ เหมือนเรียกเรือกลับฝั่งก่อนน้ำขึ้น",
        "translit": "{name} riak khwan klap, meuan riak reua klap fang kon nam khuen.",
        "gloss": "{name} calls the khwan back, the way a boat is called back to shore before the tide rises.",
    },
    {
        "en": "Come back to the rice bowl, come back to the water jar — {name}'s khwan, come back to the house that knows your step.",
        "th": "กลับมากินข้าวที่บ้าน กลับมาดื่มน้ำที่เคยดื่ม ขวัญของ {name} กลับมาบ้านที่จำก้าวเดินได้",
        "translit": "Klap ma kin khao thi ban, klap ma deum nam thi khoei deum, khwan khong {name} klap ma ban thi cham kao doen dai.",
        "gloss": "Come back to eat rice at home, come back to drink the water you used to drink — khwan of {name}, come back to the house whose steps you remember.",
    },
    {
        "en": "The string goes around the wrist, not to hold {name} down, but to keep the khwan from drifting while they sleep.",
        "th": "ด้ายที่ผูกข้อมือไม่ใช่เชือกจองจำ แต่เป็นเชือกกันขวัญไม่ให้ลอยหายตอนหลับ",
        "translit": "Dai thi phuk kho meu mai chai chueak jong jam, tae pen chueak kan khwan mai hai loi hai ton lap.",
        "gloss": "The thread tied at the wrist is not a rope of imprisonment, but a rope that keeps the khwan from drifting away while asleep.",
    },
    {
        "en": "However far the khwan travelled today, it is not lost — only away. {name}, call it, and it will come.",
        "th": "ขวัญไปไกลแค่ไหนก็ไม่หาย เพียงแต่เผลอไป {name} เรียกเมื่อไร ขวัญก็มา",
        "translit": "Khwan pai klai khae nai ko mai hai, phiang tae phloe pai, {name} riak meua rai khwan ko ma.",
        "gloss": "However far the khwan has gone, it is not lost — only careless wandering. Whenever {name} calls, the khwan comes.",
    },
    {
        "en": "Khwan-oh, khwan-oh, come and dwell in {name} the way a flame dwells in its own wick.",
        "th": "ขวัญเอย ขวัญเอย มาอยู่กับ {name} เหมือนไฟอยู่กับไส้เทียนของมันเอง",
        "translit": "Khwan oei, khwan oei, ma yu kap {name} meuan fai yu kap sai thian khong man eng.",
        "gloss": "Oh khwan, oh khwan, dwell with {name} the way a flame dwells with its own candlewick.",
    },
    {
        "en": "{name} is named, and to be named is to be findable — khwan, find your way back by the name that is calling you.",
        "th": "{name} มีชื่อ และมีชื่อแปลว่าตามหาเจอ ขวัญเอย ตามชื่อที่เรียกกลับมา",
        "translit": "{name} mi cheu, lae mi cheu plae wa tam ha jer, khwan oei, tam cheu thi riak klap ma.",
        "gloss": "{name} has a name, and having a name means being findable — oh khwan, follow the name that calls you back.",
    },
    {
        "en": "Let no fright follow {name} through this door. What frightened the khwan stays outside; what steadies it comes in.",
        "th": "อย่าให้ความตกใจตามเข้าประตูมา สิ่งที่ทำให้ขวัญหนีให้อยู่ข้างนอก สิ่งที่ทำให้ขวัญนิ่งให้เข้ามาข้างใน",
        "translit": "Ya hai khwam tok jai tam khao pratu ma, sing thi tham hai khwan ni hai yu khang nok, sing thi tham hai khwan ning hai khao ma khang nai.",
        "gloss": "Do not let the fright follow through the door. Let what made the khwan flee stay outside; let what makes the khwan settle come in.",
    },
    {
        "en": "Morning finds {name} whole again — the khwan that wandered in the dark has come back with the light.",
        "th": "รุ่งเช้าให้ {name} ครบเหมือนเดิม ขวัญที่หลงในความมืดกลับมาพร้อมแสง",
        "translit": "Rung chao hai {name} khrop meuan doem, khwan thi long nai khwam meut klap ma phrom saeng.",
        "gloss": "Let the morning find {name} whole as before — the khwan that wandered in the dark returns with the light.",
    },
    {
        "en": "Thirty-two khwan, and not one missing tonight — all of them home, all of them {name}'s.",
        "th": "สามสิบสองขวัญ คืนนี้ไม่หายไปสักขวัญ ทุกขวัญเป็นของ {name} ทั้งหมด",
        "translit": "Sam sip song khwan, khuen ni mai hai pai sak khwan, thuk khwan pen khong {name} thang mot.",
        "gloss": "Thirty-two khwan — tonight not one of them is missing. Every khwan belongs to {name}, all of them.",
    },
    {
        "en": "The threshold is crossed, the string is tied, the name is spoken: {name}, be whole.",
        "th": "ข้ามธรณีประตูมาแล้ว ผูกด้ายแล้ว เอ่ยชื่อแล้ว {name} ขอให้ครบเถิด",
        "translit": "Kham thoranee pratu ma laeo, phuk dai laeo, oei cheu laeo, {name} kho hai khrop theut.",
        "gloss": "The threshold has been crossed, the thread has been tied, the name has been spoken: may {name} be whole.",
    },
    {
        "en": "Khwan, do not linger where you were startled. Come back to the warm place, the known place, {name}'s own place.",
        "th": "ขวัญเอย อย่าแช่อยู่ตรงที่ตกใจ กลับมาที่อุ่น ที่คุ้น ที่เป็นของ {name} เอง",
        "translit": "Khwan oei, ya chae yu trong thi tok jai, klap ma thi un, thi khun, thi pen khong {name} eng.",
        "gloss": "Oh khwan, do not soak in the place that frightened you. Come back to the warm place, the familiar place, the place that belongs to {name}.",
    },
    {
        "en": "{name}'s breath, {name}'s pulse, {name}'s khwan — three names for the same staying-put.",
        "th": "ลมหายใจของ {name} ชีพจรของ {name} ขวัญของ {name} สามชื่อ แต่เป็นการอยู่นิ่งเดียวกัน",
        "translit": "Lom hai jai khong {name}, chip pha jon khong {name}, khwan khong {name}, sam cheu tae pen kan yu ning diao kan.",
        "gloss": "{name}'s breath, {name}'s pulse, {name}'s khwan — three names, but the same act of staying still.",
    },
    {
        "en": "However this day scattered you, {name}, gather back in — the calling is not once, it is every evening.",
        "th": "วันนี้กระจัดกระจายไปแค่ไหน {name} เก็บกลับมาเถิด การเรียกนี้ไม่ใช่ครั้งเดียว แต่เรียกทุกเย็น",
        "translit": "Wan ni krajat krajai pai khae nai, {name} kep klap ma theut, kan riak ni mai chai khrang diao, tae riak thuk yen.",
        "gloss": "However scattered today became, {name}, gather it back in. This calling is not once, but every evening.",
    },
    {
        "en": "Come, khwan, the way rain comes back to the river it left as vapor — {name} is the river, waiting.",
        "th": "มาเถิดขวัญ เหมือนฝนกลับคืนสู่แม่น้ำที่มันเคยระเหยจากไป {name} คือแม่น้ำที่รอ",
        "translit": "Ma theut khwan, meuan fon klap khuen su mae nam thi man khoei ra hoei jak pai, {name} khue mae nam thi ror.",
        "gloss": "Come, khwan, the way rain returns to the river it once evaporated from — {name} is the river that waits.",
    },
    {
        "en": "No harm reaches {name} tonight that the tied thread has not already turned away.",
        "th": "คืนนี้ไม่มีภัยใดถึงตัว {name} ที่ด้ายผูกไว้ไม่เบี่ยงหนีไปแล้ว",
        "translit": "Khuen ni mai mi phai dai theung tua {name} thi dai phuk wai mai biang ni pai laeo.",
        "gloss": "Tonight no harm reaches {name}, already turned away by the tied thread.",
    },
    {
        "en": "The old words called the khwan home for the newborn, the newly married, the newly returned — tonight they call it home for {name}.",
        "th": "คำโบราณเคยเรียกขวัญกลับให้เด็กเกิดใหม่ ให้คู่แต่งงานใหม่ ให้คนเพิ่งกลับจากไกล คืนนี้เรียกกลับให้ {name}",
        "translit": "Kham boran khoei riak khwan klap hai dek koet mai, hai khu taeng ngan mai, hai khon phoeng klap jak klai, khuen ni riak klap hai {name}.",
        "gloss": "The old words once called the khwan home for the newborn, for the newly married, for one just returned from afar — tonight they call it home for {name}.",
    },
    {
        "en": "Khwan-oh — {name}'s name said three times is a rope thrown, and a rope thrown is meant to be caught.",
        "th": "ขวัญเอย เอ่ยชื่อ {name} สามหน เหมือนโยนเชือกไปให้ และเชือกที่โยนไปก็รอให้จับ",
        "translit": "Khwan oei, oei cheu {name} sam hon, meuan yon chueak pai hai, lae chueak thi yon pai ko ror hai jap.",
        "gloss": "Oh khwan, {name}'s name spoken three times is like a rope thrown out, and a thrown rope waits to be caught.",
    },
    {
        "en": "{name} need not be brave to be called back whole. The calling does the work; {name} only has to answer.",
        "th": "{name} ไม่ต้องกล้าหาญเพื่อให้ขวัญกลับมาครบ การเรียกทำหน้าที่ของมันเอง {name} แค่ตอบรับ",
        "translit": "{name} mai tong kla han phuea hai khwan klap ma khrop, kan riak tham na thi khong man eng, {name} khae top rap.",
        "gloss": "{name} need not be brave for the khwan to return whole. The calling does its own work; {name} only has to answer.",
    },
    {
        "en": "Stay near the hearth, khwan. Stay near {name}'s hands, which have work tomorrow and need the khwan awake in them.",
        "th": "อยู่ใกล้เตาไฟไว้นะขวัญ อยู่ใกล้มือของ {name} ที่พรุ่งนี้ยังมีงานให้ทำ ต้องการขวัญตื่นอยู่ในนั้น",
        "translit": "Yu klai tao fai wai na khwan, yu klai meu khong {name} thi phrung ni yang mi ngan hai tham, tong kan khwan teun yu nai nan.",
        "gloss": "Stay near the hearth, khwan. Stay near {name}'s hands, which still have work tomorrow and need the khwan awake within them.",
    },
    {
        "en": "What left {name} in fright, in grief, in the ordinary wear of a hard day — it is asked, gently, to come back.",
        "th": "สิ่งที่ทำให้ {name} หนีไปด้วยความตกใจ ความเศร้า ความเหนื่อยของวันธรรมดา ขอให้ค่อยๆ กลับมา",
        "translit": "Sing thi tham hai {name} ni pai duai khwam tok jai, khwam sao, khwam neuai khong wan tham ma da, kho hai khoi khoi klap ma.",
        "gloss": "What made {name} flee — through fright, through grief, through the ordinary weariness of a hard day — may it come back slowly, gently.",
    },
    {
        "en": "The bai sri is not built tonight, but the calling still stands: {name}'s khwan, come home by the shortest road.",
        "th": "คืนนี้ไม่ได้ตั้งบายศรี แต่คำเรียกยังตั้งอยู่ ขวัญของ {name} กลับบ้านทางที่สั้นที่สุดเถิด",
        "translit": "Khuen ni mai dai tang baisri, tae kham riak yang tang yu, khwan khong {name} klap ban thang thi san thi sut theut.",
        "gloss": "Tonight no bai sri offering is raised, but the calling still stands — may khwan of {name} come home by the shortest road.",
    },
    {
        "en": "Not lost — only wandering. {name}'s khwan hears its own name and turns toward it, the way a face turns toward warmth.",
        "th": "ไม่ได้หาย เพียงแต่เดินหลงทาง ขวัญของ {name} ได้ยินชื่อตัวเองแล้วหันมา เหมือนหน้าหันหาความอุ่น",
        "translit": "Mai dai hai, phiang tae doen long thang, khwan khong {name} dai yin cheu tua eng laeo han ma, meuan na han ha khwam un.",
        "gloss": "Not lost — only walking a wrong path. Khwan of {name} hears its own name and turns toward it, the way a face turns toward warmth.",
    },
    {
        "en": "Tie the string loosely; the khwan should feel welcomed, not caught. {name}, be gathered back in, gladly.",
        "th": "ผูกด้ายหลวมๆ ขวัญจะได้รู้สึกว่าถูกต้อนรับ ไม่ใช่ถูกจับ {name} กลับมาเถิด กลับมาด้วยความยินดี",
        "translit": "Phuk dai luam luam, khwan ja dai ru seuk wa thuk ton rap, mai chai thuk jap, {name} klap ma theut, klap ma duai khwam yin di.",
        "gloss": "Tie the thread loosely, so the khwan feels welcomed, not caught. {name}, come back — come back gladly.",
    },
    {
        "en": "The last line of any su khwan is the same wish said differently: stay, {name}. Stay whole. Stay found.",
        "th": "ประโยคสุดท้ายของการสู่ขวัญทุกครั้งคือคำอวยพรเดียวกัน พูดต่างกันไป: อยู่นะ {name} อยู่ให้ครบ อยู่ให้เจอ",
        "translit": "Prayok sut thai khong kan su khwan thuk khrang khue kham uai phon diao kan, phut tang kan pai: yu na {name}, yu hai khrop, yu hai jer.",
        "gloss": "The last line of every su khwan is the same blessing, said differently each time: stay, {name}. Stay whole. Stay found.",
    },
]

SUKHWAN_NOTE = (
    "Tradition holds — su khwan (สู่ขวัญ) calls a wandering khwan back with "
    "call-and-response and a tied string; a mor soot leads it, family present. "
    "These lines are an original echo of that structure, said alone, not a "
    "substitute for the rite itself.",
    "ธรรมเนียมสู่ขวัญเรียกขวัญที่พเนจรกลับมาด้วยบทเรียกและด้ายผูกข้อมือ "
    "มีหมอสูตรเป็นผู้นำ มีญาติพี่น้องอยู่ด้วย ถ้อยคำเหล่านี้เป็นบทประพันธ์ขึ้นใหม่ "
    "สะท้อนโครงสร้างนั้นเมื่ออยู่คนเดียว ไม่ใช่สิ่งทดแทนพิธีจริง",
)


# ------------------------------------------------------------------ effigy
# THE ONLY IMPLEMENTATION. Python does not draw the effigy anywhere; the share
# card runs this same script in Chrome. One drawing, one source.
#
# The chest plate carries a real magic square built by the Siamese method (see
# the essay). Every plate on every effigy has rows, columns and both diagonals
# summing to the constant printed under it — that is a claim the bearer can
# check with their own eyes, which is the point.
EFFIGY_JS = r"""
var HUN = (function(){
  var INK='""" + INK + r"""', GOLD='""" + GOLD + r"""',
      GOLDL='""" + GOLD_LIGHT + r"""', PLATE='""" + PLATE + r"""',
      BAM='""" + BAMBOO + r"""', BAMD='""" + BAMBOO_DARK + r"""',
      CORD='""" + CORD + r"""';
  var THAI='๐๑๒๓๔๕๖๗๘๙';

  // FNV-1a, 32-bit. Small, stable, and identical in every browser — the effigy
  // must be the same drawing on the bearer's phone and on their reader's.
  function hash(s){
    var h=0x811c9dc5;
    for(var i=0;i<s.length;i++){
      h^=s.charCodeAt(i);
      h=(h+((h<<1)+(h<<4)+(h<<7)+(h<<8)+(h<<24)))>>>0;
    }
    return h>>>0;
  }
  // A deterministic stream of small integers from one seed.
  function rng(seed){
    var s=seed>>>0;
    return function(n){ s=(s*1664525+1013904223)>>>0; return s%n; };
  }
  function thaiNum(n){
    var s=String(n), o='';
    for(var i=0;i<s.length;i++) o+=THAI.charAt(+s.charAt(i));
    return o;
  }

  // --- the Siamese method -------------------------------------------------
  // De la Loubère's rule for odd n: start in the middle of the top row, step
  // up-and-right, and drop one row when that cell is taken. Adding a constant
  // to every cell keeps it magic, which is where the per-bearer variety comes
  // from without ever producing a square that is not one.
  function magic(n, add){
    var g=[], i;
    for(i=0;i<n;i++){ g.push(new Array(n).fill(0)); }
    var r=0, c=(n-1)>>1;
    for(var k=1;k<=n*n;k++){
      g[r][c]=k+add;
      var r2=(r-1+n)%n, c2=(c+1)%n;
      if(g[r2][c2]){ r=(r+1)%n; } else { r=r2; c=c2; }
    }
    return g;
  }
  // The eight symmetries of the square. Every one of them maps rows to rows or
  // columns, and diagonals to diagonals, so the square stays magic.
  function dihedral(g, k){
    var n=g.length, out=g, i, j, t;
    function rot(m){
      var o=[]; for(i=0;i<n;i++){ o.push([]); for(j=0;j<n;j++) o[i].push(m[n-1-j][i]); }
      return o;
    }
    function flip(m){
      var o=[]; for(i=0;i<n;i++) o.push(m[i].slice().reverse());
      return o;
    }
    for(t=0;t<(k&3);t++) out=rot(out);
    if(k&4) out=flip(out);
    return out;
  }
  // The plate a name produces. Returned separately from the drawing so the
  // page can print the constant and let the reader add the rows up.
  // 3x3 ONLY, deliberately. A 5x5 was tried first and had to go: on a plate
  // that sits inside a 40-unit-wide chest, five columns leave about six units
  // per cell, and two Thai digits do not fit in six units — the numbers ran
  // into each other and the plate read as texture instead of arithmetic. A
  // claim you cannot check by eye is not worth making. Variety comes from the
  // offset and the eight symmetries (80 plates) plus everything else the body
  // varies by.
  function plate(seed){
    var r=rng(seed);
    var n = 3;
    var add = r(10);                        // 0..9 keeps cells to two digits
    var sym = r(8);
    var g = dihedral(magic(n, add), sym);
    var sum = n*(n*n+1)/2 + n*add;
    return {n:n, add:add, sym:sym, grid:g, sum:sum};
  }

  // --- drawing ------------------------------------------------------------
  function lashing(x,y,w){
    // A cord tie: two crossed strokes and a knot. Drawn, not implied — the
    // lashings are what makes a bundle of laths read as a made object.
    return '<path d="M'+(x-w)+' '+(y-w)+'L'+(x+w)+' '+(y+w)+
           'M'+(x+w)+' '+(y-w)+'L'+(x-w)+' '+(y+w)+'" stroke="'+CORD+
           '" stroke-width="1.7" stroke-linecap="round" fill="none"/>'+
           '<circle cx="'+x+'" cy="'+y+'" r="1.5" fill="'+CORD+'"/>';
  }

  function weave(x,y,w,h,rows,cols){
    // A woven bamboo panel: verticals, then arcing wefts over them.
    var s='', i, t;
    for(i=0;i<=cols;i++){
      t=x-w/2+w*i/cols;
      s+='<path d="M'+t.toFixed(1)+' '+y+'L'+t.toFixed(1)+' '+(y+h)+'"/>';
    }
    for(i=0;i<=rows;i++){
      t=y+h*i/rows;
      s+='<path d="M'+(x-w/2)+' '+t.toFixed(1)+'Q'+x+' '+(t+3.2).toFixed(1)+
         ' '+(x+w/2)+' '+t.toFixed(1)+'"/>';
    }
    return '<g stroke="'+BAMD+'" stroke-width="1.1" fill="none" opacity=".75">'+
           s+'</g>';
  }

  // seed  : the bearer's name (or anything)
  // opts  : {cloth, awake, resting, scale}
  function effigy(seedStr, opts){
    opts = opts || {};
    var seed = hash(seedStr || 'unconsecrated');
    var r = rng(seed ^ 0x9e3779b9);
    var cloth = opts.cloth || '#c8322b';
    var awake = opts.awake !== false;
    var resting = !!opts.resting;
    var P = plate(seed);

    // per-bearer variety, all of it small and structural
    var armUp   = r(3);            // 0 both down, 1 right raised, 2 both out
    var stance  = r(3);            // foot placement
    var topknot = r(2);            // a tuft of cloth at the crown
    var cols    = 4 + r(3);        // weave density
    var rows    = 5 + r(3);
    var faceW   = 26 + r(5);

    // PROPORTIONS. The first version made the trunk 68 units wide against a
    // 34-unit head and it read as a barrel with a face on it. A hun payont is a
    // bundle of laths: narrow, rangy, more upright than wide. Shoulders 46,
    // waist 40, and the plate sized to sit INSIDE that with a margin.
    var SH_Y=162, WA_Y=252, SH_W=23, WA_W=20;

    var s = '';
    // aura — gold when working, ash when resting or unconsecrated
    var aur = resting ? '#8d8d86' : (awake ? GOLD : '#8d8d86');
    s += '<g opacity="'+(resting?0.30:(awake?0.55:0.20))+'">';
    for(var a=0;a<16;a++){
      var ang=a*22.5, rad=ang*Math.PI/180;
      var inr = (a%2 ? 84 : 78), outr = (a%2 ? 96 : 104);
      s += '<path d="M'+(130+Math.sin(rad)*inr).toFixed(1)+' '+
           (176-Math.cos(rad)*inr).toFixed(1)+'L'+
           (130+Math.sin(rad)*outr).toFixed(1)+' '+
           (176-Math.cos(rad)*outr).toFixed(1)+
           '" stroke="'+aur+'" stroke-width="2.6" stroke-linecap="round"/>';
    }
    s += '</g>';

    // --- legs (bamboo laths, planted) ---
    var lf = 112 - stance*7, rf = 148 + stance*7;
    var legs = '<path d="M120 '+WA_Y+'L'+lf+' 336"/><path d="M140 '+WA_Y+'L'+rf+' 336"/>';
    s += '<g stroke="'+BAM+'" stroke-width="6.5" stroke-linecap="round" fill="none">'+
         legs+'</g>'+
         '<g stroke="'+BAMD+'" stroke-width="1.1" fill="none" opacity=".55">'+
         legs+'</g>'+
         // feet: little lashed bundles
         '<rect x="'+(lf-10)+'" y="334" width="20" height="7.5" rx="3" fill="'+BAMD+'"/>'+
         '<rect x="'+(rf-10)+'" y="334" width="20" height="7.5" rx="3" fill="'+BAMD+'"/>';

    // --- arms ---
    // Two segments with an elbow and a lashed hand-bundle at the end. The
    // single straight stick version read as a broken twig poking out of the
    // side, worst of all in the beckoning pose where it ended in mid-air.
    var ax=130-SH_W+3, bx=130+SH_W-3, ay=SH_Y+14;
    var L, R;   // [elbow, hand]
    if(armUp===1){        // นางกวัก — one forearm up, palm forward, beckoning
      L=[[100,206],[96,240]]; R=[[168,204],[176,168]];
    } else if(armUp===2){ // both forearms out, offering
      L=[[100,208],[80,214]]; R=[[160,208],[180,214]];
    } else {              // at rest, hands at the hip
      L=[[98,208],[100,242]]; R=[[162,208],[160,242]];
    }
    function arm(sx,sy,j){
      return '<path d="M'+sx+' '+sy+'L'+j[0][0]+' '+j[0][1]+'L'+j[1][0]+' '+
             j[1][1]+'"/>';
    }
    var arms = arm(ax,ay,L) + arm(bx,ay,R);
    s += '<g stroke="'+BAM+'" stroke-width="6" stroke-linecap="round" '+
         'stroke-linejoin="round" fill="none">'+arms+'</g>'+
         '<g stroke="'+BAMD+'" stroke-width="1" fill="none" opacity=".5" '+
         'stroke-linejoin="round">'+arms+'</g>'+
         // hands
         '<circle cx="'+L[1][0]+'" cy="'+L[1][1]+'" r="4.6" fill="'+BAMD+'"/>'+
         '<circle cx="'+R[1][0]+'" cy="'+R[1][1]+'" r="4.6" fill="'+BAMD+'"/>'+
         lashing(L[0][0],L[0][1],3)+lashing(R[0][0],R[0][1],3);

    // --- torso: a woven cage, tapering to the waist ---
    s += '<path d="M'+(130-SH_W)+' '+SH_Y+'Q130 '+(SH_Y-7)+' '+(130+SH_W)+' '+
         SH_Y+'L'+(130+WA_W)+' '+WA_Y+'Q130 '+(WA_Y+7)+' '+(130-WA_W)+' '+WA_Y+
         'Z" fill="'+BAM+'" stroke="'+BAMD+'" stroke-width="1.6"/>'+
         weave(130, SH_Y+4, SH_W*2-6, WA_Y-SH_Y-8, rows, cols);

    // --- the cloth: a sabai over one shoulder, and a wrap at the waist ---
    // Drawn as a DIAGONAL band, not a horizontal bib. The bib version read as
    // a collar and hid the shoulders entirely.
    s += '<path d="M'+(130-SH_W-1)+' '+(SH_Y+1)+'L'+(130+WA_W)+' '+(WA_Y-14)+
         'L'+(130+WA_W)+' '+(WA_Y-1)+'L'+(130-SH_W+13)+' '+(SH_Y-3)+
         'Z" fill="'+cloth+'" opacity=".92"/>'+
         // waist wrap, over the sabai's lower end
         '<path d="M'+(130-WA_W-1)+' '+(WA_Y-14)+'Q130 '+(WA_Y-5)+' '+
         (130+WA_W+1)+' '+(WA_Y-14)+'L'+(130+WA_W)+' '+(WA_Y)+'Q130 '+
         (WA_Y+9)+' '+(130-WA_W)+' '+(WA_Y)+'Z" fill="'+cloth+'" opacity=".88"/>'+
         // knot and a short sash-end hanging from it
         '<circle cx="'+(130+WA_W-3)+'" cy="'+(WA_Y-6)+'" r="4.4" fill="'+
         cloth+'"/>'+
         '<path d="M'+(130+WA_W-1)+' '+(WA_Y-4)+'q9 9 5 21q-8-7-11-17z" fill="'+
         cloth+'" opacity=".82"/>';

    // --- chest plate: the magic square, sized to sit inside the trunk ---
    var n=P.n, pw=32, px=130-pw/2, py=182, cell=pw/n;
    s += '<rect x="'+px+'" y="'+py+'" width="'+pw+'" height="'+pw+
         '" rx="3" fill="'+PLATE+'" stroke="'+GOLD+'" stroke-width="1.8"/>';
    var gs='';
    for(var i=1;i<n;i++){
      gs+='<path d="M'+(px+cell*i).toFixed(1)+' '+py+'L'+(px+cell*i).toFixed(1)+
          ' '+(py+pw)+'M'+px+' '+(py+cell*i).toFixed(1)+'L'+(px+pw)+' '+
          (py+cell*i).toFixed(1)+'"/>';
    }
    s += '<g stroke="'+GOLDL+'" stroke-width=".7" fill="none">'+gs+'</g>';
    for(var rr=0;rr<n;rr++) for(var cc=0;cc<n;cc++){
      var v = P.grid[rr][cc];
      // Two Thai digits need a smaller face than one, or they run over the
      // cell wall. Measured by eye at the size this actually renders.
      var fs = (v > 9) ? 6.8 : 9.4;
      s += '<text x="'+(px+cell*cc+cell/2).toFixed(1)+'" y="'+
           (py+cell*rr+cell/2+fs*0.36).toFixed(1)+'" text-anchor="middle" '+
           'font-size="'+fs+'" fill="'+INK+'" '+
           'font-family="Thonburi,\'Noto Sans Thai\',sans-serif">'+
           thaiNum(v)+'</text>';
    }

    // --- head ---
    s += '<path d="M130 '+SH_Y+'L130 146" stroke="'+BAM+'" stroke-width="5.5"/>'+
         '<ellipse cx="130" cy="120" rx="'+(faceW/2+2)+'" ry="27" fill="'+BAM+
         '" stroke="'+BAMD+'" stroke-width="1.5"/>';
    // head weave
    s += '<g stroke="'+BAMD+'" stroke-width=".9" fill="none" opacity=".5">'+
         '<path d="M114 104Q130 116 146 104"/><path d="M112 120Q130 131 148 120"/>'+
         '<path d="M114 136Q130 145 146 136"/></g>';
    // face
    if(awake && !resting){
      s += '<ellipse cx="122" cy="120" rx="3.1" ry="3.9" fill="'+INK+'"/>'+
           '<ellipse cx="138" cy="120" rx="3.1" ry="3.9" fill="'+INK+'"/>';
    } else {
      s += '<path d="M118 121Q122 125 126 121M134 121Q138 125 142 121" stroke="'+
           INK+'" stroke-width="1.7" fill="none" stroke-linecap="round"/>';
    }
    s += '<path d="M125 133Q130 137 135 133" stroke="'+INK+
         '" stroke-width="1.5" fill="none" stroke-linecap="round"/>';
    // unalome on the brow — the spiral that straightens
    s += '<path d="M130 108c-4-2-5-7-1-8s5 5 1 7-6-3-2-6 7 1 5 5" stroke="'+GOLD+
         '" stroke-width="1.4" fill="none" stroke-linecap="round"/>'+
         '<path d="M130 102L130 95" stroke="'+GOLD+'" stroke-width="1.4" '+
         'stroke-linecap="round"/>';
    if(topknot){
      s += '<path d="M130 94q-8-6-4-13 5 4 7 0 5 7-3 13z" fill="'+cloth+'"/>';
    }
    s += lashing(130,148,3.6)+lashing(120,WA_Y-2,3.4)+lashing(140,WA_Y-2,3.4);

    // viewBox starts at y=58, not 0: the drawing spans roughly 72..346 and the
    // empty band above the aura was making the figure sit small in its frame.
    return '<svg viewBox="18 58 224 300" class="hunfig" '+
           'xmlns="http://www.w3.org/2000/svg" role="img" '+
           'aria-label="A bamboo effigy in '+
           (resting?'rest':(awake?'working':'unconsecrated'))+
           ', wearing a numbered plate on its chest">'+s+'</svg>';
  }

  return {hash:hash, rng:rng, magic:magic, plate:plate, effigy:effigy,
          thaiNum:thaiNum};
})();
"""


# ------------------------------------------------------------- the wan phra
# THE PUBLISHED THAI CALENDAR, NOT A CALCULATION — and the reason why is a
# measurement, not a preference.
#
# The first two versions of this derived the lunar day from the moon itself:
# once from the elongation angle, once from a mean lunation. Scored against the
# 49 published holy days of 2569/2026 they got 17 and 37 right. That is not a
# bug to tune out. The Thai lunar calendar is ARITHMETIC — fixed alternating
# 29- and 30-day months with intercalation rules — so it deliberately does not
# track the true moon, and no amount of better astronomy will reproduce it.
# 2569 is also an adhikamāsa year, carrying a doubled eighth month (เดือน ๘
# หลัง), which no simple lunation model can know about at all.
#
# So the holy days are a table, exactly like the eclipse table on the moon
# page: when a calculation cannot be right where it runs, do it somewhere it
# can and ship the answer.
#
# Source: Thai PBS's published ปฏิทินวันพระ for 2569
# (https://www.thaipbs.or.th/now/content/3498), cross-checked for July against
# myhora.com. 49 dates, every one of them a wan phra. They are ANCHORS: since
# consecutive holy days are never more than eight days apart and the lunar day
# advances by one each day, every other date in the range is reconstructed by
# counting from the nearest anchor (see expand() in READING_JS). 49 entries
# give all 365 days.
#
# EXTENDING IT: add the next year's published list. That is the whole job —
# nothing else needs touching, and the page reports its own coverage, so an
# out-of-date table announces itself rather than quietly guessing.
WAN_PHRA = {
    "2026-01-03": "w15", "2026-01-11": "n8",  "2026-01-18": "n15",
    "2026-01-26": "w8",  "2026-02-02": "w15", "2026-02-10": "n8",
    "2026-02-16": "n14", "2026-02-24": "w8",  "2026-03-03": "w15",
    "2026-03-11": "n8",  "2026-03-18": "n15", "2026-03-26": "w8",
    "2026-04-02": "w15", "2026-04-10": "n8",  "2026-04-16": "n14",
    "2026-04-24": "w8",  "2026-05-01": "w15", "2026-05-09": "n8",
    "2026-05-16": "n15", "2026-05-24": "w8",  "2026-05-31": "w15",
    "2026-06-08": "n8",  "2026-06-14": "n14", "2026-06-22": "w8",
    "2026-06-29": "w15", "2026-07-07": "n8",  "2026-07-14": "n15",
    "2026-07-22": "w8",  "2026-07-29": "w15", "2026-08-06": "n8",
    "2026-08-13": "n15", "2026-08-21": "w8",  "2026-08-28": "w15",
    "2026-09-05": "n8",  "2026-09-11": "n14", "2026-09-19": "w8",
    "2026-09-26": "w15", "2026-10-04": "n8",  "2026-10-11": "n15",
    "2026-10-19": "w8",  "2026-10-26": "w15", "2026-11-03": "n8",
    "2026-11-09": "n14", "2026-11-17": "w8",  "2026-11-24": "w15",
    "2026-12-02": "n8",  "2026-12-09": "n15", "2026-12-17": "w8",
    "2026-12-24": "w15",
}

# The great days that fall on some of them, named where the calendar names
# them. Shown instead of "a holy day" when they land, because being told it is
# Asalha Puja is worth more than being told it is the fifteenth waxing.
GREAT_DAYS = {
    "2026-03-03": "วันมาฆบูชา · Makha Bucha",
    "2026-05-31": "วันวิสาขบูชา · Visakha Bucha",
    "2026-06-08": "วันอัฏฐมีบูชา · Atthami Bucha",
    "2026-07-29": "วันอาสาฬหบูชา · Asalha Bucha",
    "2026-07-30": "วันเข้าพรรษา · the start of the rains retreat",
    "2026-10-26": "วันออกพรรษา · the end of the rains retreat",
    "2026-11-24": "วันลอยกระทง · Loi Krathong",
}


# ----------------------------------------------------------------- reading
# The day, computed. Nothing here needs the network.
READING_JS = r"""
var READ = (function(){
  var D=Math.PI/180, S=function(x){return Math.sin(x*D)}, DAY=86400000;

  // COPIED VERBATIM from moondial.py's DIAL_JS. Checked there daily against
  // JPL DE440 over 2026-2028: worst error 0.40 deg. If you change one, change
  // both — see the drift note at the top of hunpayont.py.
  function elong(ms){
    var d=(ms-Date.UTC(2000,0,1,12))/DAY;
    var Ms=357.5291092+0.98560028*d;
    var lamS=280.4665+0.98564736*d+1.9146*S(Ms)+0.0200*S(2*Ms);
    var Lm=218.3164477+13.17639648*d,
        Mm=134.9633964+13.06499295*d,
        Dm=297.8501921+12.19074912*d;
    var lamM=Lm+6.289*S(Mm)-1.274*S(Mm-2*Dm)+0.658*S(2*Dm)-0.186*S(Ms)
      -0.059*S(2*Mm-2*Dm)-0.057*S(Mm-2*Dm+Ms)+0.053*S(Mm+2*Dm)
      +0.046*S(2*Dm-Ms)+0.041*S(Mm-Ms)-0.035*S(Dm)-0.031*S(Mm+Ms);
    return ((lamM-lamS)%360+360)%360;
  }

  function key(dt){
    return dt.getFullYear()+'-'+String(dt.getMonth()+1).padStart(2,'0')+'-'+
           String(dt.getDate()).padStart(2,'0');
  }

  // Expand the 49 published anchors into every day they span.
  //
  // Consecutive holy days are never more than eight days apart and the lunar
  // day advances by exactly one per day, so the stretch between two anchors is
  // fully determined by its endpoints — no arithmetic about month lengths, no
  // assumption about where a month breaks. Whether a month closes at แรม ๑๔ or
  // ๑๕ is simply read off the anchor that says so.
  // Every anchor is itself a half-month boundary (ขึ้น ๘ / ขึ้น ๑๕ / แรม ๘ /
  // แรม ๑๔-or-๑๕), so a turnover can only ever happen IMMEDIATELY after an
  // anchor. Between anchors the count just goes up by one a day. That removes
  // all the guesswork: nothing here has to know how long a month is.
  //   after ขึ้น ๑๕      -> แรม ๑, then up
  //   after แรม ๑๔/๑๕   -> ขึ้น ๑, then up
  //   after ขึ้น ๘/แรม ๘ -> same half, then up
  // CAL.bad collects any stretch where walking from one anchor does not land
  // exactly on the next; it should stay empty, and the page's self-test says so.
  var CAL = (function(){
    var keys = Object.keys(WAN_PHRA).sort(), map = {}, bad = [], i;
    function parse(c){ return {waxing:c.charAt(0)==='w', n:+c.slice(1)}; }
    function d(k){ var p=k.split('-'); return new Date(+p[0],+p[1]-1,+p[2],12); }
    for(i=0;i<keys.length;i++){
      var a = parse(WAN_PHRA[keys[i]]);
      map[keys[i]] = {waxing:a.waxing, n:a.n, wanPhra:true};
      if(i+1 >= keys.length) break;
      var t0=d(keys[i]), t1=d(keys[i+1]);
      var gap = Math.round((t1-t0)/DAY), b = parse(WAN_PHRA[keys[i+1]]);
      var cur;
      if(a.waxing && a.n===15)        cur = {waxing:false, n:1};
      else if(!a.waxing && a.n>=14)   cur = {waxing:true,  n:1};
      else                            cur = {waxing:a.waxing, n:a.n+1};
      for(var j=1;j<gap;j++){
        map[key(new Date(t0.getTime()+j*DAY))] =
          {waxing:cur.waxing, n:cur.n, wanPhra:false};
        cur = {waxing:cur.waxing, n:cur.n+1};
      }
      if(cur.waxing!==b.waxing || cur.n!==b.n)
        bad.push(keys[i]+'->'+keys[i+1]);
    }
    return {map:map, bad:bad, first:keys[0], last:keys[keys.length-1]};
  })();

  function lunar(ms){
    var e = elong(ms);
    var dt = new Date(ms), k = key(dt);
    var c = CAL.map[k];
    var out = {elong:e, illum:(1-Math.cos(e*D))/2,
               // waxing/waning comes off the moon itself and is right whether
               // or not the table covers this date
               waxing:(e < 180),
               known:!!c, inRange:(k >= CAL.first && k <= CAL.last),
               great:GREAT_DAYS[k] || '',
               first:CAL.first, last:CAL.last};
    if(c){
      out.waxing = c.waxing; out.n = c.n; out.wanPhra = c.wanPhra;
      out.label = (c.waxing?'ขึ้น ':'แรม ')+c.n+' ค่ำ';
      out.labelEn = (c.waxing?'waxing ':'waning ')+c.n;
    } else {
      // Outside the published table. The moon is still known exactly; the
      // CALENDAR is not, and the page says so rather than printing a ค่ำ
      // number it cannot stand behind.
      out.n = null; out.wanPhra = false;
      out.label = out.waxing ? 'ข้างขึ้น' : 'ข้างแรม';
      out.labelEn = out.waxing ? 'waxing' : 'waning';
    }
    return out;
  }

  // The eight-day week. Wednesday after sunset belongs to Rahu — the boundary
  // is taken as 18:00 local, which is the usual convention and is stated on
  // the page rather than hidden.
  function dayIndex(dt){
    var w = dt.getDay();
    if(w===3 && dt.getHours() >= 18) return 7;
    return w;
  }

  // Which of the eleven themes today draws from. The day-deva decides most of
  // it; the moon and the effigy's own forging-date override.
  function themeFor(dt, forgedDay){
    var L = lunar(dt.getTime());
    // It rests on the four wan phra of the lunar month AND on any named
    // observance, even one that is not itself a wan phra.
    //
    // That second clause was missing and it showed. วันเข้าพรรษา, the start of
    // the rains retreat, falls on แรม ๑ ค่ำ — the day AFTER Asalha Bucha — so
    // it is not one of the four. The effigy would have printed the name of the
    // holy day across the top of the card and then sold you an amulet under
    // it, which is worse than either resting or saying nothing. Six of the
    // seven named days already fall on a wan phra; this is the seventh.
    if(L.wanPhra || L.great)
      return {key:null, reason:'wanphra', lunar:L, observance:!L.wanPhra};
    var di = dayIndex(dt);
    // Once a lunar month, on the day of the month it was forged, an effigy
    // fetches one of its own kind.
    if(forgedDay && dt.getDate() === forgedDay)
      return {key:'self', reason:'birthday', lunar:L, day:di};
    // Full and new moon lean on growth / letting go before the day-deva does.
    if(L.n===15 && L.waxing)  return {key:'growth',  reason:'full', lunar:L, day:di};
    if(L.n===15 && !L.waxing) return {key:'binding', reason:'new',  lunar:L, day:di};
    return {key:DAYS[di].theme, reason:'day', lunar:L, day:di};
  }

  return {elong:elong, lunar:lunar, dayIndex:dayIndex, themeFor:themeFor,
          CAL:CAL};
})();
"""


# ------------------------------------------------------------------- khata
# Link-template presets. The VERIFIED line states exactly what is known, in
# itself — see the module docstring for why none of these is hard-coded as
# fact. Most bearers should never read them at all: the "learn it from a link
# you already have" box above the picker does the job without anyone having to
# understand what a template is.
KHATA_PRESETS = [
    {"id": "none",
     "name": "Not consecrated — plain links",
     "nameTh": "ยังไม่ปลุกเสก — ลิงก์ธรรมดา",
     "tpl": "{url}",
     "status": "This earns nothing, and that is the right default: an effigy "
               "nobody has spoken over does not work.",
     "statusTh": "แบบนี้ไม่ได้เงิน และนี่คือค่าเริ่มต้นตามจริง — "
                 "หุ่นที่ยังไม่มีใครปลุกเสกก็ยังทำงานไม่ได้",
     "verified": "n/a", "verifiedTh": "ไม่เกี่ยว"},
    {"id": "suffix",
     "name": "Add a tag to the end (?sub_aff_id=…)",
     "nameTh": "เติมรหัสต่อท้ายลิงก์ (?sub_aff_id=…)",
     "tpl": "{url}?sub_aff_id=YOURID",
     "status": "The simplest shape: your id as a query parameter on the "
               "product url. Works with programmes that track by sub-id.",
     "statusTh": "แบบง่ายที่สุด: ใส่รหัสของคุณต่อท้าย url ของสินค้า "
                 "ใช้ได้กับโปรแกรมที่ติดตามด้วย sub-id",
     "verified": "shape only — check it against your dashboard",
     "verifiedTh": "ยืนยันแค่รูปแบบ — กรุณาตรวจกับแดชบอร์ดของคุณเอง"},
    {"id": "wrap",
     "name": "Wrap the url in a redirector",
     "nameTh": "ห่อ url ด้วยตัวเปลี่ยนทาง (redirector)",
     "tpl": "https://YOURNETWORK/deeplink?aff_id=YOURID&url={urlenc}",
     "status": "The shape most Southeast Asian networks use for deep links: "
               "your redirector, your id, and the destination url-encoded. "
               "Involve Asia, which runs Lazada Thailand's programme, uses a "
               "wrapper of this kind.",
     "statusTh": "รูปแบบที่เครือข่ายในเอเชียตะวันออกเฉียงใต้ส่วนใหญ่ใช้ "
                 "คือ redirector ของคุณ + รหัสของคุณ + ปลายทางที่เข้ารหัส url "
                 "แล้ว — Involve Asia ซึ่งดูแลโปรแกรมของ Lazada ไทย "
                 "ก็ใช้แบบนี้",
     "verified": "NOT verified — their exact grammar is not publicly "
                 "documented, and Lazada changed link generation recently. "
                 "Paste one real link from your own dashboard above and let "
                 "it work the shape out.",
     "verifiedTh": "ยังไม่ได้ยืนยัน — ทางนั้นไม่ได้เปิดเผยรูปแบบที่แน่นอน "
                   "และ Lazada เพิ่งเปลี่ยนวิธีสร้างลิงก์ "
                   "แนะนำให้วางลิงก์จริงจากแดชบอร์ดของคุณในช่องด้านบน "
                   "แล้วให้มันถอดรูปแบบเอง"},
    {"id": "custom",
     "name": "Custom — paste your own",
     "nameTh": "กำหนดเอง — วางของคุณเอง",
     "tpl": "",
     "status": "Anything. {url} is the product address, {urlenc} the same "
               "url-encoded, {id} the listing's id in this catalogue.",
     "statusTh": "อะไรก็ได้ — {url} คือที่อยู่สินค้า, {urlenc} "
                 "คืออันเดียวกันแบบเข้ารหัส url, {id} คือเลขที่รายการในคลังนี้",
     "verified": "you tell it", "verifiedTh": "คุณเป็นคนบอกมันเอง"},
]

LINE_ID = "defiant.to"
LINE_URL = "https://line.me/ti/p/~" + LINE_ID

# ---------------------------------------------------------------------- i18n
# Every string the widget draws at runtime, in both languages. The page's long
# prose is NOT here — it lives in _essay(), written separately in each language
# rather than translated, because a translated essay reads like one.
#
# Thai is not a second-class column: it is the default when the browser asks
# for Thai, the toggle remembers, and the choice rides inside the embed payload
# so a bearer who forges in Thai hands out a Thai widget.
T = {
    "title":      ("หุ่นพยนต์ · Hun Payont", "หุ่นพยนต์"),
    "tagline":    ("An effigy you forge, consecrate and carry. It walks to the "
                   "market every morning and brings back one thing — and the "
                   "link it brings back is wearing your name, not ours.",
                   "หุ่นที่คุณสร้างเอง ปลุกเสกเอง แล้วพกติดตัว "
                   "ทุกเช้ามันจะออกไปตลาดแล้วกลับมาพร้อมของหนึ่งชิ้น "
                   "และลิงก์ที่มันถือกลับมาก็เป็นชื่อของคุณ ไม่ใช่ของเรา"),
    # states
    "working":    ("working", "กำลังทำงาน"),
    "resting":    ("resting", "หยุดพัก"),
    "cold":       ("not consecrated", "ยังไม่ปลุกเสก"),
    "noname":     ("ยังไม่ได้ตั้งชื่อ", "ยังไม่ได้ตั้งชื่อ"),
    "nonameSub":  ("no name yet — it cannot be sent anywhere",
                   "ยังไม่มีชื่อ — ยังใช้งานไม่ได้"),
    "bornOn":     ("born", "เกิดวัน"),
    "clothOf":    ("cloth", "ผ้าสี"),
    "plateLine":  ("plate: 3×3, every row, column and diagonal sums to",
                   "แผ่นยันต์ ๓×๓ — ทุกแถว ทุกหลัก และทุกแนวทแยง รวมได้"),
    # the day
    "wear":       ("wear", "ใส่"),
    "moonLit":    ("lit", "สว่าง"),
    "holyDay":    ("holy day", "วันพระ"),
    "restingMsg": ("The effigy is standing still today and has nothing to sell "
                   "you. It will go out again tomorrow.",
                   "วันนี้หุ่นหยุดนิ่ง ไม่มีอะไรจะขายคุณ "
                   "พรุ่งนี้จึงจะออกไปใหม่"),
    "itIsWanPhra": ("It is wan phra.", "วันนี้เป็นวันพระ"),
    "itIsHolyDay": ("Today is a day of observance.", "วันนี้เป็นวันสำคัญทางศาสนา"),
    "calNote":    ("The published Thai calendar in this copy covers {a} to {b}. "
                   "Outside it the moon is still exact, but the lunar day and "
                   "the holy days are not known here, so none are claimed — "
                   "your wat’s calendar is the one that counts.",
                   "ปฏิทินไทยที่ฝังมากับสำเนานี้ครอบคลุม {a} ถึง {b} "
                   "นอกช่วงนี้ดวงจันทร์ยังคำนวณได้แม่นยำ "
                   "แต่วันขึ้น-แรมและวันพระไม่ทราบ จึงไม่ขอเดา — "
                   "ให้ยึดปฏิทินของวัดเป็นหลัก"),
    # the errand
    "goLook":     ("Go and look →", "ไปดูเลย →"),
    "plainLink":  ("This link is plain — the effigy has no khata yet, so it "
                   "earns nothing.",
                   "ลิงก์นี้เป็นลิงก์เปล่า — หุ่นยังไม่มีคาถา จึงยังไม่ได้เงิน"),
    "forgedDay":  ("the day it was forged", "วันที่สร้างมันขึ้นมา"),
    "fullMoon":   ("full moon", "จันทร์เพ็ญ"),
    "darkMoon":   ("dark moon", "จันทร์ดับ"),
    # the forge
    "forgeH":     ("Forge one", "สร้างหุ่นของคุณ"),
    "forgeLede":  ("Nothing here is sent anywhere. It is written to this "
                   "browser and into the link you copy — that is the whole of "
                   "the storage.",
                   "ไม่มีอะไรถูกส่งออกไปไหน ทุกอย่างเก็บไว้ในเบราว์เซอร์นี้ "
                   "และฝังอยู่ในลิงก์ที่คุณคัดลอก — เก็บอยู่แค่นั้นจริงๆ"),
    "step1":      ("Name it", "ตั้งชื่อ"),
    "step2":      ("Give it your khata", "ให้คาถาแก่มัน"),
    "step3":      ("Carry it", "พกมันไป"),
    "fName":      ("Its name", "ชื่อของมัน"),
    "fNameHint":  ("The name seeds the body, the stance and the square on its "
                   "chest. Change a letter and you get a different effigy.",
                   "ชื่อเป็นตัวกำหนดรูปร่าง ท่ายืน และตารางยันต์บนอก "
                   "เปลี่ยนตัวอักษรเดียวก็ได้หุ่นคนละตัว"),
    "fNamePh":    ("what you will call it", "จะเรียกมันว่าอะไร"),
    "fBorn":      ("The day you were born", "คุณเกิดวันอะไร"),
    "fBornHint":  ("Sets the colour of its cloth — your lifelong colour, not "
                   "today’s.",
                   "กำหนดสีผ้าของมัน — สีประจำตัวคุณตลอดชีวิต ไม่ใช่สีของวันนี้"),
    "learnH":     ("The easy way", "วิธีที่ง่ายที่สุด"),
    "learnLede":  ("Paste one affiliate link you already have — any product, "
                   "from your own dashboard — and it will work out the shape "
                   "by itself. You never have to learn what a template is.",
                   "วางลิงก์แอฟฟิลิเอตที่คุณมีอยู่แล้วสักอันหนึ่ง "
                   "สินค้าอะไรก็ได้ จากแดชบอร์ดของคุณเอง "
                   "แล้วมันจะถอดรูปแบบให้เอง "
                   "คุณไม่ต้องเข้าใจเลยว่าเทมเพลตคืออะไร"),
    "learnPh":    ("paste a working affiliate link here",
                   "วางลิงก์แอฟฟิลิเอตที่ใช้งานได้ตรงนี้"),
    "learnBtn":   ("Learn it", "ถอดรูปแบบ"),
    "learnOk":    ("Learned it. Check the address below before you trust it.",
                   "ถอดรูปแบบสำเร็จ — กรุณาตรวจที่อยู่ด้านล่างก่อนใช้งานจริง"),
    "learnNo":    ("Could not find the destination inside that link. Short "
                   "links (s.lazada.co.th/…) hide it, so paste a full one, or "
                   "set the shape by hand below.",
                   "หาปลายทางในลิงก์นั้นไม่เจอ ลิงก์ย่อ (s.lazada.co.th/…) "
                   "จะซ่อนไว้ ลองวางลิงก์เต็ม "
                   "หรือกำหนดรูปแบบเองด้านล่างก็ได้"),
    "advanced":   ("Set the shape by hand", "กำหนดรูปแบบเอง"),
    "fPreset":    ("Its khata", "คาถาของมัน"),
    "fTpl":       ("The words", "บทคาถา"),
    "fTplHint":   ("{url} is the product address · {urlenc} the same "
                   "url-encoded · {id} the listing’s id here.",
                   "{url} คือที่อยู่สินค้า · {urlenc} "
                   "คืออันเดียวกันแบบเข้ารหัส url · {id} คือเลขที่รายการในคลังนี้"),
    "verifiedLbl": ("Verified:", "สถานะการยืนยัน:"),
    "checkThis":  ("Check this before you trust it — this is the exact address "
                   "it will send people to:",
                   "ตรวจตรงนี้ก่อนใช้จริง — "
                   "นี่คือที่อยู่ที่มันจะพาคนไปจริงๆ"),
    "unmake":     ("Unmake it", "ลบหุ่นทิ้ง"),
    "unmakeAsk":  ("Unmake the effigy? Its name, khata and ledger are erased "
                   "from this browser. Nothing else anywhere is affected.",
                   "ลบหุ่นตัวนี้ทิ้งหรือไม่? ชื่อ คาถา และสมุดบัญชี "
                   "จะถูกลบออกจากเบราว์เซอร์นี้ ไม่กระทบอย่างอื่นที่ใด"),
    # sharing
    "shareH":     ("Share it", "แชร์"),
    "shareLede":  ("Once it has a name, your effigy has its own address. "
                   "Everything below shares that — so whoever opens it meets "
                   "YOUR effigy, working under your khata.",
                   "พอมันมีชื่อ หุ่นของคุณก็จะมีที่อยู่ของตัวเอง "
                   "ทุกปุ่มด้านล่างแชร์ที่อยู่นั้น "
                   "ใครเปิดก็จะเจอหุ่นของคุณ ที่ทำงานด้วยคาถาของคุณ"),
    "yourLink":   ("Your effigy’s own link", "ลิงก์ประจำหุ่นของคุณ"),
    "copyLink":   ("Copy the link", "คัดลอกลิงก์"),
    "copyEmbed":  ("Copy the embed code", "คัดลอกโค้ดฝังเว็บ"),
    "embedHint":  ("Paste this anywhere that takes HTML — a blog, a shop page, "
                   "a Wordpress or Wix block. It carries its own name and "
                   "khata: no script, no account, no callback.",
                   "วางโค้ดนี้ได้ทุกที่ที่รับ HTML — บล็อก หน้าร้าน "
                   "บล็อกใน WordPress หรือ Wix "
                   "มันพกชื่อและคาถาของตัวเองไปด้วย ไม่ต้องมีสคริปต์ "
                   "ไม่ต้องสมัคร ไม่มีการเรียกกลับ"),
    "nativeShare": ("Share…", "แชร์…"),
    "dlSvg":      ("Download the effigy (SVG)", "ดาวน์โหลดรูปหุ่น (SVG)"),
    "dlAll":      ("The whole thing, one file", "ทั้งหมดในไฟล์เดียว"),
    "shareText":  ("I forged a hun payont — an effigy that reads the day and "
                   "goes to market. Make your own:",
                   "ผม/ดิฉันสร้างหุ่นพยนต์ตัวหนึ่ง "
                   "มันอ่านวันแล้วออกไปตลาดให้ ลองสร้างของคุณเองดู:"),
    "copied":     ("✓ copied", "✓ คัดลอกแล้ว"),
    "forgeFirst": ("Name it first, and this becomes your own effigy’s link.",
                   "ตั้งชื่อก่อน แล้วตรงนี้จะกลายเป็นลิงก์ของหุ่นคุณเอง"),
    # ledger
    "ledgerH":    ("Its ledger", "สมุดบัญชีของมัน"),
    "ledgerLede": ("Counted in this browser only, and never sent anywhere. It "
                   "counts knocks, not coins — the coins are counted by your "
                   "network, which is the only thing in a position to count "
                   "them.",
                   "นับอยู่ในเบราว์เซอร์นี้เท่านั้น และไม่ส่งไปไหนทั้งนั้น "
                   "มันนับ “การเคาะประตู” ไม่ได้นับเงิน "
                   "เพราะคนที่นับเงินได้จริงคือเครือข่ายของคุณเท่านั้น"),
    "lDays":      ("days it has stood", "วันที่มันยืนอยู่"),
    "lKnocks":    ("knocks — clicks through", "การเคาะประตู — จำนวนคลิก"),
    "lConsec":    ("consecrated", "ปลุกเสกแล้ว"),
    "lSince":     ("counting since", "นับตั้งแต่"),
    "yes":        ("yes", "แล้ว"),
    "no":         ("no", "ยัง"),
    # LINE
    "lineH":      ("Talk to the maker on LINE", "คุยกับคนทำได้ทาง LINE"),
    "lineLede":   ("Questions, a khata that will not behave, or you want one "
                   "forged for your shop — add the ID and say so.",
                   "มีคำถาม คาถาไม่ยอมทำงาน "
                   "หรืออยากให้ช่วยสร้างหุ่นให้ร้านของคุณ "
                   "แอดไอดีมาคุยได้เลย"),
    "lineAdd":    ("Add on LINE", "แอดเพื่อนใน LINE"),
    "lineCopy":   ("Copy the LINE ID", "คัดลอกไอดี LINE"),
    "lineShare":  ("Send this to a friend on LINE", "ส่งให้เพื่อนทาง LINE"),
    # mode switch
    "modeHun":     ("Hun Payont", "หุ่นพยนต์"),
    "modeSukhwan": ("สู่ขวัญ · Name charm", "สู่ขวัญ"),
    # สู่ขวัญ mode
    "skH":        ("A name-charm, said daily", "คำเรียกขวัญ พูดทุกวัน"),
    "skLede":     ("Type one or more names and the whole chant appears, every "
                   "verse carrying the name(s) you gave it. Today's verse is "
                   "marked — chosen the same fixed way the hun payont picks "
                   "its own daily errand, by the date and the name, not by "
                   "chance you can refresh away.",
                   "พิมพ์ชื่อหนึ่งชื่อหรือมากกว่านั้น แล้วคำเรียกขวัญทั้งบทจะปรากฏ "
                   "ทุกบทมีชื่อที่คุณให้ไว้ บทของวันนี้จะถูกทำเครื่องหมายไว้ "
                   "— เลือกด้วยวิธีเดียวกับที่หุ่นพยนต์เลือกวันของมันเอง "
                   "จากวันที่และชื่อ ไม่ใช่การสุ่มที่รีเฟรชแล้วเปลี่ยนได้"),
    "skNamesH":   ("Name(s)", "ชื่อ"),
    "skNamesPh":  ("one name per line — your own, a friend's, all of them",
                   "ชื่อบรรทัดละหนึ่งชื่อ — ของคุณเอง ของเพื่อน หรือทุกชื่อที่มี"),
    "skPrivacy":  ("Kept only in this browser, or inside a link you choose to "
                   "copy. Never sent anywhere — there is no server on this "
                   "page to send it to.",
                   "เก็บไว้ในเบราว์เซอร์นี้เท่านั้น หรืออยู่ในลิงก์ที่คุณคัดลอกเอง "
                   "ไม่มีการส่งไปที่ไหนทั้งนั้น เพราะหน้านี้ไม่มีเซิร์ฟเวอร์ให้ส่งไปหา"),
    "skEmpty":    ("Type a name above to read the whole chant.",
                   "พิมพ์ชื่อด้านบนเพื่ออ่านคำเรียกขวัญทั้งบท"),
    "skToday":    ("Today's verse", "บทของวันนี้"),
    "skShareH":   ("Share this charm", "แบ่งปันคำเรียกขวัญนี้"),
    "skShareLede": ("The link carries the name(s) with it — open it on a "
                    "different browser and the same charm appears there, for "
                    "as long as this page exists.",
                    "ลิงก์นี้พกชื่อไปด้วย เปิดจากเบราว์เซอร์ไหนก็เจอคำเรียกขวัญเดียวกัน "
                    "ตราบเท่าที่หน้านี้ยังอยู่"),
    "skShareText": ("A daily name-charm, drawn from su khwan (สู่ขวัญ) — try "
                     "your own name:",
                     "คำเรียกขวัญประจำวัน จากธรรมเนียมสู่ขวัญ — ลองใส่ชื่อของคุณดู:"),
}


CSS = """
  /* Thai needs a taller line and a real Thai face; Sarabun/Noto ship on most
     Thai devices and Thonburi is on every Mac. Applied to the whole page when
     Thai is on, not just to Thai runs, because the layout has to breathe. */
  body[data-lang=th]{font-family:"Sarabun","Noto Sans Thai",Thonburi,
    "Sukhumvit Set",-apple-system,Segoe UI,Roboto,Arial,sans-serif;
    line-height:1.75}
  body[data-lang=th] .sheet p,body[data-lang=th] .sheet li{line-height:1.85}
  body[data-lang=th] h1,body[data-lang=th] h2,body[data-lang=th] h3{
    line-height:1.4}
  .th-only{display:none}
  body[data-lang=th] .th-only{display:block}
  body[data-lang=th] .en-only{display:none}
  span.th-only{display:none}
  body[data-lang=th] span.th-only{display:inline}
  body[data-lang=th] span.en-only{display:none}

  .langbar{display:flex;gap:0;align-items:center;margin:0 0 14px;
    border:1px solid var(--line);border-radius:999px;overflow:hidden;
    width:max-content;background:#fff}
  .langbar button{font:inherit;font-size:14px;font-weight:750;padding:7px 18px;
    border:0;background:#fff;color:var(--muted);cursor:pointer}
  .langbar button[aria-pressed=true]{background:var(--teal);color:#fff}

  .modebar{display:flex;gap:0;align-items:center;margin:0 0 14px;
    border:1px solid var(--line);border-radius:999px;overflow:hidden;
    width:max-content;background:#fff}
  .modebar button{font:inherit;font-size:14px;font-weight:750;padding:7px 18px;
    border:0;background:#fff;color:var(--muted);cursor:pointer}
  .modebar button[aria-pressed=true]{background:#b8892f;color:#fff}
  /* Both mode-panes are always in the DOM (so a search engine or a saved
     offline copy sees both tools); only CSS decides which one shows. */
  body[data-mode=hun] .sk-pane{display:none}
  body[data-mode=sukhwan] .hun-pane{display:none}

  .skstage{background:linear-gradient(180deg,#f7f2e6,#efe7d4);
    border:1px solid #ddd0b0;border-radius:16px;padding:22px 24px;
    margin:0 0 20px}
  .skchant{list-style:none;margin:0;padding:0;counter-reset:skverse}
  .skverse{counter-increment:skverse;padding:14px 0;
    border-bottom:1px solid rgba(61,47,22,.12)}
  .skverse:last-child{border-bottom:0}
  .skverse::before{content:counter(skverse);font:600 12px/1 ui-monospace,
    Menlo,monospace;opacity:.4;display:block;margin:0 0 6px}
  .skverse.sktoday{background:rgba(184,137,47,.10);margin:0 -16px;
    padding:14px 16px;border-radius:10px;border-bottom:0}
  .sktodaytag{display:inline-block;font:700 11px/1 ui-monospace,Menlo,monospace;
    letter-spacing:.06em;text-transform:uppercase;color:#b8892f;
    margin:0 0 8px}
  .skline{margin:0;font-family:var(--serif);font-size:18px;line-height:1.55;
    color:#3d2f16;quotes:none}
  .sktranslit{margin:10px 0 0;font-style:italic;opacity:.7;font-size:14px}
  .skgloss{margin:4px 0 0;opacity:.6;font-size:13px}
  .skempty{margin:0;opacity:.65;text-align:center}
  .skforge textarea{width:100%;min-height:72px;font:inherit;font-size:15px;
    padding:10px 12px;border:1px solid var(--line);border-radius:8px;
    resize:vertical}
  .skprivacy{font-size:13px;opacity:.65;margin:8px 0 0}
  .sknote{font-size:13px;opacity:.65;margin:10px 0 0;line-height:1.6}

  .hunwrap{display:grid;grid-template-columns:minmax(0,320px) minmax(0,1fr);
    gap:30px;align-items:start;margin:6px 0 30px}
  @media(max-width:820px){.hunwrap{grid-template-columns:1fr}}
  .hunstage{background:linear-gradient(180deg,#f7f2e6,#efe7d4);
    border:1px solid #ddd0b0;border-radius:16px;padding:12px 12px 6px;
    text-align:center;position:relative}
  .hunfig{width:100%;max-width:290px;height:auto;display:block;margin:0 auto}
  .hunname{font-family:var(--serif);font-size:20px;margin:2px 0 0;color:#3d2f16}
  body[data-lang=th] .hunname{font-family:inherit;font-weight:700}
  .hunsub{font-size:13px;color:#7a6a48;margin:1px 0 8px}
  .hunsq{font-size:12.5px;color:#7a6a48;margin:0 0 8px}
  .hunsq b{color:#3d2f16}
  .hunstate{position:absolute;top:10px;right:10px;font-size:11px;font-weight:800;
    letter-spacing:.06em;text-transform:uppercase;border-radius:999px;
    padding:4px 10px}
  .st-work{background:#e7f2ea;color:#0f6b3f;border:1px solid #b6d9c4}
  .st-rest{background:#efe9f6;color:#4b3a63;border:1px solid #cfc2e0}
  .st-cold{background:#efeeea;color:#6b6558;border:1px solid #d8d3c6}

  .hunday{background:#fff;border:1px solid var(--line);border-radius:14px;
    padding:16px 18px;margin:0 0 14px}
  .hunday h3{margin:0 0 2px;font-size:20px;font-family:var(--serif)}
  body[data-lang=th] .hunday h3{font-family:inherit}
  .hunday .devline{color:var(--muted);font-size:15px;margin:0 0 10px}
  .hunfacts{display:flex;gap:8px;flex-wrap:wrap;margin:0 0 4px}
  .hunfacts span{font-size:13px;background:#f4f2ec;border:1px solid #e2ded1;
    border-radius:999px;padding:4px 11px;color:#4a4436}
  .hunfacts span b{color:var(--ink)}
  .swatch{display:inline-block;width:11px;height:11px;border-radius:3px;
    vertical-align:-1px;margin-right:5px;border:1px solid #00000022}
  .greatday{margin:8px 0 0;font-weight:700;color:var(--gold);font-size:15px}
  .calnote{margin:9px 0 0;font-size:13px;color:var(--muted);line-height:1.5}

  .errand{display:grid;grid-template-columns:88px minmax(0,1fr);gap:14px;
    background:#fff;border:1px solid var(--line);border-radius:14px;padding:14px;
    align-items:start}
  .errand img{width:88px;height:88px;object-fit:cover;border-radius:9px;
    border:1px solid var(--line);background:#f4f2ec}
  .errand .why{font-size:12px;text-transform:uppercase;letter-spacing:.06em;
    font-weight:800;color:var(--gold);margin:0 0 3px}
  .errand h4{margin:0 0 5px;font-size:16px;line-height:1.35;font-weight:650}
  .errand h4 a{color:var(--focus);text-decoration:none}
  .errand h4 a:hover{text-decoration:underline}
  .errand .price{font-weight:800;font-size:17px;color:var(--ink)}
  .errand .go{display:inline-block;margin-top:8px;background:var(--teal);
    color:#fff;text-decoration:none;border-radius:9px;padding:8px 15px;
    font-weight:750;font-size:14px}
  .errand .go:hover{filter:brightness(1.08)}
  .errand .plain{font-size:12.5px;color:var(--muted);margin:7px 0 0}
  .resting{background:#f7f4fb;border:1px solid #ddd2ea;border-radius:14px;
    padding:16px 18px;color:#40325a}
  .resting b{color:#2e2044}

  /* the forge, as three numbered steps */
  .forge{background:#fff;border:1px solid var(--line);border-radius:14px;
    padding:18px;margin:22px 0}
  .forge h3{margin:0 0 4px;font-size:20px;font-family:var(--serif)}
  body[data-lang=th] .forge h3{font-family:inherit}
  .forge p.lede{margin:0 0 16px;color:var(--muted);font-size:15px}
  .step{border-top:1px solid var(--line);padding:16px 0 4px}
  .step:first-of-type{border-top:0;padding-top:0}
  .steph{display:flex;align-items:center;gap:10px;margin:0 0 12px}
  .stepn{flex:0 0 26px;height:26px;border-radius:50%;background:var(--teal);
    color:#fff;font-weight:800;font-size:14px;display:flex;align-items:center;
    justify-content:center}
  .steph b{font-size:17px}
  .frow{display:grid;grid-template-columns:170px minmax(0,1fr);gap:12px;
    align-items:center;margin:0 0 11px}
  @media(max-width:620px){.frow{grid-template-columns:1fr;gap:4px}}
  .frow label{font-weight:700;font-size:14.5px}
  .frow input,.frow select{width:100%;font-size:16px;padding:10px 11px;
    border:1px solid var(--line);border-radius:8px;background:#fff;
    color:var(--ink);font-family:inherit}
  .frow .hint{grid-column:1/-1;font-size:13px;color:var(--muted);margin:-4px 0 0}
  .learn{background:#f7f4ea;border:1px solid #e5dcc4;border-radius:11px;
    padding:13px 15px;margin:0 0 14px}
  .learn b.lh{font-size:15.5px}
  .learn p{margin:5px 0 10px;font-size:14px;color:#5d5340;line-height:1.6}
  .learnrow{display:flex;gap:8px;flex-wrap:wrap}
  .learnrow input{flex:1 1 260px;font-size:15px;padding:10px 11px;
    border:1px solid var(--line);border-radius:8px;font-family:inherit}
  .learnmsg{margin:9px 0 0;font-size:13.5px;font-weight:650}
  .learnmsg.ok{color:#0f6b3f}
  .learnmsg.no{color:#7a1f1f}
  details.adv{margin:4px 0 0}
  details.adv>summary{cursor:pointer;font-weight:700;font-size:14.5px;
    color:var(--focus);padding:6px 0}
  .kstat{font-size:13.5px;border-radius:9px;padding:9px 12px;margin:8px 0 12px;
    background:#fbf1dc;border:1px solid #e5cf9a;color:#6b4a00;line-height:1.55}
  .kstat.bad{background:#fbe6e6;border-color:#e9c4c4;color:#7a1f1f}
  .preview{font:12.5px/1.5 ui-monospace,Menlo,monospace;word-break:break-all;
    background:#f4f2ec;border:1px solid #e2ded1;border-radius:8px;padding:9px 11px;
    color:#3a3428;margin:0 0 12px}
  .btnrow{display:flex;gap:9px;flex-wrap:wrap;margin:6px 0 0}
  .btnrow button,.btnrow a{font:inherit;font-size:14px;font-weight:700;
    padding:10px 16px;border-radius:9px;cursor:pointer;
    border:1px solid var(--line);background:#fff;color:var(--ink);
    text-decoration:none}
  .btnrow button.pri{background:var(--teal);color:#fff;border-color:transparent}
  .btnrow button.pri:hover{filter:brightness(1.08)}

  /* the plain-words explainer */
  .howto{background:#fff;border:1px solid var(--line);border-radius:14px;
    padding:18px;margin:0 0 22px}
  .howto h3{margin:0 0 14px;font-size:20px;font-family:var(--serif)}
  body[data-lang=th] .howto h3{font-family:inherit}
  .hsteps{display:grid;grid-template-columns:repeat(auto-fit,minmax(230px,1fr));
    gap:14px;margin:0 0 16px}
  .hstep{background:#f7f5ef;border:1px solid #e6e1d3;border-radius:11px;
    padding:13px 15px}
  .hstep .hn{display:inline-flex;align-items:center;justify-content:center;
    width:24px;height:24px;border-radius:50%;background:var(--teal);color:#fff;
    font-weight:800;font-size:13px;margin:0 8px 6px 0;vertical-align:-4px}
  .hstep b{font-size:15.5px}
  .hstep p{margin:6px 0 0;font-size:14px;color:#4a4436;line-height:1.6}
  .warnbox{background:#fbf1dc;border:2px solid #e5cf9a;border-radius:11px;
    padding:14px 16px;margin:0 0 14px;color:#6b4a00}
  .warnbox b{color:#5a3d00}
  .warnbox p{margin:7px 0 0;font-size:14.5px;line-height:1.65}
  .warnbox a{color:#6b4a00}
  details.noaff{margin:0 0 14px;background:#f7f5ef;border:1px solid #e6e1d3;
    border-radius:11px;padding:10px 15px}
  details.noaff>summary{cursor:pointer;font-weight:700;font-size:15px;
    color:var(--focus)}
  details.noaff p{margin:9px 0 0;font-size:14px;line-height:1.65;color:#4a4436}
  details.noaff p.nb{color:var(--muted);font-size:13px}
  .worked{background:#f4f2ec;border:1px solid #e2ded1;border-radius:11px;
    padding:13px 15px}
  .worked>b{font-size:15px}
  .wrow{display:grid;grid-template-columns:150px minmax(0,1fr);gap:12px;
    align-items:baseline;margin:9px 0 0}
  @media(max-width:620px){.wrow{grid-template-columns:1fr;gap:2px}}
  .wrow .wl{font-size:12.5px;text-transform:uppercase;letter-spacing:.05em;
    font-weight:800;color:var(--muted)}
  body[data-lang=th] .wrow .wl{text-transform:none;letter-spacing:0;
    font-size:13.5px}
  .wrow code{font:12.5px/1.6 ui-monospace,Menlo,monospace;word-break:break-all;
    color:#3a3428}
  .wrow code b{color:#0f6b3f}
  .wrow code i{color:var(--focus);font-style:normal}
  .wrow .wt{font-size:14.5px;color:#3a3428;line-height:1.6}

  /* share/embed split: a link is the front door, code is behind a door */
  .sharesplit{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));
    gap:14px;margin:8px 0 0}
  .swaycard{background:#f7f5ef;border:1px solid #e6e1d3;border-radius:11px;
    padding:14px 16px}
  .swaycard b{font-size:15.5px}
  .swaycard p{margin:6px 0 10px;font-size:14px;color:#4a4436;line-height:1.6}
  details.embedwrap{margin:12px 0 0;background:#f4f2ec;border:1px solid #e2ded1;
    border-radius:11px;padding:11px 15px}
  details.embedwrap>summary{cursor:pointer;font-weight:700;font-size:15px;
    color:var(--focus)}
  details.embedwrap p{margin:9px 0 0;font-size:14px;line-height:1.65;
    color:#4a4436}
  details.embedwrap ul{margin:8px 0 0 20px;font-size:14px;line-height:1.7;
    color:#4a4436}
  .grouphead{font-size:13px;text-transform:uppercase;letter-spacing:.06em;
    font-weight:800;color:var(--muted);margin:16px 0 2px}
  body[data-lang=th] .grouphead{text-transform:none;letter-spacing:0;
    font-size:14.5px}
  .groupnote{font-size:13.5px;color:var(--muted);margin:0 0 8px;line-height:1.55}

  .embedbox{margin:14px 0 0}
  .embedbox textarea{width:100%;min-height:84px;font:12.5px/1.5 ui-monospace,
    Menlo,monospace;padding:10px;border:1px solid var(--line);border-radius:9px;
    background:#f4f2ec;color:#3a3428;resize:vertical}

  /* the share panel */
  .sharepanel{background:#fff;border:1px solid var(--line);border-radius:14px;
    padding:18px;margin:22px 0}
  .sharepanel h3{margin:0 0 4px;font-size:20px;font-family:var(--serif)}
  body[data-lang=th] .sharepanel h3{font-family:inherit}
  .sharepanel p.lede{margin:0 0 14px;color:var(--muted);font-size:15px}
  .permalink{display:flex;gap:8px;flex-wrap:wrap;align-items:center;
    margin:0 0 14px}
  .permalink input{flex:1 1 320px;font:13px/1.5 ui-monospace,Menlo,monospace;
    padding:10px 11px;border:1px solid var(--line);border-radius:8px;
    background:#f4f2ec;color:#3a3428}
  .sharegrid{display:grid;grid-template-columns:repeat(auto-fill,minmax(158px,1fr));
    gap:9px;margin:6px 0 0}
  .sharegrid a,.sharegrid button{font:inherit;font-size:14.5px;font-weight:700;
    display:flex;align-items:center;gap:9px;padding:11px 13px;border-radius:10px;
    border:1px solid var(--line);background:#fff;color:var(--ink);
    text-decoration:none;cursor:pointer;text-align:left;line-height:1.3}
  .sharegrid a:hover,.sharegrid button:hover{background:#f7f5ef}
  .sharegrid .ic{flex:0 0 22px;height:22px;border-radius:6px;display:flex;
    align-items:center;justify-content:center;font-size:12px;font-weight:800;
    color:#fff}
  .ic-line{background:#06c755}.ic-fb{background:#1877f2}.ic-x{background:#111}
  .ic-tg{background:#29a9eb}.ic-wa{background:#25d366}.ic-rd{background:#ff4500}
  .ic-mail{background:#6b6558}.ic-copy{background:var(--teal)}
  .ic-dl{background:var(--gold)}.ic-native{background:#7a1f7a}

  .lineblock{background:#eefaf1;border:1px solid #b6e6c8;border-radius:14px;
    padding:16px 18px;margin:22px 0}
  .lineblock h3{margin:0 0 4px;font-size:19px}
  .lineblock p{margin:0 0 12px;font-size:15px;color:#2c5140;line-height:1.6}
  .lineid{display:inline-block;font:700 17px/1 ui-monospace,Menlo,monospace;
    background:#fff;border:1px solid #b6e6c8;border-radius:8px;padding:9px 13px;
    color:#0a6b3a;margin:0 8px 8px 0;vertical-align:middle}

  .ledger{display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));
    gap:12px;margin:14px 0 0}
  .ledger div{background:#fff;border:1px solid var(--line);border-radius:12px;
    padding:12px 14px}
  .ledger .n{font-size:26px;font-weight:800;font-family:var(--serif)}
  .ledger .k{font-size:12.5px;color:var(--muted);text-transform:uppercase;
    letter-spacing:.05em;font-weight:700}

  .sheet{max-width:780px;margin:30px 0 0}
  .sheet h2{font-size:23px;margin:26px 0 8px;font-family:var(--serif)}
  body[data-lang=th] .sheet h2{font-family:inherit}
  .sheet h3{font-size:18px;margin:18px 0 6px}
  .sheet p{margin:0 0 12px;line-height:1.68}
  .sheet ul,.sheet ol{margin:0 0 12px 22px;line-height:1.66}
  .sheet li{margin:6px 0}
  .sheet .mark{color:var(--muted);font-style:italic}
  .sheet table{border-collapse:collapse;margin:0 0 14px;font-size:15px;width:100%}
  .sheet th,.sheet td{border:1px solid var(--line);padding:7px 10px;
    text-align:left;vertical-align:top}
  .sheet th{background:#f4f2ec;font-size:13.5px}
  .sheet td.num{text-align:right;font-variant-numeric:tabular-nums}
  .sheet blockquote{margin:0 0 14px;padding:10px 16px;border-left:3px solid
    var(--gold);background:#fbf1dc;border-radius:0 8px 8px 0}
  .sheet blockquote p:last-child{margin:0}
  .tablewrap{overflow-x:auto}
  .frozen{background:#fbf1dc;border:2px solid #e5cf9a;color:#6b4a00;
    border-radius:10px;padding:12px 16px;margin:0 0 14px;font-size:15px}
  .frozen a{color:#6b4a00}
"""

# page() appends the site's own furniture to every page it builds — the
# to-menu button, the floating share bar and the Ko-fi button. Inside somebody
# else's iframe all three are wrong: they are OUR asks, planted on THEIR page,
# and a floating "Support" button in a bearer's sidebar implies the bearer is
# soliciting for us. Hidden here rather than by changing page(), which every
# other page on the site depends on.
EMBED_CSS = ("body{background:#fff}header{display:none}"
             "#tomenu,#sharebar,#kofloat{display:none!important}"
             "main{padding:12px;max-width:520px}"
             ".hunwrap{grid-template-columns:1fr;gap:14px}"
             # A widget has to fit in a sidebar. Measured at 520x660: the stage
             # alone ran 730px and pushed the errand — the whole point — below
             # the fold. Figure down to 150, padding halved.
             ".hunstage{padding:6px 8px 2px}"
             ".hunfig{max-width:150px}"
             ".hunname{font-size:17px}"
             ".hunsub{font-size:12px}"
             ".hunsq{font-size:11.5px;margin:0 0 5px}"
             ".hunday{padding:11px 13px;margin:0 0 9px}"
             ".hunday h3{font-size:18px}"
             ".errand{padding:11px;gap:11px;grid-template-columns:70px minmax(0,1fr)}"
             ".errand img{width:70px;height:70px}"
             ".langbar{display:none}")


# --------------------------------------------------------------------- app
APP_JS = r"""
(function(){
  var $ = function(s,r){return (r||document).querySelector(s)};
  var KEY='wichaa.hun.v1', LKEY='wichaa.hun.ledger.v1', LANGKEY='wichaa.hun.lang';
  var qs = new URLSearchParams(location.search);
  var EMBED = qs.get('embed')==='1';

  // --- language ------------------------------------------------------------
  // Thai first when the browser asks for Thai. The choice is remembered, and it
  // travels INSIDE the embed payload, so a shop that forges its effigy in Thai
  // hands out a Thai widget to its own readers rather than an English one.
  function detectLang(){
    var fromUrl = qs.get('lang');
    if(fromUrl==='th'||fromUrl==='en') return fromUrl;
    try{ var s=localStorage.getItem(LANGKEY); if(s) return s; }catch(e){}
    var navs = (navigator.languages||[navigator.language||'en']).join(',');
    return /\bth\b|-TH/i.test(navs) ? 'th' : 'en';
  }
  var LANG = detectLang();
  function t(k){
    var e = T[k]; if(!e) return k;
    return (LANG==='th' ? e[1] : e[0]) || e[0];
  }
  function applyLang(){
    document.body.setAttribute('data-lang', LANG);
    document.documentElement.setAttribute('lang', LANG);
    [].forEach.call(document.querySelectorAll('[data-t]'), function(e){
      e.textContent = t(e.getAttribute('data-t'));
    });
    [].forEach.call(document.querySelectorAll('[data-tph]'), function(e){
      e.placeholder = t(e.getAttribute('data-tph'));
    });
    [].forEach.call(document.querySelectorAll('.langbar button'), function(b){
      b.setAttribute('aria-pressed', String(b.dataset.lang===LANG));
    });
    var opts = document.getElementById('f-born');
    if(opts) [].forEach.call(opts.options, function(o){
      var d = DAYS[+o.value];
      o.textContent = (LANG==='th') ? ('วัน'+d.th) : (d.en+' · '+d.th);
    });
    var ps = document.getElementById('f-preset');
    if(ps) [].forEach.call(ps.options, function(o){
      var p = PRESETS.filter(function(x){return x.id===o.value})[0];
      if(p) o.textContent = (LANG==='th' ? p.nameTh : p.name);
    });
  }
  function setLang(l){
    LANG = l;
    try{ localStorage.setItem(LANGKEY, l); }catch(e){}
    state.lang = l; save();
    if(skState){ skState.lang = l; skSave(); }
    applyLang(); render(); if(typeof refreshShare==='function') refreshShare();
    if(typeof skRender==='function') skRender();
    if(typeof skRefreshShare==='function') skRefreshShare();
  }

  // --- state ---------------------------------------------------------------
  // Everything the effigy is lives in this one object. It goes to localStorage
  // for the bearer, and into the link (base64) so a shared or pasted widget
  // carries itself. There is no server and no account, so there is nowhere
  // else it could live.
  function blank(){
    return {name:'', born:0, tpl:'{url}', preset:'none', forged:0, lang:LANG,
            first:new Date().toISOString().slice(0,10)};
  }
  function b64e(o){
    return btoa(unescape(encodeURIComponent(JSON.stringify(o))))
      .replace(/\+/g,'-').replace(/\//g,'_').replace(/=+$/,'');
  }
  function b64d(s){
    try{
      s=s.replace(/-/g,'+').replace(/_/g,'/');
      return JSON.parse(decodeURIComponent(escape(atob(s))));
    }catch(e){ return null; }
  }
  var fromLink = qs.get('k') && b64d(qs.get('k'));
  var state = fromLink ||
              (function(){ try{ return JSON.parse(localStorage.getItem(KEY)); }
                           catch(e){ return null; } })() || blank();
  // An effigy arriving by link brings its own language with it.
  if(fromLink && (fromLink.lang==='th'||fromLink.lang==='en') && !qs.get('lang'))
    LANG = fromLink.lang;
  function save(){
    // A widget opened from someone else's link must not overwrite the reader's
    // own effigy in their browser.
    if(fromLink) return;
    try{ localStorage.setItem(KEY, JSON.stringify(state)); }catch(e){}
  }

  // --- mode: hun payont (effigy) vs สู่ขวัญ (name-charm) --------------------
  // Same page, same server (none), two independent tools. The mode lives in
  // its own tiny localStorage key rather than inside `state`, since `state`
  // and its `?k=` link are the effigy's alone.
  var MODEKEY = 'wichaa.hun.mode';
  function detectMode(){
    var m = qs.get('mode');
    if(m==='hun'||m==='sukhwan') return m;
    if(qs.get('sk')) return 'sukhwan';
    try{ var s=localStorage.getItem(MODEKEY); if(s) return s; }catch(e){}
    return 'hun';
  }
  var MODE = detectMode();
  document.body.setAttribute('data-mode', MODE);
  function setMode(m){
    MODE = m;
    try{ localStorage.setItem(MODEKEY, m); }catch(e){}
    document.body.setAttribute('data-mode', MODE);
    [].forEach.call(document.querySelectorAll('.modebar button'), function(b){
      b.setAttribute('aria-pressed', String(b.dataset.mode===MODE));
    });
    if(typeof refreshShare==='function') refreshShare();
    if(typeof skRefreshShare==='function') skRefreshShare();
  }

  // --- สู่ขวัญ state ---------------------------------------------------------
  // A visitor's own name(s), kept ONLY here: this browser's localStorage, or
  // inside a link they choose to copy and share. Nothing is ever sent
  // anywhere — there is no server on this site, on this page, or in this
  // mode, so "recorded for prayer only" is true by construction, not policy.
  var SKKEY = 'wichaa.sukhwan.v1';
  function skBlank(){
    return {names:[], lang:LANG, first:new Date().toISOString().slice(0,10)};
  }
  var skFromLink = qs.get('sk') && b64d(qs.get('sk'));
  var skState = skFromLink ||
                (function(){ try{ return JSON.parse(localStorage.getItem(SKKEY)); }
                             catch(e){ return null; } })() || skBlank();
  if(skFromLink && (skFromLink.lang==='th'||skFromLink.lang==='en') && !qs.get('lang')){
    LANG = skFromLink.lang;
    document.body.setAttribute('data-lang', LANG);
  }
  function skSave(){
    // Never overwrite the reader's own list when they've opened someone
    // else's shared su-khwan link — same non-clobber rule as the effigy.
    if(skFromLink) return;
    try{ localStorage.setItem(SKKEY, JSON.stringify(skState)); }catch(e){}
  }

  // --- the ledger ----------------------------------------------------------
  // Counts what happens in THIS browser: days the effigy stood, and knocks
  // (clicks through to a listing). It does not and cannot count money — the
  // bearer's own network does that, and we never see it. Said plainly on the
  // page rather than implied by an empty baht column.
  function ledger(){
    try{ return JSON.parse(localStorage.getItem(LKEY)) ||
         {days:0,knocks:0,last:'',since:new Date().toISOString().slice(0,10)}; }
    catch(e){ return {days:0,knocks:0,last:'',since:''}; }
  }
  function bump(k){
    var L=ledger();
    if(k==='day'){
      var d=new Date().toISOString().slice(0,10);
      if(L.last===d) return L;
      L.last=d; L.days++;
    } else { L.knocks++; }
    try{ localStorage.setItem(LKEY, JSON.stringify(L)); }catch(e){}
    return L;
  }

  // --- the khata -----------------------------------------------------------
  function dress(url, id){
    var tpl = (state.tpl||'{url}').trim();
    if(!tpl) tpl='{url}';
    return tpl.replace(/\{urlenc\}/g, encodeURIComponent(url))
              .replace(/\{url\}/g, url)
              .replace(/\{id\}/g, String(id||''));
  }
  function consecrated(){
    var tpl=(state.tpl||'').trim();
    return !!tpl && tpl!=='{url}' && !/YOURID|YOURNETWORK/.test(tpl);
  }

  // LEARN THE KHATA FROM A LINK THE BEARER ALREADY HAS.
  //
  // This is the single biggest usability win on the page: nobody should have
  // to understand what a URL template is in order to be paid. Paste any
  // working affiliate link and the destination is found inside it, then
  // swapped for a placeholder. Three real shapes are covered:
  //   1. a redirector carrying the destination url-encoded in a parameter
  //   2. the same, but not encoded
  //   3. the product url itself with tracking parameters bolted on
  // Whatever it works out is SHOWN, never silently applied — the preview under
  // it is the check, because only the bearer's dashboard knows the truth.
  function learnKhata(pasted){
    pasted = (pasted||'').trim();
    if(!/^https?:\/\//i.test(pasted)) return null;
    var u;
    try{ u = new URL(pasted); }catch(e){ return null; }
    var params = Array.from(u.searchParams.entries());
    // 1 & 2 — a parameter whose value is itself a url
    for(var i=0;i<params.length;i++){
      var k=params[i][0], v=params[i][1];
      if(/^https?:\/\//i.test(v)){
        // URLSearchParams already decoded it; decide which token to use by
        // looking at the RAW query string.
        var raw = u.search.indexOf(encodeURIComponent(v)) >= 0;
        var tok = raw ? '{urlenc}' : '{url}';
        var sp = new URLSearchParams(u.search);
        sp.set(k, '@@SLOT@@');
        return (u.origin+u.pathname+'?'+sp.toString())
                 .replace(/%40%40SLOT%40%40|@@SLOT@@/, tok);
      }
    }
    // 3 — the product url itself, wearing tracking parameters
    if(params.length){
      return '{url}?' + u.search.replace(/^\?/,'');
    }
    return null;
  }

  // --- picking the day's errand -------------------------------------------
  function pickFor(dt){
    var R = READ.themeFor(dt, state.forged||0);
    if(!R.key) return {reading:R, item:null};
    var pool = POOL[R.key] || [];
    if(!pool.length){
      for(var k in POOL){ if(POOL[k].length){ pool=POOL[k]; R.key=k; break; } }
    }
    if(!pool.length) return {reading:R, item:null};
    var d = dt.toISOString().slice(0,10);
    var idx = HUN.hash(d + '|' + (state.name||'') + '|' + R.key) % pool.length;
    return {reading:R, item:pool[idx]};
  }

  // --- rendering -----------------------------------------------------------
  function themeText(key, field){
    var th = THEMES[key]; if(!th) return '';
    if(field==='label') return LANG==='th' ? th.th : th.en;
    return LANG==='th' ? th.whyTh : th.whyEn;
  }

  function render(){
    var dt = new Date();
    var P = pickFor(dt);
    var R = P.reading;
    var restingNow = (R.reason === 'wanphra');
    var di = (R.day != null) ? R.day : READ.dayIndex(dt);
    var born = DAYS[state.born] || DAYS[0];

    // The effigy wears the bearer's BIRTH colour — that is the lifelong one —
    // and the day's colour appears in the reading beside it.
    var fig = HUN.effigy(state.name || 'unconsecrated',
      {cloth: born.colour, awake: consecrated(), resting: restingNow});
    var pl = HUN.plate(HUN.hash(state.name || 'unconsecrated'));

    var stage = $('#stage');
    var cls = restingNow ? 'st-rest' : (consecrated() ? 'st-work' : 'st-cold');
    var lab = restingNow ? t('resting') : (consecrated() ? t('working') : t('cold'));
    var bornLine = LANG==='th'
      ? ('เกิดวัน'+born.th+' · ผ้า'+born.colourNameTh)
      : ('born '+born.en+' · '+born.colourName+' cloth');
    stage.innerHTML =
      '<span class="hunstate '+cls+'">'+esc(lab)+'</span>' + fig +
      '<p class="hunname">'+esc(state.name || t('noname'))+'</p>'+
      '<p class="hunsub">'+(state.name ? esc(bornLine) : esc(t('nonameSub')))+
      '</p>'+
      '<p class="hunsq">'+esc(t('plateLine'))+' <b>'+pl.sum+'</b></p>';

    var d = DAYS[di];
    var L = R.lunar;
    var dayName = LANG==='th' ? ('วัน'+d.th) : (d.en+' · '+d.th);
    var domain  = LANG==='th' ? d.domainTh : d.domain;
    var colour  = LANG==='th' ? d.colourNameTh : d.colourName;
    var out = '<div class=hunday><h3>'+esc(dayName)+'</h3>'+
      '<p class=devline>'+d.graha+' ('+d.grahaEn+') — '+esc(domain)+'</p>'+
      '<div class=hunfacts>'+
      '<span><i class=swatch style="background:'+d.colour+'"></i>'+
        esc(t('wear'))+' <b>'+esc(colour)+'</b></span>'+
      '<span>'+L.label+(L.n!=null&&LANG!=='th'?' <b>'+L.labelEn+'</b>':'')+'</span>'+
      '<span>'+(LANG==='th'?'จันทร์':'moon')+' <b>'+Math.round(L.illum*100)+
        '%</b> '+esc(t('moonLit'))+'</span>'+
      (L.wanPhra?'<span><b>วันพระ</b>'+(LANG==='th'?'':' — '+t('holyDay'))+
        '</span>':'')+
      '</div>'+
      (L.great?'<p class=greatday>'+esc(L.great)+'</p>':'')+
      (L.known?'':'<p class=calnote>'+
        esc(t('calNote').replace('{a}',L.first).replace('{b}',L.last))+'</p>')+
      '</div>';

    if(restingNow){
      out += '<div class=resting><b>'+
        esc(R.observance ? t('itIsHolyDay') : t('itIsWanPhra'))+
        (L.great?' — '+esc(L.great):'')+'</b> '+esc(t('restingMsg'))+'</div>';
    } else if(P.item){
      var it = P.item;
      var url = dress(it.u, it.id);
      var why = R.reason==='birthday' ? t('forgedDay')
              : R.reason==='full'     ? t('fullMoon')
              : R.reason==='new'      ? t('darkMoon')
              : (LANG==='th' ? ('วัน'+d.th+' · '+themeText(R.key,'label'))
                             : (d.en+' · '+themeText(R.key,'label')));
      out += '<div class=errand>'+
        // The product thumbnail is the one thing here that comes off the
        // network (the seller's own CDN). On a saved copy opened with no
        // connection it would otherwise leave a broken-image glyph, so it
        // removes itself instead and the card closes up around it.
        (it.i ? '<img src="'+esc(it.i)+'" alt="" loading=lazy '+
                'referrerpolicy=no-referrer '+
                'onerror="this.parentNode.style.gridTemplateColumns=&quot;1fr&quot;;'+
                'this.remove()">' : '<div></div>')+
        '<div><p class=why>'+esc(why)+'</p>'+
        '<h4><a href="'+esc(url)+'" target=_blank rel="noopener sponsored" '+
        'data-knock=1>'+esc(it.t)+'</a></h4>'+
        '<p class=price>฿'+fmt(it.p)+'</p>'+
        '<p class=plain>'+esc(themeText(R.key,'why'))+'</p>'+
        '<a class=go href="'+esc(url)+'" target=_blank rel="noopener sponsored" '+
        'data-knock=1>'+esc(t('goLook'))+'</a>'+
        (consecrated()? '' : '<p class=plain>'+esc(t('plainLink'))+'</p>')+
        '</div></div>';
    }
    $('#reading').innerHTML = out;

    var L2 = bump('day');
    var led = $('#ledger');
    if(led){
      led.innerHTML =
        tile(L2.days, t('lDays')) +
        tile(L2.knocks, t('lKnocks')) +
        tile(consecrated()?t('yes'):t('no'), t('lConsec')) +
        tile(L2.since || '—', t('lSince'));
    }
    [].forEach.call(document.querySelectorAll('[data-knock]'), function(a){
      a.addEventListener('click', function(){ bump('knock'); });
    });
  }
  function tile(n,k){
    return '<div><div class=n>'+esc(String(n))+'</div><div class=k>'+esc(k)+
           '</div></div>';
  }

  // --- สู่ขวัญ: line-of-the-day --------------------------------------------
  // Same idiom as pickFor() above — a single hash(date + names) % length,
  // never HUN.rng() — so the pick is fixed for the day and needs no state.
  function skPickIndex(dt, names){
    var d = dt.toISOString().slice(0,10);
    return HUN.hash(d + '|' + names.join(',') + '|sukhwan') % SUKHWAN.length;
  }
  // Every name typed in is named in the chant — not one rotating pick. Two
  // names read "A and B"; three or more read "A, B and C" / the Thai
  // equivalent joined with และ.
  function skJoinNames(names){
    if(names.length===1) return names[0];
    var and = (LANG==='th') ? 'และ' : 'and';
    if(names.length===2) return names[0] + ' ' + and + ' ' + names[1];
    return names.slice(0,-1).join(', ') + ' ' + and + ' ' + names[names.length-1];
  }
  // The WHOLE chant, legible start to finish — not one fragment. Every line
  // carries the entered name(s); today's line (same pick as before) is
  // marked, not the only thing shown, so the daily rhythm survives inside a
  // recitation a person can actually read start to end, the way su khwan
  // itself is a full recitation, not a single sentence.
  function skRender(){
    var box = $('#sk-reading');
    if(!box) return;
    var names = (skState.names || []).filter(Boolean);
    if(!names.length){
      box.innerHTML = '<p class=skempty>'+esc(t('skEmpty'))+'</p>';
      return;
    }
    var dt = new Date();
    var todayIdx = skPickIndex(dt, names);
    var who = esc(skJoinNames(names));
    var html = '<ol class=skchant>';
    for(var i=0; i<SUKHWAN.length; i++){
      var entry = SUKHWAN[i];
      var line     = (LANG==='th' ? entry.th : entry.en).split('{name}').join(who);
      var translit = (entry.translit || '').split('{name}').join(who);
      var gloss    = (entry.gloss || '').split('{name}').join(who);
      var today = (i===todayIdx);
      html += '<li class="skverse'+(today?' sktoday':'')+'">'+
        (today ? '<span class=sktodaytag>'+esc(t('skToday'))+'</span>' : '')+
        '<p class=skline>'+line+'</p>';
      if(LANG==='th'){
        html += '<p class=sktranslit>'+translit+'</p>'+
                '<p class=skgloss>'+gloss+'</p>';
      }
      html += '</li>';
    }
    html += '</ol>';
    box.innerHTML = html;
  }
  function esc(s){
    return String(s==null?'':s).replace(/[&<>"']/g, function(c){
      return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c];
    });
  }
  function fmt(n){
    return (n==null?'—':Number(n).toLocaleString('en-US',
      {maximumFractionDigits:0}));
  }
  function flash(btn, msg){
    var old = btn.textContent;
    btn.textContent = msg;
    setTimeout(function(){ btn.textContent = old; }, 1800);
  }
  function copy(text, btn){
    var done = function(){ if(btn) flash(btn, t('copied')); };
    if(navigator.clipboard && navigator.clipboard.writeText){
      navigator.clipboard.writeText(text).then(done, function(){ fallback(); });
    } else { fallback(); }
    function fallback(){
      var ta=document.createElement('textarea');
      ta.value=text; ta.style.position='fixed'; ta.style.opacity='0';
      document.body.appendChild(ta); ta.select();
      try{ document.execCommand('copy'); done(); }catch(e){}
      document.body.removeChild(ta);
    }
  }

  // --- sharing -------------------------------------------------------------
  // An effigy with a name has its OWN address: /hun/?k=<payload>. Everything in
  // the share panel points at that, so a shared link opens the sharer's effigy,
  // under the sharer's khata, in the sharer's language — not a generic page.
  function permalink(){
    if(!state.name) return PAGE_BASE;
    return PAGE_BASE + '?k=' + b64e(state);
  }
  function embedCode(){
    return '<iframe src="' + EMBED_BASE + '?embed=1&k=' + b64e(state) +
           '" width="100%" height="700" style="border:0;max-width:520px" ' +
           'title="Hun Payont" loading="lazy"></iframe>';
  }
  function refreshShare(){
    var pl = permalink(), txt = t('shareText');
    var U = encodeURIComponent(pl), X = encodeURIComponent(txt);
    var set = {
      'sh-line':  'https://social-plugins.line.me/lineit/share?url='+U,
      'sh-fb':    'https://www.facebook.com/sharer/sharer.php?u='+U,
      'sh-x':     'https://twitter.com/intent/tweet?url='+U+'&text='+X,
      'sh-tg':    'https://t.me/share/url?url='+U+'&text='+X,
      'sh-wa':    'https://api.whatsapp.com/send?text='+X+'%20'+U,
      'sh-rd':    'https://www.reddit.com/submit?url='+U+'&title='+X,
      'sh-mail':  'mailto:?subject='+X+'&body='+U
    };
    for(var id in set){ var e=document.getElementById(id); if(e) e.href=set[id]; }
    var box = document.getElementById('permalink-box');
    if(box) box.value = pl;
    var emb = document.getElementById('embed-code');
    if(emb) emb.value = embedCode();
    var hint = document.getElementById('share-hint');
    if(hint) hint.style.display = state.name ? 'none' : '';
    var nat = document.getElementById('sh-native');
    if(nat) nat.style.display = navigator.share ? '' : 'none';
  }

  // --- สู่ขวัญ: names input + its own permalink -----------------------------
  function skWireForge(){
    var ta = $('#sk-names');
    if(!ta) return;
    ta.value = (skState.names || []).join('\n');
    function sync(){
      skState.names = ta.value.split(/[\n,]+/)
        .map(function(s){ return s.trim(); }).filter(Boolean);
      skState.lang = LANG;
      skSave(); skRender(); skRefreshShare();
    }
    ta.addEventListener('input', sync);
    ta.addEventListener('change', sync);
  }
  function skPermalink(){
    if(!skState.names || !skState.names.length) return PAGE_BASE;
    return PAGE_BASE + '?mode=sukhwan&sk=' + b64e(skState);
  }
  function skRefreshShare(){
    var box = $('#sk-permalink-box');
    if(box) box.value = skPermalink();
    var hint = $('#sk-share-hint');
    if(hint) hint.style.display = (skState.names && skState.names.length) ? 'none' : '';
    var nat = $('#sk-native');
    if(nat) nat.style.display = navigator.share ? '' : 'none';
  }
  function skWireShare(){
    var b;
    if((b = $('#sk-copy-link')))
      b.addEventListener('click', function(){ copy(skPermalink(), b); });
    if((b = $('#sk-native'))) b.addEventListener('click', function(){
      if(navigator.share) navigator.share(
        {title:'สู่ขวัญ · wichaa.net', text:t('skShareText'), url:skPermalink()})
        .catch(function(){});
    });
    var pb = $('#sk-permalink-box');
    if(pb) pb.addEventListener('focus', function(){ pb.select(); });
  }

  function downloadEffigy(){
    var born = DAYS[state.born] || DAYS[0];
    var svg = HUN.effigy(state.name || 'unconsecrated',
      {cloth: born.colour, awake: consecrated()});
    var blob = new Blob([
      '<?xml version="1.0" encoding="UTF-8"?>\n' + svg
    ], {type:'image/svg+xml'});
    var a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = (state.name ? state.name.replace(/[^\w฀-๿-]+/g,'_')
                             : 'hun-payont') + '.svg';
    document.body.appendChild(a); a.click(); document.body.removeChild(a);
    setTimeout(function(){ URL.revokeObjectURL(a.href); }, 4000);
  }

  // --- the forge -----------------------------------------------------------
  function wireForge(){
    var nm=$('#f-name'), bn=$('#f-born'), ps=$('#f-preset'), tp=$('#f-tpl');
    if(!nm) return;
    nm.value = state.name || '';
    bn.value = String(state.born || 0);
    ps.value = state.preset || 'none';
    tp.value = state.tpl || '{url}';

    function sync(){
      state.name = nm.value.trim();
      state.born = +bn.value;
      state.preset = ps.value;
      state.tpl = tp.value;
      state.lang = LANG;
      if(!state.forged) state.forged = new Date().getDate();
      save();
      showKhata();
      refreshShare();
      render();
    }
    function showKhata(){
      var pr = PRESETS.filter(function(p){return p.id===state.preset})[0];
      var st = $('#k-status');
      // NEVER GREEN. The first version turned this green as soon as a khata
      // looked filled in, while the text inside it still said "NOT verified" —
      // the colour was making a promise the words were withdrawing. Nothing
      // here is verified by us and nothing can be: only the bearer's own
      // dashboard knows whether a link shape works. Amber = set but unchecked;
      // red = still carrying a placeholder, so it will emit a broken link.
      st.className = 'kstat' +
        (/YOURID|YOURNETWORK/.test(state.tpl||'') ? ' bad' : '');
      if(pr) st.innerHTML =
        '<b>'+esc(LANG==='th'?pr.nameTh:pr.name)+'</b> — '+
        esc(LANG==='th'?pr.statusTh:pr.status)+
        '<br><b>'+esc(t('verifiedLbl'))+'</b> '+
        esc(LANG==='th'?pr.verifiedTh:pr.verified);
      $('#k-preview').textContent = dress(SAMPLE_URL, 1234);
    }
    ps.addEventListener('change', function(){
      var pr = PRESETS.filter(function(p){return p.id===ps.value})[0];
      if(pr && pr.id!=='custom') tp.value = pr.tpl;
      sync();
    });
    [nm,bn,tp].forEach(function(e){
      e.addEventListener('input', sync);
      e.addEventListener('change', sync);
    });

    // learn-from-a-link
    var lin=$('#learn-in'), lbtn=$('#learn-go'), lmsg=$('#learn-msg');
    function doLearn(){
      var got = learnKhata(lin.value);
      if(got){
        tp.value = got; ps.value = 'custom';
        lmsg.className='learnmsg ok'; lmsg.textContent = t('learnOk');
        var adv=$('#adv'); if(adv) adv.open = true;
        sync();
      } else {
        lmsg.className='learnmsg no'; lmsg.textContent = t('learnNo');
      }
    }
    lbtn.addEventListener('click', doLearn);
    lin.addEventListener('keydown', function(e){ if(e.key==='Enter') doLearn(); });

    var un=$('#unmake');
    if(un) un.addEventListener('click', function(){
      if(!confirm(t('unmakeAsk'))) return;
      try{ localStorage.removeItem(KEY); localStorage.removeItem(LKEY); }catch(e){}
      state = blank();
      nm.value=''; bn.value='0'; ps.value='none'; tp.value='{url}';
      if(lmsg){ lmsg.textContent=''; lmsg.className='learnmsg'; }
      sync();
    });
    showKhata();
  }

  function wireShare(){
    var b;
    if((b=$('#copy-link')))  b.addEventListener('click', function(){ copy(permalink(), b); });
    // two copy-embed buttons now: one in the share grid, one inside the
    // disclosure in step 3, next to the code itself where it is actually
    // needed. querySelectorAll rather than two lookups so adding a third
    // needs no change here.
    [].forEach.call(document.querySelectorAll('#copy-embed,#copy-embed2'),
      function(btn){
        btn.addEventListener('click', function(){ copy(embedCode(), btn); });
      });
    if((b=$('#copy-line')))  b.addEventListener('click', function(){ copy(LINE_ID, b); });
    if((b=$('#dl-svg')))     b.addEventListener('click', downloadEffigy);
    if((b=$('#sh-native')))  b.addEventListener('click', function(){
      if(navigator.share) navigator.share(
        {title:'หุ่นพยนต์ · Hun Payont', text:t('shareText'), url:permalink()})
        .catch(function(){});
    });
    var pb=$('#permalink-box');
    if(pb) pb.addEventListener('focus', function(){ pb.select(); });
  }

  [].forEach.call(document.querySelectorAll('.langbar button'), function(b){
    b.addEventListener('click', function(){ setLang(b.dataset.lang); });
  });
  [].forEach.call(document.querySelectorAll('.modebar button'), function(b){
    b.addEventListener('click', function(){ setMode(b.dataset.mode); });
  });

  applyLang();
  [].forEach.call(document.querySelectorAll('.modebar button'), function(b){
    b.setAttribute('aria-pressed', String(b.dataset.mode===MODE));
  });
  wireForge();
  wireShare();
  refreshShare();
  render();
  skWireForge();
  skWireShare();
  skRefreshShare();
  skRender();
  // Redraw at midnight so a widget left open overnight is not showing
  // yesterday's errand — both modes ride the same clock.
  var midnight = new Date(); midnight.setHours(24,0,20,0);
  setTimeout(function(){ render(); skRender(); setInterval(function(){
    render(); skRender();
  }, 86400000); }, midnight - new Date());
})();
"""


# ------------------------------------------------------------------- prose
def _essay_en(s: dict) -> str:
    n, hun, med = s.get("listings", 0), s.get("hun_listings", 0), s.get("median", 130)
    return (
        "<section class='sheet en-only'>"

        "<h2>What a hun payont is</h2>"
        "<p>A <b>หุ่นพยนต์</b> is a servant made on purpose — and in Thai it is "
        "just a <b>หุ่น</b>, the same everyday noun that covers a puppet, a shop "
        "dummy, a crash-test dummy and a robot (<b>หุ่นยนต์</b>). The noun names "
        "the figure; the modifier names what moves it. A <em>yon</em> is moved by "
        "an engine. A <em>payont</em> is moved by a spell.</p>"

        "<p><span class=mark>Tradition —</span> and this archive holds the manual. "
        "<b>ตำราสร้างเครื่องรางของขลัง</b> — 42 kinds of charm in 158 methods — "
        "gives two ways to build one, on printed pages ๗๗&ndash;๗๘. "
        "<b>Method one:</b> charnel-ground earth from three separate places, and "
        "you do not simply take it — you set out a krathong of rice, a krathong of "
        "pork and white liquor, and ask (<b>พลี</b>). Mould it into the figure of "
        "a person holding a club. Wrap a fueang-weight of mercury in a yantra and "
        "push it into the <em>belly</em>. <b>Method two:</b> thirty-two strands of "
        "rice straw, <b>bound</b> (ผูก) while reciting the thirty-two parts of the "
        "body; tied with strips split from the wood that prodded a corpse; dressed "
        "in the cloth that corpse wore; holding a spear made from the same "
        "wood.</p>"

        "<p>The working word in the katha, said three times, is <b>ปลุก</b> — and "
        "ปลุก is not <em>make</em>, it is <b>wake</b>. The treatise does not "
        "describe itself as manufacturing a servant. It describes itself as waking "
        "one.</p>"

        "<p>Then the instruction that is usually left out, which changes what kind "
        "of thing this is: build it <b>a small spirit-house</b>, put it in "
        "properly, and <b>set out liquor and rice for it every single day</b>. "
        "That is not a maintenance schedule; it is a standing obligation to a "
        "dependent, and it does not end. You give the instruction once. After that "
        "it keeps watch, and thieves do not come near, because "
        "<b>มันแลเห็นเป็นคนอยู่แล</b> — to the eye, it is a person standing "
        "there.</p>"

        "<p>So the reason people want one is not that it is powerful. It is that "
        "it does not sleep. You do; it keeps working; you wake up and the work has "
        "been done — and you owe it rice in the morning.</p>"
        "<p>This is not a historical curiosity. There are <b>" + str(hun) +
        " hun payont for sale</b> in the living-market half of this catalogue "
        "right now, alongside " + f"{n:,}" + " other charms. People buy them to "
        "put behind the counter.</p>"

        "<p><span class=mark>Worth flagging —</span> and it cuts the other way: "
        "the hun payont is nearly absent from the manuscript record as harvested. "
        "Measured 2026-08-05 — <b>0</b> of this catalogue's 6,990 manuscripts "
        "mention it, against <b>3</b> pages in the one digitised treatise above "
        "and the " + str(hun) + " live market listings counted above. Its "
        "transmission runs through named "
        "ajarns and through the objects themselves, not through the palm leaf, so "
        "a reader should be slow to conclude anything about it from manuscripts "
        "alone.</p>"

        "<h2>What this one is</h2>"
        "<p>An effigy you can actually be given, that actually does the actual "
        "job. The mechanism is not a metaphor, and it is short enough to state "
        "in full:</p>"
        "<ol>"
        "<li>You <b>forge</b> it. Your name seeds the drawing, so the body, the "
        "stance and the numbers on its chest are yours and nobody else's.</li>"
        "<li>You <b>consecrate</b> it — you give it your khata. Here the khata is "
        "your own affiliate link, from whatever programme you are already in. "
        "Paste one link you already have and it learns the rest.</li>"
        "<li>You <b>carry</b> it. Your effigy has its own address; share that, or "
        "paste the embed on your site.</li>"
        "<li>Every morning it <b>reads the day</b> and walks to the market. It "
        "comes back with one thing that suits the day, and the link it brings "
        "back is wearing your khata.</li>"
        "<li>What that earns is paid <b>by your network, to you</b>.</li>"
        "</ol>"
        "<blockquote><p>This site takes nothing, and could not take anything if "
        "it wanted to. There is no server, no account, no cookie, no analytics "
        "and no callback — the whole widget is one static page that runs in the "
        "reader's browser. Your khata is stored in <em>your</em> browser and "
        "encoded in <em>your</em> link. Nobody here can see a click, and there is "
        "no code path where a cut could be taken.</p></blockquote>"

        "<h2>What it actually pays</h2>"
        "<p>The part most things like this leave out. A servant is not a fortune. "
        "Here is the arithmetic, with figures from this catalogue rather than "
        "invented ones:</p>"
        "<div class=tablewrap><table><tr><th>Step</th><th>Rate</th>"
        "<th class=num>Out of 1,000 views</th></tr>"
        "<tr><td>People who see the effigy</td><td>—</td>"
        "<td class=num>1,000</td></tr>"
        "<tr><td>People who click through</td><td>1–3% is a normal banner rate"
        "</td><td class=num>10–30</td></tr>"
        "<tr><td>Clicks that become a purchase</td><td>1–3% is normal for a "
        "marketplace</td><td class=num>0–1</td></tr>"
        "<tr><td>Value of that purchase</td><td>median listing here is <b>฿" +
        f"{med:,.0f}" + "</b></td><td class=num>฿" + f"{med:,.0f}" + "</td></tr>"
        "<tr><td>Your commission</td><td>low single-digit % on marketplace goods"
        "</td><td class=num><b>฿2–10</b></td></tr></table></div>"
        "<p><span class=mark>Inference —</span> the click and conversion rates "
        "above are ordinary industry figures, not measurements of this widget; "
        "nothing has been measured yet, because it has not been carried yet. The "
        "median price is real and comes from the " + f"{n:,}" + " priced listings "
        "in this catalogue.</p>"
        "<p>So: a page with a thousand views a month earns its bearer roughly the "
        "price of a coffee, every month, forever, while they sleep. That is a "
        "true statement and also a small one, and both halves matter. If a thing "
        "like this promises you more than a coffee it is lying to you, and the "
        "reason to build it anyway is the same reason people keep an effigy "
        "behind the counter: not because it will make you rich, but because "
        "something should be working while you are not.</p>"

        "<h2>The square on its chest</h2>"
        "<p>The plate every effigy wears is a genuine <b>magic square</b>: each "
        "row, column and both diagonals add to the same number, and the page "
        "prints that number beside the drawing so you can check it by hand. It is "
        "built by the <b>Siamese method</b> — start in the middle of the top row, "
        "step up and to the right, and drop a row whenever the cell you wanted is "
        "taken.</p>"
        "<p>The name is a piece of history worth telling properly. Simon de la "
        "Loubère led Louis XIV's embassy to Siam in 1687 and sailed home in "
        "January 1688; the account he published on his return carries a chapter on "
        "the problem of the magical square, and the rule in it is the one Europe "
        "has called the <em>Siamese method</em> ever since. "
        "<span class=mark>Worth flagging —</span> by de la Loubère's own account "
        "the method reached him from a fellow passenger, M. Vincent, who had it "
        "from Surat in India. So the technique Europe files under Siam did not "
        "start there. That is exactly the kind of provenance this archive exists "
        "to keep straight, and it would have been easier to leave out.</p>"
        "<p>Thai yantra practice does use numbered grids — <b>ยันต์ตาราง</b> — so a "
        "numbered plate on the chest of an effigy is not an invention. "
        "<span class=mark>Inference —</span> using a <em>de la Loubère</em> square "
        "specifically is my choice, made because it is the one construction with a "
        "documented road between Siam and the rest of the world, and because it "
        "lets the drawing make a claim you can verify with addition.</p>"

        "<h2>The day it reads</h2>"
        "<p>The errand is not random. Thai reckoning runs an <b>eight-day week</b>: "
        "the seven days, with Wednesday split so that its night belongs to Rahu. "
        "Each day has a graha, a colour and a posture of the Buddha, and people "
        "genuinely dress by it. The effigy reads that, plus the moon — computed "
        "from the moon's true elongation with the same series the "
        "<a href='/moon/'>moon complication</a> uses, checked there against JPL "
        "DE440 to better than half a degree.</p>"
        "<div class=tablewrap><table><tr><th>Day</th><th>Graha</th><th>Colour</th>"
        "<th>It fetches</th></tr>" +
        "".join(
            "<tr><td>" + d["en"] + " · " + d["th"] + "</td><td>" + d["graha"] +
            "</td><td>" + d["colourName"] + "</td><td>" +
            THEMES[d["theme"]]["term"] + " — " +
            THEMES[d["theme"]]["en"].lower() + "</td></tr>" for d in DAYS) +
        "</table></div>"
        "<p><span class=mark>Inference —</span> the day-to-charm pairings in the "
        "last column are mine. They follow each graha's documented domain — Budha "
        "governs trade, so Wednesday fetches นางกวัก, the beckoning lady "
        "shopkeepers keep by the till; Shukra governs love, so Friday fetches "
        "charm balm; Thursday is <b>wai khru</b> day, the day you honour teachers, "
        "so it fetches the cloth a teacher draws and gives away. The grahas and "
        "their domains are traditional. Which product answers to which is my "
        "reading.</p>"

        "<h3>It rests on wan phra</h3>"
        "<p>On the four Buddhist holy days of each lunar month the effigy shows "
        "the day and <b>sells nothing at all</b>. No product, no link, no earning. "
        "That costs its bearer about an eighth of their income and it is not "
        "negotiable, because it is what the tradition does, and because a thing "
        "that will sell to you every single day without exception is not a "
        "servant, it is a hoarding.</p>"
        "<p>It also rests on the <b>named observances</b> — Makha Bucha, "
        "Visakha Bucha, Atthami Bucha, Asalha Bucha, the start and end of the "
        "rains retreat, Loi Krathong. Six of those seven fall on a wan phra "
        "anyway. The seventh does not: <b>วันเข้าพรรษา</b>, the start of the "
        "rains retreat, is แรม ๑ ค่ำ — the day after Asalha Bucha — and for a "
        "while this page would have printed the name of that day across the top "
        "of the card and then sold you an amulet underneath it. Worse than "
        "either resting or saying nothing. It rests.</p>"
        "<p><span class=mark>Asked and declined —</span> the obvious move is to "
        "let the holy days be the day the <em>house</em> earns instead: nobody "
        "would notice, and it is an eighth of the traffic. It is declined, and "
        "the reason is written here so it stays declined. If wan phra is when we "
        "sell, then the thing sells every day without exception and the rest was "
        "never real — it was a rebate to the house, and this page's three "
        "loudest claims (no cut taken, no code path where a cut could be taken, "
        "it rests) would all be false at once. On those days it earns nobody "
        "anything, including us.</p>"
        "<p>Which days those are is <b>a published table, not a calculation</b>, "
        "and the reason is worth stating because it was measured rather than "
        "assumed. Two versions of this worked the holy days out from the moon "
        "itself — once from the elongation angle, once from a mean lunation. "
        "Scored against the 49 published wan phra of 2569, they got <b>17</b> and "
        "<b>37</b> right. The first version had the widget trading cheerfully "
        "through ขึ้น ๘ ค่ำ on the very day this page was built.</p>"
        "<p>That is not a bug to tune away. <b>The Thai lunar calendar is "
        "arithmetic</b> — alternating 29- and 30-day months with intercalation "
        "rules — so it deliberately does not track the true moon, and better "
        "astronomy cannot converge on it. 2569 is also an <i>adhikamāsa</i> year "
        "carrying a doubled eighth month, เดือน ๘ หลัง, which no lunation model "
        "can know about at all. So the holy days are carried as the published "
        "list, the same way the moon complication carries its eclipses: <i>when a "
        "calculation cannot be right where it runs, do it somewhere it can and "
        "ship the answer.</i></p>"
        "<p>Forty-nine dates are enough for the whole year. Consecutive holy days "
        "are never more than eight days apart and the lunar day advances by one a "
        "day, so every other date is reconstructed by counting from the nearest "
        "one. <span class=mark>Its limit, plainly —</span> the table covers "
        "<b>2026</b>. Outside that the page still knows the moon exactly, but it "
        "prints no ค่ำ number and claims no holy day, because it would be "
        "guessing; it says so on the day itself. Your wat's calendar is the "
        "authority, and always was.</p>"

        "<h2>What it does not do</h2>"
        "<ul>"
        "<li><b>No account.</b> There is nothing to sign up for. The effigy lives "
        "in your browser and in the link you copy.</li>"
        "<li><b>No tracking.</b> No cookie, no pixel, no beacon, no third-party "
        "script. The ledger counts in <code>localStorage</code> on the machine "
        "that is looking at it, and that count never leaves.</li>"
        "<li><b>No money passing through us.</b> Your network pays you directly. "
        "We are not in the path.</li>"
        "<li><b>It cannot count your money.</b> The ledger counts knocks at the "
        "door — clicks — because that is all a page in a browser is able to "
        "see. The coins are counted by your network's dashboard. Any widget that "
        "shows you a baht total without being able to see your account is showing "
        "you a number it made up.</li>"
        "<li><b>It does not choose your programme.</b> It emits whatever URL shape "
        "you teach it and shows you that URL in full before you save, because "
        "affiliate networks change their link grammar and this page is not going "
        "to pretend otherwise.</li>"
        "</ul>"

        "<h2>Provenance</h2>"
        "<p>The listings it fetches are real rows from this catalogue's "
        "living-market half: real titles, real prices in baht, real addresses, "
        "harvested and dated like everything else here. The market is documented "
        "as practice, not sorted into real and touristic — people buy these, so "
        "they are part of the tradition, and an effigy that goes to market is "
        "doing the most ordinary thing in the world.</p>"
        "<p>The two construction methods, the propitiation of the charnel ground, "
        "the thirty-two strands bound to the thirty-two parts, the waking-word "
        "ปลุก, the spirit-house and the daily offering are all from "
        "<b>ตำราสร้างเครื่องรางของขลัง</b>, printed pages ๗๗&ndash;๗๘, digitised "
        "in this archive and readable here. The same treatise carries a resolution "
        "limiting what the figure may do to an intruder — hardship, but not death "
        "— which is a restraint written into the consecration itself; it sits on "
        "the same printed page and the treatise runs several methods to a page, so "
        "which method it belongs to is reported here and not asserted.</p>"
        "<p>The holy-day table is Thai PBS's published ปฏิทินวันพระ for 2569, "
        "cross-checked against myhora.com for July. De la Loubère's embassy and "
        "the Siamese method, and the note that the construction reached him from "
        "Surat via M. Vincent, are on the record in his own account of the "
        "journey. The eight-day week, the day-devas, their colours and postures "
        "are standard Thai practice. The moon series is the one documented on the "
        "<a href='/moon/'>moon complication</a> page, with its measured error "
        "stated there.</p>"
        "</section>")


def _essay_th(s: dict) -> str:
    """The Thai half. Written, not translated — a translated essay reads like
    one, and the Thai reader does not need หุ่นพยนต์ or นางกวัก explained to
    them, which frees the space for the parts that are actually new."""
    n, hun, med = s.get("listings", 0), s.get("hun_listings", 0), s.get("median", 130)
    return (
        "<section class='sheet th-only'>"

        "<h2>หุ่นพยนต์คืออะไร</h2>"
        "<p>หุ่นพยนต์คือ<b>บ่าวที่ถูกสร้างขึ้นมา</b> — และในภาษาไทยมันก็คือ"
        "<b>หุ่น</b> คำเดียวกับหุ่นกระบอก หุ่นโชว์ และหุ่นยนต์ "
        "คำนามบอกว่าเป็นรูป คำขยายบอกว่าอะไรทำให้มันขยับ "
        "<em>ยนต์</em>ขยับด้วยเครื่อง <em>พยนต์</em>ขยับด้วยคาถา</p>"

        "<p>และตำราก็อยู่ในคลังนี้ — <b>ตำราสร้างเครื่องรางของขลัง</b> "
        "เครื่องราง ๔๒ ชนิด ๑๕๘ แบบ มีวิธีสร้างหุ่นพยนต์อยู่สองแบบ หน้า ๗๗–๗๘ "
        "<b>แบบที่ ๑</b> พลีเอาดินป่าช้าสามแห่ง ด้วยข้าวกระทงหนึ่ง "
        "เนื้อหมูกระทงหนึ่ง กับเหล้าขาว — คือต้องขอ ไม่ใช่ไปเอาเฉยๆ "
        "แล้วปั้นเป็นรูปคนถือกระบอง ลงยันต์ห่อปรอทหนักหนึ่งเฟื้อง "
        "ยัดลงใน<em>ท้อง</em> "
        "<b>แบบที่ ๒</b> ผูกด้วยซังข้าว ๓๒ เส้น ภาวนาด้วยอาการ ๓๒ ไปจนเสร็จ "
        "เอาไม้ทิ่มผีมาจักเป็นตอกมัดหุ่น เอาผ้าที่เขานุ่งห่มผีมาทำผ้านุ่งห่มให้ "
        "และเอาไม้ทิ่มผีนั้นเองทำเป็นหอกให้มันถือ</p>"

        "<p>คำที่ทำงานในคาถาคือ <b>ปลุก ปลุก ปลุก</b> — ไม่ใช่สร้าง แต่<b>ปลุก</b> "
        "ตำราไม่ได้พูดถึงตัวเองว่ากำลังทำบ่าวขึ้นมาสักตัว "
        "แต่พูดว่ากำลังปลุกใครสักคนให้ตื่น</p>"

        "<p>และท่อนที่มักไม่มีใครยกมา ซึ่งเปลี่ยนว่าไอ้นี่เป็นของแบบไหน: "
        "ต้อง<b>ทำโรงศาลเล็กๆ</b> เอาหุ่นเข้าไว้ให้ชอบกล "
        "แล้ว<b>เอาเหล้าข้าวเซ่นจงทุกวัน</b> "
        "นั่นไม่ใช่การดูแลของ แต่เป็นภาระที่รับไว้ต่อผู้ที่ต้องพึ่งเรา "
        "และไม่มีวันจบ สั่งความไว้ครั้งเดียว จากนั้นมันก็เฝ้าให้ "
        "โจรผู้ร้ายไม่กล้ากล้ำกราย เพราะ<b>มันแลเห็นเป็นคนอยู่แล</b></p>"

        "<p>เหตุผลที่คนอยากมีจึงไม่ใช่เพราะมันเก่ง แต่เพราะ<b>มันไม่นอน</b> "
        "เรานอน มันทำงานต่อ ตื่นมางานก็เสร็จแล้ว — "
        "และเราก็ติดข้าวมันอยู่มื้อหนึ่งทุกเช้า</p>"
        "<p>และนี่ไม่ใช่เรื่องเก่าเก็บ — ในคลังข้อมูลฝั่งตลาดของเว็บนี้ "
        "ตอนนี้มี<b>หุ่นพยนต์ประกาศขายอยู่ " + str(hun) + " รายการ</b> "
        "อยู่รวมกับเครื่องรางอื่นอีก " + f"{n:,}" + " รายการ "
        "คนซื้อไปตั้งไว้หลังเคาน์เตอร์กันจริงๆ</p>"

        "<h2>ตัวนี้คืออะไร</h2>"
        "<p>หุ่นที่รับไปได้จริง และทำงานนั้นได้จริง กลไกไม่ใช่คำเปรียบเปรย "
        "และสั้นพอจะบอกได้ครบ:</p>"
        "<ol>"
        "<li><b>สร้าง</b> — ชื่อของคุณเป็นตัวกำหนดรูปวาด "
        "รูปร่าง ท่ายืน และตัวเลขบนอกจึงเป็นของคุณคนเดียว</li>"
        "<li><b>ปลุกเสก</b> — ให้คาถาแก่มัน ซึ่งในที่นี้คือ"
        "<b>ลิงก์แอฟฟิลิเอตของคุณเอง</b> จากโปรแกรมที่คุณสมัครไว้อยู่แล้ว "
        "วางลิงก์ที่มีอยู่มาอันเดียว แล้วมันจะถอดรูปแบบที่เหลือเอง</li>"
        "<li><b>พกไป</b> — หุ่นของคุณมีที่อยู่ของตัวเอง "
        "จะแชร์ที่อยู่นั้น หรือวางโค้ดฝังลงเว็บของคุณก็ได้</li>"
        "<li>ทุกเช้ามัน<b>อ่านวัน</b>แล้วเดินไปตลาด "
        "กลับมาพร้อมของหนึ่งชิ้นที่เหมาะกับวันนั้น "
        "และลิงก์ที่มันถือกลับมาก็ติดคาถาของคุณ</li>"
        "<li>รายได้ที่เกิดขึ้น <b>เครือข่ายของคุณจ่ายให้คุณโดยตรง</b></li>"
        "</ol>"
        "<blockquote><p>เว็บนี้ไม่ได้หักอะไรเลย และต่อให้อยากหักก็ทำไม่ได้ "
        "เพราะไม่มีเซิร์ฟเวอร์ ไม่มีบัญชีผู้ใช้ ไม่มีคุกกี้ ไม่มีระบบวิเคราะห์ "
        "และไม่มีการเรียกกลับ — ทั้งหมดเป็นหน้าเว็บนิ่งหน้าเดียวที่ทำงานใน"
        "เบราว์เซอร์ของผู้อ่านเอง คาถาของคุณเก็บอยู่ใน<em>เบราว์เซอร์ของคุณ</em> "
        "และฝังอยู่ใน<em>ลิงก์ของคุณ</em> "
        "ที่นี่มองไม่เห็นการคลิกแม้แต่ครั้งเดียว "
        "และไม่มีช่องทางไหนในโค้ดที่จะหักส่วนแบ่งได้</p></blockquote>"

        "<h2>ได้เงินจริงเท่าไหร่</h2>"
        "<p>ส่วนที่ของแบบนี้มักไม่ยอมบอก: <b>บ่าวคนหนึ่งไม่ได้ทำให้รวย</b> "
        "นี่คือการคำนวณด้วยตัวเลขจริงจากคลังข้อมูลนี้ ไม่ใช่ตัวเลขที่แต่งขึ้น:</p>"
        "<div class=tablewrap><table><tr><th>ขั้น</th><th>อัตรา</th>"
        "<th class=num>จากผู้เข้าชม ๑,๐๐๐ ครั้ง</th></tr>"
        "<tr><td>คนที่เห็นหุ่น</td><td>—</td><td class=num>1,000</td></tr>"
        "<tr><td>คนที่กดเข้าไปดู</td><td>1–3% เป็นอัตราปกติของแบนเนอร์</td>"
        "<td class=num>10–30</td></tr>"
        "<tr><td>คลิกที่กลายเป็นการซื้อ</td>"
        "<td>1–3% เป็นอัตราปกติของมาร์เก็ตเพลส</td><td class=num>0–1</td></tr>"
        "<tr><td>มูลค่าการซื้อนั้น</td>"
        "<td>ราคากลางของรายการในคลังนี้คือ <b>฿" + f"{med:,.0f}" + "</b></td>"
        "<td class=num>฿" + f"{med:,.0f}" + "</td></tr>"
        "<tr><td>ค่าคอมมิชชันของคุณ</td>"
        "<td>ไม่กี่เปอร์เซ็นต์สำหรับสินค้าในมาร์เก็ตเพลส</td>"
        "<td class=num><b>฿2–10</b></td></tr></table></div>"
        "<p><span class=mark>เป็นการประมาณ —</span> "
        "อัตราการคลิกและอัตราการซื้อข้างบนเป็นตัวเลขทั่วไปของวงการ "
        "ไม่ใช่ค่าที่วัดจากวิดเจ็ตตัวนี้ เพราะยังไม่มีใครพกมันไปใช้ "
        "ส่วนราคากลางเป็นของจริง มาจากรายการที่มีราคา " + f"{n:,}" +
        " รายการในคลังนี้</p>"
        "<p>สรุปคือ หน้าเว็บที่มีคนดูเดือนละพันครั้ง "
        "จะทำเงินให้เจ้าของประมาณค่ากาแฟหนึ่งแก้ว ทุกเดือน ไปเรื่อยๆ ระหว่างที่นอนหลับ "
        "ประโยคนี้จริง และก็เล็กด้วย ทั้งสองส่วนสำคัญพอกัน "
        "ถ้าของแบบนี้สัญญากับคุณมากกว่าค่ากาแฟ แปลว่ามันกำลังโกหก "
        "และเหตุผลที่ยังทำมันขึ้นมาก็เหตุผลเดียวกับที่คนตั้งหุ่นไว้หลังเคาน์เตอร์ "
        "ไม่ใช่เพราะมันจะทำให้รวย แต่เพราะควรมีอะไรสักอย่างทำงานอยู่ตอนที่เราไม่ได้ทำ</p>"

        "<h2>ตารางบนอกของมัน</h2>"
        "<p>แผ่นยันต์บนอกหุ่นทุกตัวเป็น<b>จตุรัสกล</b>ของจริง "
        "คือทุกแถว ทุกหลัก และแนวทแยงทั้งสอง บวกได้เท่ากันหมด "
        "และหน้านี้พิมพ์ผลรวมไว้ข้างรูปให้คุณลองบวกเองได้ "
        "สร้างด้วย<b>วิธีสยาม</b> (Siamese method) — เริ่มที่กลางแถวบน "
        "แล้วเดินขึ้นไปทางขวา ถ้าช่องที่จะไปมีเลขอยู่แล้วก็เลื่อนลงมาหนึ่งแถว</p>"
        "<p>ชื่อของวิธีนี้มีที่มาที่ควรเล่าให้ครบ ซีมง เดอ ลา ลูแบร์ "
        "เป็นหัวหน้าคณะทูตของพระเจ้าหลุยส์ที่ ๑๔ มาสยามเมื่อ พ.ศ. ๒๒๓๐ "
        "และกลับฝรั่งเศสต้นปีถัดมา "
        "หนังสือที่เขาเขียนเมื่อกลับไปมีบทหนึ่งว่าด้วยปัญหาจตุรัสกล "
        "และกฎในบทนั้นก็คือกฎที่ยุโรปเรียกว่า<i>วิธีสยาม</i>มาจนทุกวันนี้ "
        "<span class=mark>แต่ต้องบอกไว้ —</span> "
        "ตามคำของเดอ ลา ลูแบร์เอง วิธีนี้เขาได้มาจากผู้โดยสารร่วมเรือ "
        "ชื่อนายแวงซองต์ ซึ่งได้มาจากเมืองสุรัตในอินเดียอีกที "
        "เทคนิคที่ยุโรปเก็บไว้ใต้ชื่อ “สยาม” จึงไม่ได้เริ่มที่นี่ "
        "และนี่คือเรื่องที่มาแบบที่คลังข้อมูลนี้ตั้งใจจะรักษาให้ตรง "
        "ทั้งที่ตัดออกไปจะง่ายกว่า</p>"
        "<p>วิชายันต์ไทยมี<b>ยันต์ตาราง</b>ที่ใช้ตัวเลขอยู่แล้ว "
        "แผ่นตัวเลขบนอกหุ่นจึงไม่ใช่ของที่คิดขึ้นใหม่ "
        "<span class=mark>ส่วนที่เป็นความเห็นของผู้ทำ —</span> "
        "การเลือกใช้จตุรัสแบบเดอ ลา ลูแบร์โดยเฉพาะเป็นการตัดสินใจของผู้ทำ "
        "เพราะเป็นวิธีเดียวที่มีเส้นทางระหว่างสยามกับโลกภายนอกบันทึกไว้ชัด "
        "และเพราะมันทำให้รูปวาดกล่าวอ้างอะไรบางอย่างที่คุณตรวจสอบได้ด้วยการบวกเลข</p>"

        "<h2>วันที่มันอ่าน</h2>"
        "<p>ของที่มันไปเอามาไม่ได้สุ่ม การนับวันแบบไทยใช้<b>สัปดาห์แปดวัน</b> "
        "คือเจ็ดวัน โดยวันพุธแยกเป็นกลางวันกับกลางคืน "
        "และกลางคืนเป็นของพระราหู แต่ละวันมีเทวดาประจำ มีสี และมีปางพระ "
        "หุ่นอ่านสิ่งเหล่านี้ บวกกับดวงจันทร์ "
        "ซึ่งคำนวณจากมุมห่างจริงของดวงจันทร์ด้วยชุดสมการเดียวกับที่ใช้ใน"
        "<a href='/moon/'>หน้ากลไกดวงจันทร์</a> "
        "ซึ่งตรวจเทียบกับ JPL DE440 ไว้แล้วว่าคลาดไม่ถึงครึ่งองศา</p>"
        "<div class=tablewrap><table><tr><th>วัน</th><th>เทวดา</th><th>สี</th>"
        "<th>ไปเอาอะไรมา</th></tr>" +
        "".join(
            "<tr><td>วัน" + d["th"] + "</td><td>" + d["graha"] + "</td><td>" +
            d["colourNameTh"] + "</td><td>" + THEMES[d["theme"]]["term"] +
            " — " + THEMES[d["theme"]]["th"] + "</td></tr>" for d in DAYS) +
        "</table></div>"
        "<p><span class=mark>ส่วนที่เป็นความเห็นของผู้ทำ —</span> "
        "การจับคู่วันกับของในคอลัมน์สุดท้ายเป็นการตีความของผู้ทำ "
        "โดยอิงจากหน้าที่ของเทวดาแต่ละองค์ตามที่บันทึกไว้ — "
        "พระพุธเป็นเทวดาแห่งการค้า วันพุธจึงไปเอานางกวัก "
        "พระศุกร์เป็นเทวดาแห่งความรัก วันศุกร์จึงไปเอาสีผึ้ง "
        "ส่วนวันพฤหัสบดีเป็น<b>วันไหว้ครู</b> จึงไปเอาผ้ายันต์ "
        "ซึ่งเป็นของที่ครูลงอักขระแล้วมอบให้ "
        "ตัวเทวดาและหน้าที่ของท่านเป็นของตามประเพณี "
        "แต่ว่าของชิ้นไหนคู่กับวันไหนเป็นการอ่านของผู้ทำ</p>"

        "<h3>วันพระมันหยุด</h3>"
        "<p>ในวันพระทั้งสี่ของแต่ละเดือนทางจันทรคติ หุ่นจะแสดงแค่วัน "
        "และ<b>ไม่ขายอะไรเลย</b> ไม่มีสินค้า ไม่มีลิงก์ ไม่มีรายได้ "
        "นั่นทำให้เจ้าของเสียรายได้ไปราวหนึ่งในแปด และเรื่องนี้ต่อรองไม่ได้ "
        "เพราะประเพณีเป็นอย่างนั้น "
        "และเพราะของที่ขายคุณได้ทุกวันไม่มีเว้นนั้นไม่ใช่บ่าว แต่เป็นป้ายโฆษณา</p>"
        "<p>และมันหยุดใน<b>วันสำคัญทางศาสนา</b>ด้วย — วันมาฆบูชา วันวิสาขบูชา "
        "วันอัฏฐมีบูชา วันอาสาฬหบูชา วันเข้าพรรษา วันออกพรรษา และวันลอยกระทง "
        "หกในเจ็ดวันนั้นตรงกับวันพระอยู่แล้ว แต่มีวันหนึ่งที่ไม่ตรง คือ"
        "<b>วันเข้าพรรษา</b> ซึ่งเป็นแรม ๑ ค่ำ ถัดจากวันอาสาฬหบูชาหนึ่งวัน "
        "และช่วงหนึ่งหน้านี้จะขึ้นชื่อวันสำคัญไว้ด้านบน "
        "แล้วขายพระให้คุณอยู่ข้างใต้ ซึ่งแย่กว่าทั้งการหยุดและการไม่พูดอะไรเลย "
        "ตอนนี้มันหยุดแล้ว</p>"
        "<p><span class=mark>เคยถูกเสนอ และปฏิเสธไป —</span> "
        "ทางที่คิดได้ง่ายที่สุดคือให้วันพระเป็นวันที่<em>เจ้าของเว็บ</em>ได้เงินแทน "
        "ไม่มีใครสังเกตหรอก และมันคือหนึ่งในแปดของทั้งหมด "
        "แต่เราปฏิเสธ และเขียนเหตุผลไว้ตรงนี้เพื่อให้มันยังถูกปฏิเสธต่อไป "
        "ถ้าวันพระคือวันที่เราขาย แปลว่าของชิ้นนี้ขายทุกวันไม่มีเว้น "
        "และการหยุดนั้นก็ไม่เคยมีจริง มันเป็นแค่การคืนกำไรให้เจ้าของเว็บ "
        "แล้วคำกล่าวอ้างสามข้อที่ดังที่สุดในหน้านี้ — ไม่หักส่วนแบ่ง, "
        "ไม่มีช่องทางในโค้ดที่จะหักได้, และมันหยุด — ก็จะกลายเป็นเท็จพร้อมกันทั้งสามข้อ "
        "ในวันเหล่านั้นไม่มีใครได้เงิน รวมทั้งเราด้วย</p>"
        "<p>วันไหนเป็นวันพระนั้นใช้<b>ตารางที่เผยแพร่ไว้ ไม่ได้คำนวณเอา</b> "
        "และเหตุผลควรบอกไว้ เพราะมันมาจากการวัด ไม่ใช่ความชอบ "
        "ก่อนหน้านี้เคยคำนวณวันพระจากดวงจันทร์สองแบบ — "
        "แบบหนึ่งจากมุมห่าง อีกแบบจากค่าเฉลี่ยของเดือนจันทรคติ "
        "เทียบกับวันพระที่ประกาศไว้ ๔๙ วันของปี ๒๕๖๙ ได้ถูก <b>๑๗</b> และ "
        "<b>๓๗</b> วันตามลำดับ "
        "แบบแรกทำให้วิดเจ็ตขายของฉลุยตลอดวันขึ้น ๘ ค่ำ "
        "ซึ่งเป็นวันเดียวกับที่สร้างหน้านี้ขึ้นมาพอดี</p>"
        "<p>นี่ไม่ใช่จุดบกพร่องที่ปรับให้ตรงได้ "
        "<b>ปฏิทินจันทรคติไทยเป็นปฏิทินเชิงคำนวณแบบตายตัว</b> "
        "เดือนสลับ ๒๙ และ ๓๐ วัน พร้อมกฎการเพิ่มเดือนเพิ่มวัน "
        "จึงตั้งใจไม่เดินตามดวงจันทร์จริง "
        "และดาราศาสตร์ที่แม่นขึ้นก็ไม่ทำให้ตรงกันได้ "
        "อีกทั้งปี ๒๕๖๙ ยังเป็นปีอธิกมาสที่มี<b>เดือน ๘ หลัง</b> "
        "ซึ่งแบบจำลองดวงจันทร์ไม่มีทางรู้ได้เลย "
        "วันพระจึงถูกพกมาเป็นรายการที่เผยแพร่ไว้ "
        "แบบเดียวกับที่หน้ากลไกดวงจันทร์พกตารางคราสมา: "
        "<i>เมื่อคำนวณให้ถูกในที่ที่มันทำงานไม่ได้ ก็ไปคำนวณในที่ที่ทำได้ "
        "แล้วส่งคำตอบมา</i></p>"
        "<p>๔๙ วันพอสำหรับทั้งปี เพราะวันพระสองวันติดกันห่างกันไม่เกินแปดวัน "
        "และวันทางจันทรคติเดินขึ้นวันละหนึ่ง "
        "วันอื่นๆ จึงนับต่อจากวันพระที่ใกล้ที่สุดได้หมด "
        "<span class=mark>ขีดจำกัด พูดตรงๆ —</span> ตารางครอบคลุมแค่ <b>พ.ศ. ๒๕๖๙</b> "
        "นอกช่วงนั้นหน้านี้ยังรู้ดวงจันทร์แม่นเหมือนเดิม "
        "แต่จะไม่พิมพ์เลขค่ำ และไม่อ้างว่าวันไหนเป็นวันพระ เพราะจะเป็นการเดา "
        "และมันจะบอกคุณตรงๆ ในวันนั้นเลย "
        "<b>ปฏิทินของวัดคือของจริง</b> และเป็นอย่างนั้นมาตลอด</p>"

        "<h2>สิ่งที่มันไม่ทำ</h2>"
        "<ul>"
        "<li><b>ไม่มีบัญชีผู้ใช้</b> ไม่มีอะไรให้สมัคร "
        "หุ่นอยู่ในเบราว์เซอร์ของคุณและในลิงก์ที่คุณคัดลอก</li>"
        "<li><b>ไม่มีการติดตาม</b> ไม่มีคุกกี้ ไม่มีพิกเซล ไม่มีสคริปต์ของบุคคลที่สาม "
        "สมุดบัญชีนับอยู่ใน <code>localStorage</code> ของเครื่องที่กำลังดูอยู่ "
        "และตัวเลขนั้นไม่เคยออกไปไหน</li>"
        "<li><b>เงินไม่ผ่านมือเรา</b> เครือข่ายของคุณจ่ายให้คุณโดยตรง "
        "เราไม่ได้อยู่ในเส้นทางนั้น</li>"
        "<li><b>มันนับเงินของคุณไม่ได้</b> สมุดบัญชีนับ “การเคาะประตู” คือจำนวนคลิก "
        "เพราะนั่นคือทั้งหมดที่หน้าเว็บในเบราว์เซอร์มองเห็นได้จริง "
        "ส่วนเงินนั้นแดชบอร์ดของเครือข่ายคุณเป็นคนนับ "
        "วิดเจ็ตไหนที่โชว์ยอดเงินบาทให้คุณดูทั้งที่มองไม่เห็นบัญชีคุณ "
        "คือกำลังโชว์ตัวเลขที่มันแต่งขึ้นเอง</li>"
        "<li><b>มันไม่เลือกโปรแกรมให้คุณ</b> "
        "คุณสอนรูปแบบ url แบบไหนมันก็ส่งแบบนั้น "
        "และมันแสดง url เต็มๆ ให้ดูก่อนบันทึกเสมอ "
        "เพราะเครือข่ายแอฟฟิลิเอตเปลี่ยนรูปแบบลิงก์กันได้ "
        "และหน้านี้จะไม่ทำเป็นไม่รู้</li>"
        "</ul>"

        "<h2>ที่มาของข้อมูล</h2>"
        "<p>รายการที่มันไปเอามาเป็นข้อมูลจริงจากคลังฝั่งตลาดของเว็บนี้ "
        "ชื่อจริง ราคาบาทจริง ที่อยู่จริง เก็บและลงวันที่ไว้เหมือนทุกอย่างในนี้ "
        "ตลาดถูกบันทึกไว้ในฐานะ<b>การปฏิบัติจริง</b> "
        "ไม่ได้ถูกแยกว่าอันไหนของแท้อันไหนของนักท่องเที่ยว — "
        "คนซื้อของพวกนี้กันจริง มันจึงเป็นส่วนหนึ่งของประเพณี "
        "และหุ่นที่เดินไปตลาดก็กำลังทำเรื่องธรรมดาที่สุดในโลก</p>"
        "<p>ตารางวันพระมาจากปฏิทินวันพระ ๒๕๖๙ ที่ไทยพีบีเอสเผยแพร่ "
        "ตรวจเทียบกับ myhora.com เฉพาะเดือนกรกฎาคม "
        "เรื่องคณะทูตของเดอ ลา ลูแบร์ วิธีสยาม "
        "และข้อที่ว่าวิธีนี้มาถึงเขาจากเมืองสุรัตผ่านนายแวงซองต์ "
        "อยู่ในบันทึกการเดินทางของเขาเอง "
        "ส่วนสัปดาห์แปดวัน เทวดาประจำวัน สีและปางพระ เป็นความรู้ไทยทั่วไป "
        "ชุดสมการดวงจันทร์เป็นชุดเดียวกับที่อธิบายไว้ใน"
        "<a href='/moon/'>หน้ากลไกดวงจันทร์</a> พร้อมค่าความคลาดที่วัดไว้แล้ว</p>"
        "</section>")


# -------------------------------------------------------------------- page
def _howto() -> str:
    """Plain words, above the forge, before any jargon.

    Written after the maker pointed out — from having actually run affiliate
    sites — that people get confused by this kind of setup and dislike pasting
    things that look like code. Three consequences, all of them here:

    * The FOUR STEPS are stated in one screen before anything asks for input.
    * The Lazada-Thailand constraint is stated LOUDLY. It is the single fact
      that decides whether the thing earns anything at all, and the page did
      not say it anywhere. An Amazon tag on a Lazada link earns nothing, and
      somebody would have found that out the slow way.
    * The worked example shows the transformation as three labelled ROWS in
      plain language, not as a template with braces in it.
    """
    return (
        "<section class=howto>"

        # ---------------------------------------------------------- English
        "<div class=en-only>"
        "<h3>How this works, in plain words</h3>"
        "<div class=hsteps>"
        "<div class=hstep><span class=hn>1</span><b>Make an effigy.</b>"
        "<p>Type a name. That is the whole of it — free, no sign-up, nothing to "
        "install. You get a drawing that is yours and nobody else's.</p></div>"
        "<div class=hstep><span class=hn>2</span>"
        "<b>Paste in one affiliate link you already have.</b>"
        "<p>Not code — just a link, the ordinary kind you would post anywhere. "
        "The page reads it, works out how your links are built, and shows you "
        "the result so you can check it.</p></div>"
        "<div class=hstep><span class=hn>3</span><b>Share it.</b>"
        "<p>One button sends your effigy to LINE, Facebook, anywhere. That is a "
        "normal web link — no code involved. If you have your own website you "
        "<em>can</em> paste it in there instead, but you do not have to.</p></div>"
        "<div class=hstep><span class=hn>4</span>"
        "<b>Every day it picks one amulet and links to it — as you.</b>"
        "<p>If somebody buys, your affiliate programme pays <em>you</em>, "
        "directly. We are not in the middle of it and never see the click.</p>"
        "</div>"
        "</div>"

        "<div class=warnbox><b>The one thing that decides whether this earns:</b>"
        "<p>The effigy links to real listings on <b>Lazada Thailand</b> "
        "(lazada.co.th) — that is what this catalogue is made of. So your "
        "affiliate link has to come from a programme that <b>pays commission on "
        "lazada.co.th</b>. Two doors are worth trying, and which of them is open "
        "changes: <a href='https://involve.asia' target=_blank "
        "rel='noopener nofollow'>Involve Asia</a>, the affiliate network, and "
        "<b>LazAffiliate</b>, Lazada's own programme, reached through Seller "
        "Centre → Marketing Centre → Super Affiliate.</p>"
        "<p><span class=mark>Checked, and worth your knowing —</span> in "
        "<b>July 2026</b> a search of Involve Asia's advertiser directory for "
        "“lazada” returned only B2B offers for Indonesia and Malaysia and "
        "<i>Lazada Talent</i> creator campaigns; Involve's own guide describes a "
        "general “Lazada Thailand” offer, but we could not find it listed. "
        "Programme line-ups shift. <b>Check what is actually on offer in your "
        "own account rather than trusting this paragraph</b> — and if the answer "
        "has changed, we would like to know.</p>"
        "<p>An Amazon or Shopee link will still <em>work</em> — the effigy will "
        "happily wear it — but it will earn you nothing on a Lazada page, "
        "because those programmes do not pay for Lazada sales. Nobody will tell "
        "you this except the arithmetic at the end of the month, so it is said "
        "here instead.</p></div>"

        "<details class=noaff><summary>I don’t have an affiliate link yet</summary>"
        "<p>Then the effigy still works — it reads the day, it fetches, it "
        "shares. It just does not earn, and it says so on its own face rather "
        "than pretending.</p>"
        "<p>Getting one is free. Try <a href='https://involve.asia' "
        "target=_blank rel='noopener nofollow'>Involve Asia</a> — make a "
        "publisher account, then look under <b>Offers</b>, not Browse "
        "Advertisers, for anything covering Lazada Thailand. If nothing there "
        "fits, go to Lazada directly: Seller Centre → Marketing Centre → "
        "<b>Super Affiliate</b>. Either way, generate a link for <em>any</em> "
        "Lazada product and paste it into the box below. You only ever do this "
        "once — the page learns the pattern and builds the rest itself.</p>"
        "<p><b>It does not matter which programme you end up in.</b> The page "
        "never asks you to name it and does not need to know: it reads the "
        "shape of the one link you paste. That is deliberate, because these "
        "programmes come and go and a page that hard-coded one of them would "
        "quietly stop working.</p>"
        "<p class=nb><b>Not affiliated.</b> We get nothing if you sign up. "
        "There is no referral code in that link, and there is nowhere in this "
        "page a cut could be taken from.</p></details>"

        "<div class=worked><b>What actually happens to your link</b>"
        "<div class=wrow><span class=wl>You paste, once</span>"
        "<code>https://invol.co/aff_m?offer_id=100974&amp;aff_id="
        "<b>884422</b>&amp;url=<i>…a Lazada product…</i></code></div>"
        "<div class=wrow><span class=wl>It works out</span>"
        "<span class=wt>“their id is <b>884422</b>, and the product goes at the "
        "end”</span></div>"
        "<div class=wrow><span class=wl>Every day it builds</span>"
        "<span class=wt>the same link, with <b>today’s amulet</b> at the end "
        "and your id untouched</span></div>"
        "</div>"
        "</div>"

        # ------------------------------------------------------------- Thai
        "<div class=th-only>"
        "<h3>มันทำงานยังไง — แบบเข้าใจง่าย</h3>"
        "<div class=hsteps>"
        "<div class=hstep><span class=hn>1</span><b>สร้างหุ่น</b>"
        "<p>พิมพ์ชื่อลงไป แค่นั้นจริงๆ — ฟรี ไม่ต้องสมัคร ไม่ต้องติดตั้งอะไร "
        "แล้วคุณจะได้รูปหุ่นที่เป็นของคุณคนเดียว</p></div>"
        "<div class=hstep><span class=hn>2</span>"
        "<b>วางลิงก์แอฟฟิลิเอตที่คุณมีอยู่แล้วหนึ่งอัน</b>"
        "<p>ไม่ใช่โค้ด — เป็นลิงก์ธรรมดาแบบที่คุณโพสต์ที่ไหนก็ได้ "
        "หน้านี้จะอ่านลิงก์นั้น หารูปแบบของมันออกมา "
        "แล้วแสดงผลให้ดูเพื่อให้คุณตรวจเองได้</p></div>"
        "<div class=hstep><span class=hn>3</span><b>แชร์</b>"
        "<p>กดปุ่มเดียวก็ส่งหุ่นของคุณเข้า LINE เฟซบุ๊ก หรือที่ไหนก็ได้ "
        "มันเป็นลิงก์เว็บธรรมดา ไม่มีโค้ดเข้ามาเกี่ยว "
        "ถ้ามีเว็บของตัวเองจะเอาไปฝังก็ได้ แต่ไม่จำเป็นต้องทำ</p></div>"
        "<div class=hstep><span class=hn>4</span>"
        "<b>ทุกวันมันจะเลือกพระหนึ่งองค์แล้วทำลิงก์ในนามของคุณ</b>"
        "<p>ถ้ามีคนซื้อ โปรแกรมแอฟฟิลิเอตของคุณจ่ายให้<em>คุณ</em>โดยตรง "
        "เราไม่ได้อยู่ตรงกลาง และไม่เคยเห็นการคลิกเลยสักครั้ง</p></div>"
        "</div>"

        "<div class=warnbox><b>เรื่องเดียวที่ชี้ขาดว่าจะได้เงินหรือไม่:</b>"
        "<p>หุ่นทำลิงก์ไปยังรายการสินค้าจริงบน <b>Lazada ไทย</b> "
        "(lazada.co.th) เพราะคลังข้อมูลนี้ทำมาจากที่นั่น "
        "ลิงก์แอฟฟิลิเอตของคุณจึงต้องมาจากโปรแกรมที่"
        "<b>จ่ายค่าคอมมิชชันให้กับ lazada.co.th</b> "
        "มีสองทางที่ควรลอง และทางไหนเปิดอยู่บ้างก็เปลี่ยนไปเรื่อยๆ: "
        "<a href='https://involve.asia' target=_blank rel='noopener nofollow'>"
        "Involve Asia</a> ซึ่งเป็นเครือข่ายแอฟฟิลิเอต และ <b>LazAffiliate</b> "
        "โปรแกรมของ Lazada เอง เข้าทาง Seller Centre → Marketing Centre → "
        "Super Affiliate</p>"
        "<p><span class=mark>ตรวจแล้ว และควรรู้ไว้ —</span> "
        "เมื่อ<b>กรกฎาคม ๒๕๖๙</b> ค้นคำว่า “lazada” "
        "ในไดเรกทอรีผู้ลงโฆษณาของ Involve Asia "
        "เจอเพียงออฟเฟอร์ B2B ของอินโดนีเซียกับมาเลเซีย "
        "และแคมเปญครีเอเตอร์ <i>Lazada Talent</i> เท่านั้น "
        "คู่มือของ Involve เองพูดถึงออฟเฟอร์ทั่วไปชื่อ “Lazada Thailand” "
        "แต่เราหาไม่เจอในรายการ รายชื่อโปรแกรมมีการเปลี่ยนแปลงอยู่เสมอ "
        "<b>กรุณาตรวจจากบัญชีของคุณเองว่ามีอะไรให้สมัครบ้าง "
        "อย่าเชื่อย่อหน้านี้</b> — และถ้าคำตอบเปลี่ยนไปแล้ว บอกเราด้วยจะดีมาก</p>"
        "<p>ลิงก์ของ Amazon หรือ Shopee ยัง<em>ใช้ได้</em>อยู่ "
        "หุ่นก็จะสวมให้ตามที่บอก แต่จะไม่ได้เงินสักบาทจากหน้า Lazada "
        "เพราะโปรแกรมพวกนั้นไม่จ่ายให้ยอดขายของ Lazada "
        "เรื่องนี้ไม่มีใครบอกคุณ นอกจากตัวเลขตอนสิ้นเดือน จึงขอบอกไว้ตรงนี้แทน</p>"
        "</div>"

        "<details class=noaff><summary>ยังไม่มีลิงก์แอฟฟิลิเอต</summary>"
        "<p>หุ่นก็ยังทำงานได้ตามปกติ — อ่านวัน ไปหาของ แชร์ได้ "
        "เพียงแต่ยังไม่ได้เงิน และมันจะบอกไว้บนตัวเองตรงๆ ไม่ทำเป็นว่าได้</p>"
        "<p>สมัครฟรี ลองที่ <a href='https://involve.asia' target=_blank "
        "rel='noopener nofollow'>Involve Asia</a> — สมัครบัญชีผู้เผยแพร่ "
        "แล้วดูในหมวด <b>Offers</b> (ไม่ใช่ Browse Advertisers) "
        "ว่ามีอะไรที่ครอบคลุม Lazada ไทยบ้าง "
        "ถ้าไม่มีอะไรเหมาะ ให้ไปที่ Lazada โดยตรง: Seller Centre → "
        "Marketing Centre → <b>Super Affiliate</b> "
        "ทางไหนก็ได้ ขอแค่สร้างลิงก์ของสินค้า Lazada <em>ชิ้นไหนก็ได้</em> "
        "แล้วเอามาวางในช่องด้านล่าง "
        "ทำแค่ครั้งเดียวพอ เพราะหน้านี้จะจำรูปแบบแล้วสร้างที่เหลือเอง</p>"
        "<p><b>คุณจะอยู่โปรแกรมไหนก็ไม่สำคัญ</b> "
        "หน้านี้ไม่เคยถามชื่อโปรแกรม และไม่จำเป็นต้องรู้ "
        "เพราะมันอ่านรูปแบบจากลิงก์อันเดียวที่คุณวางให้ "
        "ที่ทำแบบนี้เพราะโปรแกรมพวกนี้มาแล้วก็ไป "
        "หน้าเว็บที่ฝังชื่อโปรแกรมใดโปรแกรมหนึ่งไว้ตายตัวจะหยุดทำงานเงียบๆ</p>"
        "<p class=nb><b>เราไม่ได้เป็นตัวแทนของใคร</b> "
        "ถ้าคุณสมัคร เราไม่ได้อะไรเลย ลิงก์นั้นไม่มีรหัสแนะนำของเราอยู่ "
        "และในหน้านี้ไม่มีจุดไหนที่จะหักส่วนแบ่งได้</p></details>"

        "<div class=worked><b>ลิงก์ของคุณจะถูกทำอะไรบ้าง</b>"
        "<div class=wrow><span class=wl>คุณวางครั้งเดียว</span>"
        "<code>https://invol.co/aff_m?offer_id=100974&amp;aff_id="
        "<b>884422</b>&amp;url=<i>…สินค้า Lazada…</i></code></div>"
        "<div class=wrow><span class=wl>มันถอดได้ว่า</span>"
        "<span class=wt>“รหัสของเขาคือ <b>884422</b> "
        "และสินค้าอยู่ท้ายสุด”</span></div>"
        "<div class=wrow><span class=wl>ทุกวันมันจะสร้าง</span>"
        "<span class=wt>ลิงก์แบบเดิม โดยใส่<b>พระของวันนั้น</b>ไว้ท้ายสุด "
        "และไม่แตะรหัสของคุณ</span></div>"
        "</div>"
        "</div>"

        "</section>")


def _share_grid() -> str:
    """Every way out of here, in three labelled groups.

    Grouped after the maker asked, reasonably, "what do the buttons do?" — a
    wall of twelve logos answers that question for nobody. Each group now has
    a heading and one line saying what pressing anything in it will actually
    cause, including the reassurance that the social buttons only OPEN the app
    with the link ready; nothing is posted until you press send over there.
    """
    return (
        "<p class=grouphead><span class=en-only>Send it to someone</span>"
        "<span class=th-only>ส่งให้คนอื่น</span></p>"
        "<p class=groupnote><span class=en-only>Opens that app with your "
        "effigy’s link already filled in. <b>Nothing is posted until you press "
        "send there</b> — these buttons cannot post for you.</span>"
        "<span class=th-only>เปิดแอปนั้นขึ้นมาพร้อมลิงก์หุ่นของคุณที่กรอกไว้ให้แล้ว "
        "<b>ยังไม่มีอะไรถูกโพสต์จนกว่าคุณจะกดส่งในแอปนั้นเอง</b> "
        "ปุ่มพวกนี้โพสต์แทนคุณไม่ได้</span></p>"
        "<div class=sharegrid>"
        "<button id=sh-native style='display:none'><span class='ic ic-native'>"
        "⤴</span><span data-t=nativeShare></span></button>"
        "<a id=sh-line href='#' target=_blank rel=noopener>"
        "<span class='ic ic-line'>L</span><span data-t=lineShare></span></a>"
        "<a id=sh-fb href='#' target=_blank rel=noopener>"
        "<span class='ic ic-fb'>f</span>Facebook</a>"
        "<a id=sh-x href='#' target=_blank rel=noopener>"
        "<span class='ic ic-x'>X</span>X / Twitter</a>"
        "<a id=sh-tg href='#' target=_blank rel=noopener>"
        "<span class='ic ic-tg'>✈</span>Telegram</a>"
        "<a id=sh-wa href='#' target=_blank rel=noopener>"
        "<span class='ic ic-wa'>W</span>WhatsApp</a>"
        "<a id=sh-rd href='#' target=_blank rel=noopener>"
        "<span class='ic ic-rd'>r</span>Reddit</a>"
        "<a id=sh-mail href='#'><span class='ic ic-mail'>✉</span>Email</a>"
        "</div>"

        "<p class=grouphead><span class=en-only>Copy it yourself</span>"
        "<span class=th-only>คัดลอกเอง</span></p>"
        "<p class=groupnote><span class=en-only>Puts your effigy’s web address "
        "on the clipboard, so you can paste it into a message, a bio, a "
        "profile — anywhere a link goes. It is an ordinary link, not "
        "code.</span>"
        "<span class=th-only>คัดลอกที่อยู่เว็บของหุ่นคุณไว้ในคลิปบอร์ด "
        "เอาไปวางในแชต ในไบโอ ในโปรไฟล์ หรือที่ไหนก็ได้ที่วางลิงก์ได้ "
        "มันเป็นลิงก์ธรรมดา ไม่ใช่โค้ด</span></p>"
        "<div class=sharegrid>"
        "<button id=copy-link><span class='ic ic-copy'>⧉</span>"
        "<span data-t=copyLink></span></button>"
        "</div>"

        "<p class=grouphead><span class=en-only>Keep a copy</span>"
        "<span class=th-only>เก็บไว้</span></p>"
        "<p class=groupnote><span class=en-only>Downloads a file to your "
        "device. The picture is just your effigy, to print or post. The whole "
        "widget is one file that still works with no internet at all.</span>"
        "<span class=th-only>ดาวน์โหลดไฟล์ลงเครื่องคุณ "
        "รูปคือตัวหุ่นของคุณเฉยๆ เอาไปพิมพ์หรือโพสต์ได้ "
        "ส่วนทั้งหมดในไฟล์เดียวคือไฟล์ที่เปิดใช้ได้แม้ไม่มีอินเทอร์เน็ต</span></p>"
        "<div class=sharegrid>"
        "<button id=dl-svg><span class='ic ic-dl'>⬇</span>"
        "<span data-t=dlSvg></span></button>"
        "<a href='/hun/hun-offline.html' download>"
        "<span class='ic ic-dl'>⬇</span><span data-t=dlAll></span></a>"
        "</div>")


def body(pool: dict, stats: dict, nav: str = "", embed: bool = False,
         frozen_note: str = "",
         base: str = "https://wichaa.net/hun/") -> str:
    """The page body. `pool` is theme-key -> list of listing dicts, baked in so
    the widget makes no network request at all (the portability contract every
    widget on this site is held to). `embed` strips everything but the effigy
    and the day.

    NOTE ON THE TWO BASES: the embed iframe points at /hun/embed/, a SEPARATE
    built file, not /hun/?embed=1. A static host cannot vary its HTML by query
    string, so an ?embed=1 url would serve the whole page — header, forge,
    essay and all — inside the bearer's iframe. (The site's older widgets hand
    out ?embed=1 embed codes and have exactly that problem on the published
    site; not fixed here, but not repeated either.) The bearer's own PERMALINK
    is the full page at /hun/?k=… — there the `k` payload is read by JS, which
    a static host handles fine.
    """
    sample = "https://www.lazada.co.th/products/pdp-i5358370317.html"

    stage = ("<div class=hunwrap>"
             "<div class=hunstage id=stage></div>"
             "<div id=reading></div>"
             "</div>")

    if embed:
        inner = (stage +
                 "<p style='font-size:12px;color:#6b6558;margin:2px 0 0'>"
                 "<a href='https://wichaa.net/hun/' target=_blank "
                 "rel=noopener style='color:#6b6558'>หุ่นพยนต์ · wichaa.net</a>"
                 "</p>")
    else:
        opts = "".join("<option value='" + str(d["i"]) + "'></option>"
                       for d in DAYS)
        presets = "".join("<option value='" + p["id"] + "'></option>"
                          for p in KHATA_PRESETS)

        forge = (
            "<section class=forge>"
            "<h3 data-t=forgeH></h3><p class=lede data-t=forgeLede></p>"

            "<div class=step><div class=steph><span class=stepn>1</span>"
            "<b data-t=step1></b></div>"
            "<div class=frow><label for=f-name data-t=fName></label>"
            "<input id=f-name data-tph=fNamePh autocomplete=off "
            "spellcheck=false></div>"
            "<div class=frow><span class=hint data-t=fNameHint></span></div>"
            "<div class=frow><label for=f-born data-t=fBorn></label>"
            "<select id=f-born>" + opts + "</select></div>"
            "<div class=frow><span class=hint data-t=fBornHint></span></div>"
            "</div>"

            "<div class=step><div class=steph><span class=stepn>2</span>"
            "<b data-t=step2></b></div>"
            "<div class=learn><b class=lh data-t=learnH></b>"
            "<p data-t=learnLede></p>"
            "<div class=learnrow>"
            "<input id=learn-in data-tph=learnPh spellcheck=false "
            "autocomplete=off inputmode=url>"
            "<button class=pri id=learn-go data-t=learnBtn "
            "style='font:inherit;font-weight:700;font-size:14px;padding:10px 16px;"
            "border:1px solid transparent;border-radius:9px;"
            "background:var(--teal);color:#fff;cursor:pointer'></button>"
            "</div><p id=learn-msg class=learnmsg></p></div>"
            "<details class=adv id=adv><summary data-t=advanced></summary>"
            "<div class=frow><label for=f-preset data-t=fPreset></label>"
            "<select id=f-preset>" + presets + "</select></div>"
            "<div class=frow><label for=f-tpl data-t=fTpl></label>"
            "<input id=f-tpl spellcheck=false autocomplete=off "
            "placeholder='{url}'></div>"
            "<div class=frow><span class=hint data-t=fTplHint></span></div>"
            "</details>"
            "<div id=k-status class=kstat></div>"
            "<p style='font-size:13.5px;margin:0 0 5px;color:var(--muted)'>"
            "<b data-t=checkThis></b></p>"
            "<div id=k-preview class=preview></div>"
            "</div>"

            # STEP 3 — TWO ROADS, AND THE ONE WITHOUT CODE IS THE DEFAULT.
            # The first version put a textarea full of <iframe …> at the front
            # of this step. The maker's note from having run affiliate sites is
            # that people baulk at pasting something that looks like code, and
            # they are right to: it is the scariest thing on the page and most
            # bearers never need it. Sharing a link needs no code at all, so
            # that is now the whole of the visible step, and the embed sits
            # behind a disclosure with per-platform instructions for the few
            # who do have a site to put it on.
            "<div class=step><div class=steph><span class=stepn>3</span>"
            "<b data-t=step3></b></div>"
            "<div class=sharesplit>"
            "<div class=swaycard><b><span class=en-only>Most people: just "
            "share the link</span><span class=th-only>คนส่วนใหญ่: "
            "แค่แชร์ลิงก์</span></b>"
            "<p><span class=en-only>No code, nothing to install. Your effigy "
            "has a normal web address — send it on LINE, post it, put it in "
            "your bio. Everything you need is in <b>Share it</b> just "
            "below.</span>"
            "<span class=th-only>ไม่มีโค้ด ไม่ต้องติดตั้งอะไร "
            "หุ่นของคุณมีที่อยู่เว็บธรรมดา — ส่งทาง LINE โพสต์ "
            "หรือใส่ไว้ในไบโอก็ได้ ทุกอย่างที่ต้องใช้อยู่ในหัวข้อ "
            "<b>แชร์</b> ด้านล่างนี้</span></p></div>"
            "<div class=swaycard><b><span class=en-only>If you have your own "
            "website</span><span class=th-only>ถ้าคุณมีเว็บของตัวเอง</span>"
            "</b>"
            "<p><span class=en-only>Then you can embed it, so the effigy "
            "stands on your page and changes by itself every day. That takes "
            "one paste of code — open the box below only if you want "
            "it.</span>"
            "<span class=th-only>คุณฝังมันลงเว็บได้ "
            "หุ่นจะได้ยืนอยู่บนหน้าเว็บของคุณและเปลี่ยนเองทุกวัน "
            "อันนี้ต้องวางโค้ดหนึ่งครั้ง "
            "เปิดกล่องด้านล่างเฉพาะตอนที่ต้องการเท่านั้น</span></p></div>"
            "</div>"

            "<details class=embedwrap>"
            "<summary><span class=en-only>Show me the embed code "
            "(only if you have a website)</span>"
            "<span class=th-only>ขอดูโค้ดฝังเว็บ "
            "(เฉพาะกรณีที่มีเว็บของตัวเอง)</span></summary>"
            "<p><span class=en-only>Copy the whole block below and paste it "
            "into an <b>HTML</b> or <b>Embed</b> block on your page. You do "
            "not need to understand it, and you never need to edit it — it "
            "already has your effigy’s name and khata inside.</span>"
            "<span class=th-only>คัดลอกทั้งก้อนด้านล่าง "
            "แล้ววางลงในบล็อกแบบ <b>HTML</b> หรือ <b>Embed</b> บนหน้าเว็บของคุณ "
            "ไม่ต้องเข้าใจมัน และไม่ต้องแก้อะไรเลย "
            "เพราะชื่อและคาถาของหุ่นคุณฝังอยู่ในนั้นแล้ว</span></p>"
            "<ul class=en-only>"
            "<li><b>WordPress</b> — add a block, choose <i>Custom HTML</i>, "
            "paste.</li>"
            "<li><b>Wix</b> — Add → Embed Code → <i>Embed HTML</i>, paste.</li>"
            "<li><b>Squarespace</b> — add a <i>Code</i> block, paste.</li>"
            "<li><b>Blogger</b> — switch the post to <i>HTML view</i>, paste.</li>"
            "<li><b>Shopify</b> — a page or section that accepts custom "
            "HTML.</li>"
            "<li><b>Ghost / Notion / Webflow</b> — an <i>embed</i> block.</li>"
            "</ul>"
            "<ul class=th-only>"
            "<li><b>WordPress</b> — เพิ่มบล็อก เลือก <i>Custom HTML</i> แล้ววาง</li>"
            "<li><b>Wix</b> — Add → Embed Code → <i>Embed HTML</i> แล้ววาง</li>"
            "<li><b>Squarespace</b> — เพิ่มบล็อก <i>Code</i> แล้ววาง</li>"
            "<li><b>Blogger</b> — สลับโพสต์เป็น <i>HTML view</i> แล้ววาง</li>"
            "<li><b>Shopify</b> — หน้าหรือเซกชันที่รับ HTML เองได้</li>"
            "<li><b>Ghost / Notion / Webflow</b> — บล็อกแบบ <i>embed</i></li>"
            "</ul>"
            "<div class=embedbox>"
            "<textarea id=embed-code readonly spellcheck=false></textarea>"
            "</div>"
            "<div class=btnrow><button class=pri id=copy-embed2 "
            "data-t=copyEmbed></button></div>"
            "</details>"

            "<div class=btnrow style='margin-top:14px'>"
            "<button id=unmake data-t=unmake></button></div>"
            "</div>"
            "</section>")

        share = (
            "<section class=sharepanel>"
            "<h3 data-t=shareH></h3><p class=lede data-t=shareLede></p>"
            "<p style='font-size:13.5px;font-weight:700;margin:0 0 6px' "
            "data-t=yourLink></p>"
            "<div class=permalink><input id=permalink-box readonly "
            "spellcheck=false></div>"
            "<p id=share-hint style='font-size:13px;color:var(--muted);"
            "margin:-6px 0 12px' data-t=forgeFirst></p>"
            + _share_grid() +
            "</section>"

            "<section class=lineblock>"
            "<h3 data-t=lineH></h3><p data-t=lineLede></p>"
            "<span class=lineid>" + LINE_ID + "</span>"
            "<div class=btnrow style='display:inline-flex;vertical-align:middle'>"
            "<a class=pri href='" + LINE_URL + "' target=_blank rel=noopener "
            "style='background:#06c755;color:#fff;border-color:transparent' "
            "data-t=lineAdd></a>"
            "<button id=copy-line data-t=lineCopy></button>"
            "</div></section>"

            "<h2 style='font-family:var(--serif);font-size:22px;margin:26px 0 2px'"
            " data-t=ledgerH></h2>"
            "<p style='color:var(--muted);font-size:14.5px;margin:0' "
            "data-t=ledgerLede></p>"
            "<div class=ledger id=ledger></div>")

        langbar = ("<div class=langbar role=group aria-label='Language'>"
                   "<button data-lang=en>English</button>"
                   "<button data-lang=th>ไทย</button></div>")

        modebar = ("<div class=modebar role=group aria-label='Mode'>"
                   "<button data-mode=hun aria-pressed=true "
                   "data-t=modeHun></button>"
                   "<button data-mode=sukhwan aria-pressed=false "
                   "data-t=modeSukhwan></button></div>")

        hun_pane = ("<div class=hun-pane>" + stage + _howto() + forge + share
                    + _essay_en(stats) + _essay_th(stats) + "</div>")

        sk_pane = (
            "<div class=sk-pane>"
            "<section class=skforge>"
            "<h3 data-t=skH></h3><p class=lede data-t=skLede></p>"
            "<div class=frow><label for=sk-names data-t=skNamesH></label>"
            "<textarea id=sk-names data-tph=skNamesPh spellcheck=false>"
            "</textarea></div>"
            "<p class=skprivacy data-t=skPrivacy></p>"
            "</section>"
            "<div class=skstage><div id=sk-reading></div></div>"
            "<p class=sknote><span class=en-only>"
            + html.escape(SUKHWAN_NOTE[0]) + "</span><span class=th-only>"
            + html.escape(SUKHWAN_NOTE[1]) + "</span></p>"
            "<section class=sharepanel>"
            "<h3 data-t=skShareH></h3><p class=lede data-t=skShareLede></p>"
            "<div class=permalink><input id=sk-permalink-box readonly "
            "spellcheck=false></div>"
            "<p id=sk-share-hint style='font-size:13px;color:var(--muted);"
            "margin:-6px 0 12px' data-t=skEmpty></p>"
            "<div class=btnrow>"
            "<button id=sk-native style='display:none'>"
            "<span class='ic ic-native'>⤴</span>"
            "<span data-t=nativeShare></span></button>"
            "<button id=sk-copy-link data-t=copyLink></button>"
            "</div>"
            "</section>"
            "</div>"
        )

        # The explainer sits BETWEEN the effigy and the forge: you see the
        # thing, you are told plainly how it works and what it needs, and only
        # then are you asked to type anything.
        inner = frozen_note + modebar + langbar + hun_pane + sk_pane

    data = ("<script>"
            "var DAYS=" + json.dumps(DAYS, ensure_ascii=False,
                                     separators=(",", ":")) + ";"
            "var THEMES=" + json.dumps(THEMES, ensure_ascii=False,
                                       separators=(",", ":")) + ";"
            "var PRESETS=" + json.dumps(KHATA_PRESETS, ensure_ascii=False,
                                        separators=(",", ":")) + ";"
            "var T=" + json.dumps(T, ensure_ascii=False,
                                  separators=(",", ":")) + ";"
            "var WAN_PHRA=" + json.dumps(WAN_PHRA, separators=(",", ":")) + ";"
            "var GREAT_DAYS=" + json.dumps(GREAT_DAYS, ensure_ascii=False,
                                           separators=(",", ":")) + ";"
            "var POOL=" + json.dumps(pool, ensure_ascii=False,
                                     separators=(",", ":")) + ";"
            "var SUKHWAN=" + json.dumps(SUKHWAN, ensure_ascii=False,
                                        separators=(",", ":")) + ";"
            "var SAMPLE_URL=" + json.dumps(sample) + ";"
            "var PAGE_BASE=" + json.dumps(base) + ";"
            "var EMBED_BASE=" + json.dumps(base.rstrip("/") + "/embed/") + ";"
            "var LINE_ID=" + json.dumps(LINE_ID) + ";"
            + EFFIGY_JS + READING_JS + APP_JS +
            "</script>")

    head = "" if embed else (
        "<header><div><h1>หุ่นพยนต์ · Hun Payont</h1>"
        "<p class=sub><span class=en-only>An effigy you forge, consecrate and "
        "carry. It walks to the market every morning and brings back one thing "
        "— and the link it brings back is wearing your name, not ours.</span>"
        "<span class=th-only>หุ่นที่คุณสร้างเอง ปลุกเสกเอง แล้วพกติดตัว "
        "ทุกเช้ามันจะออกไปตลาดแล้วกลับมาพร้อมของหนึ่งชิ้น "
        "และลิงก์ที่มันถือกลับมาก็เป็นชื่อของคุณ ไม่ใช่ของเรา</span>"
        "</p></div>" + nav + "</header>")

    return head + "<main>" + inner + "</main>" + data


DESCRIPTION = ("A hun payont — a Thai bamboo servant-effigy — rebuilt as a "
               "widget you can carry. Forge one, consecrate it with your own "
               "affiliate khata, and share it anywhere; each day it reads the "
               "Thai eight-day week and the moon, fetches one real listing from "
               "a catalogue of thousands of amulets, and links to it under your "
               "name. Thai and English. No account, no server, no cut taken, "
               "and it rests on wan phra. หุ่นพยนต์ที่สร้างเองแล้วพกไปได้จริง")
