#!/usr/bin/env python3
"""MADS reference checks. Trust pins must come from outside the checked writer.

A PASS verifies bytes/bindings/scope, not execution, identity or production rights.
"""
import argparse
import hashlib
import json
import math
import os
import re
import stat
import subprocess
import sys
import zipfile
from pathlib import Path

MAX_JSON = 4_000_000
MAX_FILE = 4_000_000
MAX_ZIP = 32_000_000
HEX = re.compile(r'[0-9a-f]{64}\Z')
OID = re.compile(r'(?:[0-9a-f]{40}|[0-9a-f]{64})\Z')


def require(ok, code):
    if not ok:
        raise ValueError(code)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def strict_json(raw):
    def unique(pairs):
        obj = {}
        for key, value in pairs:
            require(key not in obj, 'DUPLICATE_JSON_KEY')
            obj[key] = value
        return obj

    def reject_constant(_):
        raise ValueError('NONFINITE_JSON')

    def finite(value):
        number = float(value)
        require(math.isfinite(number), 'NONFINITE_JSON')
        return number

    require(len(raw) <= MAX_JSON, 'JSON_TOO_LARGE')
    obj = json.loads(raw.decode('utf-8'), object_pairs_hook=unique,
                     parse_constant=reject_constant, parse_float=finite)
    require(type(obj) is dict, 'JSON_OBJECT_REQUIRED')
    return obj


def path_name(value):
    require(type(value) is str and bool(re.fullmatch(r'[A-Za-z0-9_.@+-]+(?:/[A-Za-z0-9_.@+-]+)*', value)), 'UNSAFE_PATH')
    require(all(part.casefold() not in ('.', '..', '.git') and not part.endswith('.') for part in value.split('/')), 'UNSAFE_PATH')
    return value


def hash_value(value):
    require(type(value) is str and HEX.fullmatch(value) is not None, 'BAD_SHA256')
    return value


def oid_value(value):
    require(type(value) is str and OID.fullmatch(value) is not None, 'BAD_GIT_OID')
    return value


def file_bytes(root, rel, limit=MAX_FILE):
    path_name(rel)
    p = root.resolve()
    for part in rel.split('/'):
        p = p / part
        require(not p.is_symlink(), 'SYMLINK_PATH')
    require(p.is_file() and p.stat().st_size <= limit, 'MISSING_OR_OVERSIZED_FILE')
    data = p.read_bytes()
    require(len(data) <= limit, 'OVERSIZED_FILE')
    return data


def hashes(obj):
    require(type(obj) is dict and bool(obj), 'HASH_MAP_REQUIRED')
    for k, v in obj.items():
        path_name(k)
        hash_value(v)
    require(len({k.casefold() for k in obj}) == len(obj), 'CASE_ALIAS_PATH')
    return obj


def exact_keys(obj, keys):
    require(type(obj) is dict and set(obj) == set(keys), 'SCHEMA_KEYS_MISMATCH')


def anchored(raw, expected):
    require(sha(raw) == hash_value(expected), 'TRUST_ANCHOR_MISMATCH')
    return strict_json(raw)


def release_anchor(raw, expected):
    a = anchored(raw, expected)
    exact_keys(a, ('schema', 'version', 'source_commit', 'archive_sha256', 'draft', 'files_sha256'))
    require(a['schema'] == 'mads.release-trust.v1', 'BAD_RELEASE_SCHEMA')
    require(type(a['version']) is str and re.fullmatch(r'[0-9]+\.[0-9]+\.[0-9]+', a['version']), 'BAD_VERSION')
    oid_value(a['source_commit'])
    hash_value(a['archive_sha256'])
    require(type(a['draft']) is bool, 'BAD_DRAFT_TYPE')
    hashes(a['files_sha256'])
    return a


