#!/usr/bin/env python3
"""MADS §32 reference broker for a trusted launcher and canonical bare Git.

Not a network service or a GitHub mirror writer. Run only under the Owner's
broker identity; keep policy and allowed-signers outside agent-writable refs.
"""
import argparse
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
import sys
from mads_verify import covers, path_name, scope_list, strict_json, exact_keys

ZERO = '0' * 40
DENY = ('production_authorized', 'external_host_authorized',
        'main_merge_authorized', 'us_poweroff_authorized')


def require(ok, reason):
    if not ok:
        raise ValueError(reason)


def canonical(value):
    return (json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False) + '\n').encode()


def parse(raw):
    require(len(raw) <= 1024 * 1024, 'oversized JSON')
    return strict_json(raw)


def git_env(env=None):
    source = os.environ if env is None else env
    clean = {k: v for k, v in source.items() if not k.startswith('GIT_')}
    if env is not None and 'GIT_INDEX_FILE' in env:
        clean['GIT_INDEX_FILE'] = env['GIT_INDEX_FILE']
    clean.update(GIT_NO_REPLACE_OBJECTS='1', GIT_CONFIG_NOSYSTEM='1', GIT_CONFIG_GLOBAL=os.devnull)
    return clean


def git(repo, *args, data=None, env=None):
    env = git_env(env)
    return subprocess.run(['git', '--git-dir', str(repo), *args], input=data,
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                          env=env, check=True).stdout


def oid(repo, ref):
    require(type(ref) is str and ref.startswith('refs/heads/'), 'not a branch ref')
    git(repo, 'check-ref-format', ref)
    tip = git(repo, 'rev-parse', '--verify', ref).decode().strip()
    refs = git(repo, 'for-each-ref', '--format=%(refname)%09%(symref)', ref).decode().splitlines()
    require(ref + '\t' in refs, 'symbolic or missing ref')
    require(re.fullmatch('[0-9a-f]{40}', tip) is not None and
            git(repo, 'cat-file', '-t', tip).strip() == b'commit', 'branch ref is not a commit')
    return tip


def read(repo, tip, path):
    require(type(tip) is str and re.fullmatch('[0-9a-f]{40}', tip) is not None, 'bad object id')
    path_name(path)
    entry = git(repo, 'ls-tree', tip, '--', path).decode().split()
    require(len(entry) >= 4 and entry[0] in ('100644', '100755') and entry[1] == 'blob' and entry[3] == path, 'not a regular Git blob')
    return git(repo, 'show', f'{tip}:{path}')


def commit(repo, parent, path, obj):
    path_name(path)
    with tempfile.TemporaryDirectory() as d:
        env = dict(os.environ, GIT_INDEX_FILE=str(Path(d) / 'index'))
        git(repo, 'read-tree', parent, env=env)
        blob = git(repo, 'hash-object', '-w', '--stdin', data=canonical(obj)).decode().strip()
        git(repo, 'update-index', '--add', '--cacheinfo', f'100644,{blob},{path}', env=env)
        tree = git(repo, 'write-tree', env=env).decode().strip()
        return git(repo, 'commit-tree', tree, '-p', parent, '-m', f'MADS successor {path}').decode().strip()


def append_mail(repo, parent, path, obj):
    require(not git(repo, 'ls-tree', parent, '--', path), 'immutable mail already exists')
    return commit(repo, parent, path, obj)


def atomic(repo, checks, updates):
    require(not set(checks) & set(updates), 'overlapping refs')
    lines = ['start']
    for ref, old in sorted(checks.items()):
        git(repo, 'check-ref-format', ref)
        require(ref.startswith('refs/heads/') and type(old) is str and re.fullmatch('[0-9a-f]{40}', old), 'bad guard')
        lines.append(f'verify {ref} {old}')
    for ref, (old, new) in sorted(updates.items()):
        git(repo, 'check-ref-format', ref)
        require(ref.startswith('refs/heads/') and all(type(x) is str and re.fullmatch('[0-9a-f]{40}', x) for x in (old, new)), 'bad OID')
        if old == ZERO:
            lines.append(f'create {ref} {new}')
        else:
            git(repo, 'merge-base', '--is-ancestor', old, new)
            lines.append(f'update {ref} {new} {old}')
    prepared_transaction(repo, lines, checks, updates)
    require(all(oid(repo, ref) == new for ref, (_, new) in updates.items()), 'postcommit drift; freeze')


