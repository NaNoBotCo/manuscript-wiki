# Moving the wiki to a custom domain — the whole checklist

The code side is already done: `publish_site.sh` has a `CUSTOM_DOMAIN` switch, and
`site_meta.py` writes the `CNAME` file (post-build, every publish, so the rebuild
wipe can't lose it) and repoints the knowledge-graph IRIs to the domain. What's left
is the part only you can do — buying the name and entering four DNS records.

## 1 · Buy the domain
Any registrar works (Cloudflare and Porkbun have at-cost pricing; Namecheap is fine).
A `.org` reads most scholarly for a research corpus; `.com`/`.net`/`.wiki` all work.

## 2 · Add DNS records at the registrar
For an APEX domain (e.g. `lannawiki.org`), add these four `A` records, name `@`:

    185.199.108.153
    185.199.109.153
    185.199.110.153
    185.199.111.153

Optionally add a `CNAME` record, name `www`, value `nanobotco.github.io` — then
`www.` works too. (If you'd rather serve from a subdomain like `wiki.yourname.com`,
skip the A records and just make ONE CNAME: name `wiki`, value `nanobotco.github.io`.)

## 3 · Tell GitHub
Repo **NaNoBotCo/Lanna → Settings → Pages → Custom domain** → enter the domain →
Save. Wait for the DNS check to pass, then tick **Enforce HTTPS** (the certificate
takes a few minutes to issue).

## 4 · Flip the switch here and republish
Edit one line at the top of `publish_site.sh`:

    CUSTOM_DOMAIN="lannawiki.org"        # ← your domain

then run the publish (double-click the usual command, or `bash publish_site.sh`).
That single run rebuilds for the domain ROOT (`/` instead of `/Lanna/`), writes the
`CNAME`, and repoints every absolute link — llms.txt, sitemap, OpenAPI, JSON-LD,
feed, graph IRIs — at the new domain.

## What the move buys (why this was worth it)
- **robots.txt finally works.** Crawlers only honor domain-root `/robots.txt`; under
  the `/Lanna/` subpath it was decorative. At the root it's real.
- **llms.txt sits where agents look first** — the root.
- **Graph IRIs dereference.** `https://yourdomain/…` node ids resolve to a live site
  instead of the `lanna.wiki` placeholder.
- Authority: a named domain with a license and structured data reads as a source,
  not a hosted page.

## Afterwards (nice-to-haves, not required)
- Old links keep working: GitHub redirects `nanobotco.github.io/Lanna/…` to the
  domain automatically once the custom domain is set.
- If you later add a Carrd landing page, put it on a DIFFERENT name (or `www`) and
  keep the wiki at the domain root — agents should hit the corpus first.