def verify_archive(archive, anchor, *, allow_draft=False):
    require(not anchor['draft'] or allow_draft, 'DRAFT_NOT_ADOPTABLE')
    require(archive.stat().st_size <= MAX_ZIP, 'ZIP_TOO_LARGE')
    raw = archive.read_bytes()
    require(len(raw) <= MAX_ZIP and sha(raw) == anchor['archive_sha256'], 'ARCHIVE_HASH_MISMATCH')
    from io import BytesIO
    expected = anchor['files_sha256']
    prefix = 'mads-standard-v' + anchor['version'] + '/'
    metadata = {'RELEASE-MANIFEST.json', 'SHA256SUMS.txt'}
    require(not {k.casefold() for k in metadata}.intersection(k.casefold() for k in expected), 'RESERVED_PATH')
    with zipfile.ZipFile(BytesIO(raw)) as z:
        infos = z.infolist()
        names = [i.filename for i in infos]
        require(len(names) == len(set(names)), 'DUPLICATE_ZIP_MEMBER')
        require(len(names) == len({n.casefold() for n in names}), 'CASE_ALIAS_ZIP_MEMBER')
        require(set(names) == {prefix + k for k in set(expected) | metadata}, 'ZIP_FILE_SET_MISMATCH')
        require(sum(i.file_size for i in infos) <= MAX_ZIP, 'ZIP_EXPANSION_LIMIT')
        for i in infos:
            require(i.filename.startswith(prefix), 'ZIP_PREFIX')
            path_name(i.filename[len(prefix):])
            require(not i.is_dir() and stat.S_IFMT(i.external_attr >> 16) == stat.S_IFREG and i.file_size <= MAX_FILE and not i.flag_bits & 1, 'UNSAFE_ZIP_MEMBER')
        manifest = strict_json(z.read(prefix + 'RELEASE-MANIFEST.json'))
        exact_keys(manifest, ('schema', 'version', 'draft', 'files_sha256'))
        require(manifest['schema'] == 'mads.release-manifest.v1' and manifest['version'] == anchor['version'] and manifest['draft'] is anchor['draft'] and manifest['files_sha256'] == expected, 'INNER_MANIFEST_MISMATCH')
        sums = {}
        for line in z.read(prefix + 'SHA256SUMS.txt').decode('utf-8').splitlines():
            digest, rel = line.split('  ', 1)
            path_name(rel)
            require(rel not in sums, 'DUPLICATE_CHECKSUM_PATH')
            sums[rel] = hash_value(digest)
        require(sums == {**expected, 'RELEASE-MANIFEST.json': sha(z.read(prefix + 'RELEASE-MANIFEST.json'))}, 'CHECKSUM_SET_MISMATCH')
        for rel, digest in expected.items():
            require(sha(z.read(prefix + rel)) == digest, 'PAYLOAD_HASH_MISMATCH:' + rel)
    return {'archive': 'PASS', 'files_checked': len(expected), 'draft': anchor['draft']}


def verify_source(root, anchor):
    require(anchor['draft'] is False, 'DRAFT_NOT_ADOPTABLE')
    for rel, digest in anchor['files_sha256'].items():
        require(sha(file_bytes(root, rel)) == digest, 'SOURCE_HASH_MISMATCH:' + rel)
    return {'source': 'PASS', 'files_checked': len(anchor['files_sha256']), 'scope': 'ANCHORED_REQUIRED_FILES_ONLY'}


def git(repo, *args):
    env = {k: v for k, v in os.environ.items() if not k.startswith('GIT_')}
    env.update(GIT_NO_REPLACE_OBJECTS='1', GIT_CONFIG_NOSYSTEM='1', GIT_CONFIG_GLOBAL=os.devnull)
    return subprocess.run(['git', '-C', str(repo), *args], check=True, env=env,
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE).stdout


def verify_evidence(repo, artifact_root, expected, receipt):
    keys = ('schema', 'head', 'tree', 'locks_sha256', 'environment_sha256', 'inputs_sha256', 'argv', 'rc', 'artifacts_sha256')
    exact_keys(receipt, keys)
    exact_keys(expected, keys)
    require(receipt['schema'] == 'mads.evidence-binding.v1' and receipt == expected, 'EVIDENCE_BINDING_MISMATCH')
    head = oid_value(receipt['head'])
    tree = oid_value(receipt['tree'])
    require(git(repo, 'rev-parse', '--verify', head + '^{commit}').decode().strip() == head, 'COMMIT_MISMATCH')
    require(git(repo, 'rev-parse', head + '^{tree}').decode().strip() == tree, 'TREE_MISMATCH')
    require(type(receipt['rc']) is int and receipt['rc'] == 0, 'NONZERO_OR_INVALID_RC')
    require(type(receipt['argv']) is list and bool(receipt['argv']) and all(type(x) is str and x and '\x00' not in x for x in receipt['argv']), 'BAD_ARGV')
    hash_value(receipt['environment_sha256'])
    hash_value(receipt['inputs_sha256'])
    locks = receipt['locks_sha256']
    require(type(locks) is dict, 'LOCK_MAP_REQUIRED')
    for rel, digest in locks.items():
        path_name(rel)
        require(sha(git(repo, 'show', head + ':' + rel)) == hash_value(digest), 'LOCK_MISMATCH:' + rel)
    for rel, digest in hashes(receipt['artifacts_sha256']).items():
        require(sha(file_bytes(artifact_root, rel)) == digest, 'ARTIFACT_MISMATCH:' + rel)
    return {'binding': 'PASS', 'execution_proven': False, 'head': head, 'tree': tree}


def scope_list(value):
    require(type(value) is list and bool(value), 'SCOPE_LIST_REQUIRED')
    for item in value:
        require(type(item) is str, 'BAD_SCOPE_TYPE')
        path_name(item[:-3] if item.endswith('/**') else item)
    require(len(value) == len(set(value)), 'DUPLICATE_SCOPE')
    return value


def covers(parent, child):
    if parent == child:
        return True
    return parent.endswith('/**') and child.startswith(parent[:-2])


