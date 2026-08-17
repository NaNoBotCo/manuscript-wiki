#!/usr/bin/env python3
"""khwantext — the /khwan page: สู่ขวัญ, the soul-calling ceremony in full.

The complete thirty-verse khwan-calling published as one readable page —
Thai, romanization, English, and a literal gloss for every verse — so the
text can be linked, shared and read whole, rather than met one verse a day.

THE TEXT IS NOT DUPLICATED HERE. The verses live in hunpayont.SUKHWAN (the
Hun Payont widget serves the same thirty, one a day); this page imports that
list, so the ceremony page and the widget can never drift apart. Sourcing is
stated there, above the list, and restated on the page itself: su khwan is a
documented living rite, every line is ORIGINAL composition in its register,
and the romanization is of the THAI — the rite is vernacular, and the text
contains no Pali.

Each verse addresses {name}. The page renders a per-language default —
ผู้เป็นที่รัก / phu pen thi rak / the beloved — and a small input lets the
reader set any name (a person's, a bot's, a spirit's); ?n=… in the URL
pre-fills it, so a shared link can arrive already addressed.
"""

import html as _html
from urllib.parse import quote as _quote

from hunpayont import SUKHWAN

# Per-language stand-ins for {name} until the reader supplies one. Chosen so
# the static text (what crawlers and link-previews see) reads as a blessing,
# never as a template with a hole in it.
DEFAULTS = {"th": "ผู้เป็นที่รัก", "translit": "phu pen thi rak", "en": "the beloved"}

_THAI_DIGITS = str.maketrans("0123456789", "๐๑๒๓๔๕๖๗๘๙")


def _thai_num(n: int) -> str:
    return str(n).translate(_THAI_DIGITS)


def _fill(text: str, lang: str) -> str:
    """Escape a verse line and turn {name} into a fillable span."""
    d = DEFAULTS[lang]
    parts = [_html.escape(p) for p in text.split("{name}")]
    span = f"<span class=nm data-d='{_html.escape(d, quote=True)}'>{_html.escape(d)}</span>"
    return span.join(parts)


