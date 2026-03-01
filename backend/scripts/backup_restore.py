#!/usr/bin/env python3
import os
import sys
import json
import shutil
from datetime import datetime
from pymongo import MongoClient

DB_NAME = os.environ.get("DB_NAME", "brikops_prod")
MONGO_PORT = int(os.environ.get("MONGO_PORT", "27017"))
BACKUP_DIR = os.environ.get("BACKUP_DIR", "/home/runner/workspace/.data/backups")
UPLOADS_DIR = "/home/runner/workspace/backend/uploads"


def get_db():
    client = MongoClient(f"mongodb://127.0.0.1:{MONGO_PORT}")
    return client[DB_NAME]


def do_backup():
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = os.path.join(BACKUP_DIR, f"{DB_NAME}_{ts}")
    os.makedirs(backup_path, exist_ok=True)

    db = get_db()
    collections = db.list_collection_names()
    print(f"[BACKUP] Starting backup of {DB_NAME} ({len(collections)} collections)")

    manifest = {"db_name": DB_NAME, "timestamp": ts, "collections": {}}
    for coll_name in sorted(collections):
        docs = list(db[coll_name].find({}))
        for d in docs:
            d["_id"] = str(d["_id"])
        coll_path = os.path.join(backup_path, f"{coll_name}.json")
        with open(coll_path, "w") as f:
            json.dump(docs, f, default=str)
        manifest["collections"][coll_name] = len(docs)
        print(f"  {coll_name}: {len(docs)} documents")

    if os.path.isdir(UPLOADS_DIR):
        uploads_snap = os.path.join(backup_path, "uploads_snapshot")
        shutil.copytree(UPLOADS_DIR, uploads_snap)
        file_count = sum(1 for _, _, files in os.walk(uploads_snap) for _ in files)
        manifest["uploads_files"] = file_count
        print(f"  uploads: {file_count} files")

    with open(os.path.join(backup_path, "manifest.json"), "w") as f:
        json.dump(manifest, f, indent=2)

    print(f"[BACKUP] Complete: {backup_path}")
    return backup_path


def do_restore(backup_name, confirm=False):
    backup_path = os.path.join(BACKUP_DIR, backup_name)
    if not os.path.isdir(backup_path):
        print(f"[RESTORE] Error: Backup not found at {backup_path}")
        sys.exit(1)

    manifest_path = os.path.join(backup_path, "manifest.json")
    if os.path.exists(manifest_path):
        with open(manifest_path) as f:
            manifest = json.load(f)
    else:
        manifest = {}

    json_files = [f for f in os.listdir(backup_path) if f.endswith(".json") and f != "manifest.json"]

    if not confirm:
        print(f"[RESTORE] DRY RUN - Would restore from: {backup_path}")
        print(f"[RESTORE] Collections to restore:")
        for jf in sorted(json_files):
            coll_name = jf.replace(".json", "")
            count = manifest.get("collections", {}).get(coll_name, "?")
            print(f"  - {coll_name} ({count} documents)")
        uploads_snap = os.path.join(backup_path, "uploads_snapshot")
        if os.path.isdir(uploads_snap):
            file_count = sum(1 for _, _, files in os.walk(uploads_snap) for _ in files)
            print(f"  - uploads: {file_count} files")
        print(f"\n[RESTORE] To execute: python {sys.argv[0]} restore {backup_name} --confirm")
        return True

    db = get_db()
    print(f"[RESTORE] LIVE RESTORE from: {backup_path}")
    for jf in sorted(json_files):
        coll_name = jf.replace(".json", "")
        with open(os.path.join(backup_path, jf)) as f:
            docs = json.load(f)
        from bson import ObjectId
        for d in docs:
            try:
                d["_id"] = ObjectId(d["_id"])
            except Exception:
                pass
        db[coll_name].drop()
        if docs:
            db[coll_name].insert_many(docs)
        print(f"  {coll_name}: {len(docs)} documents restored")

    uploads_snap = os.path.join(backup_path, "uploads_snapshot")
    if os.path.isdir(uploads_snap):
        shutil.copytree(uploads_snap, UPLOADS_DIR, dirs_exist_ok=True)
        print(f"[RESTORE] Uploads restored")

    print("[RESTORE] Complete")


def do_list():
    print(f"[LIST] Available backups in {BACKUP_DIR}:")
    if not os.path.isdir(BACKUP_DIR):
        print("  (no backups)")
        return
    for entry in sorted(os.listdir(BACKUP_DIR)):
        full = os.path.join(BACKUP_DIR, entry)
        if os.path.isdir(full) and entry.startswith(DB_NAME):
            manifest_path = os.path.join(full, "manifest.json")
            if os.path.exists(manifest_path):
                with open(manifest_path) as f:
                    m = json.load(f)
                colls = len(m.get("collections", {}))
                total_docs = sum(m.get("collections", {}).values())
                print(f"  {entry} ({colls} collections, {total_docs} documents)")
            else:
                print(f"  {entry}")


def do_verify(backup_name):
    backup_path = os.path.join(BACKUP_DIR, backup_name)
    if not os.path.isdir(backup_path):
        print(f"[VERIFY] Error: Backup not found")
        sys.exit(1)

    print(f"[VERIFY] Checking backup: {backup_name}")
    all_ok = True
    json_files = [f for f in os.listdir(backup_path) if f.endswith(".json") and f != "manifest.json"]
    for jf in sorted(json_files):
        path = os.path.join(backup_path, jf)
        size = os.path.getsize(path)
        try:
            with open(path) as f:
                docs = json.load(f)
            print(f"  {jf}: {len(docs)} docs, {size} bytes [OK]")
        except Exception as e:
            print(f"  {jf}: CORRUPT ({e}) [FAIL]")
            all_ok = False

    uploads_snap = os.path.join(backup_path, "uploads_snapshot")
    if os.path.isdir(uploads_snap):
        file_count = sum(1 for _, _, files in os.walk(uploads_snap) for _ in files)
        print(f"  uploads_snapshot: {file_count} files [OK]")

    verdict = "PASS" if all_ok else "FAIL"
    print(f"[VERIFY] Integrity: {verdict}")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    if cmd == "backup":
        do_backup()
    elif cmd == "restore":
        name = sys.argv[2] if len(sys.argv) > 2 else ""
        confirm = "--confirm" in sys.argv
        do_restore(name, confirm)
    elif cmd == "list":
        do_list()
    elif cmd == "verify":
        name = sys.argv[2] if len(sys.argv) > 2 else ""
        do_verify(name)
    else:
        print(f"Usage: python {sys.argv[0]} {{backup|restore|list|verify}} [backup_name] [--confirm]")
        sys.exit(1)