def verify_scope(registry, lease, order, task, changed, forbidden=()):
    levels = [scope_list(x) for x in (registry, lease, order, task)]
    require(type(forbidden) in (list, tuple), 'BAD_FORBIDDEN_SCOPE')
    denies = scope_list(list(forbidden)) if forbidden else []
    for outer, inner in zip(levels, levels[1:]):
        require(all(any(covers(p, c) for p in outer) for c in inner), 'SCOPE_EXPANSION')
    require(not any(covers(d, c) or covers(c, d) for d in denies for c in levels[-1]), 'FORBIDDEN_SCOPE_INTERSECTION')
    require(type(changed) is list, 'CHANGED_PATHS_REQUIRED')
    for rel in changed:
        path_name(rel)
        require(any(covers(p, rel) for p in levels[-1]) and not any(covers(d, rel) for d in denies), 'OUT_OF_SCOPE:' + rel)
    return {'scope': 'PASS', 'write_authorized': False}


def verify_projection(root, anchor, projection):
    require(anchor['draft'] is False, 'DRAFT_NOT_ADOPTABLE')
    exact_keys(projection, ('schema', 'release_source_commit', 'paths'))
    require(projection['schema'] == 'mads.release-projection.v1' and projection['release_source_commit'] == anchor['source_commit'], 'PROJECTION_RELEASE_MISMATCH')
    mapping = projection['paths']
    require(type(mapping) is dict and bool(mapping), 'PROJECTION_MAP_REQUIRED')
    targets = []
    for upstream, local in mapping.items():
        path_name(upstream)
        path_name(local)
        require(upstream in anchor['files_sha256'], 'UNKNOWN_UPSTREAM_PATH')
        targets.append(local.casefold())
        require(sha(file_bytes(root, local)) == anchor['files_sha256'][upstream], 'PROJECT_SOURCE_MISMATCH:' + local)
    require(len(targets) == len(set(targets)), 'DUPLICATE_PROJECTION_TARGET')
    return {'source': 'PASS', 'files_checked': len(mapping), 'scope': 'PROTECTED_PROJECT_PROJECTION_ONLY'}


def changed_paths(repo, base, head):
    for commit in (base, head):
        require(git(repo, 'rev-parse', '--verify', commit + '^{commit}').decode().strip() == commit, 'COMMIT_MISMATCH')
    git(repo, 'merge-base', '--is-ancestor', base, head)
    # Compare complete immutable trees, not a configurable worktree diff.
    def entries(commit):
        raw = git(repo, 'ls-tree', '-r', '-z', '--full-tree', commit)
        require(not raw or raw.endswith(b'\0'), 'MALFORMED_GIT_TREE')
        result = {}
        for entry in raw.split(b'\0')[:-1]:
            meta, rel = entry.decode('utf-8').split('\t', 1)
            mode, kind, oid = meta.split()
            require(rel not in result, 'DUPLICATE_GIT_PATH')
            result[rel] = (mode, kind, oid)
        return result
    before, after = entries(base), entries(head)
    paths = []
    for rel in sorted(before.keys() | after.keys()):
        if before.get(rel) == after.get(rel):
            continue
        for entry in (before.get(rel), after.get(rel)):
            require(entry is None or (entry[0] in ('100644', '100755') and entry[1] == 'blob'), 'UNSAFE_GIT_FILE_MODE:' + rel)
        paths.append(path_name(rel))
    return paths


def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument('mode', choices=['archive', 'source', 'projection', 'evidence', 'scope'])
    p.add_argument('--anchor', type=Path, required=True)
    p.add_argument('--anchor-sha256', required=True)
    p.add_argument('--archive', type=Path)
    p.add_argument('--root', type=Path, default=Path('.'))
    p.add_argument('--receipt', type=Path)
    p.add_argument('--projection', type=Path)
    p.add_argument('--projection-sha256')
    p.add_argument('--repo', type=Path, default=Path('.'))
    a = p.parse_args(argv)
    try:
        raw = a.anchor.read_bytes()
        if a.mode in ('source', 'archive', 'projection'):
            anchor = release_anchor(raw, a.anchor_sha256)
            if a.mode == 'source':
                result = verify_source(a.root, anchor)
            elif a.mode == 'projection':
                result = verify_projection(a.root, anchor, anchored(a.projection.read_bytes(), a.projection_sha256))
            else:
                result = verify_archive(a.archive, anchor)
        elif a.mode == 'evidence':
            result = verify_evidence(a.repo, a.root, anchored(raw, a.anchor_sha256), strict_json(a.receipt.read_bytes()))
        else:
            config = anchored(raw, a.anchor_sha256)
            exact_keys(config, ('registry', 'lease', 'order', 'task', 'forbidden', 'base', 'head'))
            base, head = oid_value(config['base']), oid_value(config['head'])
            changed = changed_paths(a.repo, base, head)
            result = verify_scope(config['registry'], config['lease'], config['order'], config['task'], changed, config['forbidden'])
        print(json.dumps({'state': 'PASS', **result}, sort_keys=True))
        return 0
    except (OSError, ValueError, TypeError, AttributeError, KeyError, RuntimeError, zipfile.BadZipFile, subprocess.CalledProcessError) as exc:
        print(json.dumps({'state': 'FAIL', 'error': str(exc), 'type': type(exc).__name__}, sort_keys=True))
        return 1


if __name__ == '__main__':
    sys.exit(main())