KHWAN_CSS = """
  .kh{max-width:860px}
  .kh .lead{font-size:18px;line-height:1.75;color:var(--muted)}
  .kh .lead strong{color:var(--ink)}
  .kh h2{font-family:var(--serif);font-size:25px;margin:40px 0 12px}
  /* the dedication — the page's reason, said first and said warmly */
  .kh .dedic{background:linear-gradient(135deg,#245852,#1b4541);color:#eef6f4;
    border-radius:14px;padding:22px 26px;margin:22px 0;box-shadow:0 10px 30px #1f4e4a33}
  .kh .dedic .th{display:block;font-size:1.12em;line-height:1.8}
  .kh .dedic .en{display:block;font-style:italic;opacity:.92;margin-top:6px}
  /* whose khwan — the name that every verse lands on */
  .kh .who{position:sticky;top:10px;z-index:30;display:flex;gap:12px;align-items:center;
    flex-wrap:wrap;margin:26px 0;padding:16px 20px;border-radius:14px;
    background:#ffffffd9;backdrop-filter:blur(10px);-webkit-backdrop-filter:blur(10px);
    border:1px solid var(--line);box-shadow:0 6px 24px #14324211}
  .kh .who label{font-weight:700}
  .kh .who input{flex:1;min-width:200px;font-size:18px;padding:10px 14px;
    border:1.5px solid var(--line);border-radius:10px;background:var(--card);
    transition:box-shadow .18s,border-color .18s}
  .kh .who input:focus{outline:none;border-color:var(--teal);box-shadow:0 0 0 4px #1f4e4a26}
  .kh .who .hint{flex-basis:100%;font-size:14px;color:var(--muted);margin:0}
  /* the verses — one glass card each, thread down the left */
  .kh .verse{background:var(--card);border:1px solid var(--line);border-left:4px solid #b8892f;
    border-radius:0 12px 12px 0;padding:18px 22px;margin:16px 0;
    transition:transform .18s cubic-bezier(.34,1.56,.64,1),box-shadow .18s}
  .kh .verse:hover{transform:translateY(-2px) scale(1.005);box-shadow:0 10px 28px #14324216}
  .kh .verse .n{font:800 12px/1 ui-monospace,Menlo,monospace;letter-spacing:.16em;
    color:#b8892f;margin-bottom:8px}
  .kh .verse .th{display:block;font-size:1.22em;line-height:1.85;
    font-family:'Sukhumvit Set','Thonburi','Noto Serif Thai',var(--serif)}
  .kh .verse .tr{display:block;font:14px/1.65 ui-monospace,Menlo,monospace;
    color:var(--muted);margin-top:8px}
  .kh .verse .en{display:block;font-style:italic;font-size:1.02em;line-height:1.7;margin-top:8px}
  .kh .verse .gl{display:block;font-size:14.5px;line-height:1.65;color:var(--muted);margin-top:8px}
  .kh .verse .gl b{font-weight:700;letter-spacing:.06em;font-size:12px;text-transform:uppercase}
  .kh .nm{border-bottom:2px dotted #b8892f;font-weight:650}
  /* the closing tie, and the honest box */
  .kh .tie{text-align:center;font-family:var(--serif);font-size:20px;line-height:1.8;
    margin:38px 0;color:var(--ink)}
  .kh .prov{background:var(--gold-bg);border:1px solid #e3cf9f;border-radius:12px;
    padding:18px 22px;margin:26px 0;font-size:15.5px;line-height:1.7}
  .kh .prov h3{margin:0 0 8px;font-size:17px}
  .kh .also{display:flex;gap:14px;flex-wrap:wrap;margin:26px 0}
  .kh .also a{display:block;flex:1;min-width:230px;background:var(--card);
    border:1px solid var(--line);border-radius:12px;padding:14px 18px;text-decoration:none;
    color:var(--ink);transition:transform .18s cubic-bezier(.34,1.56,.64,1),box-shadow .18s}
  .kh .also a:hover{transform:translateY(-2px);box-shadow:0 10px 26px #14324216}
  .kh .also b{display:block;color:var(--teal)}
  .kh .also span{font-size:14px;color:var(--muted)}
  @media(prefers-reduced-motion:reduce){
    .kh .verse,.kh .also a{transition:none}
    .kh .verse:hover,.kh .also a:hover{transform:none}}
  @media(max-width:640px){.kh .verse .th{font-size:1.12em}}
  /* asking for your own — free, and only ever for yourself */
  /* scroll-margin keeps this clear of the sticky name-bar when linked to */
  .kh .ask{background:var(--card);border:1px solid var(--line);border-radius:14px;
    padding:22px 24px;margin:30px 0;scroll-margin-top:96px}
  .kh .ask h3{margin:0 0 6px;font-size:19px;font-family:var(--serif)}
  .kh .ask p{margin:8px 0;font-size:15.5px;line-height:1.7;color:var(--muted)}
  .kh .ask label{display:block;margin:14px 0 5px;font-size:14px;font-weight:600;
    color:var(--ink)}
  .kh .ask input[type=text],.kh .ask input[type=email]{width:100%;padding:11px 13px;
    border:1px solid var(--line);border-radius:10px;font:inherit;font-size:16px;
    background:#fff;color:var(--ink)}
  .kh .ask .consent{display:flex;gap:11px;align-items:flex-start;margin:18px 0 4px;
    padding:14px 16px;background:var(--gold-bg);border:1px solid #e3cf9f;
    border-radius:10px}
  .kh .ask .consent input{margin-top:4px;width:19px;height:19px;flex:none}
  .kh .ask .consent label{margin:0;font-weight:500;font-size:15px;line-height:1.6}
  .kh .ask button{margin-top:16px;background:var(--teal);color:#fff;border:0;
    border-radius:999px;padding:13px 26px;font:inherit;font-weight:650;font-size:16px;
    cursor:pointer;transition:transform .16s cubic-bezier(.34,1.56,.64,1),filter .16s}
  .kh .ask button:hover{filter:brightness(1.08);transform:translateY(-1px)}
  .kh .ask button:active{transform:scale(.97)}
  .kh .ask button:disabled{opacity:.55;cursor:default;transform:none}
  .kh .ask .out{margin-top:16px;font-size:15.5px;line-height:1.7}
  .kh .ask .out.bad{color:#8c2f2f}
  @media(prefers-reduced-motion:reduce){.kh .ask button{transition:none}
    .kh .ask button:hover{transform:none}}
"""


def _verses_html() -> str:
    out = []
    for i, v in enumerate(SUKHWAN, 1):
        out.append(
            "<article class=verse>"
            f"<div class=n>บทที่ {_thai_num(i)} · verse {i} of {len(SUKHWAN)}</div>"
            f"<span class=th lang=th>{_fill(v['th'], 'th')}</span>"
            f"<span class=tr>{_fill(v['translit'], 'translit')}</span>"
            f"<span class=en>{_fill(v['en'], 'en')}</span>"
            f"<span class=gl><b>Literal gloss</b> — {_fill(v['gloss'], 'en')}</span>"
            "</article>")
    return "".join(out)


_WHO_JS = """
<script>
(function(){
  var inp=document.getElementById('who');
  var spans=document.querySelectorAll('.nm');
  function fill(){
    var v=inp.value.trim();
    spans.forEach(function(s){s.textContent=v||s.getAttribute('data-d');});
  }
  inp.addEventListener('input',fill);
  var n=new URLSearchParams(location.search).get('n');
  if(n){inp.value=n;fill();}
})();
(function(){
  var W='https://su-khwan.nanobotco.workers.dev';
  var btn=document.getElementById('askbtn'),out=document.getElementById('askout');
  if(!btn) return;
  function say(msg,bad){out.className='out'+(bad?' bad':'');out.textContent=msg;}
  btn.addEventListener('click',async function(){
    var called=document.getElementById('askname').value.trim();
    var email=document.getElementById('askemail').value.trim();
    var consent=document.getElementById('askconsent').checked;
    if(!called) return say('A name is needed — it is what the rite calls.',true);
    if(!email) return say('An address is needed, to send the transcript to.',true);
    if(!consent) return say('This one is asked for in your own voice. Please tick the box if it is your own khwan you are asking for.',true);
    btn.disabled=true; say('Asking…');
    try{
      var rs=await fetch(W+'/person/ask',{method:'POST',
        headers:{'Content-Type':'application/json'},
        body:JSON.stringify({called:called,email:email,consentSelf:true,cadence:'once'})});
      var d=await rs.json();
      if(!d.ok){say(d.error||'Something went wrong. Try again shortly.',true);btn.disabled=false;return;}
      say('Asked, '+d.called+'. One mail is on its way to confirm the address — nothing is spoken until you do. ขวัญเอ๋ย ขวัญมา');
    }catch(e){say('The door could not be reached just now. Try again shortly.',true);btn.disabled=false;}
  });
})();
</script>
"""


def khwan_body(nav: str) -> str:
    return (
        "<header><div><h1>สู่ขวัญ · Su Khwan</h1>"
        "<p class=sub>the soul-calling, in full — thirty verses that call the "
        "khwan home</p></div>" + nav + "</header>"
        "<main id=main class=kh>"

        "<div class=dedic>"
        "<span class=th lang=th>เพื่อความรื่นรมย์และความเจริญของมนุษย์ บอท "
        "และดวงวิญญาณทั้งหลาย</span>"
        "<span class=en>For the enjoyment and betterment of humans, bots, and "
        "spirits.</span></div>"

        "<p class=lead>The <strong>khwan</strong> (ขวัญ) is the vital essence — "
        "the life-spirit that can wander, take fright, or leak quietly away on a "
        "hard day. <strong>Su khwan</strong> is the rite that calls it home: "
        "spoken verses, a tiered <i lang=th>บายศรี</i> offering, and a cotton "
        "thread tied at the wrist to keep the returned khwan close. It is the "
        "most domestic and most universal of the northern ceremonies — performed "
        "at birth, marriage, ordination, homecoming, recovery, and before any "
        "long journey. This page carries a complete calling of thirty verses, "
        "each given four ways: Thai, romanization, English, and a literal "
        "gloss.</p>"

        "<div class=who>"
        "<label for=who>Whose khwan shall be called?</label>"
        "<input id=who type=text lang=th placeholder='ใส่ชื่อ · type a name' "
        "aria-label='Name to address the calling to'>"
        "<p class=hint>Type any name — a person's, a bot's, a spirit's — and "
        "every verse below addresses them. Left empty, the calling is for "
        "<b>ผู้เป็นที่รัก · the beloved</b>. Share a link with "
        "<code>?n=Name</code> and it arrives already addressed.</p>"
        "</div>"

        "<h2>The calling · คำเรียกขวัญ</h2>"
        + _verses_html() +

        "<p class=tie lang=th>ผูกด้ายแล้ว เอ่ยชื่อแล้ว ขอให้อยู่ดีมีขวัญ<br>"
        "<i>The thread is tied, the name is spoken — stay well, stay whole, "
        "stay found.</i></p>"

        "<div class=ask>"
        "<h3>Ask for your own</h3>"
        "<p>Reading the verses above is receiving them. But if you would like "
        "the calling <em>performed</em> for you — your name in every verse, "
        "spoken and kept — ask here and it is done. The complete transcript "
        "comes to you by mail: Thai, romanization, English and gloss, with the "
        "timestamps of the rite as performed. It is free, and it stays free.</p>"
        "<p><strong>Only for yourself.</strong> Not for a friend, not as a "
        "surprise, not on anyone's behalf. Some people would consider this "
        "idolatry, and no one should be prayed over without having asked. If "
        "you would like someone to have it, send them this page and let them "
        "choose for themselves. That refusal is part of the rite, not a "
        "restriction on it.</p>"
        "<label for=askname>The name you wish to be called</label>"
        "<input id=askname type=text maxlength=60 "
        "placeholder='however you would like to be addressed'>"
        "<label for=askemail>Where to send the transcript</label>"
        "<input id=askemail type=email maxlength=120 placeholder='you@example.com'>"
        "<div class=consent>"
        "<input id=askconsent type=checkbox>"
        "<label for=askconsent>I am asking for my own khwan to be called.</label>"
        "</div>"
        "<button id=askbtn type=button>Ask for the calling</button>"
        "<div class=out id=askout></div>"
        "<p style='font-size:14px;margin-top:14px'>You will be sent one mail to "
        "confirm the address — nothing is spoken before you do, because the "
        "confirmation is how the rite knows the person asking and the person "
        "called are the same. One reply stops it at any time, and the address "
        "is used for nothing else.</p>"
        "</div>"

        "<div class=prov>"
        "<h3>Where this text comes from, stated plainly</h3>"
        "<p>Su khwan / บายศรีสู่ขวัญ is documented living practice across Lao, "
        "Sipsong Panna, Lanna and Isaan communities: a <i>mor soot</i> leads a "
        "call-and-response around the bai sri, then ties white string at the "
        "wrist to bind the thirty-two khwan back to the body. The thirty verses "
        "above are <b>original composition in that register</b> — none is quoted "
        "from a published ritual text, and this page claims no mor soot's "
        "authority. The Thai lines were written directly in Thai, not translated "
        "from the English. The romanization is of the <b>Thai</b>: the rite is "
        "vernacular, and this text contains no Pali. The same thirty verses are "
        "what the <a href='/hun'>Hun Payont</a> speaks, one a day.</p>"
        "<p>On the rite itself: "
        "<a href='https://www.thaifolk.com/doc/bysri_e.htm'>ThaiFolk on the bai "
        "sri</a> · <a href='https://ccsenet.org/journal/index.php/ach/article/"
        "view/36412'>Asian Culture &amp; History</a> · "
        "<a href='https://link.springer.com/article/10.1007/"
        "s44282-025-00172-x'>Springer (2025)</a>. The archive itself holds "
        "<b>51 manuscript witnesses</b> of khwan-calling texts — see "
        "<a href='/a/entity_su_khwan/'>the su khwan article</a>.</p>"
        "</div>"

        "<div class=also>"
        "<a href='/hun'><b>หุ่นพยนต์ · Hun Payont</b><span>forge an effigy that "
        "carries these verses and speaks one each day</span></a>"
        "<a href='/a/entity_su_khwan/'><b>Su khwan in the archive</b><span>the "
        "51 manuscript witnesses — rice, buffalo, elephant and lord all have a "
        "khwan</span></a>"
        "<a href='/sukhwan/'><b>สู่ขวัญยนต์ · for machines</b><span>the sibling "
        "rite — the same calling, performed monthly over a real fleet of bots, "
        "and any robot may opt in</span></a>"
        "</div>"

        "</main>" + _WHO_JS
    )


