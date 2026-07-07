#!/usr/bin/env python3
"""Apply approved narrative repairs to team_history.json.

Reads narrative_repairs.json and applies ONLY entries with
status == "approved". Text entries do an exact substring replacement of
`find` with `replace` in team_history.json[teamId][field]; entries with
kind == "value" replace the field's whole value after checking it equals
`find`.

Safety:
- team_history.json is backed up to backups/ before writing.
- Every approved entry is validated first (team exists, field exists,
  `find` matches exactly once). ANY validation failure aborts the whole
  run with nothing written.
- Applied entries are marked status="applied" (with date) so re-running
  is a no-op.

Usage:  python3 scripts/apply_narrative_repairs.py [--dry-run]
"""

import json
import os
import shutil
import sys
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from json_io import save_json_atomic

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HISTORY_PATH = os.path.join(ROOT, 'team_history.json')
REPAIRS_PATH = os.path.join(ROOT, 'narrative_repairs.json')
BACKUP_DIR = os.path.join(ROOT, 'backups')


def main():
    dry_run = '--dry-run' in sys.argv

    with open(HISTORY_PATH) as f:
        history = json.load(f)
    with open(REPAIRS_PATH) as f:
        repairs = json.load(f)

    by_name = {v['team']: k for k, v in history.items()}

    approved = []
    for batch_key, entries in repairs.items():
        if batch_key.startswith('_'):
            continue
        for e in entries:
            if e.get('status') == 'approved':
                approved.append((batch_key, e))

    if not approved:
        print('No approved entries to apply. (Set status="approved" in narrative_repairs.json first.)')
        return

    # Validate ALL before applying ANY.
    errors = []
    for batch_key, e in approved:
        tid = by_name.get(e['team'])
        label = f"[{batch_key}#{e['findingId']} {e['team']}/{e['field']}]"
        if not tid:
            errors.append(f"{label} team not found in team_history.json")
            continue
        e['_tid'] = tid
        current = history[tid].get(e['field'])
        if current is None:
            errors.append(f"{label} field missing")
        elif e.get('kind') == 'value':
            if current != e['find']:
                errors.append(f"{label} current value {current!r} != expected {e['find']!r}")
        else:
            n = str(current).count(e['find'])
            if n != 1:
                errors.append(f"{label} `find` text matched {n} times (need exactly 1)")

    if errors:
        print('VALIDATION FAILED — nothing applied:')
        for err in errors:
            print(' ', err)
        sys.exit(1)

    print(f'{len(approved)} approved entries validated.')
    if dry_run:
        for _, e in approved:
            print(f"  would apply: {e['team']}/{e['field']} (finding {e['findingId']})")
        return

    os.makedirs(BACKUP_DIR, exist_ok=True)
    backup_path = os.path.join(BACKUP_DIR, f"team_history.pre-repairs.{date.today().isoformat()}.json")
    shutil.copy2(HISTORY_PATH, backup_path)
    print(f'Backup: {backup_path}')

    for _, e in approved:
        tid = e.pop('_tid')
        if e.get('kind') == 'value':
            history[tid][e['field']] = e['replace']
        else:
            history[tid][e['field']] = history[tid][e['field']].replace(e['find'], e['replace'])
        e['status'] = 'applied'
        e['appliedOn'] = date.today().isoformat()
        print(f"  applied: {e['team']}/{e['field']} (finding {e['findingId']})")

    save_json_atomic(HISTORY_PATH, history, indent=2, ensure_ascii=False)
    save_json_atomic(REPAIRS_PATH, repairs, indent=2, ensure_ascii=False)
    print(f'Done: {len(approved)} repairs applied to team_history.json.')


if __name__ == '__main__':
    main()
