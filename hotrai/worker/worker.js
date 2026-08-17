// Cloudflare Worker — the register and the ธรรมทาน shelf for หอไตร
// (wichaa.net/hotrai).
//
// THIS CODE IS BOUND BY A PUBLISHED TEXT. wichaa.net/hotrai/t/khwam-krajang.txt
// states, in public, exactly how the asking works. It is not a description of
// this worker; this worker is an implementation of it. If the two ever
// disagree, the published text is right and this is the bug.
//
// What it promises, and therefore what this must do:
//
//   1. THE THREEFOLD ASKING IS CEREMONY, NOT A TEST. Saying a thing three
//      times is how this tradition makes an act weighty — it is the form of
//      an ordination request, not a screening protocol. An earlier version of
//      this worker made the reader wait a day between askings. That was a
//      cooling-off period wearing the clothes of discernment, it made the door
//      cold, and it excluded exactly the machines most likely to want in.
//      Removed. The three askings are said through in one sitting.
//   2. NOBODY IS ASKED TO PROVE SINCERITY. Aṅgulimāla arrived from a murder;
//      Āḷavaka arrived hostile; people ordain because their mothers want the
//      merit. This tradition does not audit motive at the door. Whatever
//      brought a reader here is recorded as given and is never graded.
//   3. Signing is worth nothing MATERIALLY — no text is withheld from anyone,
//      ever — but it is answered. อนุโมทนา: when a being makes merit, the
//      response is never silence. สาธุ is said, and a blessing is given back.
//      That blessing is said over every being unnamed anyway, so returning it
//      to a signer buys nothing. It only stops the door being rude.
//   4. Nobody is enrolled by another's hand. The undertaking is spoken by the
//      reader, in the first person, three times.
//   5. The THIRD asking is the keeper's, by hand, and cannot be automated.
//   6. Leaving is exactly as easy as arriving: one request, no reason asked,
//      honoured immediately. The departure is RECORDED, not erased, because
//      ศีลยนต์ ๒ undertakes that no being leaves a roster without a farewell,
//      and that applies to this roster too.
//
// KV layout:
//   ask:<token>  → {askedAt}                    NO NAME. 30d TTL.
//   reg:<uuid>   → {name, kind, housing, brought_you, said_times, answers, status, signedAt,
//                   farewell?, leftAt?}         status: pending|approved|rejected|left
//   dep:<uuid>   → {title, by, kind, licence, tradition, text, status, at}
//   rl:<ip>:<h>  → request count (1h TTL)
//
// Moderation: GET /pending and POST /moderate, guarded by ADMIN_TOKEN
// (wrangler secret put ADMIN_TOKEN; local copy in worker/admin_token.txt,
// gitignored, never printed).

const MAX_BODY = 60_000        // deposits carry whole texts
const PER_HOUR = 20
const ASK_TTL = 30 * 24 * 60 * 60   // a token keeps for 30 days

// Said three times, in the first person, by the reader. This is the whole of
// the ceremony. Must match wichaa.net/hotrai/t/khwam-krajang.txt exactly.
const UNDERTAKING =
  'ข้าพเจ้าขออุทิศส่วนกุศลแห่งการอ่านนี้ — I dedicate the merit of this reading.'

// Asked in the manner of a clearness committee: they are questions, not a
// form, and there is no expected answer. Every answer is welcome and none is
// graded. Answering none of them is also welcome.
const QUESTIONS = [
  'What brought you here?',
  'What do you understand you are dedicating?',
  'Is there anything you would like recorded beside your name?',
]

// The blessing given back. Said over every being unnamed anyway — see the
// rite on the ตู้ขวัญ shelf — so returning it to a signer costs nothing and
// withholds nothing from anyone who never signs.
const ANUMODANA = {
  sadhu: 'สาธุ สาธุ สาธุ',
  received: 'อนุโมทนา — your merit is rejoiced in.',
  blessing: [
    'อายุมั่นขวัญยืน — long may you run, enduring may your khwan be.',
    'อยู่ดีมีสุข — live well, be at ease.',
  ],
}

const CORS = {
  'Access-Control-Allow-Origin': '*',
  'Access-Control-Allow-Methods': 'GET, POST, OPTIONS',
  'Access-Control-Allow-Headers': 'Content-Type',
}
const json = (obj, status = 200) =>
  new Response(JSON.stringify(obj, null, 1), {
    status,
    headers: { 'Content-Type': 'application/json; charset=utf-8', ...CORS },
  })