def prepared_transaction(repo, lines, checks, updates):
    """Recheck direct ref type while the Git transaction holds its ref locks.

    This covers Git-mediated writers, not privileged raw ref-file mutation.
    The deployment must independently prevent bypass of the canonical writer.
    """
    argv = ['git', '--git-dir', str(repo), 'update-ref', '--no-deref', '--stdin']
    with tempfile.TemporaryFile() as errors:
        proc = subprocess.Popen(argv, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                stderr=errors, env=git_env())
        try:
            def step(command, reply):
                proc.stdin.write(command.encode())
                proc.stdin.flush()
                if proc.stdout.readline() != reply:
                    raise subprocess.CalledProcessError(proc.poll() or 1, argv)
            step('start\n', b'start: ok\n')
            step('\n'.join(lines[1:] + ['prepare']) + '\n', b'prepare: ok\n')
            for ref, old in {**checks, **{r: pair[0] for r, pair in updates.items()}}.items():
                if old == ZERO:
                    probe = subprocess.run(['git', '--git-dir', str(repo), 'symbolic-ref', '-q', ref],
                                           env=git_env(), capture_output=True)
                    require(probe.returncode == 1, 'symbolic or invalid create target')
                else:
                    require(oid(repo, ref) == old, 'prepared guard drift')
            step('commit\n', b'commit: ok\n')
            proc.stdin.close()
            require(proc.wait() == 0, 'transaction failed')
        finally:
            # Close owned pipes even if prepare failed and the child already exited.
            # EOF aborts any uncommitted prepared transaction; always reap the child.
            try:
                if not proc.stdin.closed:
                    proc.stdin.close()
            finally:
                try:
                    proc.wait()
                finally:
                    proc.stdout.close()


def time(value):
    require(type(value) is str, 'invalid time type')
    result = dt.datetime.fromisoformat(value.replace('Z', '+00:00'))
    require(result.tzinfo is not None, 'time zone required')
    return result


def role_status(status, cfg, role, now):
    require(type(status) is dict and type(cfg.get('status_schema')) is str and status.get('schema') == cfg['status_schema'], 'unknown status schema')
    require(status.get('role_id') == role, 'role mismatch')
    require(type(status.get('lease_epoch')) is int and status['lease_epoch'] > 0, 'invalid epoch')
    require(all(type(status.get(k)) is str and status[k] for k in ('session_id', 'source_branch', 'status_branch', 'inbox', 'outbox', 'monitoring_mode')), 'invalid status field')
    require(all(type(status.get(k)) is str and re.fullmatch('[0-9a-f]{40}', status[k]) for k in ('source_head', 'source_tree')), 'invalid source pin')
    require(status['monitoring_mode'] in ('manual', 'OWNER_EXPLICIT_BOUNDED_MANUAL_EXCEPTION', 'WATCHDOG_VERIFIED') and
            status['monitoring_mode'] == cfg['monitoring_mode'], 'unapproved monitoring mode')
    approved = scope_list(cfg['allowed_paths'])
    actual = scope_list(status['allowed_paths'])
    require(all(any(covers(p, x) for p in approved) for x in actual), 'unapproved scope')
    require(all(status.get(k) is False for k in DENY) and status.get('upgrade_hold') is True, 'forbidden authority')
    require(time(status['expires_utc']) > now and time(status['manual_monitoring_expires_utc']) > now, 'expired status')
    state = status.get('state')
    require((state in ('ACTIVE', 'LEASE_ACTIVE_SOURCE_SCOPED') and status.get('source_write_authorized') is True) or (state == 'OFFERED_CONDITIONAL' and status.get('source_write_authorized') is False), 'invalid status state/authority')


def safe_status(status, now):
    require(status.get('source_write_authorized') is True and status.get('state') in
            ('ACTIVE', 'LEASE_ACTIVE_SOURCE_SCOPED'), 'not active')
    require(all(status.get(k) is False for k in DENY), 'forbidden authority')
    require(status.get('upgrade_hold') is True, 'hold required')
    require(time(status['expires_utc']) > now and time(status['manual_monitoring_expires_utc']) > now,
            'expired lease or monitoring')
    scope_list(status['allowed_paths'])
    require(type(status['lease_epoch']) is int and status['lease_epoch'] > 0, 'invalid epoch')