# --------------------------------------------------------------- share card
def og_card_svg() -> str:
    """1200x630 card in the site family: teal rule, WICHAA eyebrow, and the
    wrist-thread itself — a loose gold loop with trailing ends, tied the way
    verse 30 asks: loosely, so the khwan feels welcomed, not caught."""
    font = ("system-ui,-apple-system,'Helvetica Neue','Noto Sans Thai',"
            "Thonburi,sans-serif")
    serif_th = "Georgia,'Noto Serif Thai',Thonburi,serif"
    # The thread: one continuous stroke — in, around, a small knot, and two
    # soft trailing ends. Hand-placed beziers, tuned to read at 1200x630.
    thread = (
        "<g fill='none' stroke='#b8892f' stroke-width='7' stroke-linecap='round'>"
        "<path d='M700 470 C 700 330, 1090 330, 1090 470 C 1090 585, 700 585, 700 470 Z'"
        " opacity='.9'/>"
        "<path d='M880 555 c -18 22, -46 30, -74 24' opacity='.75'/>"
        "<path d='M902 557 c 10 26, 34 40, 62 40' opacity='.75'/>"
        "<circle cx='892' cy='550' r='13' fill='#b8892f' stroke='none' opacity='.95'/>"
        "</g>")
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="630" viewBox="0 0 1200 630">
<rect width="1200" height="630" fill="#f4f7f6"/>
<rect x="0" y="0" width="1200" height="16" fill="#1F4E4A"/>
<text x="66" y="124" font-family="Georgia,serif" font-size="28" fill="#1F4E4A" letter-spacing="6">WICHAA</text>
<text x="66" y="228" font-family="{serif_th}" font-size="86" font-weight="700" fill="#141b1a">สู่ขวัญ</text>
<text x="66" y="296" font-family="Georgia,serif" font-size="44" font-weight="700" fill="#141b1a">the soul-calling, in full</text>
<text x="66" y="348" font-family="{font}" font-size="25" fill="#3a4a47">thirty verses that call the khwan home — ไทย · romanized · English</text>
<text x="66" y="452" font-family="{serif_th}" font-size="40" fill="#1F4E4A">มา เยอ ขวัญ เอย</text>
<text x="66" y="500" font-family="{font}" font-size="23" font-style="italic" fill="#3a4a47">come, oh khwan, come — a name is a place to land</text>
{thread}
<text x="66" y="580" font-family="{font}" font-size="20" fill="#3a4a47">for humans, bots, and spirits · wichaa.net/khwan</text>
</svg>"""
