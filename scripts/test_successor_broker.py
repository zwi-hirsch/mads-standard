import copy
import datetime as dt
import hashlib
import json
import sys
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch
import successor_broker as broker
from successor_broker import ZERO, atomic, canonical, commit, git, oid, parse, read, transact

NOW = dt.datetime(2026, 1, 1, tzinfo=dt.timezone.utc)
ROLE = 'demo-ci-01'
PTR = 'refs/heads/status/ci-current'
OLD = 'refs/heads/status/ci-3'
SRC = 'refs/heads/agent/ci/old'
IN = 'refs/heads/coord/owner-to-ci'
OUT = 'refs/heads/coord/ci-to-owner'
MAIN = 'refs/heads/main'
GLOBAL = 'refs/heads/coord/owner-to-agent'


class BrokerTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.repo = Path(temp.name) / 'repo.git'
        subprocess.run(['git', 'init', '--bare', '-q', str(self.repo)], check=True)
        git(self.repo, 'config', 'user.name', 'TEST ONLY')
        git(self.repo, 'config', 'user.email', 'test@example.invalid')
        tree = git(self.repo, 'mktree', data=b'').decode().strip()
        base = git(self.repo, 'commit-tree', tree, '-m', 'base').decode().strip()
        self.head = commit(self.repo, base, 'ledger.json', {'tasks': ['R1', 'R2']})
        self.tree = git(self.repo, 'rev-parse', f'{self.head}^{{tree}}').decode().strip()
        s = dict(schema='test', role_id=ROLE, state='ACTIVE', lease_epoch=3,
                 session_id='old', source_branch=SRC[11:], status_branch=OLD[11:],
                 inbox=IN[11:], outbox=OUT[11:], source_head=self.head, source_tree=self.tree,
                 allowed_paths=['src/a'], expires_utc='2026-05-01T00:00:00Z',
                 manual_monitoring_expires_utc='2026-05-01T00:00:00Z', monitoring_mode='manual',
                 lock_blobs={'ledger.json': git(self.repo, 'rev-parse', f'{self.head}:ledger.json').decode().strip()},
                 source_write_authorized=True, upgrade_hold=True, production_authorized=False,
                 external_host_authorized=False, main_merge_authorized=False, us_poweroff_authorized=False)
        self.old = commit(self.repo, self.head, 'sessions/onboarding.json', s)
        for ref in (MAIN, SRC, GLOBAL, IN, OUT):
            git(self.repo, 'update-ref', ref, self.head)
        for ref in (OLD, PTR):
            git(self.repo, 'update-ref', ref, self.old)
        self.policy = dict(enabled=True, canonical_bare=True, project='demo', repo_path=str(self.repo),
                           roles={ROLE: dict(enabled=True, runtime='manual', current=PTR,
                           inbox=IN, outbox=OUT, status_prefix='refs/heads/status/ci-',
                           source_prefix='refs/heads/agent/ci/', guards=[MAIN, GLOBAL], lock_paths=['ledger.json'],
                           status_schema='test', allowed_paths=['src/**'], monitoring_mode='manual',
                           ledger_ref=MAIN, ledger_path='ledger.json')})
        self.req = dict(project='demo', kind='offer', role=ROLE, directive='HUMAN_REPLACEMENT',
                        conflict=False, stop_reviewed=True, ledger_reviewed=True,
                        issued_at='2025-12-31T23:55:00Z', expires_at='2026-01-01T00:05:00Z',
                        id='a'*32, current_tip=self.old, old_session='old', source_head=self.head,
                        source_tree=self.tree, lock_blobs={'ledger.json':git(self.repo,'rev-parse',f'{self.head}:ledger.json').decode().strip()}, guards={MAIN:self.head, GLOBAL:self.head, OUT:self.head},
                        inbox_tip=self.head, ledger_ref=MAIN, ledger_path='ledger.json',
                        ledger_sha256=hashlib.sha256(read(self.repo,self.head,'ledger.json')).hexdigest())

    def runreq(self, req=None):
        return transact(self.repo,self.policy,self.req if req is None else req,NOW)

    def status(self):
        return parse(read(self.repo,oid(self.repo,PTR),'sessions/onboarding.json'))

    def ack(self):
        offer=self.runreq(); s=self.status()
        a=dict(offer_id=s['offer_id'],session_id=s['session_id'],status_tip=offer['status'],
               source_head=self.head,source_tree=self.tree,ledger_sha256=s['ledger_sha256'],decision='ACK')
        at=commit(self.repo,self.head,'coordination/messages/MADS-ACK-'+s['offer_id']+'.json',a)
        git(self.repo,'update-ref',OUT,at,self.head)
        return dict(self.req,kind='activate',id='b'*32,offer_id=s['offer_id'],current_tip=offer['status'],
                    inbox_tip=oid(self.repo,IN),guards={MAIN:self.head,GLOBAL:self.head,OUT:at})

    def denied(self, req=None):
        before=oid(self.repo,PTR)
        with self.assertRaises((ValueError,subprocess.CalledProcessError,KeyError)):
            self.runreq(req)
        self.assertEqual(oid(self.repo,PTR),before)

    def test_offer_activation_and_retry(self):
        a=self.ack(); s=self.status()
        self.assertEqual(s['lease_epoch'],4)
        self.assertEqual(s['allowed_paths'],['src/a'])
        self.assertFalse(s['source_write_authorized'])
        self.assertEqual(parse(read(self.repo,oid(self.repo,OLD),'sessions/onboarding.json'))['state'],'REVOKED')
        r=self.runreq(a)
        self.assertEqual(r['state'],'ACTIVE')
        self.assertTrue(self.runreq(a)['reused'])
        self.assertEqual(oid(self.repo,SRC),self.head)

    def test_offer_retry(self):
        first=self.runreq(); second=self.runreq()
        self.assertEqual(first['status'],second['status']); self.assertTrue(second['reused'])

    def test_wrong_role(self): self.denied(dict(self.req,role='unknown'))
    def test_ambiguous(self): self.denied(dict(self.req,directive='AGENT_ASSERTION'))
    def test_conflict(self): self.denied(dict(self.req,conflict=True))
    def test_stale(self): self.denied(dict(self.req,expires_at='2025-12-31T23:59:00Z'))
    def test_bad_ledger(self): self.denied(dict(self.req,ledger_sha256='0'*64))
    def test_no_stop_review(self): self.denied(dict(self.req,stop_reviewed=False))
    def test_inbox_drift(self): self.denied(dict(self.req,inbox_tip=self.old))
    def test_external(self):
        self.policy['roles'][ROLE]['runtime']='external'; self.denied()
    def test_duplicate_offer(self):
        self.runreq(); self.denied(dict(self.req,id='c'*32))
    def test_missing_ack(self):
        x=self.runreq(); self.denied(dict(self.req,kind='activate',current_tip=x['status'],
            inbox_tip=oid(self.repo,IN),offer_id=self.req['id']))
    def test_late_old_write(self):
        a=self.ack(); late=commit(self.repo,self.head,'late.json',{})
        git(self.repo,'update-ref',SRC,late,self.head); self.denied(a)
    def test_atomic_race(self):
        with self.assertRaises(subprocess.CalledProcessError):
            atomic(self.repo,{SRC:self.old},{PTR:(self.old,self.old),'refs/heads/test-new':(ZERO,self.head)})
        with self.assertRaises(subprocess.CalledProcessError): oid(self.repo,'refs/heads/test-new')
    def test_retry_after_stop_drift(self):
        self.runreq()
        previous=oid(self.repo,IN)
        late=commit(self.repo,previous,'coordination/messages/STOP.json',{})
        git(self.repo,'update-ref',IN,late,previous)
        self.denied()
    def test_activate_ledger_changed(self):
        a=self.ack()
        late=commit(self.repo,self.head,'ledger.json',{'tasks':[]})
        git(self.repo,'update-ref',MAIN,late,self.head)
        a['guards'][MAIN]=late
        self.denied(a)
    def test_existing_immutable_mail(self):
        late=commit(self.repo,self.head,'coordination/messages/MADS-STOP-'+self.req['id']+'.json',{})
        git(self.repo,'update-ref',IN,late,self.head)
        self.req['inbox_tip']=late
        self.denied()
    def test_wrong_lock(self): self.denied(dict(self.req,lock_blobs={'ledger.json':'0'*40}))
    def alter_status(self, **changes):
        status = dict(self.status(), **changes)
        updated = commit(self.repo, self.old, 'sessions/onboarding.json', status)
        for ref in (OLD, PTR):
            git(self.repo, 'update-ref', ref, updated, self.old)
        self.req['current_tip'] = updated

    def test_unknown_status_schema(self):
        self.alter_status(schema='unknown'); self.denied()

    def test_unapproved_scope(self):
        self.alter_status(allowed_paths=['other/**']); self.denied()

    def test_malformed_scope(self):
        self.alter_status(allowed_paths=['src/../other']); self.denied()

    def test_boolean_epoch(self):
        self.alter_status(lease_epoch=True); self.denied()

    def test_symbolic_guard(self):
        git(self.repo, 'symbolic-ref', MAIN, SRC); self.denied()

    def test_late_symbolic_guard_same_oid(self):
        original = broker.prepared_transaction
        def mutate(repo, lines, checks, updates):
            git(repo, 'symbolic-ref', MAIN, SRC)
            return original(repo, lines, checks, updates)
        with patch.object(broker, 'prepared_transaction', side_effect=mutate):
            self.denied()
        self.assertEqual(oid(self.repo, IN), self.head)
        self.assertEqual(oid(self.repo, OLD), self.old)

    def test_predecessor_lock_mismatch(self):
        self.alter_status(lock_blobs={'ledger.json': '0'*40})
        self.denied()

    def test_tree_guard_is_not_commit(self):
        # Deliberate raw fixture corruption, not a normal Git writer.
        (self.repo / GLOBAL).write_text(self.tree + '\n')
        self.req['guards'][GLOBAL] = self.tree
        self.denied()

    def test_cross_kind_request_id_reuse(self):
        a = self.ack()
        a['id'] = self.req['id']
        self.denied(a)

    def test_unapproved_monitoring_mode(self):
        self.alter_status(monitoring_mode='arbitrary')
        self.denied()

    def test_monitoring_policy_mismatch(self):
        self.alter_status(monitoring_mode='WATCHDOG_VERIFIED')
        self.denied()

    def test_unknown_request_field(self):
        self.denied(dict(self.req, unexpected=True))
        a = self.ack()
        self.denied(dict(a, unexpected=True))

    def test_canonical_ledger_path(self):
        self.policy['roles'][ROLE]['ledger_path'] = 'other.json'
        self.denied()

    def test_non_object_and_nonfinite_json(self):
        for raw in (b'[]', b'null', b'{"x":NaN}', b'{"x":1e999}', b'\xff'):
            with self.subTest(raw=raw), self.assertRaises(ValueError): parse(raw)

    def test_cli_structured_bad_json(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d)/'request.json'; p.write_bytes(b'[]')
            r = subprocess.run([sys.executable, str(Path(__file__).with_name('successor_broker.py')), '--repo', str(self.repo), '--request', str(p), '--policy', str(p), '--signature', str(p), '--allowed-signers', str(p)], capture_output=True)
            self.assertEqual(r.returncode, 1)
            self.assertEqual(json.loads(r.stdout)['state'], 'BLOCKED')
            self.assertNotIn(b'Traceback', r.stderr)

    def test_duplicate_json(self):
        with self.assertRaises(ValueError): parse(b'{"a":1,"a":2}')


if __name__=='__main__': unittest.main(verbosity=2)
