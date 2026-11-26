#!/usr/bin/env python3
"""Bind a built ZIP to the exact reviewed Git checkout, not its own manifest."""
import argparse
import json
from pathlib import Path
from build_release import CORE, REQUIRED, ROOT, VERSION, project_sections
from mads_verify import file_bytes, git, require, sha, verify_archive


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--archive', type=Path, required=True)
    p.add_argument('--anchor-out', type=Path, required=True)
    p.add_argument('--draft', action='store_true')
    a = p.parse_args()
    head = git(ROOT, 'rev-parse', 'HEAD').decode().strip()
    require(git(ROOT, 'status', '--porcelain', '--untracked-files=no') == b'', 'DIRTY_TRACKED_SOURCE')
    paths = set(REQUIRED) | {'LICENSE'}
    files = {}
    for rel in sorted(paths):
        entry = git(ROOT, 'ls-tree', head, '--', rel).decode().split()
        require(len(entry) >= 4 and entry[0] in ('100644', '100755') and entry[1] == 'blob' and entry[3] == rel, 'NOT_TRACKED_REGULAR_FILE:' + rel)
        content = git(ROOT, 'show', head + ':' + rel)
        require(file_bytes(ROOT, rel) == content, 'CHECKOUT_DRIFT:' + rel)
        files[rel] = sha(content)
    anchor = dict(schema='mads.release-trust.v1', version=VERSION, source_commit=head,
                  archive_sha256=sha(a.archive.read_bytes()), draft=a.draft, files_sha256=files)
    result = verify_archive(a.archive, anchor, allow_draft=a.draft)
    doc = git(ROOT, 'show', head + ':' + CORE).decode()
    import re
    require([int(n) for n in re.findall(r'(?m)^## ([0-9]+)\.', doc)] == list(range(1, project_sections() + 1)), 'SECTION_SET_MISMATCH')
    prompt = git(ROOT, 'show', head + ':templates/mads/v2/NEW-PROJECT-BOOTSTRAP-PROMPT.ru.md').decode()
    require(prompt.count('[НАЗВАНИЕ ПРОЕКТА]') == 1 and 'SESSION_START' in prompt and 'sha256' in prompt.lower(), 'BOOTSTRAP_CONTRACT_MISMATCH')
    raw = (json.dumps(anchor, sort_keys=True, indent=2) + '\n').encode()
    a.anchor_out.write_bytes(raw)
    print(json.dumps({**result, 'source_commit': head, 'anchor_sha256': sha(raw), 'status': 'CANDIDATE_SOURCE_BOUND' if a.draft else 'PUBLISHED_BYTES_NOT_YET_VERIFIED'}, sort_keys=True))


if __name__ == '__main__':
    main()