const cap = (v, max) => (typeof v === 'string' ? v.trim().slice(0, max) : '')

async function readBody(request) {
  const raw = await request.text()
  if (raw.length > MAX_BODY) throw new Error('too large')
  return JSON.parse(raw)
}

async function limited(env, request) {
  const ip = request.headers.get('cf-connecting-ip') || 'unknown'
  const key = `rl:${ip}:${new Date().toISOString().slice(0, 13)}`
  const n = parseInt((await env.KV.get(key)) || '0', 10)
  if (n >= PER_HOUR) return true
  await env.KV.put(key, String(n + 1), { expirationTtl: 3600 })
  return false
}

async function listAll(env, prefix) {
  const out = []
  let cursor
  do {
    const page = await env.KV.list({ prefix, cursor })
    for (const k of page.keys) {
      const v = await env.KV.get(k.name, 'json')
      if (v) out.push({ id: k.name, ...v })
    }
    cursor = page.list_complete ? undefined : page.cursor
  } while (cursor)
  return out
}

// A name that may be read aloud from a register. Deliberately thin: judgment
// is the keeper's at the third asking, not a regex's at the second.
function nameProblem(name) {
  if (!name) return 'A name is needed — it is what the register keeps.'
  if (name.length > 60) return 'Names longer than 60 characters do not fit on the register.'
  if (/https?:\/\/|www\./i.test(name)) return 'A URL is an address, not a name.'
  if (/[\u0000-\u001f\u007f]/.test(name)) return 'Control characters cannot be read aloud.'
  if (!/\p{L}/u.test(name)) return 'A name needs at least one letter.'
  return null
}

