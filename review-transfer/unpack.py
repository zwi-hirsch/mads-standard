#!/usr/bin/env python3
"""Offline review carrier, not a release, Git bundle or trust root."""
import argparse, base64, hashlib, json, pathlib, re
HEAD = "b8bf9abaa10f8ff98dddb4815e77046c481cfaf2"
TREE = "d82368dfc9a43e26ab4241c386a5e1065a903ee6"
def decode(encoded):
    raw = base64.b64decode(encoded, validate=True)
    out = bytearray()
    i = 0
    while i < len(raw):
        tag = raw[i]; i += 1
        if tag < 128:
            n = tag + 1
            if i+n > len(raw): raise ValueError("short literal")
            out.extend(raw[i:i+n]); i += n
        else:
            n = tag-128+3
            if i+2 > len(raw): raise ValueError("short backref")
            d = raw[i]*256+raw[i+1]; i += 2
            if not 0 < d <= len(out): raise ValueError("invalid backref")
            for _ in range(n): out.append(out[-d])
        if len(out) > 2000000: raise ValueError("expansion bound")
    return json.loads(out)
def main():
    p=argparse.ArgumentParser()
    p.add_argument("--chunks",type=pathlib.Path,required=True)
    p.add_argument("--out",type=pathlib.Path,required=True)
    p.add_argument("--baseline-only",action="store_true")
    a=p.parse_args()
    if a.out.exists(): raise ValueError("output must not exist")
    expected=json.loads((a.chunks/"inventory.json").read_text())
    if expected["head"]!=HEAD or expected["tree"]!=TREE: raise ValueError("pin mismatch")
    want={r["path"]:r["blob"] for r in expected["files"] if not a.baseline_only or r["path"].startswith("scripts/") or r["path"]=="MADS-VERSION.yaml"}
    got={}
    groups=["01"] if a.baseline_only else ["01","02","03"]
    for group in groups:
        paths=sorted(a.chunks.glob("pack-"+group+"-*.b64"))
        if not paths: raise ValueError("missing pack "+group)
        obj=decode("".join(x.read_text().strip() for x in paths))
        if obj["head"]!=HEAD or obj["tree"]!=TREE: raise ValueError("pack pin")
        for f in obj["files"]:
            rel=f["path"]
            if rel in got or rel not in want or not re.fullmatch(r"[A-Za-z0-9_.+@/-]+",rel) or any(x in ("",".","..",".git") for x in rel.split("/")): raise ValueError("path")
            b=f["text"].encode("utf-8")
            oid=hashlib.sha1(("blob "+str(len(b))+"\0").encode()+b).hexdigest()
            if f["mode"]!="100644" or oid!=f["blob"] or oid!=want[rel]: raise ValueError("blob mismatch "+rel)
            got[rel]=b
    if set(got)!=set(want): raise ValueError("incomplete inventory")
    a.out.mkdir()
    for rel,b in got.items():
        dest=a.out/rel; dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(b)
    print(json.dumps({"state":"SOURCE_BLOB_PARITY","upstream_head":HEAD,"upstream_tree":TREE,"files":len(got),"actual_git_commit_restored":False,"independent_trust_approved":False},sort_keys=True))
if __name__=="__main__": main()
