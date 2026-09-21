#!/usr/bin/env node
// golden_queries.mjs — refuse to ship a build whose own /search examples fail.
//
// WHY THIS EXISTS
// On 2026-08-26 wichaa.net/search returned zero results for EVERY query —
// including the six example chips the page itself offers — and had for days.
// The index built fine, the page rendered fine, every gate passed: the failure
// was in the one moving part nothing tested, the client-side matcher's answer
// shape. A search page whose own examples return nothing is not degraded, it
// is dead, and it must not deploy.
//
// WHAT IT CHECKS
// The six EXAMPLES chips are read from the BUILT search page (not repeated
// here — edit them in wiki.py and the gate follows). Each is run through
// search_match.js — the exact file every built page ships inline — against the
// build's api/searchdocs.json + api/thesaurus.json. Any chip with 0 results,
// any missing file, or an empty chip list fails the gate: it must never
// quietly test nothing.
//
// Called by publishing/publish_site.sh (gate 2e, before the commit) and by
// cloudflare-mirror/deploy.sh do_wichaa (before the upload).
//
//   usage: node golden_queries.mjs <docs-dir>
//   exit 0 = every chip returns results;  exit 1 = do not deploy.

import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { createRequire } from "node:module";

const HERE = path.dirname(fileURLToPath(import.meta.url));
const MATCH = createRequire(import.meta.url)(path.join(HERE, "search_match.js"));

const docsDir = process.argv[2];
if (!docsDir) {
  console.error("usage: golden_queries.mjs <docs-dir>   (the built site, e.g. nanobotco-lanna/docs)");
  process.exit(64);
}

function die(msg) {
  console.error(`✘ golden queries: ${msg}`);
  console.error("✘ NOT safe to deploy — /search would ship broken.");
  process.exit(1);
}

function load(rel, what) {
  const p = path.join(docsDir, rel);
  let text;
  try {
    text = fs.readFileSync(p, "utf8");
  } catch (e) {
    die(`cannot read ${what} at ${p} (${e.message})`);
  }
  return text;
}

// The chips live in the built page as:  var EXAMPLES = [ "…", "…" ];
// The literal is double-quoted strings with no trailing comma, i.e. valid JSON.
const page = load("search/index.html", "the built search page");
const m = page.match(/var EXAMPLES = (\[[^\]]*\])/);
if (!m) die("could not find the EXAMPLES chip array in search/index.html — the page template moved; update this gate rather than skipping it");
let chips;
try {
  chips = JSON.parse(m[1]);
} catch (e) {
  die(`the EXAMPLES array no longer parses as JSON (${e.message}) — keep it double-quoted with no trailing comma, or teach this gate the new form`);
}
if (!Array.isArray(chips) || chips.length === 0) die("the EXAMPLES chip array is empty — a gate with nothing to test proves nothing");

let docs, thes;
try {
  docs = JSON.parse(load("api/searchdocs.json", "the search index"));
  thes = JSON.parse(load("api/thesaurus.json", "the thesaurus"));
} catch (e) {
  die(`search index or thesaurus is not valid JSON (${e.message})`);
}
if (!Array.isArray(docs) || docs.length === 0) die("api/searchdocs.json is empty — there is nothing to search");

let failed = 0;
for (const q of chips) {
  const n = MATCH.match(docs, thes, q).length;
  if (n === 0) failed++;
  console.log(`  ${n === 0 ? "✘" : "✓"} ${String(n).padStart(5)}  ${q}`);
}
if (failed) {
  die(`${failed} of ${chips.length} example chips return NOTHING against the built index (${docs.length} docs)`);
}
console.log(`✓ golden queries: all ${chips.length} /search example chips return results (${docs.length} docs indexed)`);
