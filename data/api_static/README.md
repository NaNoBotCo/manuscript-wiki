# api_static — data files the axis pages read, owned by no generator

Every JSON here is copied verbatim into `docs/api/` on each build
(build_static.py, right after the no-arg API dumps). That copy step is the
entire reason this folder exists, and the history says why:

The /need and /nuea pages (the emic-axis directories) were written by one-off
builders that no longer exist as scripts. Their HTML lives in docs/ and is
preserved across builds by build_static's UNMANAGED list — but their DATA
(`api/needs.json`, `functions.json`, `classes.json`, `materials.json`,
`term-echo.json`, `wander.json`) was never on that list. The 2026-07-28 03:06
wipe deleted all six; every later build rebuilt api/ without them; and Cloudflare
Pages answered the misses with the landing page HTML and HTTP 200, so nothing
flagged it. From 2026-07-28 to 2026-08-26 "Find by need" said "The directory
could not load" while every monitor stayed green.

Recovered 2026-08-26 from the nanobotco-lanna git history — the last commits
that carried each file:

    needs.json functions.json classes.json term-echo.json wander.json
        ← 67bb5a0071  (snapshot 2026-07-27 16:16)
    materials.json
        ← 00c87f253c  (snapshot 2026-07-27 22:49)

The corpus counts inside them are as of those snapshots. When a real generator
for the axis data exists again, it should write THESE files (then the build
copies them, same as now) — not docs/ directly, which a wipe erases.

`landing-strata`: wander.json is also read by the landing page's "เดินเล่น"
button and term-echo.json by the market strata. Same recovery, same rule.
