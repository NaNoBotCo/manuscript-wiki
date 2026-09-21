/* search_match.js — the ONE lexical matcher for wichaa's static export.
 *
 * Two callers, one implementation:
 *   - the static shim (build_static.py injects this file inline into every
 *     page, just before the shim) answers /api/search fetches from
 *     api/searchdocs.json with it;
 *   - golden_queries.mjs (the deploy gate) requires this SAME file in Node and
 *     refuses to ship a build whose /search example chips return nothing.
 * The gate only proves something because both run this exact file — a
 * reimplemented matcher could pass while the shipped one fails.
 *
 * Semantics mirror wiki.py (_norm / _expand_token / the FTS re-rank):
 *   - normalize: lowercase + recompose decomposed sara-am, so Thai typed
 *     composed matches OCR text that decomposed it;
 *   - each query token becomes an OR-set of thesaurus equivalents (exact key,
 *     or substring either way at >= 3 chars);
 *   - token groups AND together; a title hit scores 12, body hits score
 *     min(occurrences, 6); the earliest body position feeds the snippet.
 * Thai needs no word segmentation here: the index fields are pre-_norm()'d at
 * build time and matching is plain substring, so "ยันต์กันภัย" reaches the
 * yantra group via the thesaurus substring rule.
 */
(function (root) {
  "use strict";

  var SA_AM = "ำ"; /* ำ */
  /* nikhahit + (tone?) + sara-aa  ->  (tone) + sara-am   — wiki.py _RE_NKAA */
  var RE_NKAA = /ํ([่-๋]?)า/g;
  /* tone + nikhahit + sara-aa     ->  tone + sara-am     — wiki.py _RE_TNKAA */
  var RE_TNKAA = /([่-๋])ํา/g;

  function norm(s) {
    s = (s == null ? "" : String(s));
    s = s.replace(RE_NKAA, function (_, t) { return t + SA_AM; });
    s = s.replace(RE_TNKAA, function (_, t) { return t + SA_AM; });
    return s.toLowerCase();
  }

  /* One query token -> the OR-set of its normalized equivalents. */
  function expand(tok, thes) {
    tok = norm(tok);
    var members = {};
    members[tok] = 1;
    if (tok.length < 2) return Object.keys(members);
    for (var key in thes) {
      if (tok === key || (tok.length >= 3 && (tok.indexOf(key) >= 0 || key.indexOf(tok) >= 0))) {
        var grp = thes[key];
        for (var i = 0; i < grp.length; i++) members[grp[i]] = 1;
      }
    }
    return Object.keys(members);
  }

  /* Match `q` against docs [{ref,kind,label,ntitle,nbody}] using thesaurus
   * `thes` {token: [equivalents]}. Returns [{score, doc, pos}] best-first;
   * pos is the earliest body hit (null if the match was title-only). */
  function match(docs, thes, q) {
    q = (q == null ? "" : String(q)).trim();
    if (!q) return [];
    var groups = norm(q).split(/\s+/).filter(Boolean)
      .map(function (t) { return expand(t, thes); })
      .filter(function (g) { return g.length; });
    if (!groups.length) return [];
    var scored = [];
    for (var i = 0; i < docs.length; i++) {
      var d = docs[i];
      /* ntitle/nbody are already _norm()'d at build time; lowercase again is
       * cheap insurance against a half-normalized index, nothing more. */
      var title = (d.ntitle || "").toLowerCase(), body = (d.nbody || "").toLowerCase();
      var ok = true, score = 0, pos = null;
      for (var j = 0; j < groups.length; j++) {
        var g = groups[j], ghit = 0;
        for (var m = 0; m < g.length; m++) {
          var tk = g[m];
          if (!tk) continue;
          if (title.indexOf(tk) >= 0) ghit += 12;
          var idx = body.indexOf(tk);
          if (idx >= 0) {
            ghit += Math.min(body.split(tk).length - 1, 6);
            if (pos === null || idx < pos) pos = idx;
          }
        }
        if (ghit === 0) { ok = false; break; }
        score += ghit;
      }
      if (ok) scored.push({ score: score, doc: d, pos: pos });
    }
    scored.sort(function (a, b) { return b.score - a.score; });
    return scored;
  }

  var api = { norm: norm, expand: expand, match: match };
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  else root.WICHAA_MATCH = api;
})(typeof self !== "undefined" ? self : this);
