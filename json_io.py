"""Atomic JSON writes for the Hoopsipedia data pipeline.

Every scraper/compiler that writes a tracked data file must go through
save_json_atomic() instead of json.dump(open(path, 'w')). A plain dump
truncates the destination first, so a crash mid-write (disk full, OOM,
Ctrl-C) leaves a corrupt file — and these files represent weeks of
rate-limited scraping.

The write goes to a temp file in the same directory (same filesystem),
is fsynced, then os.replace()d over the destination — atomic on POSIX.
"""

import json
import os
import tempfile


def save_json_atomic(path, obj, **dump_kwargs):
    """Write obj as JSON to path atomically. Accepts json.dump kwargs
    (indent, separators, ensure_ascii, ...)."""
    path = os.fspath(path)
    dirname = os.path.dirname(os.path.abspath(path))
    fd, tmp_path = tempfile.mkstemp(dir=dirname, prefix=os.path.basename(path) + '.', suffix='.tmp')
    try:
        with os.fdopen(fd, 'w') as f:
            json.dump(obj, f, **dump_kwargs)
            f.flush()
            os.fsync(f.fileno())
        os.chmod(tmp_path, 0o644)  # mkstemp defaults to 0600; match sibling data files
        os.replace(tmp_path, path)
    except BaseException:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise
