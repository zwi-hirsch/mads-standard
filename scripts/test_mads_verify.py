import io
import json
import stat
import runpy
import shutil
import sys
import subprocess
import tempfile
import unittest
import warnings
import zipfile
from pathlib import Path
from mads_verify import (anchored, changed_paths, git, path_name, portable_paths, release_anchor, sha, strict_json, verify_archive,
                         verify_evidence, verify_projection, verify_scope, verify_source)


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
        for raw in (b'[]',b'null',b'1',b'"x"',b'true',b'{"x":NaN}',b'{"x":Infinity}',b'{"x":1e999}',b'{"x":1,"x":2}',b'\xff'):
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

    def test_projection(self):
        projection=dict(schema='mads.release-projection.v1',release_source_commit='1'*40,paths={'STANDARD.md':'STANDARD.md','templates/required.md':'templates/required.md'})
        self.assertEqual(verify_projection(self.root,self.anchor,projection)['files_checked'],2)
        with self.assertRaises(ValueError): verify_projection(self.root,self.anchor,dict(projection,release_source_commit='2'*40))
        with self.assertRaises(ValueError): verify_projection(self.root,self.anchor,dict(projection,paths={'foreign.md':'STANDARD.md'}))
        (self.root/'STANDARD.md').write_bytes(b'changed')
        with self.assertRaises(ValueError): verify_projection(self.root,self.anchor,projection)

    def test_real_git_changed_paths(self):
        subprocess.run(['git','init','-q',str(self.root)],check=True)
        git(self.root,'config','user.name','TEST');git(self.root,'config','user.email','test@example.invalid')
        git(self.root,'add','STANDARD.md');git(self.root,'commit','-qm','one')
        base=git(self.root,'rev-parse','HEAD').decode().strip()
        git(self.root,'mv','STANDARD.md','renamed.md');git(self.root,'commit','-qm','rename')
        head=git(self.root,'rev-parse','HEAD').decode().strip()
        self.assertEqual(set(changed_paths(self.root,base,head)),{'STANDARD.md','renamed.md'})
        (self.root/'link').symlink_to('renamed.md');git(self.root,'add','link');git(self.root,'commit','-qm','symlink')
        bad=git(self.root,'rev-parse','HEAD').decode().strip()
        with self.assertRaisesRegex(ValueError,'UNSAFE_GIT_FILE_MODE'): changed_paths(self.root,head,bad)

    def test_release_pipeline_fixture(self):
        # Real exporter and source checker, synthetic standard text and Git history.
        scripts = self.root / 'scripts'; scripts.mkdir()
        for path in Path(__file__).resolve().parent.glob('*.py'):
            shutil.copyfile(path, scripts/path.name)
        (self.root/'MADS-VERSION.yaml').write_text('version: "2.0.7"\nnormative_sections: 33\npublication_status: STAGED_NOT_PUBLISHED\n')
        exporter = runpy.run_path(str(scripts/'build_release.py'))
        for rel in set(exporter['REQUIRED']) | {'LICENSE'}:
            path = self.root/rel
            if not path.exists():
                path.parent.mkdir(parents=True,exist_ok=True); path.write_text('TEST ONLY\n')
        (self.root/exporter['CORE']).write_text(''.join(f'## {i}. Synthetic section\n' for i in range(1,34)))
        (self.root/'templates/mads/v2/NEW-PROJECT-BOOTSTRAP-PROMPT.ru.md').write_text('[НАЗВАНИЕ ПРОЕКТА] SESSION_START sha256\n')
        (self.root/'STANDARD.md').unlink(); (self.root/'templates/required.md').unlink()
        subprocess.run(['git','init','-q',str(self.root)],check=True)
        git(self.root,'config','user.name','TEST');git(self.root,'config','user.email','test@example.invalid')
        git(self.root,'add','.');git(self.root,'commit','-qm','synthetic release')
        def call(script,*args):
            return subprocess.run([sys.executable,str(scripts/script),*map(str,args)],capture_output=True)
        out=self.root/'dist'; build=call('build_release.py','--draft','--out',out)
        self.assertEqual(build.returncode,0,build.stderr)
        archive=next(out.glob('*.zip')); first=archive.read_bytes()
        self.assertEqual(call('build_release.py','--draft','--out',out).returncode,0)
        self.assertEqual(first,archive.read_bytes())
        trust=out/'candidate.trust.json'; good=call('check_release.py','--archive',archive,'--anchor-out',trust,'--draft')
        self.assertEqual(good.returncode,0,good.stdout+good.stderr)
        self.assertEqual(json.loads(good.stdout)['files_checked'],len(set(exporter['REQUIRED'])|{'LICENSE'}))
        self.assertNotEqual(call('build_release.py','--out',out).returncode,0)
        wrong=call('check_release.py','--archive',archive,'--anchor-out',trust)
        self.assertEqual(wrong.returncode,1);self.assertEqual(json.loads(wrong.stdout)['error'],'PUBLICATION_STATUS_MISMATCH')
        archive.write_bytes(b'not a zip')
        bad=call('check_release.py','--archive',archive,'--anchor-out',trust,'--draft')
        self.assertEqual(bad.returncode,1);self.assertEqual(json.loads(bad.stdout)['state'],'FAIL')
        archive.write_bytes(first)
        (self.root/'README.md').write_text('changed')
        dirty=call('check_release.py','--archive',archive,'--anchor-out',trust,'--draft')
        self.assertEqual(dirty.returncode,1);self.assertEqual(json.loads(dirty.stdout)['error'],'DIRTY_TRACKED_SOURCE')

    def test_reserved_metadata_case_aliases(self):
        for rel in ('release-manifest.json', 'sha256sums.TXT', 'RELEASE-MANIFEST.JSON'):
            payload = dict(self.payload, **{rel: b'alias'})
            p, a = self.archive(payload)
            a['files_sha256'] = {k: sha(v) for k, v in payload.items()}
            with self.subTest(rel=rel), self.assertRaisesRegex(ValueError, 'RESERVED_PATH'):
                verify_archive(p, release_anchor(encode(a), sha(encode(a))))

    def test_version_yaml_duplicates_and_unsupported_syntax(self):
        from build_release import version_fields
        valid = 'version: "2.0.7"\nnormative_sections: 33\npublication_status: STAGED_NOT_PUBLISHED\nintegrity:\n  release_tag: v2.0.7\n'
        self.assertEqual(version_fields(valid)['version'], '"2.0.7"')
        for suffix in ('version: "9.9.9"\n', 'normative_sections: 34\n',
                       'publication_status: RELEASED\n', '  release_tag: v9.9.9\n',
                       '"version": "9.9.9"\n', 'extra: &alias value\n', 'extra: {x: y}\n'):
            with self.subTest(suffix=suffix), self.assertRaises(ValueError):
                version_fields(valid + suffix)

    def test_gitlink_changes_under_hostile_diff_config(self):
        subprocess.run(['git', 'init', '-q', str(self.root)], check=True)
        git(self.root, 'config', 'user.name', 'TEST')
        git(self.root, 'config', 'user.email', 'test@example.invalid')
        git(self.root, 'add', 'STANDARD.md')
        git(self.root, 'commit', '-qm', 'base')
        base = git(self.root, 'rev-parse', 'HEAD').decode().strip()
        git(self.root, 'config', 'diff.ignoreSubmodules', 'all')
        git(self.root, 'update-index', '--add', '--cacheinfo', '160000,' + base + ',foreign-module')
        git(self.root, 'commit', '-qm', 'add gitlink')
        added = git(self.root, 'rev-parse', 'HEAD').decode().strip()
        git(self.root, 'update-index', '--cacheinfo', '160000,' + added + ',foreign-module')
        git(self.root, 'commit', '-qm', 'update gitlink')
        updated = git(self.root, 'rev-parse', 'HEAD').decode().strip()
        git(self.root, 'update-index', '--force-remove', 'foreign-module')
        git(self.root, 'commit', '-qm', 'delete gitlink')
        deleted = git(self.root, 'rev-parse', 'HEAD').decode().strip()
        for old, new in ((base, added), (added, updated), (updated, deleted)):
            with self.subTest(old=old, new=new), self.assertRaisesRegex(ValueError, 'UNSAFE_GIT_FILE_MODE'):
                changed_paths(self.root, old, new)

    def test_portable_device_names(self):
        for rel in ('src/CON', 'src/NUL.txt', 'src/AUX', 'src/COM1', 'src/LPT9',
                    'src/prn.tar.gz', 'src/con/file.txt', 'src/lpt1.any'):
            with self.subTest(rel=rel), self.assertRaisesRegex(ValueError, 'RESERVED_DEVICE_PATH'):
                path_name(rel)
        for rel in ('src/CONSOLE.txt', 'src/COM10', 'src/LPT0', 'src/Auxiliary/a.py', 'src/a.txt'):
            self.assertEqual(path_name(rel), rel)

    def test_portable_component_sets(self):
        for paths in (['src/a', 'src/A'], ['Src/x', 'src/y'],
                      ['src/a', 'src/a/b'], ['src/a', 'src/a']):
            with self.subTest(paths=paths), self.assertRaises(ValueError):
                portable_paths(paths)
        portable_paths(['src/a', 'src/b', 'src/sub/c'])

    def test_portable_git_cli(self):
        subprocess.run(['git', 'init', '-q', str(self.root)], check=True)
        git(self.root, 'config', 'user.name', 'TEST')
        git(self.root, 'config', 'user.email', 'test@example.invalid')
        git(self.root, 'config', 'core.ignorecase', 'false')
        blob = git(self.root, 'hash-object', '-w', 'STANDARD.md')
        blob = blob.decode().strip()
        git(self.root, 'update-index', '--add', '--cacheinfo', '100644,' + blob + ',src/a')
        git(self.root, 'commit', '-qm', 'base')
        base = git(self.root, 'rev-parse', 'HEAD').decode().strip()
        for rel in ('src/A', 'Src/x', 'src/CON', 'src/NUL.txt', 'src/AUX', 'src/COM1', 'src/LPT9', 'src/safe.txt'):
            with self.subTest(rel=rel):
                git(self.root, 'reset', '--mixed', base)
                git(self.root, 'update-index', '--add', '--cacheinfo', '100644,' + blob + ',' + rel)
                git(self.root, 'commit', '-qm', 'candidate')
                head = git(self.root, 'rev-parse', 'HEAD').decode().strip()
                cfg = dict(registry=['src/**'], lease=['src/**'], order=['src/**'],
                           task=['src/**'], forbidden=[], base=base, head=head)
                raw = encode(cfg)
                f = self.root / 'anchor.json'; f.write_bytes(raw)
                run = subprocess.run([sys.executable, str(Path(__file__).with_name('mads_verify.py')),
                                      'scope', '--repo', str(self.root), '--anchor', str(f),
                                      '--anchor-sha256', sha(raw)], capture_output=True)
                safe = rel == 'src/safe.txt'
                self.assertEqual(run.returncode, 0 if safe else 1, run.stdout + run.stderr)
                self.assertEqual(json.loads(run.stdout)['state'], 'PASS' if safe else 'FAIL')

    def test_case_only_transition_and_unchanged_alias(self):
        subprocess.run(['git', 'init', '-q', str(self.root)], check=True)
        git(self.root, 'config', 'user.name', 'TEST')
        git(self.root, 'config', 'user.email', 'test@example.invalid')
        git(self.root, 'config', 'core.ignorecase', 'false')
        git(self.root, 'add', 'STANDARD.md')
        git(self.root, 'commit', '-qm', 'base')
        base = git(self.root, 'rev-parse', 'HEAD').decode().strip()
        git(self.root, 'mv', 'STANDARD.md', 'standard.md')
        git(self.root, 'commit', '-qm', 'case rename')
        head = git(self.root, 'rev-parse', 'HEAD').decode().strip()
        with self.assertRaisesRegex(ValueError, 'CASE_ALIAS_PATH'):
            changed_paths(self.root, base, head)
        blob = git(self.root, 'hash-object', '-w', 'standard.md').decode().strip()
        git(self.root, 'update-index', '--add', '--cacheinfo', '100644,' + blob + ',STANDARD.md')
        git(self.root, 'commit', '-qm', 'ambiguous tree')
        bad = git(self.root, 'rev-parse', 'HEAD').decode().strip()
        with self.assertRaisesRegex(ValueError, 'CASE_ALIAS_PATH'):
            changed_paths(self.root, bad, bad)

    def test_portable_source_projection_archive(self):
        for payload in ({'Src/x': b'x', 'src/y': b'y'}, {'src/CON.txt': b'x'},
                        {'src/a': b'x', 'src/a/b': b'y'}):
            with self.subTest(payload=payload):
                p, a = self.archive(payload)
                a['files_sha256'] = {k: sha(v) for k, v in payload.items()}
                with self.assertRaises(ValueError):
                    verify_archive(p, a)
                with self.assertRaises(ValueError):
                    verify_source(self.root, a)
        projection = dict(schema='mads.release-projection.v1', release_source_commit='1'*40,
                          paths={'STANDARD.md': 'Src/x', 'templates/required.md': 'src/y'})
        with self.assertRaisesRegex(ValueError, 'CASE_ALIAS_PATH'):
            verify_projection(self.root, self.anchor, projection)
        (self.root/'standard.md').write_bytes(b'standard')
        with self.assertRaisesRegex(ValueError, 'MISSING_OR_ALIASED_PATH'):
            verify_source(self.root, self.anchor)

    def test_scope_case_alias_policy(self):
        with self.assertRaisesRegex(ValueError, 'CASE_ALIAS_PATH'):
            verify_scope(['src/**'], ['src/**'], ['src/**'], ['src/**'], ['src/a'], ['Src/**'])


    def test_next_dynamic_identifier_real_paths_and_scope(self):
        routes = [
            'apps/web/src/app/api/v1/customer-requests/[id]/route.ts',
            'apps/web/src/app/api/v1/price-inquiries/[id]/route.ts',
            'apps/web/src/app/api/v1/stones/[id]/route.ts',
        ]
        for route in routes:
            with self.subTest(route=route):
                self.assertEqual(path_name(route), route)
        self.assertEqual(verify_scope(
            ['apps/web/src/**'], ['apps/web/src/app/**'],
            ['apps/web/src/app/api/**'],
            ['apps/web/src/app/api/v1/stones/[id]/**'],
            ['apps/web/src/app/api/v1/stones/[id]/route.ts']
        )['scope'], 'PASS')

    def test_next_dynamic_identifier_is_not_a_general_bracket_escape(self):
        invalid = [
            'src/[..]/route.ts', 'src/[.]/route.ts', 'src/[...slug]/route.ts',
            'src/[[...slug]]/route.ts', 'src/[[id]]/route.ts',
            'src/[id].ts', 'src/[id?]/route.ts', 'src/[a-b]/route.ts',
            'src/[123]/route.ts', 'src/[id]/../secret',
            'src/[id]//route.ts', 'src/[id]/x[abc].ts',
            'src/[id]/**/route.ts', 'src/[id]/[...path]/route.ts',
            'src/[id]/./route.ts', 'src/[id]/.git/config',
            'src/CON/[id]/route.ts', 'src/[id]/NUL.txt',
            'src/[id]/foo.', 'src/[id]/COM1',
        ]
        for rel in invalid:
            with self.subTest(rel=rel), self.assertRaises(ValueError):
                path_name(rel)
        # Brackets are a literal portable directory name, not a Windows device alias.
        self.assertEqual(path_name('src/[CON]/route.ts'), 'src/[CON]/route.ts')

    def test_next_dynamic_identifier_alias_and_file_directory_denial(self):
        conflicts = [
            ['src/[id]/a.ts', 'src/[ID]/b.ts'],
            ['src/[id]/a.ts', 'Src/[id]/b.ts'],
            ['src/[id]/a.ts', 'src/[id]/a.ts'],
            ['src/[id]', 'src/[id]/route.ts'],
            ['src/[id]/route.ts', 'src/[id]/route.ts/x'],
        ]
        for paths in conflicts:
            with self.subTest(paths=paths), self.assertRaises(ValueError):
                portable_paths(paths)
        portable_paths(['src/[id]/route.ts', 'src/[stoneId]/route.ts'])

    def test_next_dynamic_identifier_full_git_trees_and_case_rename(self):
        subprocess.run(['git', 'init', '-q', str(self.root)], check=True)
        git(self.root, 'config', 'user.name', 'TEST')
        git(self.root, 'config', 'user.email', 'test@example.invalid')
        git(self.root, 'config', 'core.ignorecase', 'false')
        blob = git(self.root, 'hash-object', '-w', 'STANDARD.md').decode().strip()
        prefix = 'apps/web/src/app/api/v1/'
        initial = [
            prefix + 'customer-requests/[id]/route.ts',
            prefix + 'price-inquiries/[id]/route.ts',
            prefix + 'stones/[id]/route.ts',
        ]
        for rel in initial:
            git(self.root, 'update-index', '--add', '--cacheinfo', '100644,' + blob + ',' + rel)
        git(self.root, 'commit', '-qm', 'three legitimate dynamic routes')
        base = git(self.root, 'rev-parse', 'HEAD').decode().strip()
        adjacent = prefix + 'stones/[id]/extra.ts'
        git(self.root, 'update-index', '--add', '--cacheinfo', '100644,' + blob + ',' + adjacent)
        git(self.root, 'commit', '-qm', 'safe adjacent change')
        head = git(self.root, 'rev-parse', 'HEAD').decode().strip()
        self.assertEqual(changed_paths(self.root, base, head), [adjacent])
        self.assertEqual(verify_scope(
            ['apps/web/src/**'], ['apps/web/src/app/**'],
            ['apps/web/src/app/api/**'], ['apps/web/src/app/api/v1/stones/[id]/**'],
            [adjacent])['scope'], 'PASS')
        # An unchanged before/after tree with the old routes is still portable.
        self.assertEqual(changed_paths(self.root, base, base), [])
        alias = prefix + 'stones/[ID]/route.ts'
        git(self.root, 'update-index', '--add', '--cacheinfo', '100644,' + blob + ',' + alias)
        git(self.root, 'commit', '-qm', 'bad sibling casefold alias')
        bad = git(self.root, 'rev-parse', 'HEAD').decode().strip()
        with self.assertRaisesRegex(ValueError, 'CASE_ALIAS_PATH'):
            changed_paths(self.root, head, bad)
        with self.assertRaisesRegex(ValueError, 'CASE_ALIAS_PATH'):
            changed_paths(self.root, bad, bad)
        git(self.root, 'reset', '--mixed', head)
        git(self.root, 'update-index', '--force-remove', prefix + 'stones/[id]/route.ts')
        git(self.root, 'update-index', '--add', '--cacheinfo', '100644,' + blob + ',' + alias)
        git(self.root, 'commit', '-qm', 'case-only transition')
        renamed = git(self.root, 'rev-parse', 'HEAD').decode().strip()
        with self.assertRaisesRegex(ValueError, 'CASE_ALIAS_PATH'):
            changed_paths(self.root, head, renamed)

    def test_next_dynamic_identifier_source_archive_projection(self):
        route = 'apps/web/src/app/api/v1/stones/[id]/route.ts'
        p = self.root / route
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(b'synthetic route only')
        payload = {route: b'synthetic route only'}
        archive, anchor = self.archive(payload)
        anchor['files_sha256'] = {route: sha(payload[route])}
        self.assertEqual(verify_archive(archive, anchor)['archive'], 'PASS')
        self.assertEqual(verify_source(self.root, anchor)['files_checked'], 1)
        p.write_bytes(b'standard')
        projection = dict(schema='mads.release-projection.v1',
                          release_source_commit='1'*40,
                          paths={'STANDARD.md': route})
        self.assertEqual(verify_projection(self.root, self.anchor, projection)['files_checked'], 1)
        p.write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError, 'PROJECT_SOURCE_MISMATCH'):
            verify_projection(self.root, self.anchor, projection)

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
