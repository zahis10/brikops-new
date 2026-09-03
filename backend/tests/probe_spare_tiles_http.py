"""Live HTTP + local Mongo probe for BATCH #585 spare-tile profiles.

This intentionally targets the already-running development server. It does not
use ASGITransport and never prints minted bearer tokens.
"""

import os
import sys
import uuid
from datetime import datetime, timedelta, timezone

import requests
from pymongo import MongoClient


os.environ["MONGO_URL"] = "mongodb://127.0.0.1:27017"
os.environ["DB_NAME"] = "contractor_ops"
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from contractor_ops.router import _create_token  # noqa: E402


BASE_URL = "http://127.0.0.1:5000"
RESULTS = []


def check(name, condition, detail=""):
    if not condition:
        raise AssertionError(f"{name}: {detail}")
    RESULTS.append(name)
    print(f"[PASS] {name}" + (f" — {detail}" if detail else ""))


def call(method, path, headers, expected, **kwargs):
    response = requests.request(
        method,
        f"{BASE_URL}{path}",
        headers=headers,
        timeout=15,
        **kwargs,
    )
    check(
        f"{method} {path} -> {expected}",
        response.status_code == expected,
        f"status={response.status_code}",
    )
    return response


def main():
    client = MongoClient(os.environ["MONGO_URL"], serverSelectionTimeoutMS=3000)
    db = client[os.environ["DB_NAME"]]
    tag = uuid.uuid4().hex[:10]
    org_id = f"probe-spare-org-{tag}"
    project_id = f"probe-spare-project-{tag}"
    other_project_id = f"probe-spare-other-project-{tag}"
    pm_id = f"probe-spare-pm-{tag}"
    owner_id = f"probe-spare-owner-{tag}"
    viewer_id = f"probe-spare-viewer-{tag}"
    building_id = f"probe-spare-building-main-{tag}"
    other_building_id = f"probe-spare-building-first-{tag}"
    floor_low_id = f"probe-spare-floor-low-{tag}"
    floor_high_id = f"probe-spare-floor-high-{tag}"
    unit_one_id = f"probe-spare-unit-1-{tag}"
    unit_two_id = f"probe-spare-unit-2-{tag}"
    unit_three_id = f"probe-spare-unit-3-{tag}"
    cross_unit_id = f"probe-spare-cross-unit-{tag}"
    profile_a = str(uuid.uuid4())
    profile_b = str(uuid.uuid4())

    user_ids = [pm_id, owner_id, viewer_id]
    project_ids = [project_id, other_project_id]
    building_ids = [building_id, other_building_id]
    floor_ids = [floor_low_id, floor_high_id]
    unit_ids = [unit_one_id, unit_two_id, unit_three_id, cross_unit_id]

    try:
        client.admin.command("ping")
        health = requests.get(f"{BASE_URL}/api/health", timeout=10)
        check("live server reachable without ASGITransport", health.status_code < 500,
              f"status={health.status_code}")

        now = datetime.now(timezone.utc)
        db.organizations.insert_one({
            "id": org_id,
            "name": f"Spare Probe {tag}",
            "owner_user_id": owner_id,
        })
        db.subscriptions.insert_one({
            "id": f"probe-spare-sub-{tag}",
            "org_id": org_id,
            "status": "active",
            "paid_until": (now + timedelta(days=30)).isoformat(),
        })
        db.projects.insert_many([
            {
                "id": project_id,
                "name": f"Spare Probe Project {tag}",
                "code": tag,
                "org_id": org_id,
                "status": "active",
                "archived": False,
            },
            {
                "id": other_project_id,
                "name": f"Spare Probe Other {tag}",
                "org_id": org_id,
                "status": "active",
                "archived": False,
            },
        ])
        db.users.insert_many([
            {
                "id": pm_id,
                "role": "project_manager",
                "full_name": "מנהל בדיקת ספייר",
                "user_status": "active",
                "session_version": 0,
            },
            {
                "id": owner_id,
                "role": "owner",
                "full_name": "בעלים בדיקת ספייר",
                "user_status": "active",
                "session_version": 0,
            },
            {
                "id": viewer_id,
                "role": "viewer",
                "full_name": "צופה בדיקת ספייר",
                "user_status": "active",
                "session_version": 0,
            },
        ])
        db.organization_memberships.insert_many([
            {"id": f"probe-om-pm-{tag}", "org_id": org_id, "user_id": pm_id, "role": "member"},
            {"id": f"probe-om-owner-{tag}", "org_id": org_id, "user_id": owner_id, "role": "owner"},
            {"id": f"probe-om-view-{tag}", "org_id": org_id, "user_id": viewer_id, "role": "member"},
        ])
        db.project_memberships.insert_many([
            {"id": f"probe-pm-pm-{tag}", "project_id": project_id, "user_id": pm_id,
             "role": "project_manager"},
            {"id": f"probe-pm-owner-{tag}", "project_id": project_id, "user_id": owner_id,
             "role": "owner"},
            {"id": f"probe-pm-view-{tag}", "project_id": project_id, "user_id": viewer_id,
             "role": "viewer"},
        ])
        # Insert deliberately out of display order.
        db.buildings.insert_many([
            {"id": building_id, "project_id": project_id, "name": "בניין 20",
             "sort_index": 20, "archived": False},
            {"id": other_building_id, "project_id": project_id, "name": "בניין 2",
             "sort_index": 10, "archived": False},
        ])
        db.floors.insert_many([
            {"id": floor_high_id, "project_id": project_id, "building_id": building_id,
             "name": "קומה 8", "floor_number": 8, "sort_index": 8000, "archived": False},
            {"id": floor_low_id, "project_id": project_id, "building_id": building_id,
             "name": "קומה 1", "floor_number": 1, "sort_index": 1000, "archived": False},
        ])
        db.units.insert_many([
            {
                "id": unit_two_id, "project_id": project_id, "building_id": building_id,
                "floor_id": floor_low_id, "unit_no": "102", "display_label": "דירה 102",
                "sort_index": 20, "status": "available", "archived": False,
            },
            {
                "id": unit_one_id, "project_id": project_id, "building_id": building_id,
                "floor_id": floor_low_id, "unit_no": "101", "display_label": "דירה 101",
                "sort_index": 10, "status": "available", "archived": False,
                "spare_tiles": [{"type": "ריצוף יבש", "count": 8, "notes": ""}],
            },
            {
                "id": unit_three_id, "project_id": project_id, "building_id": building_id,
                "floor_id": floor_high_id, "unit_no": "801", "display_label": "דירה 801",
                "sort_index": 5, "status": "available", "archived": False,
            },
            {
                "id": cross_unit_id, "project_id": other_project_id,
                "building_id": f"probe-cross-building-{tag}",
                "floor_id": f"probe-cross-floor-{tag}", "unit_no": "X1",
                "sort_index": 1, "status": "available", "archived": False,
            },
        ])

        pm_headers = {"Authorization": f"Bearer {_create_token(pm_id, 'project_manager')}"}
        owner_headers = {"Authorization": f"Bearer {_create_token(owner_id, 'owner')}"}
        viewer_headers = {"Authorization": f"Bearer {_create_token(viewer_id, 'viewer')}"}

        # V3 baseline before any project settings are persisted.
        baseline_response = call("GET", f"/api/units/{unit_one_id}", viewer_headers, 200)
        baseline = baseline_response.json()
        check("V3 absent settings has no profiles", baseline["spare_profiles_exist"] is False)
        check("V3 absent settings status is no_profile",
              baseline["spare_status"]["overall"] == "no_profile")
        additive_top = {"spare_settings", "spare_profiles_exist", "spare_status", "spare_can_write"}
        baseline_top_keys = set(baseline) - additive_top
        baseline_unit_keys = set(baseline["unit"]) - {"spare_profile_id"}
        check("V3 baseline existing top-level keys captured", bool(baseline_top_keys))
        check("V3 baseline existing unit keys captured", bool(baseline_unit_keys))

        settings_path = f"/api/projects/{project_id}/spare-settings"
        assignments_path = f"/api/projects/{project_id}/spare-assignments"
        profile_payload = {
            "categories": [
                {"name": "ריצוף יבש", "measure": "tiles"},
                {"name": "ריצוף מרפסות", "measure": "cartons"},
            ],
            "profiles": [
                {"id": profile_a, "name": "3 חדרים",
                 "targets": {"ריצוף יבש": 10, "ריצוף מרפסות": 2}},
                {"id": profile_b, "name": "4 חדרים",
                 "targets": {"ריצוף יבש": 12, "ריצוף מרפסות": 3}},
            ],
            "margin_pct": 10,
        }

        viewer_get = call("GET", settings_path, viewer_headers, 200).json()
        check("V2 viewer GET settings allowed and read-only",
              viewer_get["can_write"] is False)
        call("GET", assignments_path, viewer_headers, 200)
        call("PUT", settings_path, viewer_headers, 403, json=profile_payload)
        call("PATCH", f"{settings_path.rsplit('/', 1)[0]}/spare-profiles/{profile_a}/units",
             viewer_headers, 403, json={"add": [unit_one_id], "remove": []})

        pm_saved = call("PUT", settings_path, pm_headers, 200, json=profile_payload).json()
        check("V2 PM saved two profiles",
              [p["id"] for p in pm_saved["profiles"]] == [profile_a, profile_b])
        pm_version = pm_saved["updated_at"]

        owner_payload = {
            **profile_payload,
            "margin_pct": 11,
            "updated_at": pm_version,
        }
        owner_saved = call("PUT", settings_path, owner_headers, 200, json=owner_payload).json()
        check("V2 owner project-scoped write allowed",
              owner_saved["can_write"] is True and owner_saved["margin_pct"] == 11)
        owner_version = owner_saved["updated_at"]

        stale_payload = {**profile_payload, "margin_pct": 12, "updated_at": pm_version}
        call("PUT", settings_path, pm_headers, 409, json=stale_payload)

        assignment_payload = call(
            "GET", f"{assignments_path}?building_id={building_id}", viewer_headers, 200
        ).json()
        check("V2 buildings preserve structure ordering",
              [b["id"] for b in assignment_payload["buildings"]]
              == [other_building_id, building_id])
        check("V2 floors preserve sort_index ordering",
              [f["id"] for f in assignment_payload["floors"]]
              == [floor_low_id, floor_high_id])
        check("V2 units preserve sort_index ordering",
              [u["id"] for u in assignment_payload["floors"][0]["units"]]
              == [unit_one_id, unit_two_id])
        expected_unit_keys = {"id", "unit_no", "display_label", "spare_profile_id"}
        check("V2 assignment unit payload is exact",
              set(assignment_payload["floors"][0]["units"][0]) == expected_unit_keys)

        profile_base = f"/api/projects/{project_id}/spare-profiles"
        added = call("PATCH", f"{profile_base}/{profile_a}/units", pm_headers, 200,
                     json={"add": [unit_one_id, unit_two_id], "remove": []}).json()
        check("V2 assignment add exact count", added == {"added": 2, "removed": 0})
        moved = call("PATCH", f"{profile_base}/{profile_b}/units", owner_headers, 200,
                     json={"add": [unit_one_id], "remove": []}).json()
        check("V2 assignment move exact count", moved == {"added": 1, "removed": 0})
        removed = call("PATCH", f"{profile_base}/{profile_b}/units", pm_headers, 200,
                       json={"add": [], "remove": [unit_one_id]}).json()
        check("V2 assignment remove exact count", removed == {"added": 0, "removed": 1})
        removed_again = call("PATCH", f"{profile_base}/{profile_b}/units", pm_headers, 200,
                             json={"add": [], "remove": [unit_one_id]}).json()
        check("V2 no-op removal reports zero", removed_again == {"added": 0, "removed": 0})

        delete_assigned = {
            "categories": owner_saved["categories"],
            "profiles": [p for p in owner_saved["profiles"] if p["id"] != profile_a],
            "margin_pct": owner_saved["margin_pct"],
            "updated_at": owner_version,
        }
        call("PUT", settings_path, pm_headers, 409, json=delete_assigned)
        call("PATCH", f"{profile_base}/{profile_b}/units", pm_headers, 422,
             json={"add": [cross_unit_id], "remove": []})

        final_add = call("PATCH", f"{profile_base}/{profile_a}/units", pm_headers, 200,
                         json={"add": [unit_one_id], "remove": []}).json()
        check("V3 final profile assignment exact count",
              final_add == {"added": 1, "removed": 0})
        after = call("GET", f"/api/units/{unit_one_id}", viewer_headers, 200).json()
        check("V3 existing top-level keys unchanged",
              set(after) - additive_top == baseline_top_keys)
        check("V3 existing nested unit keys unchanged",
              set(after["unit"]) - {"spare_profile_id"} == baseline_unit_keys)
        check("V3 assigned profile returned",
              after["spare_status"]["profile"]["id"] == profile_a)
        dry_row = next(row for row in after["spare_status"]["categories"]
                       if row["name"] == "ריצוף יבש")
        check("V3 status reflects actual 8 against target 10",
              after["spare_status"]["overall"] == "short"
              and dry_row["actual"] == 8 and dry_row["target"] == 10
              and dry_row["missing"] == 2)
        check("V3 viewer unit capability is false", after["spare_can_write"] is False)

        audit_actions = {
            row["action"] for row in db.audit_events.find(
                {"entity_type": "project", "entity_id": project_id},
                {"_id": 0, "action": 1},
            )
        }
        check("V2 settings audit action recorded",
              "spare_settings_updated" in audit_actions)
        check("V2 assignment audit action recorded",
              "spare_profile_units_updated" in audit_actions)
        print(f"\nAll {len(RESULTS)} live HTTP checks passed.")
    finally:
        db.audit_events.delete_many({"entity_id": {"$in": project_ids}})
        db.spare_tile_locks.delete_many({"_id": {"$in": project_ids}})
        db.units.delete_many({"id": {"$in": unit_ids}})
        db.floors.delete_many({"id": {"$in": floor_ids}})
        db.buildings.delete_many({"id": {"$in": building_ids}})
        db.project_memberships.delete_many({
            "$or": [{"project_id": {"$in": project_ids}}, {"user_id": {"$in": user_ids}}]
        })
        db.organization_memberships.delete_many({
            "$or": [{"org_id": org_id}, {"user_id": {"$in": user_ids}}]
        })
        db.subscriptions.delete_many({"org_id": org_id})
        db.projects.delete_many({"id": {"$in": project_ids}})
        db.users.delete_many({"id": {"$in": user_ids}})
        db.organizations.delete_many({"id": org_id})
        client.close()


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"\n[FAIL] {type(exc).__name__}: {exc}", file=sys.stderr)
        raise