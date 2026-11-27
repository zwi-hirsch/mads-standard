import copy
import unittest
from intake_gate import verify

class Intake(unittest.TestCase):
    def setUp(self):
        self.pin={'commit':'a'*40,'blob':'b'*40,'path':'src/a.py'}
        self.frozen={'schema':'mads.intake.frozen.v1','cycle':'one','main':'c'*40,'results':[{'id':'one','kind':'PRODUCT','origin':'dev','source':self.pin}]}
        self.item={'id':'one','source':copy.deepcopy(self.pin),'owner':'owner','next_action':'import','state':'HANDOFF_READY'}
        self.ledger={'schema':'mads.intake.ledger.v1','cycle':'one','results':[self.item]}
        self.proof={'id':'one','source':copy.deepcopy(self.pin)}
        self.observed={'schema':'mads.intake.observed.v1','cycle':'one','start_main':'c'*40,'end_main':'d'*40,'proofs':[self.proof],'history_coverage':'INDEPENDENTLY_RECONCILED','ref_coverage':'INDEPENDENTLY_RECONCILED'}
    def check(self,close=False): return verify(self.frozen,self.ledger,self.observed,close)
    def imported(self):
        self.item.update(state='IMPORTED_TO_PR',target={'pr':1,'head':'e'*40,'tree':'f'*40,'blob':'b'*40}); self.proof['target']=copy.deepcopy(self.item['target'])
    def qa(self):
        self.imported(); self.item.update(state='INDEPENDENT_QA_PASS',qa={'head':'e'*40,'tree':'f'*40,'verdict':'PASS','reviewer':'qa','receipt':'a'*40}); self.proof['qa']=copy.deepcopy(self.item['qa'])
    def merged(self):
        self.qa(); self.item.update(state='MERGED_TO_MAIN',merge={'pr':1,'head':'e'*40,'commit':'a'*40,'main':'d'*40,'ancestor_verified':True,'blob':'b'*40}); self.proof['merge']=copy.deepcopy(self.item['merge'])
    def test_pending_blocks(self):
        self.assertEqual(self.check()['pending'],['one'])
        with self.assertRaises(ValueError): self.check(True)
    def test_missing(self):
        self.ledger['results']=[]
        with self.assertRaises(ValueError): self.check()
    def test_forged_target(self):
        self.imported(); self.item['target']['blob']='9'*40
        with self.assertRaises(ValueError): self.check()
    def test_stale_qa(self):
        self.qa(); self.item['qa']['head']='9'*40
        with self.assertRaises(ValueError): self.check()
    def test_self_qa(self):
        self.qa(); self.item['qa']['reviewer']='dev'; self.proof['qa']=copy.deepcopy(self.item['qa'])
        with self.assertRaises(ValueError): self.check()
    def test_merged(self):
        self.merged(); self.assertEqual(self.check(True)['status'],'CLOSED')
    def test_false_ancestry(self):
        self.merged(); self.item['merge']['ancestor_verified']=False; self.proof['merge']=copy.deepcopy(self.item['merge'])
        with self.assertRaises(ValueError): self.check(True)
    def test_missing_history(self):
        self.merged(); self.observed['history_coverage']='UNKNOWN'
        with self.assertRaises(ValueError): self.check(True)
    def test_rejected_unverified(self):
        self.item.update(disposition='REJECTED',decision={'commit':'a'*40,'blob':'b'*40,'owner':'owner','reason':'duplicate'})
        with self.assertRaises(ValueError): self.check(True)
    def test_explicit_rejection(self):
        self.item.update(disposition='REJECTED',decision={'commit':'a'*40,'blob':'b'*40,'owner':'owner','reason':'obsolete'}); self.proof['decision']=copy.deepcopy(self.item['decision']); self.proof['disposition']='REJECTED'; self.assertEqual(self.check(True)['status'],'CLOSED')

    def test_disposition_drift(self):
        self.item.update(disposition='REJECTED',decision={'commit':'a'*40,'blob':'b'*40,'owner':'owner','reason':'obsolete'}); self.proof['decision']=copy.deepcopy(self.item['decision']); self.proof['disposition']='SUPERSEDED'
        with self.assertRaises(ValueError): self.check(True)

if __name__=='__main__': unittest.main()
