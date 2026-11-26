import io
import json
import stat
import subprocess
import tempfile
import unittest
import warnings
import zipfile
from pathlib import Path
from mads_verify import (anchored, git, release_anchor, sha, strict_json, verify_archive,
                         verify_evidence, verify_scope, verify_source)


def encode(obj):
    return json.dumps(obj, sort_keys=True).encode()


class VerifyTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.payload = {'STANDARD.md': b'standard', 'templates/required.md': b'required'}
        for rel, data in self.payload.items():
            p = self.root / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_bytes(data)
        self.anchor = dict(schema='mads.release-trust.v1', version='2.0.7', source_commit='1'*40,
                           archive_sha256='0'*64, draft=False,
                           files_sha256={k: sha(v) for k, v in self.payload.items()})

    def archive(self, payload=None, duplicate=False, symlink=False, extra=False):
        payload = self.payload if payload is None else payload
        files = dict(payload)
        files['RELEASE-MANIFEST.json'] = encode(dict(schema='mads.release-manifest.v1', version='2.0.7', draft=False, files_sha256={k: sha(v) for k,v in payload.items()}))
        files['SHA256SUMS.txt'] = ''.join(sha(v)+'  '+k+'\n' for k,v in files.items()).encode()
        b = io.BytesIO()
        with warnings.catch_warnings(), zipfile.ZipFile(b, 'w') as z:
            warnings.simplefilter('ignore', UserWarning)
            for rel, data in files.items():
                i = zipfile.ZipInfo('mads-standard-v2.0.7/'+rel)
                i.external_attr = ((stat.S_IFLNK if symlink and rel == 'STANDARD.md' else stat.S_IFREG) | 0o644) << 16
                z.writestr(i, data)
                if duplicate and rel == 'STANDARD.md':
                    z.writestr(i, data)
            if extra:
                z.writestr('mads-standard-v2.0.7/../outside', b'x')
        p = self.root / 'release.zip'
        p.write_bytes(b.getvalue())
        return p, dict(self.anchor, archive_sha256=sha(b.getvalue()))

    def test_valid_source_and_zip(self):
        p,a = self.archive()
        self.assertEqual(verify_archive(p, release_anchor(encode(a), sha(encode(a))))['archive'], 'PASS')
        self.assertEqual(verify_source(self.root,a)['files_checked'],2)

    def test_required_substitution(self):
        (self.root/'templates/required.md').unlink()
        (self.root/'templates/foreign.md').write_bytes(b'required')
        with self.assertRaises(ValueError): verify_source(self.root,self.anchor)

    def test_joint_tampering(self):
        pin = sha(encode(self.anchor))
        (self.root/'STANDARD.md').write_bytes(b'changed')
        a = dict(self.anchor, files_sha256=dict(self.anchor['files_sha256'], **{'STANDARD.md':sha(b'changed')}))
        with self.assertRaises(ValueError): release_anchor(encode(a),pin)
        with self.assertRaises(ValueError): verify_source(self.root,self.anchor)

    def test_json_types(self):
        for raw in (b'[]',b'null',b'1',b'"x"',b'true',b'{"x":NaN}',b'{"x":Infinity}',b'{"x":1,"x":2}',b'\xff'):
            with self.subTest(raw=raw), self.assertRaises(ValueError): strict_json(raw)

    def test_arbitrary_matching_bytes_not_zip(self):
        p=self.root/'release.zip';p.write_bytes(b'not zip')
        with self.assertRaises(zipfile.BadZipFile): verify_archive(p,dict(self.anchor,archive_sha256=sha(p.read_bytes())))

    def test_duplicate_zip(self):
        p,a=self.archive(duplicate=True)
        with self.assertRaisesRegex(ValueError,'DUPLICATE_ZIP_MEMBER'): verify_archive(p,a)

    def test_zip_symlink(self):
        p,a=self.archive(symlink=True)
        with self.assertRaisesRegex(ValueError,'UNSAFE_ZIP_MEMBER'): verify_archive(p,a)

    def test_zip_extra_traversal(self):
        p,a=self.archive(extra=True)
        with self.assertRaisesRegex(ValueError,'ZIP_FILE_SET_MISMATCH'): verify_archive(p,a)

    def test_zip_self_consistent_wrong_payload(self):
        p,a=self.archive(dict(self.payload, **{'STANDARD.md':b'forged'}))
        with self.assertRaisesRegex(ValueError,'INNER_MANIFEST_MISMATCH'): verify_archive(p,a)

    def test_draft_denied(self):
        p,a=self.archive()
        with self.assertRaisesRegex(ValueError,'DRAFT_NOT_ADOPTABLE'): verify_archive(p,dict(a,draft=True))

    def test_ancestor_symlink(self):
        (self.root/'templates/required.md').unlink();(self.root/'templates').rmdir()
        (self.root/'other').mkdir();(self.root/'other/required.md').write_bytes(b'required')
        (self.root/'templates').symlink_to(self.root/'other',target_is_directory=True)
        with self.assertRaisesRegex(ValueError,'SYMLINK_PATH'): verify_source(self.root,self.anchor)

    def test_path_aliases(self):
        for path in ('./STANDARD.md','templates//required.md','templates/../STANDARD.md','/STANDARD.md','templates\\required.md'):
            a=dict(self.anchor,files_sha256={path:'0'*64})
            with self.subTest(path=path),self.assertRaises(ValueError): release_anchor(encode(a),sha(encode(a)))

    def test_scope(self):
        self.assertEqual(verify_scope(['src/**'],['src/commerce/**'],['src/commerce/**'],['src/commerce/a.py'],['src/commerce/a.py'])['scope'],'PASS')
        for task,changed,deny in ((['src/**'],['src/a'],()),(['src/commerce/**'],['src/other/a'],()),(['src/commerce/**'],[],['src/commerce/private/**']),(['src/../a'],[],()),(['src/*'],[],()),(['src/commerce/**'],['src/commerceevil/a'],())):
            with self.subTest(task=task,changed=changed),self.assertRaises(ValueError): verify_scope(['src/**'],['src/commerce/**'],['src/commerce/**'],task,changed,deny)

    def test_evidence(self):
        subprocess.run(['git','init','-q',str(self.root)],check=True)
        git(self.root,'config','user.name','TEST');git(self.root,'config','user.email','test@example.invalid')
        git(self.root,'add','STANDARD.md');git(self.root,'commit','-qm','one')
        h=git(self.root,'rev-parse','HEAD').decode().strip();t=git(self.root,'rev-parse','HEAD^{tree}').decode().strip()
        (self.root/'raw.log').write_bytes(b'actual fixture')
        rec=dict(schema='mads.evidence-binding.v1',head=h,tree=t,locks_sha256={'STANDARD.md':sha(b'standard')},environment_sha256='1'*64,inputs_sha256='2'*64,argv=['test'],rc=0,artifacts_sha256={'raw.log':sha(b'actual fixture')})
        self.assertFalse(verify_evidence(self.root,self.root,rec,rec)['execution_proven'])
        for r in (dict(rec,head='HEAD-FE006-WIP'),dict(rec,tree='0'*40),dict(rec,rc=True),dict(rec,rc=1),dict(rec,locks_sha256={'STANDARD.md':'0'*64})):
            with self.subTest(r=r),self.assertRaises(ValueError): verify_evidence(self.root,self.root,r,r)
        with self.assertRaises(ValueError): verify_evidence(self.root,self.root,rec,dict(rec,head='1'*40))
        (self.root/'raw.log').write_bytes(b'tampered')
        with self.assertRaises(ValueError): verify_evidence(self.root,self.root,rec,rec)


if __name__ == '__main__':
    unittest.main(verbosity=2)
