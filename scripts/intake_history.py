#!/usr/bin/env python3
"""Read-only exact-root Git history inventory, not an integration verdict."""
import argparse
import base64
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys

OID = re.compile(r'[0-9a-f]{40}\Z')


def git(repo, *args, data=None):
    env = {k: v for k, v in os.environ.items() if not k.startswith('GIT_')}
    env.update(GIT_NO_REPLACE_OBJECTS='1', GIT_GRAFT_FILE=os.devnull,
               GIT_CONFIG_NOSYSTEM='1', GIT_CONFIG_GLOBAL=os.devnull,
               GIT_NO_LAZY_FETCH='1', GIT_TERMINAL_PROMPT='0')
    return subprocess.check_output(['git', '-C', str(repo), *args], input=data,
                                   stderr=subprocess.PIPE, env=env)


def dump(obj):
    return json.dumps(obj, sort_keys=True, ensure_ascii=True, separators=(',', ':'))


def roots(snapshot):
    if snapshot.get('schema') != 'mads.history-roots.v1':
        raise ValueError('wrong root schema')
    rows = snapshot['roots']
    labels = set()
    for row in rows:
        if set(row) != {'label', 'oid'} or not isinstance(row['label'], str) or not row['label'] or row['label'] in labels or not isinstance(row['oid'], str) or not OID.fullmatch(row['oid']):
            raise ValueError('invalid or duplicate root')
        labels.add(row['label'])
    if not rows:
        raise ValueError('empty roots')
    return rows


def inventory(repo, snapshot, out):
    rows = roots(snapshot)
    if git(repo, 'rev-parse', '--is-shallow-repository').strip() != b'false':
        raise ValueError('shallow repository')
    if git(repo, 'rev-parse', '--show-object-format').strip() != b'sha1':
        raise ValueError('unsupported object format')
    missing = []
    commits = set()
    for row in rows:
        try:
            commit = git(repo, 'rev-parse', '--verify', row['oid'] + '^{commit}').decode().strip()
            commits.add(commit)
        except subprocess.CalledProcessError:
            missing.append(row)
    if missing:
        return {'status': 'BLOCKED_MISSING_ROOTS', 'missing': missing, 'roots': len(rows)}
    # Locally surviving unreachable objects are recoverable leads, not proof of remote history completeness.
    fsck = git(repo, 'fsck', '--full', '--no-reflogs', '--unreachable').decode('ascii', 'replace')
    recovered = sorted(set(re.findall(r'^unreachable commit ([0-9a-f]{40})$', fsck, re.M)))
    commits.update(recovered)
    graph = git(repo, 'rev-list', '--parents', '--stdin', data=('\n'.join(sorted(commits))+'\n').encode()).decode().splitlines()
    temp = out.with_name(out.name + '.partial')
    if out.exists() or temp.exists():
        raise ValueError('output already exists')
    count = deleted = replaced = edges = 0
    digest = hashlib.sha256()
    with temp.open('xb') as stream:
        def emit(obj):
            raw = (dump(obj)+'\n').encode(); stream.write(raw); digest.update(raw)
        emit({'kind':'header','roots':rows,'locally_unreachable_commits':recovered,
              'fsck_sha256':hashlib.sha256(fsck.encode()).hexdigest(),
              'claim':'reachable and locally surviving objects only'})
        for line in graph:
            commit, *parents = line.split()
            emit({'kind':'commit','oid':commit,'parents':parents})
            for parent in parents or [None]:
                args = ['diff-tree','-r','--raw','-z','--no-renames','--no-abbrev','--no-commit-id']
                args += [parent,commit] if parent else ['--root',commit]
                data = git(repo,*args).split(b'\0')
                if data[-1] != b'' or (len(data)-1)%2:
                    raise ValueError('invalid raw Git delta')
                edges += 1
                for i in range(0,len(data)-1,2):
                    old_mode,new_mode,old,new,status = data[i].decode('ascii').lstrip(':').split()
                    path = data[i+1]
                    if not path or not OID.fullmatch(old) or not OID.fullmatch(new):
                        raise ValueError('invalid Git delta entry')
                    emit({'kind':'delta','commit':commit,'parent':parent,'path_b64':base64.b64encode(path).decode(),'old_mode':old_mode,'new_mode':new_mode,'old':old,'new':new,'status':status})
                    count += 1
                    deleted += status == 'D'
                    replaced += status in ('M','T')
        stream.flush(); os.fsync(stream.fileno())
    temp.rename(out)
    return {'status':'INVENTORY_ONLY','roots':len(rows),'commits':len(graph),'parent_edges':edges,'deltas':count,'deleted':deleted,'replaced':replaced,'locally_unreachable_commits':len(recovered),'sha256':digest.hexdigest(),'remote_deleted_ref_completeness':False}


def main():
    p=argparse.ArgumentParser(); p.add_argument('--repo',type=Path,required=True); p.add_argument('--roots',type=Path,required=True); p.add_argument('--out',type=Path,required=True)
    a=p.parse_args()
    try:
        result=inventory(a.repo,json.loads(a.roots.read_text()),a.out)
    except (ValueError,KeyError,TypeError,OSError,subprocess.CalledProcessError) as exc:
        result={'status':'BLOCKED','reason':str(exc)}
    print(dump(result)); return 0 if result['status']=='INVENTORY_ONLY' else 2


if __name__=='__main__': sys.exit(main())
