#!/usr/bin/env python3
"""LINECOUNT gate for @whatifrpg Reel 7 (whatif7v).

Fetches js/sim.js from DerpfaceJr/daily-tower-web at a pinned commit, counts
the lines of each named function (declaration line through closing brace,
inclusive) and prints:

    LINECOUNT playerAct=N hurtPlayer=M

Exits non-zero if any count differs from the expected value in config, so the
number shown on screen can never drift from the code.

Usage:
    python3 live/linecount.py --config live/reels/whatif7v.json [--out docs/whatif7v-linecount.json]
    python3 live/linecount.py --expect playerAct=19 --expect hurtPlayer=10

Config shape (top level or under "linecount"):
    {"repo": "DerpfaceJr/daily-tower-web", "sha": "9cd6114...", "path": "js/sim.js",
     "functions": ["playerAct", "hurtPlayer"], "expect": {"playerAct": 19, "hurtPlayer": 10}}

Exit codes: 0 all match, 1 mismatch, 2 fetch/parse/config error.
Auth: DT_READ, GH_TOKEN or GITHUB_TOKEN env var if the repo is private.
Limitation: the brace scanner skips strings and comments but not regex
literals; LINECOUNT_SPANS prints the line range so a bad parse is visible.
"""
import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.request

DEFAULT = {
    "repo": "DerpfaceJr/daily-tower-web",
    "sha": "9cd61142978ce9ef60b64630a1cce865067a8f9c",
    "path": "js/sim.js",
    "functions": ["playerAct", "hurtPlayer"],
}


def fail(msg, code=2):
    print(f"LINECOUNT_ERROR {msg}")
    print("LINECOUNT_FAIL")
    sys.exit(code)


def fetch(repo, sha, path):
    tok = os.environ.get("DT_READ") or os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
    urls = [
        (f"https://api.github.com/repos/{repo}/contents/{path}?ref={sha}", True),
        (f"https://raw.githubusercontent.com/{repo}/{sha}/{path}", False),
    ]
    errs = []
    for url, api in urls:
        h = {"User-Agent": "cattown-reels-linecount"}
        if api:
            h["Accept"] = "application/vnd.github.raw"
        if tok:
            h["Authorization"] = f"Bearer {tok}"
        try:
            req = urllib.request.Request(url, headers=h)
            with urllib.request.urlopen(req, timeout=30) as r:
                return r.read().decode("utf-8"), url
        except (urllib.error.URLError, OSError) as e:
            errs.append(f"{url} -> {e}")
    fail("fetch failed: " + " | ".join(errs))


def decl_re(name):
    n = re.escape(name)
    return re.compile(
        r"^[ \t]*(?:export[ \t]+)?(?:async[ \t]+)?function[ \t]*\*?[ \t]*" + n + r"[ \t]*\("
        + r"|^[ \t]*(?:export[ \t]+)?(?:const|let|var)[ \t]+" + n
        + r"[ \t]*=[ \t]*(?:async[ \t]+)?(?:function\b|\(|[A-Za-z_$][\w$]*[ \t]*=>)"
        + r"|^[ \t]*" + n + r"[ \t]*\([^)\n]*\)[ \t]*\{",
        re.M,
    )


def skip_string(src, i):
    q = src[i]
    j = i + 1
    n = len(src)
    while j < n:
        c = src[j]
        if c == "\\":
            j += 2
            continue
        if c == q:
            return j + 1
        if c == "\n" and q != "`":
            return j
        j += 1
    fail("unterminated string")


def body_end(src, start):
    """Index of the '}' that closes the function body starting after start."""
    i, n = start, len(src)
    paren = 0
    depth = 0
    opened = False
    while i < n:
        c = src[i]
        nx = src[i + 1] if i + 1 < n else ""
        if c == "/" and nx == "/":
            j = src.find("\n", i)
            i = n if j < 0 else j
            continue
        if c == "/" and nx == "*":
            j = src.find("*/", i + 2)
            if j < 0:
                fail("unterminated block comment")
            i = j + 2
            continue
        if c in "'\"`":
            i = skip_string(src, i)
            continue
        if not opened:
            if c == "(":
                paren += 1
            elif c == ")":
                paren -= 1
            elif c == "{" and paren == 0:
                opened = True
                depth = 1
        else:
            if c == "{":
                depth += 1
            elif c == "}":
                depth -= 1
                if depth == 0:
                    return i
        i += 1
    fail("no closing brace found")


def count(src, name):
    ms = list(decl_re(name).finditer(src))
    if not ms:
        fail(f"{name} not found")
    if len(ms) > 1:
        lines = [src.count("\n", 0, m.start()) + 1 for m in ms]
        fail(f"{name} declared {len(ms)} times at lines {lines}")
    s = ms[0].start()
    e = body_end(src, s)
    a = src.count("\n", 0, s) + 1
    b = src.count("\n", 0, e) + 1
    return {"start": a, "end": b, "lines": b - a + 1}


def main():
    ap = argparse.ArgumentParser(description="LINECOUNT gate")
    ap.add_argument("--config")
    ap.add_argument("--expect", action="append", default=[], metavar="NAME=N")
    ap.add_argument("--out")
    a = ap.parse_args()

    cfg = dict(DEFAULT)
    expect = {}
    if a.config:
        try:
            with open(a.config, encoding="utf-8") as f:
                c = json.load(f)
        except (OSError, ValueError) as e:
            fail(f"config {a.config}: {e}")
        lc = c.get("linecount", c)
        for k in ("repo", "sha", "path", "functions"):
            if k in lc:
                cfg[k] = lc[k]
        for k, v in (lc.get("expect") or {}).items():
            expect[k] = int(v)
    for e in a.expect:
        k, sep, v = e.partition("=")
        if not sep:
            fail(f"bad --expect {e!r}, use NAME=N")
        expect[k.strip()] = int(v)
    missing = [f for f in cfg["functions"] if f not in expect]
    if missing:
        fail(f"no expected value for {missing}")

    src, url = fetch(cfg["repo"], cfg["sha"], cfg["path"])
    got = {f: count(src, f) for f in cfg["functions"]}
    print("LINECOUNT " + " ".join(f"{f}={got[f]['lines']}" for f in cfg["functions"]))
    print(f"LINECOUNT_SRC repo={cfg['repo']} sha={cfg['sha']} path={cfg['path']}")
    print("LINECOUNT_SPANS " + " ".join(f"{f}=L{got[f]['start']}-L{got[f]['end']}" for f in cfg["functions"]))
    bad = [f for f in cfg["functions"] if got[f]["lines"] != expect[f]]
    for f in bad:
        print(f"LINECOUNT_MISMATCH {f} expected={expect[f]} got={got[f]['lines']}")
    ok = not bad
    print("LINECOUNT_OK" if ok else "LINECOUNT_FAIL")
    if a.out:
        d = os.path.dirname(a.out)
        if d:
            os.makedirs(d, exist_ok=True)
        rec = {
            "ok": ok,
            "repo": cfg["repo"],
            "sha": cfg["sha"],
            "path": cfg["path"],
            "source_url": url,
            "counts": got,
            "expect": expect,
            "mismatch": bad,
        }
        with open(a.out, "w", encoding="utf-8") as fh:
            json.dump(rec, fh, indent=2)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
