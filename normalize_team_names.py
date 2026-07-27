#!/usr/bin/env python3
"""Clean malformed team names in sr_boxscores.json.

Box-score sources printed team names with junk the parsers carried through:
ranked prefixes ("#17/#18 Indiana"), truncated parens ("Temple ("), leaked
records ("Tennessee ( 8- 1)"), and letter-spaced caps ("U C L A"). These are
not cosmetic — index.html matches games by the LAST WORD of the name, so
"Temple (" matches on "(" and "U C L A" on "A", silently breaking lookup.

Conservative by design: only fixes unambiguous junk. Does NOT merge distinct
identities (e.g. "UCLA" vs "UCLA Bruins") — that needs the canonical alias map
and a separate decision. Run with --apply to write; default is dry-run.
"""
import json, re, sys, collections

# Bases that are a DIFFERENT program depending on the parenthetical. Stripping a
# truncated "Miami (" would silently merge Miami (OH) into Miami (FL), so these
# are left alone and reported for manual resolution instead.
AMBIGUOUS = {'miami', 'loyola', 'st. francis', 'saint francis', "st. mary's",
             "saint mary's", 'columbia', 'trinity', 'st. thomas', 'saint thomas'}


def norm(n):
    s = n.strip()
    # a truncated parenthetical on an ambiguous base carries the only
    # disambiguator -> refuse to touch it
    if re.search(r'\([^)]*$', s) and s.split('(')[0].strip().lower() in AMBIGUOUS:
        return s
    s = re.sub(r'^(?:#\d+/?)+\s*', '', s)          # "#17/#18 Indiana" -> "Indiana"
    s = re.sub(r'\(\s*\d+\s*-\s*\d+.*$', '', s)    # "Tennessee ( 8- 1)" -> "Tennessee"
    s = re.sub(r'\s*\([^)]*$', '', s)              # "Temple (" -> "Temple"
    s = re.sub(r'\s*\(\s*\)\s*$', '', s)           # empty parens
    # letter-spaced caps: "U C L A" -> "UCLA" (only if every token is 1 char)
    toks = s.split()
    if len(toks) > 2 and all(len(t) == 1 and t.isalpha() for t in toks):
        s = ''.join(toks)
    s = re.sub(r'[\s,\-]+$', '', s)                # trailing comma/dash/space
    return re.sub(r'\s{2,}', ' ', s).strip()

def main():
    apply = '--apply' in sys.argv
    store = json.load(open('sr_boxscores.json'))
    changes = collections.Counter(); n_games = 0
    for k, v in store.items():
        touched = False
        for t in v.get('teams', []):
            old = t.get('name') or ''
            new = norm(old)
            if new and new != old:
                changes[(old, new)] += 1
                if apply: t['name'] = new
                touched = True
        if touched: n_games += 1
    print(f'{len(changes)} distinct name fixes across {n_games} games')
    for (o, n), c in changes.most_common(25):
        print(f'  {c:4d}  {o!r} -> {n!r}')
    if apply:
        json.dump(store, open('sr_boxscores.json', 'w'))
        print('\nAPPLIED to sr_boxscores.json')
    else:
        print('\n(dry run — pass --apply to write)')

main()