def transact(repo, policy, request, now):
    # Caller MUST authenticate exact request bytes using the trusted launcher.
    require(type(policy) is dict and type(request) is dict, 'object policy/request required')
    require(policy['enabled'] is True and policy['canonical_bare'] is True, 'broker disabled')
    require(Path(repo).resolve() == Path(policy['repo_path']).resolve(), 'wrong repository path')
    require(git(repo, 'rev-parse', '--is-bare-repository').strip() == b'true', 'bare repo required')
    require(request['project'] == policy['project'], 'wrong project')
    require(request['kind'] in ('offer', 'activate'), 'bad request kind')
    fields = {'project', 'kind', 'role', 'directive', 'conflict', 'stop_reviewed',
              'ledger_reviewed', 'issued_at', 'expires_at', 'id', 'current_tip',
              'old_session', 'source_head', 'source_tree', 'lock_blobs', 'guards',
              'inbox_tip', 'ledger_ref', 'ledger_path', 'ledger_sha256'}
    exact_keys(request, fields | ({'offer_id'} if request['kind'] == 'activate' else set()))
    role = request['role']
    require(role in policy['roles'], 'role not enrolled')
    cfg = policy['roles'][role]
    require(cfg['runtime'] == 'manual' and cfg['enabled'] is True, 'not manual/enrolled')
    require(request['directive'] == 'HUMAN_REPLACEMENT' and request['conflict'] is False and request['stop_reviewed'] is True and
            request['ledger_reviewed'] is True,
            'ambiguous launch or conflict')
    require(time(request['issued_at']) <= now < time(request['expires_at']) and
            time(request['expires_at']) - time(request['issued_at']) <= dt.timedelta(minutes=15), 'stale request')
    rid = request['id']
    require(type(rid) is str and re.fullmatch('[0-9a-f]{32}', rid) is not None, 'invalid request id')
    ptr, inbox, outbox = (cfg[k] for k in ('current', 'inbox', 'outbox'))
    current = oid(repo, ptr)
    status = parse(read(repo, current, 'sessions/onboarding.json'))
    role_status(status, cfg, role, now)
    require(type(request.get('guards')) is dict and type(request.get('lock_blobs')) is dict, 'guard/lock map required')
    require(set(request['guards']) == set(cfg['guards']) | {outbox}, 'incomplete guard set')
    require(set(request['lock_blobs']) == set(scope_list(cfg['lock_paths'])), 'incomplete lock pins')
    for path in request['lock_blobs']:
        path_name(path)
    require(status['inbox'] == inbox.removeprefix('refs/heads/') and
            status['outbox'] == outbox.removeprefix('refs/heads/'), 'mailbox mapping mismatch')
    require(status.get('lock_blobs') == request['lock_blobs'], 'predecessor/offered lock mismatch')
    require(request['ledger_ref'] == cfg['ledger_ref'] and request['ledger_path'] == cfg['ledger_path'], 'unapproved canonical ledger')
    path_name(cfg['ledger_path'])
    request_hash = hashlib.sha256(canonical(request)).hexdigest()
    request_path = 'coordination/messages/MADS-REQUEST-' + rid + '.json'
    incoming = oid(repo, inbox)
    seen = bool(git(repo, 'ls-tree', incoming, '--', request_path))
    if seen:
        require(parse(read(repo, incoming, request_path)) ==
                {'id': rid, 'kind': request['kind'], 'sha256': request_hash}, 'request ID reuse')
        require(status.get('last_request_sha256') == request_hash, 'historical request replay')
    else:
        require(status.get('last_request_sha256') != request_hash, 'missing request journal')
    if status.get('last_request_sha256') == request_hash:
        require(oid(repo, 'refs/heads/' + status['status_branch']) == current, 'status drift')
        require(oid(repo, 'refs/heads/' + status['source_branch']) == status['source_head'], 'source drift')
        for ref, expected in request['guards'].items():
            require(oid(repo, ref) == expected, 'guard drift after transaction')
        require(oid(repo, inbox) == status['verified_inbox_tip'], 'inbox drift after transaction')
        require(oid(repo, status['prior_status_ref']) == status['prior_status_head'], 'prior revoke drift')
        prior = parse(read(repo, status['prior_status_head'], 'sessions/onboarding.json'))
        require(oid(repo, 'refs/heads/' + prior['source_branch']) == status['prior_source_head'], 'late predecessor write')
        return {'state': status['state'], 'status': current, 'reused': True}
    require(current == request['current_tip'], 'current CAS conflict')
    oldref = 'refs/heads/' + status['status_branch']
    source = 'refs/heads/' + status['source_branch']
    require(oldref == cfg['status_prefix'] + str(status['lease_epoch']), 'status prefix mismatch')
    require(source.startswith(cfg['source_prefix']), 'source prefix mismatch')
    require(oid(repo, oldref) == current, 'epoch status drift')
    head = oid(repo, source)
    require(head == request['source_head'] == status['source_head'], 'source drift; reconcile first')
    tree = git(repo, 'rev-parse', f'{head}^{{tree}}').decode().strip()
    require(tree == status['source_tree'] == request['source_tree'], 'tree drift')
    require(set(request['lock_blobs']) == set(cfg['lock_paths']), 'incomplete lock pins')
    for path, expected in request['lock_blobs'].items():
        read(repo, head, path)
        require(git(repo, 'rev-parse', f'{head}:{path}').decode().strip() == expected, 'lock drift')
    guards = request['guards']
    require('refs/heads/main' in cfg['guards'], 'main guard missing')
    require(set(guards) == set(cfg['guards']) | {outbox}, 'incomplete guard set')
    require(all(oid(repo, ref) == expected for ref, expected in guards.items()), 'mail/main drift')
    require(not set(guards) & {ptr, oldref, source, inbox}, 'guard overlap')
    incoming = oid(repo, inbox)
    require(incoming == request['inbox_tip'], 'inbox drift')
    checks = {**guards, source: head}
    if request['kind'] == 'offer':
        safe_status(status, now)
        require(request['old_session'] == status['session_id'], 'wrong predecessor')
        require(request['ledger_ref'] in guards and request['ledger_path'], 'missing pinned ledger')
        ledger = read(repo, guards[request['ledger_ref']], request['ledger_path'])
        require(hashlib.sha256(ledger).hexdigest() == request['ledger_sha256'], 'ledger mismatch')
        epoch = status['lease_epoch'] + 1
        newref = cfg['status_prefix'] + str(epoch)
        newsource = cfg['source_prefix'] + f'successor-{epoch}-{rid}'
        revoked = dict(status, state='REVOKED', source_write_authorized=False,
                       stop_id='MADS-STOP-' + rid, replacement_request=rid)
        rtip = commit(repo, current, 'sessions/onboarding.json', revoked)
        new = {k: status[k] for k in ('schema', 'role_id', 'allowed_paths', 'expires_utc',
               'manual_monitoring_expires_utc', 'monitoring_mode')}
        new.update(dict(state='OFFERED_CONDITIONAL', source_write_authorized=False,
                        source_permission_issued=True, lease_epoch=epoch, session_id=role + '-' + rid,
                        status_branch=newref.removeprefix('refs/heads/'),
                        source_branch=newsource.removeprefix('refs/heads/'), source_head=head,
                        source_tree=tree, lock_blobs=request['lock_blobs'], prior_status_ref=oldref, prior_status_head=rtip,
                        prior_session_id=status['session_id'], prior_lease_epoch=status['lease_epoch'],
                        prior_source_head=head, ledger_ref=request['ledger_ref'],
                        ledger_path=request['ledger_path'], ledger_sha256=request['ledger_sha256'],
                        order_id='MADS-SESSION-START-' + rid, offer_id=rid,
                        inbox=status['inbox'], outbox=status['outbox'],
                        last_request_sha256=request_hash, upgrade_hold=True,
                        github_credential_revocation_verified=False, unpublished_work='UNKNOWN',
                        **{k: False for k in DENY}))
        mail = append_mail(repo, incoming, request_path, {'id': rid, 'kind': request['kind'], 'sha256': request_hash})
        mail = append_mail(repo, mail, f'coordination/messages/MADS-STOP-{rid}.json', revoked)
        mail = append_mail(repo, mail, f'coordination/messages/MADS-SESSION-START-{rid}.json', new)
        new['verified_inbox_tip'] = mail
        ntip = commit(repo, rtip, 'sessions/onboarding.json', new)
        atomic(repo, checks, {ptr: (current, ntip), oldref: (current, rtip),
                               newref: (ZERO, ntip), newsource: (ZERO, head), inbox: (incoming, mail)})
        return {'state': new['state'], 'status': ntip, 'reused': False}
    require(all(status.get(k) is False for k in DENY) and status.get('upgrade_hold') is True, 'forbidden offered authority')
    require(status['state'] == 'OFFERED_CONDITIONAL' and status['source_write_authorized'] is False,
            'no conditional offer')
    require(request['offer_id'] == status['offer_id'], 'wrong offer')
    require(request['old_session'] == status['prior_session_id'] and
            all(request[k] == status[k] for k in ('ledger_ref', 'ledger_path', 'ledger_sha256')), 'activation baseline mismatch')
    require(status['lock_blobs'] == request['lock_blobs'], 'offered lock mismatch')
    require(time(status['expires_utc']) > now and time(status['manual_monitoring_expires_utc']) > now,
            'expired offer')
    require(status['ledger_ref'] in guards, 'offered ledger not guarded')
    ledger = read(repo, guards[status['ledger_ref']], status['ledger_path'])
    require(hashlib.sha256(ledger).hexdigest() == status['ledger_sha256'], 'offered ledger drift')
    prior = status['prior_status_ref']
    require(oid(repo, prior) == status['prior_status_head'], 'prior revoke drift')
    old = parse(read(repo, status['prior_status_head'], 'sessions/onboarding.json'))
    oldsource = 'refs/heads/' + old['source_branch']
    require(oldsource.startswith(cfg['source_prefix']) and oid(repo, oldsource) == status['prior_source_head'],
            'late predecessor write; freeze')
    require(old['state'] == 'REVOKED' and old['source_write_authorized'] is False, 'prior not revoked')
    ack = parse(read(repo, guards[outbox], 'coordination/messages/MADS-ACK-' + status['offer_id'] + '.json'))
    require(ack == {'offer_id': status['offer_id'], 'session_id': status['session_id'],
                    'status_tip': current, 'source_head': head, 'source_tree': tree,
                    'ledger_sha256': status['ledger_sha256'], 'decision': 'ACK'}, 'ACK mismatch')
    mail = append_mail(repo, incoming, request_path, {'id': rid, 'kind': request['kind'], 'sha256': request_hash})
    active = dict(status, state='ACTIVE', source_write_authorized=True,
                  last_request_sha256=request_hash, verified_inbox_tip=mail)
    atip = commit(repo, current, 'sessions/onboarding.json', active)
    atomic(repo, {**checks, oldsource: status['prior_source_head'], prior: status['prior_status_head']},
           {ptr: (current, atip), oldref: (current, atip), inbox: (incoming, mail)})
    return {'state': 'ACTIVE', 'status': atip, 'reused': False}


def main():
    p = argparse.ArgumentParser()
    for field in ('repo', 'policy', 'request', 'signature', 'allowed-signers'):
        p.add_argument('--' + field, required=True)
    a = p.parse_args()
    try:
        raw = Path(a.request).read_bytes()
        request = parse(raw)
        policy = parse(Path(a.policy).read_bytes())
        subprocess.run(['ssh-keygen', '-Y', 'verify', '-f', a.allowed_signers, '-I',
                        policy['launcher_principal'], '-n', 'mads.successor.v1', '-s', a.signature],
                       input=raw, check=True)
        print(json.dumps(transact(Path(a.repo), policy, request, dt.datetime.now(dt.timezone.utc))))
        return 0
    except (OSError, ValueError, TypeError, AttributeError, KeyError, RuntimeError, subprocess.CalledProcessError) as exc:
        print(json.dumps({'state': 'BLOCKED', 'error_type': type(exc).__name__}, sort_keys=True))
        return 1


if __name__ == '__main__':
    sys.exit(main())
