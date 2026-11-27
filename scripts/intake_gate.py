#!/usr/bin/env python3
"""Frozen result-ledger reference gate; independent acquisition/approval is external."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import sys

OID = re.compile(r'[0-9a-f]{40}\Z')
STATES = ('HANDOFF_READY', 'IMPORTED_TO_PR', 'INDEPENDENT_QA_PASS', 'MERGED_TO_MAIN')


def need(ok, reason):
    if not ok:
        raise ValueError(reason)


def load(path, digest=None):
    raw = path.read_bytes()
    if digest is not None:
        need(hashlib.sha256(raw).hexdigest() == digest, 'UNTRUSTED_INPUT')
    def pairs(items):
        result = {}
        for key, value in items:
            need(key not in result, 'DUPLICATE_KEY')
            result[key] = value
        return result
    def reject(_):
        raise ValueError('NONFINITE_JSON')
    return json.loads(raw, object_pairs_hook=pairs, parse_constant=reject)


def index(rows, key):
    need(type(rows) is list, 'EXPECTED_LIST')
    out = {}
    for row in rows:
        value = row[key]
        need(type(value) is str and bool(value) and value not in out, 'DUPLICATE_OR_INVALID_ID')
        out[value] = row
    return out


def oid(value):
    return type(value) is str and OID.fullmatch(value) is not None


def verify(frozen, ledger, observed, close=False):
    need(frozen['schema'] == 'mads.intake.frozen.v1' and ledger['schema'] == 'mads.intake.ledger.v1' and observed['schema'] == 'mads.intake.observed.v1', 'SCHEMA')
    need(frozen['cycle'] == ledger['cycle'] == observed['cycle'], 'CYCLE_DRIFT')
    expected = index(frozen['results'], 'id')
    items = index(ledger['results'], 'id')
    proofs = index(observed['proofs'], 'id')
    need(set(items) == set(expected) == set(proofs), 'RESULT_COVERAGE')
    need(frozen['main'] == observed['start_main'] and oid(frozen['main']), 'START_MAIN_DRIFT')
    counts = {s: 0 for s in STATES}
    pending = []
    replacements = {}
    for key, source in expected.items():
        item, proof = items[key], proofs[key]
        pin = source['source']
        need(oid(pin['commit']) and oid(pin['blob']) and type(pin['path']) is str and bool(pin['path']), 'SOURCE_PIN:'+key)
        need(item['source'] == pin == proof['source'], 'SOURCE_DRIFT:'+key)
        need(type(source['origin']) is str and bool(source['origin']), 'ORIGIN:'+key)
        need(type(item['owner']) is str and bool(item['owner']) and type(item['next_action']) is str and bool(item['next_action']), 'UNASSIGNED:'+key)
        kind = source['kind']
        need(kind in ('PRODUCT','EVIDENCE'), 'UNKNOWN_KIND:'+key)
        disposition = item.get('disposition')
        if disposition in ('REJECTED','SUPERSEDED','EVIDENCE_ATTACHED'):
            need(disposition == proof.get('disposition'), 'DISPOSITION_DRIFT:'+key)
            decision = item['decision']
            need(decision == proof.get('decision') and oid(decision['commit']) and oid(decision['blob']) and type(decision['reason']) is str and bool(decision['reason']) and decision['owner'] == item['owner'], 'UNVERIFIED_DECISION:'+key)
            if disposition == 'EVIDENCE_ATTACHED':
                need(kind == 'EVIDENCE', 'PRODUCT_CANNOT_BE_EVIDENCE:'+key)
            if disposition != 'REJECTED':
                replacement = item['replacement']
                need(replacement in expected and replacement != key and replacement == proof.get('replacement'), 'INVALID_REPLACEMENT:'+key)
                replacements[key] = replacement
            continue
        need(disposition is None and proof.get('disposition') is None and kind == 'PRODUCT', 'INVALID_DISPOSITION:'+key)
        state = item['state']
        need(state in STATES, 'STATE:'+key)
        counts[state] += 1
        if state == STATES[0]:
            pending.append(key)
            continue
        target = item['target']
        need(target == proof.get('target') and type(target['pr']) is int and target['pr'] > 0 and oid(target['head']) and oid(target['tree']) and oid(target['blob']) and target['blob'] == pin['blob'], 'TARGET_READBACK:'+key)
        if state in STATES[2:]:
            qa = item['qa']
            need(qa == proof.get('qa') and qa['head'] == target['head'] and qa['tree'] == target['tree'] and qa['verdict'] == 'PASS' and qa['reviewer'] not in (source['origin'], item['owner']) and bool(qa['reviewer']) and oid(qa['receipt']), 'QA_READBACK:'+key)
        if state == STATES[3]:
            merge = item['merge']
            need(merge == proof.get('merge') and merge['pr'] == target['pr'] and merge['head'] == target['head'] and oid(merge['commit']) and merge['main'] == observed['end_main'] and oid(merge['main']) and merge['ancestor_verified'] is True and merge['blob'] == pin['blob'], 'MERGE_READBACK:'+key)
        else:
            pending.append(key)
    for key in replacements:
        seen = {key}; end = replacements[key]
        while end in replacements:
            need(end not in seen, 'REPLACEMENT_CYCLE')
            seen.add(end); end = replacements[end]
        need(expected[end]['kind'] == 'PRODUCT', 'REPLACEMENT_NOT_PRODUCT')
    if close:
        need(not pending, 'INTAKE_PENDING')
        need(observed['history_coverage'] == 'INDEPENDENTLY_RECONCILED' and observed['ref_coverage'] == 'INDEPENDENTLY_RECONCILED', 'HISTORY_OR_REF_GAP')
    return {'status':'CLOSED' if close else 'COVERAGE_OK', 'results':len(expected), 'states':counts, 'pending':pending, 'independent_input_required':True}


def main():
    p = argparse.ArgumentParser()
    for arg in ('frozen','ledger','observed'):
        p.add_argument('--'+arg,type=Path,required=True)
    p.add_argument('--expected-frozen-sha256',required=True)
    p.add_argument('--expected-observed-sha256',required=True)
    p.add_argument('--close',action='store_true')
    a=p.parse_args()
    try:
        result=verify(load(a.frozen,a.expected_frozen_sha256),load(a.ledger),load(a.observed,a.expected_observed_sha256),a.close)
    except (ValueError,KeyError,TypeError,OSError,AttributeError) as exc:
        print(json.dumps({'status':'BLOCKED','reason':str(exc)})); return 2
    print(json.dumps(result,sort_keys=True)); return 0


if __name__=='__main__': sys.exit(main())