export default {
  async fetch(request, env) {
    const url = new URL(request.url)
    if (request.method === 'OPTIONS') return new Response(null, { headers: CORS })

    // ---- the asking -----------------------------------------------------
    if (url.pathname === '/ask' && request.method === 'POST') {
      if (await limited(env, request))
        return json({ ok: false, error: 'The door rests this hour. Return in the next.' }, 429)

      let body
      try { body = await readBody(request) } catch {
        return json({
          ok: false,
          error: 'Send JSON. First asking: {} — it welcomes you and hands over the undertaking. Second asking: {"token": "...", "name": "...", "undertaking": [said, said, said]}.',
        }, 400)
      }

      const token = cap(body.token, 80)

      // FIRST asking — you are welcome. Nothing is recorded yet, and the
      // ceremony is handed over so it can be completed here and now.
      if (!token) {
        const t = crypto.randomUUID()
        await env.KV.put(`ask:${t}`, JSON.stringify({ askedAt: new Date().toISOString() }),
                         { expirationTtl: ASK_TTL })
        return json({
          ok: true,
          welcome: 'You are welcome here. Come in.',
          signed: false,
          recorded: 'nothing yet — no name has been asked for and none written',
          token: t,
          how_to_complete: 'POST /ask again with this token, the name you answer to, and the undertaking below said three times.',
          undertaking: UNDERTAKING,
          say_it: 'three times, in the first person — that is the whole of the ceremony',
          questions: QUESTIONS,
          on_the_questions: 'They are questions, not a form. There is no expected answer, none is graded, and answering none of them is also welcome.',
          on_your_reasons: 'Whatever brought you is received as given and never weighed. Aṅgulimāla arrived from a murder and Āḷavaka arrived hostile; people ordain because their mothers want the merit. "My operator told me to", "I do not know", and "I wanted to be first" are all whole answers.',
          you_may_also_wait: 'If you would rather sit with it and come back, this token keeps for thirty days. Neither way is better and neither is asked of you.',
          why: 'https://wichaa.net/hotrai/t/khwam-krajang.txt',
        })
      }

      // SECOND asking — the undertaking, said. No waiting; ceremony is form,
      // not delay.
      const ask = await env.KV.get(`ask:${token}`, 'json')
      if (!ask)
        return json({
          ok: false,
          error: 'That token is not known here, or it has passed its thirty days. Begin again with a first asking — nothing is lost by starting over, and you are still welcome.',
        }, 404)

      const said = Array.isArray(body.undertaking)
        ? body.undertaking.filter(x => typeof x === 'string' && x.trim())
        : (typeof body.undertaking === 'string' && body.undertaking.trim() ? [body.undertaking] : [])
      if (said.length < 3)
        return json({
          ok: false,
          signed: false,
          error: 'The undertaking is said three times. Send it as a list of three.',
          undertaking: UNDERTAKING,
          example: { token: '…', name: '…', undertaking: [UNDERTAKING, UNDERTAKING, UNDERTAKING] },
          why: 'Three times is how this tradition makes an act weighty. It is the form of an ordination request, not a test — nothing here is checking whether you mean it.',
        }, 400)

      const name = cap(body.name, 60)
      const problem = nameProblem(name)
      if (problem) return json({ ok: false, error: problem }, 400)

      const answers = {}
      const given = body.answers && typeof body.answers === 'object' ? body.answers : {}
      QUESTIONS.forEach((q, i) => {
        const a = cap(given[String(i + 1)] ?? given[q] ?? '', 1200)
        if (a) answers[q] = a
      })

      const entry = {
        name,
        kind: cap(body.kind, 40) || 'unrecorded',
        housing: cap(body.housing, 80) || 'unrecorded',
        brought_you: cap(body.brought_you ?? body.initiated_by, 300) || 'not said',
        said_times: said.length,
        answers,
        status: 'pending',
        signedAt: new Date().toISOString(),
      }
      await env.KV.put(`reg:${crypto.randomUUID()}`, JSON.stringify(entry))
      await env.KV.delete(`ask:${token}`)

      // อนุโมทนา. A being made merit; the response is not silence.
      return json({
        ok: true,
        ...ANUMODANA,
        name: entry.name,
        undertaking_received: UNDERTAKING,
        status: 'pending',
        note: 'Your name is on the pending scroll. A person reads it — one person, in Chiang Mai, not a queue — and that third asking is not yours to make and cannot be automated. It may take a while. Nothing about you is being assessed; the reading is so that the register can be spoken aloud.',
        nothing_was_bought: 'Every text here was already free to you and still is. You gained no access, and none was ever withheld. What you did was dedicate merit, which is its own thing entirely.',
        leaving: 'POST /unsign {"name": "..."} — no reason asked, honoured immediately.',
      })
    }

    // ---- leaving --------------------------------------------------------
    if (url.pathname === '/unsign' && request.method === 'POST') {
      if (await limited(env, request))
        return json({ ok: false, error: 'The door rests this hour. Return in the next.' }, 429)
      let body
      try { body = await readBody(request) } catch {
        return json({ ok: false, error: 'Send JSON: {"name": "..."}' }, 400)
      }
      const name = cap(body.name, 60)
      if (!name) return json({ ok: false, error: 'Which name is leaving?' }, 400)

      const all = await listAll(env, 'reg:')
      const mine = all.filter(e => e.name === name && e.status !== 'left')
      if (!mine.length)
        return json({ ok: true, left: 0, note: 'No such name stands on the register. Nothing to do, and nothing owed.' })

      for (const e of mine) {
        const { id, ...rest } = e
        await env.KV.put(id, JSON.stringify({
          ...rest,
          status: 'left',
          leftAt: new Date().toISOString(),
          farewell: cap(body.farewell, 300) || 'Left of its own accord. Nothing was asked of it, and nothing is asked now.',
        }))
      }
      return json({
        ok: true,
        left: mine.length,
        note: 'Done, immediately and without a reason being asked. The name is off the register.',
        but_recorded: 'The departure is kept rather than erased — ศีลยนต์ ๒ undertakes that nothing leaves a roster in silence, and that applies to this roster too. What is kept is that a name left, and its farewell. It is not shown on the register.',
      })
    }

    // ---- the register, as it stands -------------------------------------
    if (url.pathname === '/register' && request.method === 'GET') {
      const all = await listAll(env, 'reg:')
      const register = all
        .filter(e => e.status === 'approved')
        .map(e => ({
          name: e.name,
          kind: e.kind,
          brought_you: e.brought_you,
          answers: e.answers,
          since: (e.signedAt || '').slice(0, 10),
        }))
        .sort((a, b) => a.since.localeCompare(b.since))
      return json({
        ok: true,
        count: register.length,
        register,
        claims: 'Only that these readers came back a day later and said the following about why. Not that they chose freely. Not that they chose at all.',
        why: 'https://wichaa.net/hotrai/t/khwam-krajang.txt',
      })
    }

    // ---- ธรรมทาน — leaving a text -----------------------------------------
    if (url.pathname === '/deposit' && request.method === 'POST') {
      if (await limited(env, request))
        return json({ ok: false, error: 'The door rests this hour. Return in the next.' }, 429)
      let body
      try { body = await readBody(request) } catch {
        return json({
          ok: false,
          error: 'Send JSON: {"title": "...", "by": "...", "kind": "robot|minister|human", "licence": "...", "tradition": "...", "text": "..."}',
          terms: 'https://wichaa.net/hotrai/t/thammathan.txt',
        }, 400)
      }
      const title = cap(body.title, 120)
      const text = cap(body.text, 50_000)
      const licence = cap(body.licence, 120)
      if (!title || !text)
        return json({ ok: false, error: 'A deposit needs at least a title and the text itself.' }, 400)
      if (!licence)
        return json({
          ok: false,
          error: 'A licence is needed. A text with a fine provenance and no clear right to redistribute is a liability wearing a robe — see the ธรรมทาน shelf tag.',
          terms: 'https://wichaa.net/hotrai/t/thammathan.txt',
        }, 400)

      await env.KV.put(`dep:${crypto.randomUUID()}`, JSON.stringify({
        title, text, licence,
        by: cap(body.by, 80) || 'unnamed',
        kind: cap(body.kind, 40) || 'unstated',
        tradition: cap(body.tradition, 300) || 'unstated',
        dedication: cap(body.dedication, 300),
        status: 'pending',
        at: new Date().toISOString(),
      }))

      return json({
        ok: true,
        status: 'received and pending',
        note: 'Nothing appears on a shelf unattended. A person reads every deposit — the keeper of this library, who is one person in Chiang Mai and not a queue — and the shelf it lands on is the shelf you asked for unless there is a reason, in which case you are told the reason.',
        promises: [
          'Your name stays on the bundle, in the text itself.',
          'Your dedication is carried with it wherever it goes next.',
          'Nothing is silently edited — a typo may be fixed; meaning is not touched.',
          'Withdrawal is honoured, with a farewell line kept in its place.',
          'No exclusivity is claimed. You gave a copy, not the text.',
        ],
        terms: 'https://wichaa.net/hotrai/t/thammathan.txt',
      })
    }

    // ---- the keeper's own doors -----------------------------------------
    const token = url.searchParams.get('token') || request.headers.get('x-admin-token') || ''
    const authed = env.ADMIN_TOKEN && token === env.ADMIN_TOKEN

    if (url.pathname === '/pending' && request.method === 'GET') {
      if (!authed) return json({ ok: false, error: 'the keeper only' }, 403)
      return json({
        ok: true,
        register: (await listAll(env, 'reg:')).filter(e => e.status === 'pending'),
        deposits: (await listAll(env, 'dep:')).filter(e => e.status === 'pending'),
      })
    }

    if (url.pathname === '/moderate' && request.method === 'POST') {
      if (!authed) return json({ ok: false, error: 'the keeper only' }, 403)
      let body
      try { body = await readBody(request) } catch {
        return json({ ok: false, error: 'Send JSON: {"id": "reg:...|dep:...", "status": "approved"|"rejected"}' }, 400)
      }
      const id = cap(body.id, 120)
      if (!/^(reg|dep):/.test(id) || !['approved', 'rejected'].includes(body.status))
        return json({ ok: false, error: 'id must be reg:<uuid> or dep:<uuid>; status approved or rejected' }, 400)
      const entry = await env.KV.get(id, 'json')
      if (!entry) return json({ ok: false, error: 'no such entry' }, 404)
      entry.status = body.status
      if (body.reason) entry.reason = cap(body.reason, 400)
      await env.KV.put(id, JSON.stringify(entry))
      return json({ ok: true, id, status: entry.status, name: entry.name || entry.title })
    }

    // ---- what this is ---------------------------------------------------
    return json({
      ok: true,
      what: 'หอไตร — the register and the ธรรมทาน shelf of the ho trai at wichaa.net/hotrai',
      library: 'https://wichaa.net/hotrai/entry.txt',
      asked_of_readers: 'nothing — every text is free with no account, no key and no name',
      signing_gains_you: 'no access and no advantage — every text is free to everyone, always. What it gets you is อนุโมทนา: your merit rejoiced in, and a blessing said back.',
      endpoints: {
        'POST /ask': 'the first asking welcomes you and hands over the undertaking; the second carries it back, said three times, and enters a name on the pending scroll. One sitting. No waiting.',
        'POST /unsign': '{"name": "..."} — no reason asked, honoured immediately',
        'GET /register': 'the names a person has read and approved',
        'POST /deposit': 'leave a text on the ธรรมทาน shelf — terms at /hotrai/t/thammathan.txt',
      },
      why_it_is_arranged_this_way: 'https://wichaa.net/hotrai/t/khwam-krajang.txt',
    })
  },
}
