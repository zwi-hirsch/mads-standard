#!/usr/bin/env python3
"""Deterministic, sanitized MADS v2.0 release ZIP from its OWN public-standard tree.

Usage:
  python3 scripts/build_release.py --draft --out ./dist
  python3 scripts/build_release.py --out ./dist   # requires LICENSE
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import sys
import zipfile

ROOT = Path(__file__).resolve().parent.parent
def project_version():
    text=(ROOT/"MADS-VERSION.yaml").read_text(encoding="utf-8")
    match=re.search(r'^version:\s*"([0-9]+\.[0-9]+\.[0-9]+)"\s*
CORE = "MULTI-AGENT-DEVELOPMENT-SYSTEM.md"
REQUIRED = [
    "README.md", "SECURITY.md", "PUBLISHING.md", "MADS-VERSION.yaml", CORE,
    "templates/mads/v2/README.md",
    "templates/mads/v2/MADS-VERSION-LOCK.example.yaml",
    "templates/mads/v2/PROJECT-MANIFEST.example.yaml",
    "templates/mads/v2/SOURCE-SESSION-START.example.md",
    "templates/mads/v2/SOURCE-HANDOFF.example.yaml",
    "templates/mads/v2/READ-ONLY-ONBOARDING.example.md",
    "templates/mads/v2/INTEGRATION-HANDOFF.example.md",
    "templates/mads/v2/ROLE-REPORT.example.md",
    "templates/mads/v2/PILOT-ACCEPTANCE.example.md",
    "templates/mads/v2/NEW-PROJECT-BOOTSTRAP-PROMPT.ru.md",
    "scripts/build_release.py",
]
FORBIDDEN = [
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    re.compile(r"(?:github_pat_|ghp_)[A-Za-z0-9_]{20,}"),
    re.compile(r"(?:sk-proj-|sk_live_)[A-Za-z0-9_-]{20,}"),
    re.compile(r"(?i)-----BEGIN (?:RSA|EC|OPENSSH|DSA) PRIVATE KEY-----"),
]
ROOT_PREFIX = "mads-standard-v" + VERSION + "/"

def digest(content):
    return hashlib.sha256(content).hexdigest()

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--out", default="./dist")
    p.add_argument("--draft", action="store_true", help="allow missing public LICENSE; never publish this as a licensed release")
    args = p.parse_args()
    missing = [rel for rel in REQUIRED if not (ROOT / rel).is_file()]
    if missing:
        raise SystemExit("MISSING_RELEASE_FILES: " + ", ".join(missing))
    files = sorted(x for x in ROOT.rglob("*") if x.is_file() and not any(
        part in {".git", ".github", "__pycache__", "dist", ".env", ".secrets"} for part in x.relative_to(ROOT).parts))
    unknown = [x.relative_to(ROOT).as_posix() for x in files if
               x.relative_to(ROOT).as_posix() not in set(REQUIRED + ["LICENSE"])]
    if unknown:
        raise SystemExit("UNREVIEWED_RELEASE_FILES: " + ", ".join(unknown))
    if not (ROOT / "LICENSE").is_file() and not args.draft:
        raise SystemExit("LICENSE_REQUIRED: select and add an explicit public reuse license before release")
    if not args.draft and not (ROOT / "LICENSE").read_text(encoding="utf-8").startswith("Apache License\nVersion 2.0, January 2004"):
        raise SystemExit("INVALID_RELEASE_LICENSE: expected approved official Apache 2.0 text")
    if not args.draft and "STAGED_NOT_PUBLISHED" in (ROOT/"MADS-VERSION.yaml").read_text(encoding="utf-8"):
        raise SystemExit("VERSION_NOT_FINAL: update MADS-VERSION.yaml status before public release")
    manifest = {}
    for item in files:
        rel = item.relative_to(ROOT).as_posix()
        if item.stat().st_size > 4_000_000:
            raise SystemExit(f"OVERSIZED_FILE: {rel}")
        data = item.read_bytes()
        try:
            txt = data.decode("utf-8")
        except UnicodeDecodeError:
            raise SystemExit(f"UNEXPECTED_BINARY_FILE: {rel}")
        for pat in FORBIDDEN:
            if pat.search(txt):
                raise SystemExit(f"POTENTIAL_SECRET_OR_PRIVATE_IDENTIFIER: {rel} / {pat.pattern}")
        if rel.startswith(("memory/", "evidence/", "coord/", ".git/", "production/")):
            raise SystemExit(f"FORBIDDEN_PROJECT_DIRECTORY: {rel}")
        manifest[rel] = digest(data)
    doc = (ROOT / CORE).read_text(encoding="utf-8")
    headings = [int(m.group(1)) for m in re.finditer(r"^## (\d+)\.", doc, re.M)]
    if headings != list(range(1, 27)):
        raise SystemExit("INVALID_STANDARD_SECTIONS: expected Sections 1 through 26")
    payload = {rel: (ROOT / rel).read_bytes() for rel in manifest}
    release_manifest = json.dumps({
        "schema": "mads.release-manifest.v1",
        "version": VERSION,
        "draft": args.draft,
        "files_sha256": manifest,
    }, ensure_ascii=False, sort_keys=True, indent=2).encode("utf-8") + b"\n"
    payload["RELEASE-MANIFEST.json"] = release_manifest
    payload["SHA256SUMS.txt"] = "".join(
        f"{digest(payload[rel])}  {rel}\n" for rel in sorted(payload) if rel != "SHA256SUMS.txt"
    ).encode("utf-8")
    out = Path(args.out).resolve()
    out.mkdir(parents=True, exist_ok=True)
    zip_path = out / f"mads-standard-v{VERSION}{'-draft' if args.draft else ''}.zip"
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for rel in sorted(payload):
            info = zipfile.ZipInfo(ROOT_PREFIX + rel, date_time=(2026, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            z.writestr(info, payload[rel], compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)
    actual = digest(zip_path.read_bytes())
    (out / (zip_path.name + ".sha256")).write_text(f"{actual}  {zip_path.name}\n", encoding="utf-8")
    with zipfile.ZipFile(zip_path) as z:
        assert z.testzip() is None
        extracted = z.read(ROOT_PREFIX + CORE)
        assert digest(extracted) == manifest[CORE]
    print(json.dumps({"state": "PASS_DRAFT" if args.draft else "PASS_RELEASE",
        "zip": str(zip_path), "sha256": actual, "file_count": len(payload),
        "verified_source": manifest[CORE], "draft": args.draft}, indent=2))

if __name__ == "__main__":
    main()
,text,re.M)
    if not match:
        raise SystemExit("INVALID_VERSION: require MADS-VERSION.yaml version semver")
    return match.group(1)

VERSION = project_version()
CORE = "MULTI-AGENT-DEVELOPMENT-SYSTEM.md"
REQUIRED = [
    "README.md", "SECURITY.md", "PUBLISHING.md", "MADS-VERSION.yaml", CORE,
    "templates/mads/v2/README.md",
    "templates/mads/v2/MADS-VERSION-LOCK.example.yaml",
    "templates/mads/v2/PROJECT-MANIFEST.example.yaml",
    "templates/mads/v2/SOURCE-SESSION-START.example.md",
    "templates/mads/v2/SOURCE-HANDOFF.example.yaml",
    "templates/mads/v2/READ-ONLY-ONBOARDING.example.md",
    "templates/mads/v2/INTEGRATION-HANDOFF.example.md",
    "templates/mads/v2/ROLE-REPORT.example.md",
    "templates/mads/v2/PILOT-ACCEPTANCE.example.md",
    "templates/mads/v2/NEW-PROJECT-BOOTSTRAP-PROMPT.ru.md",
    "scripts/build_release.py",
]
FORBIDDEN = [
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    re.compile(r"(?:github_pat_|ghp_)[A-Za-z0-9_]{20,}"),
    re.compile(r"(?:sk-proj-|sk_live_)[A-Za-z0-9_-]{20,}"),
    re.compile(r"(?i)-----BEGIN (?:RSA|EC|OPENSSH|DSA) PRIVATE KEY-----"),
]
ROOT_PREFIX = "mads-standard-v" + VERSION + "/"

def digest(content):
    return hashlib.sha256(content).hexdigest()

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--out", default="./dist")
    p.add_argument("--draft", action="store_true", help="allow missing public LICENSE; never publish this as a licensed release")
    args = p.parse_args()
    missing = [rel for rel in REQUIRED if not (ROOT / rel).is_file()]
    if missing:
        raise SystemExit("MISSING_RELEASE_FILES: " + ", ".join(missing))
    files = sorted(x for x in ROOT.rglob("*") if x.is_file() and not any(
        part in {".git", ".github", "__pycache__", "dist", ".env", ".secrets"} for part in x.relative_to(ROOT).parts))
    unknown = [x.relative_to(ROOT).as_posix() for x in files if
               x.relative_to(ROOT).as_posix() not in set(REQUIRED + ["LICENSE"])]
    if unknown:
        raise SystemExit("UNREVIEWED_RELEASE_FILES: " + ", ".join(unknown))
    if not (ROOT / "LICENSE").is_file() and not args.draft:
        raise SystemExit("LICENSE_REQUIRED: select and add an explicit public reuse license before release")
    if not args.draft and not (ROOT / "LICENSE").read_text(encoding="utf-8").startswith("Apache License\nVersion 2.0, January 2004"):
        raise SystemExit("INVALID_RELEASE_LICENSE: expected approved official Apache 2.0 text")
    if not args.draft and "STAGED_NOT_PUBLISHED" in (ROOT/"MADS-VERSION.yaml").read_text(encoding="utf-8"):
        raise SystemExit("VERSION_NOT_FINAL: update MADS-VERSION.yaml status before public release")
    manifest = {}
    for item in files:
        rel = item.relative_to(ROOT).as_posix()
        if item.stat().st_size > 4_000_000:
            raise SystemExit(f"OVERSIZED_FILE: {rel}")
        data = item.read_bytes()
        try:
            txt = data.decode("utf-8")
        except UnicodeDecodeError:
            raise SystemExit(f"UNEXPECTED_BINARY_FILE: {rel}")
        for pat in FORBIDDEN:
            if pat.search(txt):
                raise SystemExit(f"POTENTIAL_SECRET_OR_PRIVATE_IDENTIFIER: {rel} / {pat.pattern}")
        if rel.startswith(("memory/", "evidence/", "coord/", ".git/", "production/")):
            raise SystemExit(f"FORBIDDEN_PROJECT_DIRECTORY: {rel}")
        manifest[rel] = digest(data)
    doc = (ROOT / CORE).read_text(encoding="utf-8")
    headings = [int(m.group(1)) for m in re.finditer(r"^## (\d+)\.", doc, re.M)]
    if headings != list(range(1, 27)):
        raise SystemExit("INVALID_STANDARD_SECTIONS: expected Sections 1 through 26")
    payload = {rel: (ROOT / rel).read_bytes() for rel in manifest}
    release_manifest = json.dumps({
        "schema": "mads.release-manifest.v1",
        "version": VERSION,
        "draft": args.draft,
        "files_sha256": manifest,
    }, ensure_ascii=False, sort_keys=True, indent=2).encode("utf-8") + b"\n"
    payload["RELEASE-MANIFEST.json"] = release_manifest
    payload["SHA256SUMS.txt"] = "".join(
        f"{digest(payload[rel])}  {rel}\n" for rel in sorted(payload) if rel != "SHA256SUMS.txt"
    ).encode("utf-8")
    out = Path(args.out).resolve()
    out.mkdir(parents=True, exist_ok=True)
    zip_path = out / f"mads-standard-v{VERSION}{'-draft' if args.draft else ''}.zip"
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for rel in sorted(payload):
            info = zipfile.ZipInfo(ROOT_PREFIX + rel, date_time=(2026, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            z.writestr(info, payload[rel], compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)
    actual = digest(zip_path.read_bytes())
    (out / (zip_path.name + ".sha256")).write_text(f"{actual}  {zip_path.name}\n", encoding="utf-8")
    with zipfile.ZipFile(zip_path) as z:
        assert z.testzip() is None
        extracted = z.read(ROOT_PREFIX + CORE)
        assert digest(extracted) == manifest[CORE]
    print(json.dumps({"state": "PASS_DRAFT" if args.draft else "PASS_RELEASE",
        "zip": str(zip_path), "sha256": actual, "file_count": len(payload),
        "verified_source": manifest[CORE], "draft": args.draft}, indent=2))

if __name__ == "__main__":
    main()
