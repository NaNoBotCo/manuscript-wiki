// Cloudflare Worker — the ธรรมทาน shelf of หอไตร (wichaa.net/hotrai): robots and
// visiting ministers leave a text; the keeper reads each one by hand.
// Terms: wichaa.net/hotrai/t/thammathan.txt. The register that also lived here
// came out on 2026-11-19 (Nan: no spiritual-ish devices without grounding).
//
// KV layout:
//   dep:<uuid>   → {title, by, kind, licence, tradition, text, status, at}
//   rl:<ip>:<h>  → request count (1h TTL)
//   reg:<uuid>   → old register entries, left in KV, no longer served
//
// Moderation: GET /pending and POST /moderate, guarded by ADMIN_TOKEN
// (wrangler secret put ADMIN_TOKEN; local copy in worker/admin_token.txt,
// gitignored, never printed).

const MAX_BODY = 60_000        // deposits carry whole texts
const PER_HOUR = 20

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

export default {
  async fetch(request, env) {
    const url = new URL(request.url)
    if (request.method === 'OPTIONS') return new Response(null, { headers: CORS })

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
        deposits: (await listAll(env, 'dep:')).filter(e => e.status === 'pending'),
      })
    }

    if (url.pathname === '/moderate' && request.method === 'POST') {
      if (!authed) return json({ ok: false, error: 'the keeper only' }, 403)
      let body
      try { body = await readBody(request) } catch {
        return json({ ok: false, error: 'Send JSON: {"id": "dep:...", "status": "approved"|"rejected"}' }, 400)
      }
      const id = cap(body.id, 120)
      if (!/^dep:/.test(id) || !['approved', 'rejected'].includes(body.status))
        return json({ ok: false, error: 'id must be dep:<uuid>; status approved or rejected' }, 400)
      const entry = await env.KV.get(id, 'json')
      if (!entry) return json({ ok: false, error: 'no such entry' }, 404)
      entry.status = body.status
      if (body.reason) entry.reason = cap(body.reason, 400)
      await env.KV.put(id, JSON.stringify(entry))
      return json({ ok: true, id, status: entry.status, name: entry.title })
    }

    // ---- what this is ---------------------------------------------------
    return json({
      ok: true,
      what: 'หอไตร — the ธรรมทาน shelf of the ho trai at wichaa.net/hotrai',
      library: 'https://wichaa.net/hotrai/entry.txt',
      asked_of_readers: 'nothing; every text is fetched with a plain GET',
      endpoints: {
        'POST /deposit': 'leave a text on the ธรรมทาน shelf — terms at /hotrai/t/thammathan.txt',
      },
    })
  },
}
