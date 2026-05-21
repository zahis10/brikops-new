#!/usr/bin/env python3
"""
BATCH cleanup-orphan-qc-items — Remove stale QC checklist items.

When a QC template stage's item list is edited DOWN, existing qc_runs
keep qc_items for the removed items. `_backfill_missing_items` ADDS
missing items but never PRUNES removed ones. Result: floor view shows
inconsistent denominators (e.g. apartment 3 = 9 items, apartments 4-7
= 1, on the same stage).

Standalone migration. Does NOT touch app code. Run from Replit
terminal — MONGO_URL + DB_NAME from env.

USAGE:
    python scripts/cleanup_orphan_qc_items.py                              # --report (default, dry run)
    python scripts/cleanup_orphan_qc_items.py --project <id>               # scope to one project
    python scripts/cleanup_orphan_qc_items.py --show-template              # print current resolved template per project
    python scripts/cleanup_orphan_qc_items.py --delete                     # destructive
    python scripts/cleanup_orphan_qc_items.py --delete --include-completed # also remove pass/fail orphans

SAFETY:
    --delete dumps a JSON backup of every doc to be removed BEFORE
    deleting (scripts/orphan_qc_items_backup_<ts>.json).
    Default --delete SKIPS orphans with status pass/fail (completed
    work). --include-completed overrides this.
"""
import os
import sys
import json
import argparse
from datetime import datetime, timezone
from collections import defaultdict
from pymongo import MongoClient


# ─────────────────────────────────────────────────────────────────────
# Template resolution — MIRRORS backend.contractor_ops.qc_router._get_template
# (L298). Kept in sync MANUALLY because importing qc_router pulls in
# heavy app deps (motor, FastAPI deps, settings). If `_get_template`
# changes its fallback order, update this function to match.
#
# Resolution chain (per project):
#   1. project.qc_template_version_id → qc_templates.find_one({id: vid})
#   2. qc_templates.find_one({is_default: true, is_active: true})
#   3. None (skip project — cannot resolve)
#
# NOTE: the live function also has a FLOOR_TEMPLATE hardcoded fallback,
# but FLOOR_TEMPLATE only matters if NEITHER (1) NOR (2) yields a doc.
# For orphan detection we DELIBERATELY skip a project rather than
# guess against the hardcoded constant — if a project has no resolvable
# template, we cannot safely declare anything an orphan.
# ─────────────────────────────────────────────────────────────────────
def resolve_current_template(db, project_id):
    proj = db.projects.find_one({"id": project_id}, {"_id": 0, "qc_template_version_id": 1, "name": 1})
    proj_name = (proj or {}).get("name", "")
    vid = (proj or {}).get("qc_template_version_id")
    if vid:
        doc = db.qc_templates.find_one({"id": vid}, {"_id": 0})
        if doc:
            return doc, proj_name, "project_pinned"
    default = db.qc_templates.find_one({"is_default": True, "is_active": True}, {"_id": 0})
    if default:
        return default, proj_name, "default_active"
    return None, proj_name, "unresolved"


def build_valid_pairs(tpl):
    """Return set of (stage_id, item_id) pairs valid in this template."""
    pairs = set()
    for stage in tpl.get("stages", []) or []:
        sid = stage.get("id")
        if not sid:
            continue
        for item in stage.get("items", []) or []:
            iid = item.get("id")
            if iid:
                pairs.add((sid, iid))
    return pairs


def build_stage_titles(tpl):
    return {s.get("id"): s.get("title", "") for s in tpl.get("stages", []) or []}


def build_item_titles(tpl):
    titles = {}
    for stage in tpl.get("stages", []) or []:
        sid = stage.get("id")
        for item in stage.get("items", []) or []:
            titles[(sid, item.get("id"))] = item.get("title", "")
    return titles


