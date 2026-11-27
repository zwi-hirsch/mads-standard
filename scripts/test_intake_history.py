import base64
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from intake_history import inventory

class History(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name); self.repo=self.root/'repo'; self.repo.mkdir()
        self.git('init','-q'); self.git('config','user.name','Fixture'); self.git('config','user.email','fixture@example.invalid')
        self.path=self.repo/'a.py'; self.path.write_text('first\n'); self.git('add','.'); self.git('commit','-qm','first'); self.first=self.git('rev-parse','HEAD')
        self.path.write_text('second\n'); self.git('add','.'); self.git('commit','-qm','second'); self.second=self.git('rev-parse','HEAD')
        self.path.unlink(); self.git('add','-A'); self.git('commit','-qm','delete'); self.head=self.git('rev-parse','HEAD')
        self.snap={'schema':'mads.history-roots.v1','roots':[{'label':'branch','oid':self.head}]}; self.out=self.root/'inventory.jsonl'
    def git(self,*args):
        return subprocess.check_output(['git','-C',str(self.repo),*args],text=True,stderr=subprocess.PIPE).strip()
    def test_deleted_and_replaced(self):
        r=inventory(self.repo,self.snap,self.out); self.assertEqual((r['deleted'],r['replaced']),(1,1)); self.assertEqual(r['commits'],3)
        rows=[json.loads(l) for l in self.out.read_text().splitlines()]; d=[x for x in rows if x['kind']=='delta']; self.assertEqual({x['status'] for x in d},{'A','M','D'}); self.assertTrue(all(base64.b64decode(x['path_b64'])==b'a.py' for x in d))
    def test_missing_root(self):
        self.snap['roots'].append({'label':'old-pr','oid':'f'*40}); r=inventory(self.repo,self.snap,self.out); self.assertEqual(r['status'],'BLOCKED_MISSING_ROOTS'); self.assertFalse(self.out.exists())
    def test_duplicate_label(self):
        self.snap['roots']*=2
        with self.assertRaises(ValueError): inventory(self.repo,self.snap,self.out)
    def test_unreachable_commit(self):
        self.git('checkout','-qb','orphan',self.first); (self.repo/'lost.py').write_text('lost\n'); self.git('add','.'); self.git('commit','-qm','lost'); lost=self.git('rev-parse','HEAD'); self.git('checkout','--detach',self.head); self.git('branch','-D','orphan'); r=inventory(self.repo,self.snap,self.out); self.assertGreaterEqual(r['locally_unreachable_commits'],1); self.assertIn(lost,self.out.read_text())
    def test_existing_output(self):
        self.out.write_text('preserve')
        with self.assertRaises(ValueError): inventory(self.repo,self.snap,self.out)
        self.assertEqual(self.out.read_text(),'preserve')

if __name__=='__main__': unittest.main()
