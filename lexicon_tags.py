"""One list of the `use` tags that mean "not a compound of this head".

Four modules ask the same question — the queue, the wiki build, the portal and
the doors — and each one used to spell the answer out as a string comparison
against "false-split". A fifth tag then has to be added in five places. It is
one import now.

  nominalisation    a การ-/ความ- form of a word already filed
  synonym-pointer   a gloss that only names a synonym
  false-split       the head is not in the word; the syllable merely starts it
  spelling-variant  a gloss that reads only "รูปสะกดผิดของ X" — the entry points
                    at another spelling and carries no sense of its own
"""

NOT_A_COMPOUND = {
    "nominalisation",
    "synonym-pointer",
    "false-split",
    "spelling-variant",
}


def is_compound(c) -> bool:
    """True when this row is a compound of its head and can be filed."""
    return c.get("use") not in NOT_A_COMPOUND