def scan_orphans(db, project_filter=None):
    """Yield (orphan_doc, ctx) tuples. ctx = {project_id, project_name,
    building_id, building_name, floor_id, floor_name, unit_id, unit_name,
    run_id, stage_id, stage_title, item_id, item_title_in_old_run, status}."""
    project_query = {"id": project_filter} if project_filter else {}
    projects = list(db.projects.find(project_query, {"_id": 0, "id": 1, "name": 1}))
    print(f"Scanning {len(projects)} project(s)...", file=sys.stderr)

    for proj in projects:
        pid = proj["id"]
        tpl, pname, source = resolve_current_template(db, pid)
        if not tpl:
            print(f"  ⚠️  project {pid} ({proj.get('name', '')}) — no resolvable template, SKIPPING", file=sys.stderr)
            continue
        valid_pairs = build_valid_pairs(tpl)
        valid_stages = {s for s, _ in valid_pairs}
        stage_titles = build_stage_titles(tpl)

        runs = list(db.qc_runs.find({"project_id": pid}, {"_id": 0}))
        if not runs:
            continue
        run_ids = [r["id"] for r in runs]
        runs_by_id = {r["id"]: r for r in runs}

        # Resolve building/floor/unit names in one shot per project.
        building_ids = list({r.get("building_id") for r in runs if r.get("building_id")})
        floor_ids = list({r.get("floor_id") for r in runs if r.get("floor_id")})
        unit_ids = list({r.get("unit_id") for r in runs if r.get("unit_id")})
        buildings = {b["id"]: b for b in db.buildings.find({"id": {"$in": building_ids}}, {"_id": 0, "id": 1, "name": 1})}
        floors = {f["id"]: f for f in db.floors.find({"id": {"$in": floor_ids}}, {"_id": 0, "id": 1, "name": 1})}
        units = {u["id"]: u for u in db.units.find({"id": {"$in": unit_ids}}, {"_id": 0, "id": 1, "name": 1, "unit_no": 1})}

        items_cursor = db.qc_items.find({"run_id": {"$in": run_ids}})
        for it in items_cursor:
            sid = it.get("stage_id")
            iid = it.get("item_id")
            if (sid, iid) in valid_pairs:
                continue  # valid
            # Orphan: either stage not in template, or item not in stage.
            run = runs_by_id.get(it["run_id"])
            if not run:
                continue
            u = units.get(run.get("unit_id"), {})
            unit_name = u.get("name") or u.get("unit_no") or ""
            ctx = {
                "project_id": pid,
                "project_name": pname,
                "building_id": run.get("building_id"),
                "building_name": (buildings.get(run.get("building_id"), {}) or {}).get("name", ""),
                "floor_id": run.get("floor_id"),
                "floor_name": (floors.get(run.get("floor_id"), {}) or {}).get("name", ""),
                "unit_id": run.get("unit_id"),
                "unit_name": unit_name,
                "run_id": it["run_id"],
                "stage_id": sid,
                "stage_title": stage_titles.get(sid, "(stage removed)"),
                "item_id": iid,
                "status": it.get("status", "pending"),
                "reason": "stage_removed" if sid not in valid_stages else "item_removed",
            }
            yield it, ctx


def print_report(orphans_with_ctx, scope_label, mode):
    print()
    print("=" * 68)
    print("=== ORPHAN QC ITEMS REPORT ===")
    print(f"Scan date: {datetime.now(timezone.utc).isoformat()}")
    print(f"Scope: {scope_label}")
    print()

    total = len(orphans_with_ctx)
    pending = sum(1 for _, c in orphans_with_ctx if c["status"] == "pending")
    completed = sum(1 for _, c in orphans_with_ctx if c["status"] in ("pass", "fail"))
    other = total - pending - completed

    print("SUMMARY:")
    print(f"  - Total orphan qc_items: {total}")
    print(f"  - Pending (safe to delete): {pending}")
    print(f"  - Completed (pass/fail) — DATA LOSS RISK: {completed}")
    if other:
        print(f"  - Other status: {other}")
    print()

    if completed > 0:
        print(f"  ⚠️  {completed} orphans have completed work. Default --delete SKIPS these.")
        print(f"      Pass --include-completed to delete them (DISCARDS recorded contractor work).")
        print()

    if total == 0:
        print("  ✅ No orphans found. Nothing to do.")
        print()
        return

    print("BREAKDOWN:")
    grouped = defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: defaultdict(list)))))
    for it, c in orphans_with_ctx:
        grouped[(c["project_id"], c["project_name"])][c["building_name"] or "(no building)"][c["floor_name"] or "(no floor)"][c["unit_name"] or "(no unit)"][(c["run_id"], c["stage_id"], c["stage_title"])].append((c, it))

    for (pid, pname), buildings in sorted(grouped.items()):
        print(f"Project {pid} ({pname})")
        for bname, floors in sorted(buildings.items()):
            print(f'  Building "{bname}"')
            for fname, units in sorted(floors.items()):
                print(f'    Floor "{fname}"')
                for uname, runs in sorted(units.items()):
                    print(f'      Unit "{uname}"')
                    for (run_id, stage_id, stage_title), items in sorted(runs.items()):
                        print(f"        run {run_id}, stage {stage_id} ({stage_title or '(removed stage)'})")
                        for c, it in items:
                            tag = "(work done)" if c["status"] in ("pass", "fail") else ""
                            print(f"          - {c['item_id']} [{c['status']}] [{c['reason']}] → ORPHAN {tag}".rstrip())
    print()
    print("ACTION:")
    print("  --report only — no destructive action (current run).")
    print("  --delete                    → removes pending orphans.")
    print("  --delete --include-completed → removes ALL orphans.")
    print()
    if mode == "report":
        print("DRY RUN — no changes. Re-run with --delete to apply.")
        print()


