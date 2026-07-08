"""Identity-proof tool for BATCH refactor-safety-split (P-A / P-B / P-C).

Usage:
    python tests/refactor_identity.py before   # writes baseline artifacts
    python tests/refactor_identity.py after    # writes AFTER artifacts + diffs

Artifacts go to .local/artifacts/refactor-safety-split/ in the repo root.

P-A  Route table dump of the safety router (sorted, deterministic).
P-B  Full-app OpenAPI schema (flag on), json sort_keys=True.
P-C  Per-function body sha256 of the OLD monolith (BEFORE) vs. the union of
     the new package modules (AFTER); plus module-level constant values.
"""
import ast
import hashlib
import json
import os
import sys

os.environ["ENABLE_SAFETY_MODULE"] = "true"
os.environ["APP_MODE"] = "dev"
os.environ["MONGO_URL"] = "mongodb://localhost:27017"
os.environ["DB_NAME"] = "contractor_ops"

BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ROOT = os.path.dirname(BACKEND)
OUT = os.path.join(ROOT, ".local", "artifacts", "refactor-safety-split")
os.makedirs(OUT, exist_ok=True)
sys.path.insert(0, BACKEND)

MODE = sys.argv[1] if len(sys.argv) > 1 else "before"
assert MODE in ("before", "after"), "arg must be before|after"

CONSTANTS = [
    "SAFETY_WRITERS", "SAFETY_DELETERS", "REQUIRED_TRAINING_TYPES",
    "DEFAULT_TOUR_CHECKLIST", "_TOUR_SIGN_SLOTS", "DEFAULT_EQUIPMENT_CHECKS",
]


def route_table():
    from contractor_ops.safety_router import router
    rows = []
    for r in router.routes:
        methods = sorted(getattr(r, "methods", []) or [])
        rm = getattr(r, "response_model", None)
        deps = [d.dependency.__name__ for d in getattr(r, "dependencies", [])]
        rows.append((str(methods), r.path, r.endpoint.__name__,
                     getattr(rm, "__name__", str(rm)), str(deps)))
    rows.sort(key=lambda t: (t[1], t[0]))
    return "\n".join(" | ".join(t) for t in rows) + "\n"


def openapi_dump():
    import server
    return json.dumps(server.app.openapi(), sort_keys=True, ensure_ascii=False)


def _norm_hash(src_lines):
    body = "\n".join(l.rstrip() for l in src_lines)
    return hashlib.sha256(body.encode()).hexdigest()


def file_func_hashes(path):
    with open(path, encoding="utf-8") as f:
        src = f.read()
    lines = src.splitlines()
    tree = ast.parse(src)
    out = {}
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            # skip decorators: hash from `def` line to end (decorators contain
            # router paths which are also identity-checked via P-A/P-B)
            seg = lines[node.lineno - 1:node.end_lineno]
            out.setdefault(node.name, []).append(_norm_hash(seg))
    return out


def const_values(module_paths):
    vals = {}
    for path in module_paths:
        with open(path, encoding="utf-8") as f:
            src = f.read()
        tree = ast.parse(src)
        for node in tree.body:
            targets = []
            if isinstance(node, ast.Assign):
                targets = node.targets
            elif isinstance(node, ast.AnnAssign) and node.value is not None:
                targets = [node.target]
            for t in targets:
                if isinstance(t, ast.Name) and t.id in CONSTANTS:
                    seg = ast.get_source_segment(src, node.value)
                    vals[t.id] = hashlib.sha256(
                        "\n".join(l.rstrip() for l in seg.splitlines()).encode()
                    ).hexdigest()
    return vals


MONOLITH = os.path.join(BACKEND, "contractor_ops", "safety_router.py")
PKG_DIR = os.path.join(BACKEND, "contractor_ops", "safety")

if MODE == "before":
    files = [MONOLITH]
else:
    files = sorted(
        os.path.join(PKG_DIR, f) for f in os.listdir(PKG_DIR) if f.endswith(".py")
    ) + [MONOLITH]  # facade included: should contribute no function bodies

# P-C
merged = {}
for fp in files:
    for name, hashes in file_func_hashes(fp).items():
        merged.setdefault(name, []).extend(hashes)
with open(os.path.join(OUT, f"funcs_{MODE}.json"), "w") as f:
    json.dump({k: sorted(v) for k, v in sorted(merged.items())}, f, indent=1)
consts = const_values(files)
with open(os.path.join(OUT, f"consts_{MODE}.json"), "w") as f:
    json.dump(consts, f, indent=1, sort_keys=True)

# P-A + P-B (import the app — must be after files exist)
with open(os.path.join(OUT, f"routes_{MODE}.txt"), "w") as f:
    f.write(route_table())
with open(os.path.join(OUT, f"openapi_{MODE}.json"), "w") as f:
    f.write(openapi_dump())

n_funcs = sum(len(v) for v in merged.values())
print(f"[{MODE}] functions hashed: {n_funcs} (unique names: {len(merged)})")
print(f"[{MODE}] constants hashed: {sorted(consts.keys())}")
print(f"[{MODE}] artifacts in {OUT}")

if MODE == "after":
    import subprocess
    fails = []
    for pair in ("routes", "openapi"):
        a = os.path.join(OUT, f"{pair}_before.{'txt' if pair=='routes' else 'json'}")
        b = os.path.join(OUT, f"{pair}_after.{'txt' if pair=='routes' else 'json'}")
        r = subprocess.run(["diff", "-q", a, b], capture_output=True)
        status = "IDENTICAL" if r.returncode == 0 else "DIFFERS"
        print(f"P-{'A' if pair=='routes' else 'B'} {pair}: {status}")
        if r.returncode != 0:
            fails.append(pair)
    with open(os.path.join(OUT, "funcs_before.json")) as f:
        before = json.load(f)
    moved = missing = changed = extra = 0
    for name, hashes in before.items():
        after_h = merged.get(name, [])
        for h in hashes:
            if h in after_h:
                moved += 1
            else:
                if name in merged:
                    changed += 1
                    print(f"P-C CHANGED: {name}")
                else:
                    missing += 1
                    print(f"P-C MISSING: {name}")
    for name, hashes in merged.items():
        base = before.get(name, [])
        for h in hashes:
            if h not in base:
                extra += 1
                print(f"P-C NEW/ALTERED body present after: {name}")
    with open(os.path.join(OUT, "consts_before.json")) as f:
        cb = json.load(f)
    const_ok = cb == consts
    print(f"P-C functions: total={n_funcs} moved-identical={moved} changed={changed} missing={missing} extra={extra}")
    print(f"P-C constants identical: {const_ok} ({len(consts)}/{len(cb)})")
    ok = not fails and changed == 0 and missing == 0 and extra == 0 and const_ok
    print("IDENTITY:", "PASS" if ok else "FAIL")
    sys.exit(0 if ok else 1)