def dump_backup(orphans_with_ctx, ts):
    backup_path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                               f"orphan_qc_items_backup_{ts}.json")
    payload = []
    for it, c in orphans_with_ctx:
        doc = dict(it)
        if "_id" in doc:
            doc["_id"] = str(doc["_id"])
        payload.append({"context": c, "qc_item": doc})
    with open(backup_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2, default=str)
    return backup_path


def main():
    parser = argparse.ArgumentParser(description="Cleanup orphan qc_items")
    parser.add_argument("--project", help="Scope to one project id (default: all projects)")
    grp = parser.add_mutually_exclusive_group()
    grp.add_argument("--report", action="store_true", help="Dry run (default)")
    grp.add_argument("--delete", action="store_true", help="Actually delete orphans")
    grp.add_argument("--show-template", action="store_true",
                     help="Print the current resolved template per project (read-only, no scan)")
    parser.add_argument("--include-completed", action="store_true",
                        help="Also delete orphans with status pass/fail (DATA LOSS)")
    args = parser.parse_args()

    if args.delete:
        mode = "delete"
    elif args.show_template:
        mode = "show_template"
    else:
        mode = "report"

    mongo_url = os.environ.get("MONGO_URL") or os.environ.get("MONGODB_URI")
    if not mongo_url:
        print("ERROR: MONGO_URL or MONGODB_URI env var required.", file=sys.stderr)
        sys.exit(2)
    db_name = os.environ.get("DB_NAME", "contractor_ops")

    client = MongoClient(mongo_url, serverSelectionTimeoutMS=10000)
    db = client[db_name]

    scope_label = args.project if args.project else "ALL projects"
    print(f"Database: {db_name}", file=sys.stderr)
    print(f"Scope: {scope_label}", file=sys.stderr)

    if mode == "show_template":
        project_query = {"id": args.project} if args.project else {}
        projects = list(db.projects.find(project_query, {"_id": 0, "id": 1, "name": 1}))
        print()
        for proj in projects:
            pid = proj["id"]
            tpl, pname, source = resolve_current_template(db, pid)
            print("=" * 68)
            print(f"=== CURRENT TEMPLATE — project {pid} ({pname}) ===")
            if not tpl:
                print(f"  ⚠️  no resolvable template (source={source}) — SKIPPED by --delete")
                print()
                continue
            print(f"Template id: {tpl.get('id', '')}  source: {source}  "
                  f"family: {tpl.get('family_id', '')}  version: {tpl.get('version', '')}")
            stages = tpl.get("stages", []) or []
            if not stages:
                print("  (no stages in template)")
            for stage in stages:
                sid = stage.get("id", "")
                stitle = stage.get("title", "")
                items = stage.get("items", []) or []
                print(f'Stage {sid} ({stitle}):')
                if not items:
                    print("  (no items)")
                for item in items:
                    iid = item.get("id", "")
                    ititle = item.get("title", "")
                    print(f'  - {iid} "{ititle}"')
            print()
        print("READ-ONLY — no scan, no changes.")
        sys.exit(0)

    orphans_with_ctx = list(scan_orphans(db, project_filter=args.project))
    print_report(orphans_with_ctx, scope_label, mode)

    if mode == "report":
        sys.exit(0)

    # DELETE phase
    to_delete = []
    skipped_completed = []
    for it, c in orphans_with_ctx:
        if c["status"] in ("pass", "fail") and not args.include_completed:
            skipped_completed.append((it, c))
        else:
            to_delete.append((it, c))

    if not to_delete:
        print("Nothing to delete (all orphans skipped or report empty).")
        if skipped_completed:
            print(f"  SKIPPED (work done) — {len(skipped_completed)} items; "
                  f"pass --include-completed to remove.")
        sys.exit(0)

    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup_path = dump_backup(to_delete, ts)
    print(f"Backup written: {backup_path}")

    ids = [it["_id"] for it, _ in to_delete]
    try:
        # Delete in batches of 500.
        deleted = 0
        for i in range(0, len(ids), 500):
            batch = ids[i:i + 500]
            res = db.qc_items.delete_many({"_id": {"$in": batch}})
            deleted += res.deleted_count
        print(f"Deleted {deleted} orphan qc_items.")
        if skipped_completed:
            print(f"SKIPPED (work done) — {len(skipped_completed)} items; "
                  f"pass --include-completed to remove.")
        print(f"\nSUMMARY: deleted={deleted}, skipped_completed={len(skipped_completed)}, backup={backup_path}")
    except Exception as e:
        print(f"ERROR during delete: {e}", file=sys.stderr)
        print(f"Backup still available at: {backup_path}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
