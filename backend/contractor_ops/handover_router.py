from fastapi import APIRouter, HTTPException, Depends, Query, Request, UploadFile, File, Form
from datetime import datetime, timezone
import uuid
import logging
import re

from contractor_ops.router import get_db, get_current_user, require_roles, _check_project_access, _check_project_read_access, _audit, _now, _is_super_admin
from services.object_storage import save_bytes, generate_url

logger = logging.getLogger("contractor_ops.handover")

router = APIRouter(prefix="/api")

_require_super_admin = None

def set_handover_deps(require_super_admin_fn):
    global _require_super_admin
    _require_super_admin = require_super_admin_fn

def _get_require_super_admin():
    from contractor_ops.router import require_super_admin
    return _require_super_admin or require_super_admin


HANDOVER_TEMPLATE = {
    "name": "תבנית מסירה — סטנדרטית",
    "type": "handover",
    "sections": [
        {
            "id": "section_entrance",
            "name": "כניסה לדירה",
            "order": 1,
            "visible_in_initial": True,
            "visible_in_final": True,
            "items": [
                {"id": "entrance_frame", "name": "משקוף", "trade": "אלומיניום", "order": 1, "input_type": "status"},
                {"id": "entrance_door", "name": "דלת כניסה", "trade": "דלתות", "order": 2, "input_type": "status"},
                {"id": "entrance_closer", "name": "סגר עליון", "trade": "דלתות", "order": 3, "input_type": "status"},
                {"id": "entrance_peephole", "name": "עינית", "trade": "דלתות", "order": 4, "input_type": "status"},
                {"id": "entrance_intercom", "name": "אינטרקום", "trade": "חשמל", "order": 5, "input_type": "status"},
                {"id": "entrance_plaster", "name": "טיח", "trade": "טיח", "order": 6, "input_type": "status"},
                {"id": "entrance_tiling", "name": "ריצוף+רובה", "trade": "ריצוף", "order": 7, "input_type": "status"},
                {"id": "entrance_paint", "name": "צבע", "trade": "צביעה", "order": 8, "input_type": "status"},
                {"id": "entrance_bell", "name": "פעמון", "trade": "חשמל", "order": 9, "input_type": "status"},
                {"id": "entrance_elec_panel", "name": "ארון חשמל", "trade": "חשמל", "order": 10, "input_type": "status"},
                {"id": "entrance_comm_panel", "name": "ארון תקשורת", "trade": "חשמל", "order": 11, "input_type": "status"},
                {"id": "entrance_electrical", "name": "חשמל", "trade": "חשמל", "order": 12, "input_type": "status"},
                {"id": "entrance_other", "name": "אחר", "trade": "כללי", "order": 13, "input_type": "status"},
            ],
        },
        {
            "id": "section_lobby",
            "name": "מבואה",
            "order": 2,
            "visible_in_initial": True,
            "visible_in_final": True,
            "items": [
                {"id": "lobby_tiling", "name": "ריצוף+רובה", "trade": "ריצוף", "order": 1, "input_type": "status"},
                {"id": "lobby_plaster", "name": "טיח", "trade": "טיח", "order": 2, "input_type": "status"},
                {"id": "lobby_paint", "name": "צבע", "trade": "צביעה", "order": 3, "input_type": "status"},
                {"id": "lobby_electrical", "name": "חשמל", "trade": "חשמל", "order": 4, "input_type": "status"},
                {"id": "lobby_drainage", "name": "ניקוז+צמה מיני מרכזי", "trade": "אינסטלציה", "order": 5, "input_type": "status"},
                {"id": "lobby_other", "name": "אחר", "trade": "כללי", "order": 6, "input_type": "status"},
            ],
        },
        {
            "id": "section_kitchen",
            "name": "מטבח",
            "order": 3,
            "visible_in_initial": True,
            "visible_in_final": True,
            "items": [
                {"id": "kitchen_cabinets", "name": "ארונות עץ", "trade": "מטבחים", "order": 1, "input_type": "status"},
                {"id": "kitchen_countertop", "name": "שיש", "trade": "שיש", "order": 2, "input_type": "status"},
                {"id": "kitchen_backsplash", "name": "חיפוי", "trade": "ריצוף", "order": 3, "input_type": "status"},
                {"id": "kitchen_faucet", "name": "ברז", "trade": "אינסטלציה", "order": 4, "input_type": "status"},
                {"id": "kitchen_electrical", "name": "חשמל ותקשורת", "trade": "חשמל", "order": 5, "input_type": "status"},
                {"id": "kitchen_plumbing", "name": "אינסטלציה", "trade": "אינסטלציה", "order": 6, "input_type": "status"},
                {"id": "kitchen_tiling", "name": "ריצוף+רובה", "trade": "ריצוף", "order": 7, "input_type": "status"},
                {"id": "kitchen_aluminum", "name": "אלומיניום", "trade": "אלומיניום", "order": 8, "input_type": "status"},
                {"id": "kitchen_other", "name": "אחר", "trade": "כללי", "order": 9, "input_type": "status"},
            ],
        },
        {
            "id": "section_guest_wc",
            "name": "שירותי אורחים",
            "order": 4,
            "visible_in_initial": True,
            "visible_in_final": True,
            "items": [
                {"id": "guest_wc_door", "name": "דלת פנים", "trade": "דלתות", "order": 1, "input_type": "status"},
                {"id": "guest_wc_tiles", "name": "חיפוי", "trade": "ריצוף", "order": 2, "input_type": "status"},
                {"id": "guest_wc_toilet", "name": "אסלה+מושב", "trade": "אינסטלציה", "order": 3, "input_type": "status"},
                {"id": "guest_wc_faucet", "name": "ברז כיור", "trade": "אינסטלציה", "order": 4, "input_type": "status"},
                {"id": "guest_wc_plaster", "name": "טיח", "trade": "טיח", "order": 5, "input_type": "status"},
                {"id": "guest_wc_paint", "name": "צבע", "trade": "צביעה", "order": 6, "input_type": "status"},
                {"id": "guest_wc_electrical", "name": "חשמל", "trade": "חשמל", "order": 7, "input_type": "status"},
                {"id": "guest_wc_aluminum", "name": "אלומיניום/וונטה", "trade": "אלומיניום", "order": 8, "input_type": "status"},
                {"id": "guest_wc_tiling", "name": "ריצוף+רובה", "trade": "ריצוף", "order": 9, "input_type": "status"},
                {"id": "guest_wc_other", "name": "אחר", "trade": "כללי", "order": 10, "input_type": "status"},
            ],
        },
        {
            "id": "section_living",
            "name": "סלון",
            "order": 5,
            "visible_in_initial": True,
            "visible_in_final": True,
            "items": [
                {"id": "living_plaster", "name": "טיח", "trade": "טיח", "order": 1, "input_type": "status"},
                {"id": "living_paint", "name": "צבע", "trade": "צביעה", "order": 2, "input_type": "status"},
                {"id": "living_aluminum", "name": "אלומיניום", "trade": "אלומיניום", "order": 3, "input_type": "status"},
                {"id": "living_electrical", "name": "חשמל ותקשורת", "trade": "חשמל", "order": 4, "input_type": "status"},
                {"id": "living_tiling", "name": "ריצוף+רובה", "trade": "ריצוף", "order": 5, "input_type": "status"},
                {"id": "living_other", "name": "אחר", "trade": "כללי", "order": 6, "input_type": "status"},
            ],
        },
        {
            "id": "section_balcony",
            "name": "מרפסת סלון",
            "order": 6,
            "visible_in_initial": True,
            "visible_in_final": True,
            "items": [
                {"id": "balcony_stone", "name": "חיפוי אבן חוץ", "trade": "ריצוף", "order": 1, "input_type": "status"},
                {"id": "balcony_glass", "name": "זגוגית מעקה", "trade": "אלומיניום", "order": 2, "input_type": "status"},
                {"id": "balcony_railing", "name": "מעקה אלומיניום", "trade": "אלומיניום", "order": 3, "input_type": "status"},
                {"id": "balcony_plaster", "name": "טיח", "trade": "טיח", "order": 4, "input_type": "status"},
                {"id": "balcony_paint", "name": "צבע", "trade": "צביעה", "order": 5, "input_type": "status"},
                {"id": "balcony_plumbing", "name": "אינסטלציה", "trade": "אינסטלציה", "order": 6, "input_type": "status"},
                {"id": "balcony_electrical", "name": "חשמל", "trade": "חשמל", "order": 7, "input_type": "status"},
                {"id": "balcony_render", "name": "שליכט צבעוני", "trade": "טיח", "order": 8, "input_type": "status"},
                {"id": "balcony_tiling", "name": "ריצוף+רובה", "trade": "ריצוף", "order": 9, "input_type": "status"},
                {"id": "balcony_slopes", "name": "שיפועים", "trade": "ריצוף", "order": 10, "input_type": "status"},
                {"id": "balcony_other", "name": "אחר", "trade": "כללי", "order": 11, "input_type": "status"},
            ],
        },
        {
            "id": "section_mamad",
            "name": "ממ\"ד",
            "order": 7,
            "visible_in_initial": True,
            "visible_in_final": True,
            "items": [
                {"id": "mamad_paint", "name": "צבע", "trade": "צביעה", "order": 1, "input_type": "status"},
                {"id": "mamad_frame", "name": "משקוף", "trade": "אלומיניום", "order": 2, "input_type": "status"},
                {"id": "mamad_electrical", "name": "חשמל ותקשורת", "trade": "חשמל", "order": 3, "input_type": "status"},
                {"id": "mamad_steel_door", "name": "דלת ברזל", "trade": "ברזל", "order": 4, "input_type": "status"},
                {"id": "mamad_tiling", "name": "ריצוף+רובה", "trade": "ריצוף", "order": 5, "input_type": "status"},
                {"id": "mamad_aluminum", "name": "אלומיניום", "trade": "אלומיניום", "order": 6, "input_type": "status"},
                {"id": "mamad_steel_window", "name": "חלון ברזל", "trade": "ברזל", "order": 7, "input_type": "status"},
                {"id": "mamad_inner_door", "name": "דלת פנים", "trade": "דלתות", "order": 8, "input_type": "status"},
                {"id": "mamad_omer", "name": "התקן עומר", "trade": "ברזל", "order": 9, "input_type": "status"},
                {"id": "mamad_air_filter", "name": "מסנן אויר", "trade": "ברזל", "order": 10, "input_type": "status"},
                {"id": "mamad_other", "name": "אחר", "trade": "כללי", "order": 11, "input_type": "status"},
            ],
        },
        {
            "id": "section_bathroom",
            "name": "אמבטיה כללית",
            "order": 8,
            "visible_in_initial": True,
            "visible_in_final": True,
            "items": [
                {"id": "bath_tub", "name": "אמבטיה", "trade": "אינסטלציה", "order": 1, "input_type": "status"},
                {"id": "bath_mixer", "name": "סוללה/אינטרפוץ", "trade": "אינסטלציה", "order": 2, "input_type": "status"},
                {"id": "bath_shower_faucet", "name": "ברז מקלחת", "trade": "אינסטלציה", "order": 3, "input_type": "status"},
                {"id": "bath_toilet", "name": "ניאגרה+אסלה+מושב", "trade": "אינסטלציה", "order": 4, "input_type": "status"},
                {"id": "bath_vanity", "name": "ארון אמבט+מראה", "trade": "מטבחים", "order": 5, "input_type": "status"},
                {"id": "bath_tiling", "name": "ריצוף+רובה", "trade": "ריצוף", "order": 6, "input_type": "status"},
                {"id": "bath_electrical", "name": "חשמל", "trade": "חשמל", "order": 7, "input_type": "status"},
                {"id": "bath_wall_tiles", "name": "חיפוי", "trade": "ריצוף", "order": 8, "input_type": "status"},
                {"id": "bath_ventilation", "name": "איוורור", "trade": "חשמל", "order": 9, "input_type": "status"},
                {"id": "bath_plaster", "name": "טיח", "trade": "טיח", "order": 10, "input_type": "status"},
                {"id": "bath_paint", "name": "צבע", "trade": "צביעה", "order": 11, "input_type": "status"},
                {"id": "bath_window", "name": "חלון", "trade": "אלומיניום", "order": 12, "input_type": "status"},
                {"id": "bath_door", "name": "דלת פנים", "trade": "דלתות", "order": 13, "input_type": "status"},
                {"id": "bath_other", "name": "אחר", "trade": "כללי", "order": 14, "input_type": "status"},
            ],
        },
        {
            "id": "section_laundry",
            "name": "חדר כביסה",
            "order": 9,
            "visible_in_initial": True,
            "visible_in_final": True,
            "items": [
                {"id": "laundry_tiling", "name": "ריצוף+רובה", "trade": "ריצוף", "order": 1, "input_type": "status"},
                {"id": "laundry_plaster", "name": "טיח", "trade": "טיח", "order": 2, "input_type": "status"},
                {"id": "laundry_window", "name": "חלון", "trade": "אלומיניום", "order": 3, "input_type": "status"},
                {"id": "laundry_door", "name": "דלת", "trade": "דלתות", "order": 4, "input_type": "status"},
                {"id": "laundry_plumbing", "name": "אינסטלציה", "trade": "אינסטלציה", "order": 5, "input_type": "status"},
                {"id": "laundry_electrical", "name": "חשמל", "trade": "חשמל", "order": 6, "input_type": "status"},
                {"id": "laundry_dryer_prep", "name": "הכנה למייבש", "trade": "חשמל", "order": 7, "input_type": "status"},
                {"id": "laundry_shutter", "name": "תריס חלון", "trade": "אלומיניום", "order": 8, "input_type": "status"},
                {"id": "laundry_paint", "name": "צבע", "trade": "צביעה", "order": 9, "input_type": "status"},
                {"id": "laundry_other", "name": "אחר", "trade": "כללי", "order": 10, "input_type": "status"},
            ],
        },
        {
            "id": "section_bedroom1",
            "name": "חדר שינה 1",
            "order": 10,
            "visible_in_initial": True,
            "visible_in_final": True,
            "items": [
                {"id": "bed1_door", "name": "דלת פנים", "trade": "דלתות", "order": 1, "input_type": "status"},
                {"id": "bed1_tiling", "name": "ריצוף+רובה", "trade": "ריצוף", "order": 2, "input_type": "status"},
                {"id": "bed1_plaster", "name": "טיח", "trade": "טיח", "order": 3, "input_type": "status"},
                {"id": "bed1_paint", "name": "צבע", "trade": "צביעה", "order": 4, "input_type": "status"},
                {"id": "bed1_aluminum", "name": "אלומיניום", "trade": "אלומיניום", "order": 5, "input_type": "status"},
                {"id": "bed1_electrical", "name": "חשמל", "trade": "חשמל", "order": 6, "input_type": "status"},
                {"id": "bed1_drainage", "name": "ניקוז+חשמל", "trade": "חשמל", "order": 7, "input_type": "status"},
                {"id": "bed1_other", "name": "אחר", "trade": "כללי", "order": 8, "input_type": "status"},
            ],
        },
        {
            "id": "section_bedroom2",
            "name": "חדר שינה 2",
            "order": 11,
            "visible_in_initial": True,
            "visible_in_final": True,
            "items": [
                {"id": "bed2_door", "name": "דלת פנים", "trade": "דלתות", "order": 1, "input_type": "status"},
                {"id": "bed2_tiling", "name": "ריצוף+רובה", "trade": "ריצוף", "order": 2, "input_type": "status"},
                {"id": "bed2_plaster", "name": "טיח", "trade": "טיח", "order": 3, "input_type": "status"},
                {"id": "bed2_paint", "name": "צבע", "trade": "צביעה", "order": 4, "input_type": "status"},
                {"id": "bed2_aluminum", "name": "אלומיניום", "trade": "אלומיניום", "order": 5, "input_type": "status"},
                {"id": "bed2_electrical", "name": "חשמל", "trade": "חשמל", "order": 6, "input_type": "status"},
                {"id": "bed2_drainage", "name": "ניקוז+חשמל", "trade": "חשמל", "order": 7, "input_type": "status"},
                {"id": "bed2_other", "name": "אחר", "trade": "כללי", "order": 8, "input_type": "status"},
            ],
        },
        {
            "id": "section_master",
            "name": "חדר הורים",
            "order": 12,
            "visible_in_initial": True,
            "visible_in_final": True,
            "items": [
                {"id": "master_door", "name": "דלת פנים", "trade": "דלתות", "order": 1, "input_type": "status"},
                {"id": "master_tiling", "name": "ריצוף+רובה", "trade": "ריצוף", "order": 2, "input_type": "status"},
                {"id": "master_plaster", "name": "טיח", "trade": "טיח", "order": 3, "input_type": "status"},
                {"id": "master_paint", "name": "צבע", "trade": "צביעה", "order": 4, "input_type": "status"},
                {"id": "master_aluminum", "name": "אלומיניום", "trade": "אלומיניום", "order": 5, "input_type": "status"},
                {"id": "master_electrical", "name": "חשמל", "trade": "חשמל", "order": 6, "input_type": "status"},
                {"id": "master_drainage", "name": "ניקוז+חשמל", "trade": "חשמל", "order": 7, "input_type": "status"},
                {"id": "master_other", "name": "אחר", "trade": "כללי", "order": 8, "input_type": "status"},
            ],
        },
        {
            "id": "section_master_bath",
            "name": "שירותי הורים",
            "order": 13,
            "visible_in_initial": True,
            "visible_in_final": True,
            "items": [
                {"id": "mbath_door", "name": "דלת פנים", "trade": "דלתות", "order": 1, "input_type": "status"},
                {"id": "mbath_shower", "name": "מקלחון+נקז", "trade": "אינסטלציה", "order": 2, "input_type": "status"},
                {"id": "mbath_faucets", "name": "ברזים", "trade": "אינסטלציה", "order": 3, "input_type": "status"},
                {"id": "mbath_toilet", "name": "אסלה+מושב", "trade": "אינסטלציה", "order": 4, "input_type": "status"},
                {"id": "mbath_vanity", "name": "ארון אמבט+מראה", "trade": "מטבחים", "order": 5, "input_type": "status"},
                {"id": "mbath_tiling", "name": "ריצוף+רובה", "trade": "ריצוף", "order": 6, "input_type": "status"},
                {"id": "mbath_electrical", "name": "חשמל", "trade": "חשמל", "order": 7, "input_type": "status"},
                {"id": "mbath_wall_tiles", "name": "חיפוי", "trade": "ריצוף", "order": 8, "input_type": "status"},
                {"id": "mbath_ventilation", "name": "איוורור", "trade": "חשמל", "order": 9, "input_type": "status"},
                {"id": "mbath_plaster", "name": "טיח", "trade": "טיח", "order": 10, "input_type": "status"},
                {"id": "mbath_paint", "name": "צבע", "trade": "צביעה", "order": 11, "input_type": "status"},
                {"id": "mbath_window", "name": "חלון", "trade": "אלומיניום", "order": 12, "input_type": "status"},
                {"id": "mbath_other", "name": "אחר", "trade": "כללי", "order": 13, "input_type": "status"},
            ],
        },
        {
            "id": "section_storage",
            "name": "מחסן",
            "order": 14,
            "visible_in_initial": True,
            "visible_in_final": True,
            "items": [
                {"id": "storage_door", "name": "דלת", "trade": "דלתות", "order": 1, "input_type": "status"},
                {"id": "storage_frame", "name": "משקוף", "trade": "אלומיניום", "order": 2, "input_type": "status"},
                {"id": "storage_plaster", "name": "טיח", "trade": "טיח", "order": 3, "input_type": "status"},
                {"id": "storage_paint", "name": "צבע", "trade": "צביעה", "order": 4, "input_type": "status"},
                {"id": "storage_electrical", "name": "חשמל", "trade": "חשמל", "order": 5, "input_type": "status"},
                {"id": "storage_tiling", "name": "ריצוף+רובה", "trade": "ריצוף", "order": 6, "input_type": "status"},
                {"id": "storage_other", "name": "אחר", "trade": "כללי", "order": 7, "input_type": "status"},
            ],
        },
        {
            "id": "section_laundry_yard",
            "name": "מסתור כביסה",
            "order": 15,
            "visible_in_initial": True,
            "visible_in_final": True,
            "items": [
                {"id": "ly_plumbing", "name": "אינסטלציה", "trade": "אינסטלציה", "order": 1, "input_type": "status"},
                {"id": "ly_paint", "name": "צבע", "trade": "צביעה", "order": 2, "input_type": "status"},
                {"id": "ly_boiler", "name": "דוד חשמל+מערכת סולרית", "trade": "אינסטלציה", "order": 3, "input_type": "status"},
                {"id": "ly_plaster", "name": "טיח", "trade": "טיח", "order": 4, "input_type": "status"},
                {"id": "ly_ventilation", "name": "איוורור", "trade": "חשמל", "order": 5, "input_type": "status"},
                {"id": "ly_ac_prep", "name": "הכנה למזגן", "trade": "חשמל", "order": 6, "input_type": "status"},
                {"id": "ly_electrical", "name": "חשמל", "trade": "חשמל", "order": 7, "input_type": "status"},
                {"id": "ly_louver", "name": "רפפה", "trade": "אלומיניום", "order": 8, "input_type": "status"},
                {"id": "ly_window", "name": "חלון", "trade": "אלומיניום", "order": 9, "input_type": "status"},
                {"id": "ly_drainage", "name": "ניקוז מסתור", "trade": "אינסטלציה", "order": 10, "input_type": "status"},
                {"id": "ly_other", "name": "אחר", "trade": "כללי", "order": 11, "input_type": "status"},
            ],
        },
    ],
}

HARDCODED_PROPERTY_FIELDS = [
    {"key": "rooms", "label": "חדרים"},
    {"key": "storage_num", "label": "מספר מחסנים"},
    {"key": "parking_num", "label": "מספר חניות"},
    {"key": "model", "label": "דגם"},
    {"key": "area", "label": "שטח דירה"},
    {"key": "balcony_area", "label": "שטח מרפסת"},
    {"key": "parking_area", "label": "שטח חניה"},
    {"key": "laundry_area", "label": "שטח מרפסת שירות"},
]

HARDCODED_SIGNATURE_LABELS = {
    "manager": "אני מאשר/ת את חתימתי על פרוטוקול המסירה כמנהל/ת הפרויקט",
    "tenant": "אני מאשר/ת את חתימתי על פרוטוקול המסירה כרוכש/ת ראשי/ת",
    "tenant_2": "אני מאשר/ת את חתימתי על פרוטוקול המסירה כרוכש/ת נוסף/ת",
    "contractor_rep": "אני מאשר/ת את חתימתי על פרוטוקול המסירה כנציג/ת הקבלן",
}

DEFAULT_DELIVERED_ITEMS = [
    {"name": "מפתח דלת כניסה", "quantity": None, "notes": ""},
    {"name": "מפתחות דלתות פנים", "quantity": None, "notes": ""},
    {"name": "מפתח חדר חשמל", "quantity": None, "notes": ""},
    {"name": "מפתח תיבת דואר", "quantity": None, "notes": ""},
    {"name": "מטף כיבוי אש", "quantity": None, "notes": ""},
    {"name": "חבלי כביסה", "quantity": None, "notes": ""},
    {"name": "מושבי אסלה", "quantity": None, "notes": ""},
    {"name": "מנואלה", "quantity": None, "notes": ""},
    {"name": "מוט + צינור + מזלף", "quantity": None, "notes": ""},
    {"name": "סוללה + מזלף + מתלה", "quantity": None, "notes": ""},
    {"name": "סטופרים לדלתות", "quantity": None, "notes": ""},
    {"name": "תעודות אחריות", "quantity": None, "notes": ""},
    {"name": "מפתח אינטרקום", "quantity": None, "notes": ""},
]

VALID_ITEM_STATUSES = {"ok", "partial", "defective", "not_relevant", "not_checked"}


async def _resolve_handover_template(project_id: str):
    db = get_db()
    project = await db.projects.find_one({"id": project_id}, {"_id": 0, "handover_template_version_id": 1})
    if project and project.get("handover_template_version_id"):
        tpl = await db.qc_templates.find_one(
            {"id": project["handover_template_version_id"], "type": "handover"},
            {"_id": 0}
        )
        if tpl:
            return tpl
        logger.warning(
            f"Project {project_id} references missing template version "
            f"{project['handover_template_version_id']}, falling back to default"
        )

    tpl = await db.qc_templates.find_one(
        {"type": "handover", "is_default": True, "is_active": True},
        {"_id": 0}
    )
    if tpl:
        return tpl

    return HANDOVER_TEMPLATE


async def _check_handover_access(user: dict, project_id: str):
    if _is_super_admin(user):
        return
    db = get_db()
    membership = await db.project_memberships.find_one(
        {"user_id": user["id"], "project_id": project_id}
    )
    if not membership:
        raise HTTPException(status_code=403, detail="אין לך גישה לפרויקט זה")
    allowed = {"owner", "project_manager", "management_team"}
    if membership.get("role") not in allowed:
        raise HTTPException(status_code=403, detail="אין הרשאה לצפות בנתוני מסירה")


async def _check_handover_management(user: dict, project_id: str):
    if _is_super_admin(user):
        return
    db = get_db()
    membership = await db.project_memberships.find_one(
        {"user_id": user["id"], "project_id": project_id}
    )
    if not membership:
        raise HTTPException(status_code=403, detail="אין לך גישה לפרויקט זה")
    allowed = {"owner", "project_manager", "management_team"}
    if membership.get("role") not in allowed:
        raise HTTPException(status_code=403, detail="אין הרשאה לפעולה זו")


async def _get_protocol_or_404(protocol_id: str, project_id: str):
    db = get_db()
    protocol = await db.handover_protocols.find_one(
        {"id": protocol_id, "project_id": project_id},
        {"_id": 0}
    )
    if not protocol:
        raise HTTPException(status_code=404, detail="פרוטוקול לא נמצא")
    return protocol


VALID_SIGNATURE_ROLES = ("manager", "tenant", "tenant_2", "contractor_rep")
REQUIRED_SIGNATURE_ROLES = ("manager", "tenant")
OPTIONAL_SIGNATURE_ROLES = ("tenant_2", "contractor_rep")

SIGNING_COMPLETION_THRESHOLD = 0.90


def _calculate_completion(protocol):
    total = 0
    checked = 0
    for section in protocol.get("sections", []):
        for item in section.get("items", []):
            total += 1
            status = item.get("status") or ""
            if status and status != "not_checked":
                checked += 1
    pct = checked / total if total > 0 else 1.0
    return (checked, total, pct)

SIGNATURE_ROLE_LABELS = {
    "manager": "מנהל פרויקט / מפקח",
    "tenant": "רוכש/ת ראשי/ת",
    "tenant_2": "רוכש/ת נוסף/ת",
    "contractor_rep": "נציג קבלן",
}


def _check_not_locked(protocol):
    if protocol.get("locked") is True:
        raise HTTPException(status_code=403, detail="פרוטוקול חתום — לא ניתן לערוך")


def _normalize_signatures(protocol):
    sigs = protocol.get("signatures")
    if isinstance(sigs, list):
        return {}
    if isinstance(sigs, dict):
        return sigs
    return {}


def _count_signatures(protocol):
    sigs = _normalize_signatures(protocol)
    return sum(1 for role in VALID_SIGNATURE_ROLES if role in sigs and sigs[role])


def _legal_section_sign_score(section, num_tenants):
    if not section.get("requires_signature"):
        return None
    sigs = section.get("signatures") or {}
    has_old_sig = bool(section.get("signed_at") and section.get("signature"))
    if section.get("requires_both_tenants") and num_tenants >= 2:
        t1 = bool(sigs.get("tenant", {}).get("signed_at")) or (has_old_sig and not sigs)
        t2 = bool(sigs.get("tenant_2", {}).get("signed_at"))
        if t1 and t2:
            return 1.0
        if t1 or t2:
            return 0.5
        return 0.0
    if has_old_sig or bool(sigs.get("tenant", {}).get("signed_at")):
        return 1.0
    return 0.0


def _valid_tenant_count(protocol):
    return len([
        t for t in (protocol.get("tenants") or [])
        if t and (t.get("name") or "").strip()
    ])


def _is_protocol_fully_signed(protocol):
    sigs = _normalize_signatures(protocol)
    for role in REQUIRED_SIGNATURE_ROLES:
        if role not in sigs or not sigs[role]:
            return False
    num_tenants = _valid_tenant_count(protocol)
    if num_tenants >= 2 and ("tenant_2" not in sigs or not sigs["tenant_2"]):
        return False
    for section in protocol.get("legal_sections", []):
        score = _legal_section_sign_score(section, num_tenants)
        if score is not None and score < 1.0:
            return False
    return True


def _recalculate_signature_status(protocol):
    if _is_protocol_fully_signed(protocol):
        return "signed", True
    count = _count_signatures(protocol)
    num_tenants = _valid_tenant_count(protocol)
    legal_any_signed = any(
        (_legal_section_sign_score(s, num_tenants) or 0) > 0
        for s in protocol.get("legal_sections", [])
    )
    if count >= 1 or legal_any_signed:
        return "partially_signed", False
    else:
        has_item_changes = any(
            item.get("status") and item["status"] != "not_checked"
            for section in protocol.get("sections", [])
            for item in section.get("items", [])
        )
        if has_item_changes:
            return "in_progress", False
        return "draft", False


@router.put("/projects/{project_id}/handover-template")
async def assign_handover_template(project_id: str, request: Request, user: dict = Depends(get_current_user)):
    require_sa = _get_require_super_admin()
    if not _is_super_admin(user):
        raise HTTPException(status_code=403, detail="נדרשת הרשאת מנהל מערכת")
    db = get_db()
    project = await db.projects.find_one({"id": project_id}, {"_id": 0, "id": 1, "name": 1})
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    body = await request.json()
    template_version_id = body.get("template_version_id")
    if not template_version_id:
        raise HTTPException(status_code=400, detail="template_version_id is required")

    tpl = await db.qc_templates.find_one(
        {"id": template_version_id, "type": "handover"},
        {"_id": 0, "id": 1, "name": 1, "version": 1, "family_id": 1}
    )
    if not tpl:
        raise HTTPException(status_code=404, detail="Handover template version not found")

    family_id = tpl.get("family_id")
    await db.projects.update_one(
        {"id": project_id},
        {"$set": {
            "handover_template_version_id": template_version_id,
            "handover_template_family_id": family_id,
        }}
    )
    logger.info(f"[HANDOVER-TPL] Assigned template={template_version_id} family={family_id} to project={project_id} by user={user['id']}")

    return {
        "success": True,
        "project_id": project_id,
        "template_version_id": template_version_id,
        "template_family_id": family_id,
        "template_name": tpl["name"],
        "template_version": tpl["version"],
    }


@router.get("/projects/{project_id}/handover-template")
async def get_handover_template(project_id: str, user: dict = Depends(get_current_user)):
    if not _is_super_admin(user):
        db_check = get_db()
        membership = await db_check.project_memberships.find_one(
            {"user_id": user["id"], "project_id": project_id}
        )
        if not membership:
            raise HTTPException(status_code=403, detail="אין לך גישה לפרויקט זה")
        if membership.get("role") not in ("owner", "project_manager", "management_team"):
            raise HTTPException(status_code=403, detail="אין הרשאה לצפות בתבנית מסירה")
    db = get_db()
    project = await db.projects.find_one(
        {"id": project_id},
        {"_id": 0, "id": 1, "handover_template_version_id": 1, "handover_template_family_id": 1}
    )
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    version_id = project.get("handover_template_version_id")
    family_id = project.get("handover_template_family_id")

    if not version_id:
        return {
            "assigned": False,
            "template_version_id": None,
            "template_family_id": None,
            "template_name": None,
            "template_version": None,
        }

    tpl = await db.qc_templates.find_one(
        {"id": version_id},
        {"_id": 0, "id": 1, "name": 1, "version": 1, "family_id": 1}
    )
    if not tpl:
        return {
            "assigned": True,
            "template_version_id": version_id,
            "template_family_id": family_id,
            "template_name": "(נמחקה)",
            "template_version": None,
        }

    resolved_family = family_id or tpl.get("family_id")

    return {
        "assigned": True,
        "template_version_id": version_id,
        "template_family_id": resolved_family,
        "template_name": tpl["name"],
        "template_version": tpl["version"],
    }


VALID_APPLIES_TO = {"initial", "final"}


def _validate_legal_sections(sections):
    validated = []
    for idx, s in enumerate(sections):
        title = (s.get("title") or "").strip()
        if not title:
            raise HTTPException(status_code=400, detail=f"נסח #{idx + 1}: כותרת נדרשת")
        body = (s.get("body") or "").strip()
        if not body:
            raise HTTPException(status_code=400, detail=f"נסח #{idx + 1}: תוכן נדרש")
        requires_signature = s.get("requires_signature")
        if not isinstance(requires_signature, bool):
            raise HTTPException(status_code=400, detail=f"נסח #{idx + 1}: requires_signature חייב להיות boolean")
        signature_role = s.get("signature_role")
        if requires_signature:
            if signature_role not in VALID_SIGNATURE_ROLES:
                raise HTTPException(status_code=400, detail=f"נסח #{idx + 1}: signature_role חייב להיות manager/tenant/tenant_2/contractor_rep")
        else:
            if signature_role is not None:
                raise HTTPException(status_code=400, detail=f"נסח #{idx + 1}: signature_role חייב להיות null כאשר requires_signature=false")
            signature_role = None
        applies_to = s.get("applies_to")
        if not isinstance(applies_to, list) or not applies_to:
            raise HTTPException(status_code=400, detail=f"נסח #{idx + 1}: applies_to חייב להיות מערך לא ריק")
        if not all(v in VALID_APPLIES_TO for v in applies_to):
            raise HTTPException(status_code=400, detail=f"נסח #{idx + 1}: applies_to חייב להכיל רק initial/final")
        order = s.get("order")
        if not isinstance(order, int) or order < 1:
            raise HTTPException(status_code=400, detail=f"נסח #{idx + 1}: order חייב להיות מספר שלם >= 1")
        section_id = s.get("id") or str(uuid.uuid4())
        requires_both_tenants = bool(s.get("requires_both_tenants", False))
        if requires_both_tenants and not (requires_signature and signature_role in ("tenant", "tenant_2")):
            requires_both_tenants = False
        validated.append({
            "id": section_id,
            "title": title,
            "body": body,
            "requires_signature": requires_signature,
            "signature_role": signature_role,
            "requires_both_tenants": requires_both_tenants,
            "applies_to": applies_to,
            "order": order,
        })
    return validated


@router.put("/organizations/{org_id}/handover-legal-sections")
async def put_org_legal_sections(org_id: str, request: Request, user: dict = Depends(get_current_user)):
    db = get_db()
    org = await db.organizations.find_one({"id": org_id}, {"_id": 0, "id": 1, "owner_user_id": 1})
    if not org:
        raise HTTPException(status_code=404, detail="ארגון לא נמצא")
    if not _is_super_admin(user):
        is_owner = org.get("owner_user_id") == user["id"]
        if not is_owner:
            mem = await db.organization_memberships.find_one(
                {"org_id": org_id, "user_id": user["id"]}, {"_id": 0, "role": 1}
            )
            if not mem or mem.get("role") not in ("owner", "org_admin"):
                raise HTTPException(status_code=403, detail="רק מנהל ארגון יכול לערוך נסחים משפטיים")
    body = await request.json()
    raw_sections = body.get("sections")
    if not isinstance(raw_sections, list):
        raise HTTPException(status_code=400, detail="sections חייב להיות מערך")
    validated = _validate_legal_sections(raw_sections)
    await db.organizations.update_one(
        {"id": org_id},
        {"$set": {"handover_legal_sections": validated}}
    )
    await _audit("organization", org_id, "legal_sections_updated", user["id"], {
        "section_count": len(validated),
    })
    logger.info(f"[HANDOVER] Org={org_id} legal sections updated ({len(validated)} sections) by user={user['id']}")
    return {"sections": validated}


@router.get("/organizations/{org_id}/handover-legal-sections")
async def get_org_legal_sections(org_id: str, user: dict = Depends(get_current_user)):
    db = get_db()
    org = await db.organizations.find_one({"id": org_id}, {"_id": 0, "id": 1, "owner_user_id": 1})
    if not org:
        raise HTTPException(status_code=404, detail="ארגון לא נמצא")
    if not _is_super_admin(user):
        is_owner = org.get("owner_user_id") == user["id"]
        if not is_owner:
            mem = await db.organization_memberships.find_one(
                {"org_id": org_id, "user_id": user["id"]}, {"_id": 0, "role": 1}
            )
            if not mem:
                raise HTTPException(status_code=403, detail="אין לך גישה לארגון זה")
    sections = (await db.organizations.find_one({"id": org_id}, {"_id": 0, "handover_legal_sections": 1})) or {}
    return {"sections": sections.get("handover_legal_sections", [])}


async def _check_org_logo_permission(user: dict, org: dict, org_id: str, db):
    if _is_super_admin(user):
        return
    is_owner = org.get("owner_user_id") == user["id"]
    if is_owner:
        return
    mem = await db.organization_memberships.find_one(
        {"org_id": org_id, "user_id": user["id"]}, {"_id": 0, "role": 1}
    )
    if mem and mem.get("role") in ("project_manager",):
        return
    raise HTTPException(status_code=403, detail="אין לך הרשאה לעדכן לוגו ארגון")


@router.put("/organizations/{org_id}/logo")
async def upload_org_logo(org_id: str, file: UploadFile = File(...), user: dict = Depends(get_current_user)):
    import io as _io
    from PIL import Image as _PILImage
    from services.object_storage import save_bytes as _save_bytes, generate_url as _gen_url, delete as _delete_stored

    db = get_db()
    org = await db.organizations.find_one({"id": org_id}, {"_id": 0, "id": 1, "owner_user_id": 1, "logo_url": 1})
    if not org:
        raise HTTPException(status_code=404, detail="ארגון לא נמצא")
    await _check_org_logo_permission(user, org, org_id, db)

    MAX_SIZE = 2 * 1024 * 1024
    raw = await file.read()
    if len(raw) == 0:
        raise HTTPException(status_code=400, detail="קובץ ריק")
    if len(raw) > MAX_SIZE:
        raise HTTPException(status_code=400, detail="גודל הקובץ חורג מ-2MB")

    ct = (file.content_type or "").lower()
    if ct not in ("image/png", "image/jpeg", "image/jpg"):
        raise HTTPException(status_code=400, detail="סוג קובץ לא נתמך — PNG או JPEG בלבד")

    try:
        img = _PILImage.open(_io.BytesIO(raw))
        img.verify()
        img = _PILImage.open(_io.BytesIO(raw))
        if img.format not in ("PNG", "JPEG"):
            raise HTTPException(status_code=400, detail="סוג קובץ לא נתמך — PNG או JPEG בלבד")
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=400, detail="הקובץ אינו תמונה תקינה")

    if img.mode in ("RGBA", "P"):
        img = img.convert("RGBA")
        out_format = "PNG"
        out_ext = "png"
        out_ct = "image/png"
    else:
        img = img.convert("RGB")
        out_format = "JPEG"
        out_ext = "jpg"
        out_ct = "image/jpeg"

    img.thumbnail((400, 400))

    buf = _io.BytesIO()
    img.save(buf, format=out_format, quality=85 if out_format == "JPEG" else None)
    resized_bytes = buf.getvalue()

    import asyncio
    key = f"org_logos/{org_id}.{out_ext}"
    stored_ref = await asyncio.to_thread(_save_bytes, resized_bytes, key, out_ct)

    old_logo = org.get("logo_url")
    if old_logo and old_logo != stored_ref:
        try:
            await asyncio.to_thread(_delete_stored, old_logo)
        except Exception:
            pass

    await db.organizations.update_one(
        {"id": org_id},
        {"$set": {"logo_url": stored_ref, "updated_at": _now()}}
    )
    await _audit("organization", org_id, "logo_uploaded", user["id"], {})
    logger.info(f"[ORG_LOGO] Org={org_id} logo uploaded by user={user['id']} size={len(resized_bytes)}")

    return {"logo_url": _gen_url(stored_ref)}


@router.delete("/organizations/{org_id}/logo")
async def delete_org_logo(org_id: str, user: dict = Depends(get_current_user)):
    from services.object_storage import delete as _delete_stored

    db = get_db()
    org = await db.organizations.find_one({"id": org_id}, {"_id": 0, "id": 1, "owner_user_id": 1, "logo_url": 1})
    if not org:
        raise HTTPException(status_code=404, detail="ארגון לא נמצא")
    await _check_org_logo_permission(user, org, org_id, db)

    old_logo = org.get("logo_url")

    await db.organizations.update_one(
        {"id": org_id},
        {"$unset": {"logo_url": ""}, "$set": {"updated_at": _now()}}
    )
    await _audit("organization", org_id, "logo_deleted", user["id"], {})

    if old_logo:
        import asyncio
        try:
            await asyncio.to_thread(_delete_stored, old_logo)
        except Exception:
            pass
    logger.info(f"[ORG_LOGO] Org={org_id} logo deleted by user={user['id']}")

    return {"ok": True}


@router.post("/projects/{project_id}/handover/protocols")
async def create_protocol(project_id: str, request: Request, user: dict = Depends(get_current_user)):
    await _check_handover_management(user, project_id)
    db = get_db()

    body = await request.json()
    unit_id = body.get("unit_id")
    protocol_type = body.get("type")
    if not unit_id or protocol_type not in ("initial", "final"):
        raise HTTPException(status_code=400, detail="unit_id ו-type (initial/final) נדרשים")

    unit = await db.units.find_one({"id": unit_id, "archived": {"$ne": True}}, {"_id": 0})
    if not unit:
        raise HTTPException(status_code=404, detail="דירה לא נמצאה")

    floor = await db.floors.find_one({"id": unit["floor_id"]}, {"_id": 0, "id": 1, "name": 1, "building_id": 1})
    if not floor:
        raise HTTPException(status_code=404, detail="קומה לא נמצאה")

    building = await db.buildings.find_one({"id": floor["building_id"]}, {"_id": 0, "id": 1, "name": 1, "project_id": 1})
    if not building or building.get("project_id") != project_id:
        raise HTTPException(status_code=400, detail="הדירה לא שייכת לפרויקט זה")

    project = await db.projects.find_one({"id": project_id}, {"_id": 0, "id": 1, "name": 1, "org_id": 1})
    if not project:
        raise HTTPException(status_code=404, detail="פרויקט לא נמצא")

    tpl = await _resolve_handover_template(project_id)
    visibility_key = f"visible_in_{protocol_type}"

    sections = []
    for section in tpl.get("sections", []):
        if not section.get(visibility_key, True):
            continue
        items = []
        for item in section.get("items", []):
            items.append({
                "item_id": item["id"],
                "name": item["name"],
                "trade": item.get("trade", "כללי"),
                "status": "not_checked",
                "notes": "",
                "photos": [],
                "defect_id": None,
            })
        sections.append({
            "section_id": section["id"],
            "name": section["name"],
            "items": items,
        })

    org_legal_text = "הנוסח המשפטי ייקבע על ידי הארגון."
    legal_sections_snapshot = []

    tpl_legal = tpl.get("legal_sections", [])
    if tpl_legal:
        for ls in sorted(tpl_legal, key=lambda x: x.get("order", 0)):
            if protocol_type in ls.get("applies_to", []):
                legal_sections_snapshot.append({
                    "id": ls["id"],
                    "title": ls["title"],
                    "body": ls["body"],
                    "requires_signature": ls.get("requires_signature", False),
                    "signature_role": ls.get("signature_role"),
                    "requires_both_tenants": ls.get("requires_both_tenants", False),
                    "order": ls.get("order", 0),
                    "edited": False,
                    "signature": None,
                    "signatures": {},
                    "signer_name": None,
                    "signed_at": None,
                })

    if project.get("org_id"):
        org = await db.organizations.find_one({"id": project["org_id"]}, {"_id": 0})
        if org:
            legal_field = f"default_handover_legal_text_{protocol_type}"
            org_legal = org.get(legal_field, "").strip()
            if org_legal:
                org_legal_text = org_legal
            # TODO: Remove org fallback after migration verified
            if not tpl_legal:
                for ls in sorted(org.get("handover_legal_sections", []), key=lambda x: x.get("order", 0)):
                    if protocol_type in ls.get("applies_to", []):
                        legal_sections_snapshot.append({
                            "id": ls["id"],
                            "title": ls["title"],
                            "body": ls["body"],
                            "requires_signature": ls.get("requires_signature", False),
                            "signature_role": ls.get("signature_role"),
                            "requires_both_tenants": ls.get("requires_both_tenants", False),
                            "order": ls.get("order", 0),
                            "edited": False,
                            "signature": None,
                            "signatures": {},
                            "signer_name": None,
                            "signed_at": None,
                        })

    company_name = ""
    company_logo_url = None
    if project.get("org_id"):
        org_doc = await db.organizations.find_one({"id": project["org_id"]}, {"_id": 0, "name": 1, "logo_url": 1})
        if org_doc:
            company_name = org_doc.get("name", "")
            company_logo_url = org_doc.get("logo_url")

    ts = _now()
    protocol_id = str(uuid.uuid4())

    from pymongo import ReturnDocument
    counter_doc = await db.counters.find_one_and_update(
        {"_id": f"handover_seq:{project_id}"},
        {"$inc": {"seq": 1}},
        upsert=True,
        return_document=ReturnDocument.AFTER,
    )
    display_number = counter_doc["seq"]

    protocol_doc = {
        "id": protocol_id,
        "project_id": project_id,
        "building_id": building["id"],
        "floor_id": floor["id"],
        "unit_id": unit_id,
        "type": protocol_type,
        "template_version_id": tpl.get("id"),
        "status": "draft",
        "display_number": display_number,
        "snapshot": {
            "project_name": project.get("name", ""),
            "building_name": building.get("name", ""),
            "floor_name": floor.get("name", ""),
            "unit_name": unit.get("name", unit.get("unit_no", "")),
            "unit_number": unit.get("unit_no", ""),
            "company_name": company_name,
            "company_logo_url": company_logo_url,
        },
        "property_fields_schema": tpl.get("default_property_fields") or [dict(f) for f in HARDCODED_PROPERTY_FIELDS],
        "property_details": {
            f["key"]: None for f in (tpl.get("default_property_fields") or HARDCODED_PROPERTY_FIELDS)
        },
        "tenants": [
            {"name": "", "id_number": "", "phone": "", "email": "", "id_photo_url": None}
        ],
        "meters": {
            "water": {"reading": None, "photo_url": None},
            "electricity": {"reading": None, "photo_url": None},
        } if protocol_type == "final" else None,
        "sections": sections,
        "delivered_items": [dict(item) for item in (tpl.get("default_delivered_items") or DEFAULT_DELIVERED_ITEMS)] if protocol_type == "final" else [],
        "signature_labels": dict(tpl.get("signature_labels") or HARDCODED_SIGNATURE_LABELS),
        "general_notes": {"apartment": "", "storage": "", "parking": ""},
        "legal_text": org_legal_text,
        "legal_text_edited": False,
        "legal_text_edit_log": [],
        "legal_sections": legal_sections_snapshot,
        "signatures": [],
        "pdf_url": None,
        "created_by": user["id"],
        "created_at": ts,
        "updated_at": ts,
        "signed_at": None,
    }

    try:
        _tenant_prefill = None
        if unit_id:
            _tenant_prefill = await db.unit_tenant_data.find_one({
                "project_id": project_id,
                "unit_id": unit_id,
            })
        if not _tenant_prefill:
            _match_building = building.get("name", "")
            _match_floor = str(floor.get("name", ""))
            _match_apt = str(unit.get("name", unit.get("unit_no", "")))
            _tenant_prefill = await db.unit_tenant_data.find_one({
                "project_id": project_id,
                "building_name": _match_building,
                "floor": _match_floor,
                "apartment_number": _match_apt,
            })
        if _tenant_prefill and _tenant_prefill.get("tenant", {}).get("name"):
            _t1 = _tenant_prefill["tenant"]
            _prefill_tenants = [{
                "name": _t1["name"],
                "id_number": _t1.get("id_number", ""),
                "phone": _t1.get("phone", ""),
                "phone_2": _t1.get("phone_2", ""),
                "email": _t1.get("email", ""),
                "id_photo_url": None,
            }]
            _t2 = _tenant_prefill.get("tenant_2")
            if _t2 and _t2.get("name"):
                _prefill_tenants.append({
                    "name": _t2["name"],
                    "id_number": _t2.get("id_number", ""),
                    "phone": _t2.get("phone", ""),
                    "email": _t2.get("email", ""),
                    "id_photo_url": None,
                })
            if _tenant_prefill.get("handover_date"):
                protocol_doc["handover_date"] = _tenant_prefill["handover_date"]
            protocol_doc["tenants"] = _prefill_tenants
    except Exception:
        pass

    try:
        await db.handover_protocols.insert_one(protocol_doc)
    except Exception as e:
        if "duplicate key" in str(e).lower() or "E11000" in str(e):
            raise HTTPException(status_code=409, detail="כבר קיים פרוטוקול מסוג זה עבור דירה זו")
        raise

    await _audit("handover_protocol", protocol_id, "created", user["id"], {
        "project_id": project_id, "unit_id": unit_id, "type": protocol_type,
    })

    protocol_doc.pop("_id", None)
    logger.info(f"[HANDOVER] Created protocol={protocol_id} type={protocol_type} unit={unit_id} project={project_id}")
    return protocol_doc


@router.get("/projects/{project_id}/handover/protocols")
async def list_protocols(
    project_id: str,
    user: dict = Depends(get_current_user),
    building_id: str = Query(default=None),
    floor_id: str = Query(default=None),
    unit_id: str = Query(default=None),
    type: str = Query(default=None),
    status: str = Query(default=None),
):
    await _check_handover_access(user, project_id)
    db = get_db()

    query = {"project_id": project_id}
    if building_id:
        query["building_id"] = building_id
    if floor_id:
        query["floor_id"] = floor_id
    if unit_id:
        query["unit_id"] = unit_id
    if type and type in ("initial", "final"):
        query["type"] = type
    if status:
        query["status"] = status

    projection = {
        "_id": 0, "id": 1, "project_id": 1, "building_id": 1, "floor_id": 1,
        "unit_id": 1, "type": 1, "status": 1, "snapshot": 1,
        "created_at": 1, "updated_at": 1, "signed_at": 1, "created_by": 1,
    }

    protocols = await db.handover_protocols.find(query, projection).sort("created_at", -1).to_list(1000)
    return protocols


@router.get("/projects/{project_id}/handover/protocols/{protocol_id}")
async def get_protocol(project_id: str, protocol_id: str, user: dict = Depends(get_current_user)):
    await _check_handover_access(user, project_id)
    protocol = await _get_protocol_or_404(protocol_id, project_id)

    version_id = protocol.get("template_version_id")
    if version_id:
        db = get_db()
        tpl = await db.qc_templates.find_one(
            {"id": version_id},
            {"_id": 0, "version": 1, "family_id": 1}
        )
        if tpl:
            protocol["template_snapshot_version"] = tpl.get("version")
            project = await db.projects.find_one(
                {"id": project_id},
                {"_id": 0, "handover_template_version_id": 1}
            )
            if project and project.get("handover_template_version_id"):
                current_tpl = await db.qc_templates.find_one(
                    {"id": project["handover_template_version_id"]},
                    {"_id": 0, "version": 1}
                )
                if current_tpl:
                    protocol["project_current_version"] = current_tpl.get("version")

    return protocol


@router.put("/projects/{project_id}/handover/protocols/{protocol_id}")
async def update_protocol(project_id: str, protocol_id: str, request: Request, user: dict = Depends(get_current_user)):
    await _check_handover_management(user, project_id)
    protocol = await _get_protocol_or_404(protocol_id, project_id)
    _check_not_locked(protocol)

    body = await request.json()
    db = get_db()
    ts = _now()
    update_fields = {"updated_at": ts}

    for field in ("property_details", "tenants", "meters", "delivered_items", "general_notes", "signature_labels"):
        if field in body:
            update_fields[field] = body[field]

    if "property_details" in update_fields:
        pd = update_fields["property_details"]
        if isinstance(pd, dict):
            import unicodedata
            model_val = pd.get("model")
            if model_val and isinstance(model_val, str) and re.match(r'^[A-Za-z0-9\-áàâãéèêëíìîïóòôõúùûü\s]+$', model_val):
                cleaned = unicodedata.normalize('NFKD', model_val)
                cleaned = cleaned.encode('ascii', 'ignore').decode('ascii').strip()
                if cleaned:
                    pd["model"] = cleaned

    if "legal_text" in body and body["legal_text"] != protocol.get("legal_text"):
        update_fields["legal_text"] = body["legal_text"]
        update_fields["legal_text_edited"] = True
        log_entry = {
            "edited_by": user["id"],
            "edited_at": ts,
            "previous_text": protocol.get("legal_text", ""),
        }
        await db.handover_protocols.update_one(
            {"id": protocol_id, "project_id": project_id},
            {"$push": {"legal_text_edit_log": log_entry}}
        )

    await db.handover_protocols.update_one({"id": protocol_id, "project_id": project_id}, {"$set": update_fields})
    updated = await db.handover_protocols.find_one({"id": protocol_id, "project_id": project_id}, {"_id": 0})
    return updated


VALID_SEVERITIES = {"critical", "normal", "cosmetic"}
TERMINAL_TASK_STATUSES = ("closed", "done", "cancelled")

STATUS_LABELS = {
    "defective": "לא תקין",
    "partial": "חלקי",
    "ok": "תקין",
    "not_relevant": "לא רלוונטי",
    "not_checked": "לא נבדק",
}

@router.patch("/projects/{project_id}/handover/protocols/{protocol_id}/sections/{section_id}/batch-items")
async def batch_update_items(
    project_id: str, protocol_id: str, section_id: str,
    request: Request, user: dict = Depends(get_current_user),
):
    await _check_handover_management(user, project_id)
    protocol = await _get_protocol_or_404(protocol_id, project_id)
    _check_not_locked(protocol)

    body = await request.json()
    item_ids = body.get("item_ids")
    new_status = body.get("status")

    if not item_ids or not isinstance(item_ids, list):
        raise HTTPException(status_code=400, detail="item_ids חייב להיות רשימה")
    if new_status not in ("ok", "not_checked", "not_relevant"):
        raise HTTPException(status_code=400, detail="סטטוס חייב להיות ok, not_relevant או not_checked")

    db = get_db()
    ts = _now()

    target_section = None
    for section in protocol.get("sections", []):
        if section["section_id"] == section_id:
            target_section = section
            break

    if not target_section:
        raise HTTPException(status_code=404, detail="חלק לא נמצא בפרוטוקול")

    item_id_set = set(item_ids)
    eligible_items = []
    skipped = 0

    for item in target_section.get("items", []):
        if item["item_id"] not in item_id_set:
            continue
        cur_status = item.get("status") or "not_checked"
        has_defect = bool(item.get("defect_id"))

        if new_status in ("ok", "not_relevant"):
            if cur_status in (None, "not_checked", ""):
                if cur_status != new_status:
                    eligible_items.append(item)
                else:
                    skipped += 1
            else:
                skipped += 1
        elif new_status == "not_checked":
            if has_defect:
                skipped += 1
            elif cur_status != "not_checked":
                eligible_items.append(item)
            else:
                skipped += 1

    if not eligible_items:
        return {"updated": 0, "skipped": skipped, "items": []}

    update_ops = {"$set": {"updated_at": ts}}
    if protocol.get("status") == "draft":
        update_ops["$set"]["status"] = "in_progress"

    changed_items = []
    for item in eligible_items:
        idx = next(
            (i for i, it in enumerate(target_section["items"]) if it["item_id"] == item["item_id"]),
            None,
        )
        if idx is not None:
            update_ops["$set"][f"sections.$[sec].items.{idx}.status"] = new_status
            changed_items.append({"item_id": item["item_id"], "status": new_status})

    array_filters = [{"sec.section_id": section_id}]

    await db.handover_protocols.update_one(
        {"id": protocol_id, "project_id": project_id},
        update_ops,
        array_filters=array_filters,
    )

    return {"updated": len(changed_items), "skipped": skipped, "items": changed_items}


@router.put("/projects/{project_id}/handover/protocols/{protocol_id}/sections/{section_id}/items/{item_id}")
async def update_item(
    project_id: str, protocol_id: str, section_id: str, item_id: str,
    request: Request, user: dict = Depends(get_current_user),
):
    await _check_handover_management(user, project_id)
    protocol = await _get_protocol_or_404(protocol_id, project_id)
    _check_not_locked(protocol)

    body = await request.json()
    db = get_db()
    ts = _now()

    target_section = None
    target_item = None
    for section in protocol.get("sections", []):
        if section["section_id"] != section_id:
            continue
        target_section = section
        for item in section.get("items", []):
            if item["item_id"] != item_id:
                continue
            target_item = item
            break
        break

    if not target_section:
        raise HTTPException(status_code=404, detail="חלק לא נמצא בפרוטוקול")
    if not target_item:
        raise HTTPException(status_code=404, detail="פריט לא נמצא בחלק")

    new_status = body.get("status")
    notes = body.get("notes")
    description = body.get("description")
    severity = body.get("severity")
    photos = body.get("photos")
    skip_photo_reason = body.get("skip_photo_reason")
    photos_pending_count = body.get("photos_pending_count", 0)

    if photos is not None and not isinstance(photos, list):
        raise HTTPException(status_code=400, detail="photos חייב להיות רשימה")

    is_defect_status = new_status in ("defective", "partial")

    if is_defect_status:
        if severity and severity not in VALID_SEVERITIES:
            raise HTTPException(status_code=400, detail=f"חומרה לא חוקית: {severity}")
        if not severity:
            raise HTTPException(status_code=400, detail="חובה לבחור חומרה עבור סטטוס זה")
        if new_status == "defective":
            if not description or not description.strip():
                raise HTTPException(status_code=400, detail="תיאור חובה עבור סטטוס 'לא תקין'")
            has_photos = (photos and len(photos) > 0) or photos_pending_count > 0
            if not has_photos and not skip_photo_reason:
                raise HTTPException(status_code=400, detail="נדרשת תמונה או סיבת דילוג עבור סטטוס 'לא תקין'")

    update_ops = {"$set": {"updated_at": ts}}
    has_item_change = False

    if new_status is not None:
        if new_status not in VALID_ITEM_STATUSES:
            raise HTTPException(status_code=400, detail=f"סטטוס לא חוקי: {new_status}")
        update_ops["$set"]["sections.$[sec].items.$[itm].status"] = new_status
        has_item_change = True

    if notes is not None:
        update_ops["$set"]["sections.$[sec].items.$[itm].notes"] = notes
        has_item_change = True

    if description is not None:
        update_ops["$set"]["sections.$[sec].items.$[itm].description"] = description
        has_item_change = True

    if severity is not None:
        update_ops["$set"]["sections.$[sec].items.$[itm].severity"] = severity
        has_item_change = True

    if photos is not None:
        update_ops["$set"]["sections.$[sec].items.$[itm].photos"] = photos
        has_item_change = True

    if skip_photo_reason is not None:
        update_ops["$set"]["sections.$[sec].items.$[itm].skip_photo_reason"] = skip_photo_reason
        has_item_change = True

    if not has_item_change:
        raise HTTPException(status_code=400, detail="לא סופקו שדות לעדכון")

    if protocol.get("status") == "draft":
        update_ops["$set"]["status"] = "in_progress"

    array_filters = [
        {"sec.section_id": section_id},
        {"itm.item_id": item_id},
    ]

    defect_created = False
    defect_id = None

    if is_defect_status:
        source = f"handover_{protocol['type']}"
        section_name = target_section.get("name", "")
        item_name = target_item.get("name", "")
        status_label = STATUS_LABELS.get(new_status, new_status)
        defect_title = f"{section_name} > {item_name} — {status_label}"
        defect_description = (description or "").strip()
        defect_trade = target_item.get("trade", "כללי")
        defect_photos = list(photos or [])
        defect_severity = severity or "normal"

        existing_defect = None
        existing_defect_id = target_item.get("defect_id")
        if existing_defect_id:
            existing_defect = await db.tasks.find_one({"id": existing_defect_id}, {"_id": 0, "id": 1, "status": 1})

        if not existing_defect or existing_defect.get("status") in TERMINAL_TASK_STATUSES:
            existing_defect = await db.tasks.find_one({
                "handover_protocol_id": protocol["id"],
                "handover_section_id": section_id,
                "handover_item_id": item_id,
                "status": {"$nin": list(TERMINAL_TASK_STATUSES)},
            }, {"_id": 0, "id": 1, "status": 1})

        if existing_defect and existing_defect.get("status") not in TERMINAL_TASK_STATUSES:
            defect_id = existing_defect["id"]
            await db.tasks.update_one(
                {"id": defect_id},
                {"$set": {
                    "title": defect_title,
                    "description": defect_description,
                    "severity": defect_severity,
                    "priority": _severity_to_priority(defect_severity),
                    "proof_urls": defect_photos,
                    "attachments_count": len(defect_photos),
                    "skip_photo_reason": skip_photo_reason,
                    "updated_at": ts,
                }}
            )
            if defect_id != existing_defect_id:
                update_ops["$set"]["sections.$[sec].items.$[itm].defect_id"] = defect_id
            logger.info(f"[HANDOVER] Updated existing defect={defect_id} for item={item_id}")
        else:
            from pymongo.errors import DuplicateKeyError
            try:
                defect_id = await _create_handover_defect(
                    db, ts, user, project_id, protocol, section_id, item_id,
                    defect_title, defect_description, defect_trade, defect_severity,
                    defect_photos, skip_photo_reason, source,
                )
                defect_created = True
                logger.info(f"[HANDOVER] Created defect={defect_id} for item={item_id}")
            except DuplicateKeyError:
                race_defect = await db.tasks.find_one({
                    "handover_protocol_id": protocol["id"],
                    "handover_section_id": section_id,
                    "handover_item_id": item_id,
                    "status": {"$nin": list(TERMINAL_TASK_STATUSES)},
                }, {"_id": 0, "id": 1})
                if race_defect:
                    defect_id = race_defect["id"]
                    await db.tasks.update_one(
                        {"id": defect_id},
                        {"$set": {
                            "title": defect_title,
                            "description": defect_description,
                            "severity": defect_severity,
                            "priority": _severity_to_priority(defect_severity),
                            "proof_urls": defect_photos,
                            "attachments_count": len(defect_photos),
                            "skip_photo_reason": skip_photo_reason,
                            "updated_at": ts,
                        }}
                    )
                    logger.info(f"[HANDOVER] DuplicateKeyError race — updated existing defect={defect_id} for item={item_id}")
                else:
                    raise
            update_ops["$set"]["sections.$[sec].items.$[itm].defect_id"] = defect_id

    await db.handover_protocols.update_one(
        {"id": protocol_id, "project_id": project_id},
        update_ops,
        array_filters=array_filters,
    )

    updated = await db.handover_protocols.find_one({"id": protocol_id, "project_id": project_id}, {"_id": 0})

    updated_item = None
    for sec in updated.get("sections", []):
        if sec["section_id"] != section_id:
            continue
        for itm in sec.get("items", []):
            if itm["item_id"] == item_id:
                updated_item = itm
                break
        break

    return {
        "protocol": updated,
        "item": updated_item,
        "defect_created": defect_created,
        "defect_id": defect_id,
    }


def _severity_to_priority(severity):
    return {"critical": "critical", "normal": "medium", "cosmetic": "low"}.get(severity, "medium")


async def _create_handover_defect(
    db, ts, user, project_id, protocol, section_id, item_id,
    title, description, trade, severity, photos, skip_photo_reason, source,
):
    from pymongo import ReturnDocument
    task_id = str(uuid.uuid4())

    counter_doc = await db.counters.find_one_and_update(
        {"_id": f"task_seq:{project_id}"},
        {"$inc": {"seq": 1}},
        upsert=True,
        return_document=ReturnDocument.AFTER,
    )
    display_number = counter_doc["seq"]

    task_doc = {
        "id": task_id,
        "project_id": project_id,
        "building_id": protocol.get("building_id"),
        "floor_id": protocol.get("floor_id"),
        "unit_id": protocol.get("unit_id"),
        "title": title,
        "description": description,
        "category": trade,
        "severity": severity,
        "priority": _severity_to_priority(severity),
        "status": "open",
        "company_id": None,
        "assignee_id": None,
        "due_date": None,
        "created_by": user["id"],
        "created_at": ts,
        "updated_at": ts,
        "short_ref": task_id[:8],
        "display_number": display_number,
        "attachments_count": len(photos),
        "comments_count": 0,
        "source": source,
        "handover_protocol_id": protocol["id"],
        "handover_section_id": section_id,
        "handover_item_id": item_id,
        "proof_urls": photos,
        "skip_photo_reason": skip_photo_reason,
    }

    await db.tasks.insert_one(task_doc)

    await db.task_status_history.insert_one({
        "id": str(uuid.uuid4()),
        "task_id": task_id,
        "old_status": None,
        "new_status": "open",
        "changed_by": user["id"],
        "note": f"ליקוי ממסירה: {title}",
        "created_at": ts,
    })

    await _audit("handover_defect", task_id, "created_from_handover", user["id"], {
        "protocol_id": protocol["id"], "section_id": section_id, "item_id": item_id, "source": source,
    })

    return task_id


@router.post("/projects/{project_id}/handover/protocols/{protocol_id}/items/{item_id}/create-defect")
async def create_defect_from_item(
    project_id: str, protocol_id: str, item_id: str,
    user: dict = Depends(get_current_user),
):
    await _check_handover_management(user, project_id)
    protocol = await _get_protocol_or_404(protocol_id, project_id)
    _check_not_locked(protocol)

    target_item = None
    target_section_name = None
    for section in protocol.get("sections", []):
        for item in section.get("items", []):
            if item["item_id"] == item_id:
                target_item = item
                target_section_name = section["name"]
                break
        if target_item:
            break

    if not target_item:
        raise HTTPException(status_code=404, detail="פריט לא נמצא בפרוטוקול")

    if target_item.get("defect_id"):
        raise HTTPException(status_code=409, detail="ליקוי כבר קיים עבור פריט זה")

    db = get_db()
    ts = _now()
    task_id = str(uuid.uuid4())

    source = f"handover_{protocol['type']}"

    target_section_id = None
    for section in protocol.get("sections", []):
        for item in section.get("items", []):
            if item["item_id"] == item_id:
                target_section_id = section["section_id"]
                break
        if target_section_id:
            break

    link_result = await db.handover_protocols.update_one(
        {
            "id": protocol_id,
            "project_id": project_id,
            "sections.items": {"$elemMatch": {"item_id": item_id, "defect_id": None}},
        },
        {"$set": {
            "sections.$[sec].items.$[itm].defect_id": task_id,
            "updated_at": ts,
        }},
        array_filters=[
            {"sec.section_id": target_section_id},
            {"itm.item_id": item_id},
        ],
    )
    if link_result.modified_count == 0:
        raise HTTPException(status_code=409, detail="ליקוי כבר קיים עבור פריט זה")

    from pymongo import ReturnDocument
    counter_doc = await db.counters.find_one_and_update(
        {"_id": f"task_seq:{project_id}"},
        {"$inc": {"seq": 1}},
        upsert=True,
        return_document=ReturnDocument.AFTER,
    )
    display_number = counter_doc["seq"]

    task_doc = {
        "id": task_id,
        "project_id": project_id,
        "building_id": protocol.get("building_id"),
        "floor_id": protocol.get("floor_id"),
        "unit_id": protocol.get("unit_id"),
        "title": f"{target_item['name']} — {target_section_name}",
        "description": target_item.get("notes", ""),
        "category": target_item.get("trade", "general"),
        "priority": "medium",
        "status": "open",
        "company_id": None,
        "assignee_id": None,
        "due_date": None,
        "created_by": user["id"],
        "created_at": ts,
        "updated_at": ts,
        "short_ref": task_id[:8],
        "display_number": display_number,
        "attachments_count": len(target_item.get("photos", [])),
        "comments_count": 0,
        "source": source,
        "handover_protocol_id": protocol_id,
        "handover_item_id": item_id,
        "proof_urls": list(target_item.get("photos", [])),
    }

    await db.tasks.insert_one(task_doc)

    await db.task_status_history.insert_one({
        "id": str(uuid.uuid4()),
        "task_id": task_id,
        "old_status": None,
        "new_status": "open",
        "changed_by": user["id"],
        "note": f"ליקוי ממסירה: {target_item['name']} — {target_section_name}",
        "created_at": ts,
    })

    await _audit("handover_defect", task_id, "created_from_handover", user["id"], {
        "protocol_id": protocol_id, "item_id": item_id, "source": source,
    })

    task_doc.pop("_id", None)
    logger.info(f"[HANDOVER] Created defect={task_id} from protocol={protocol_id} item={item_id}")
    return task_doc


async def _get_user_project_role(user: dict, project_id: str) -> str:
    if _is_super_admin(user):
        return "super_admin"
    db = get_db()
    membership = await db.project_memberships.find_one(
        {"user_id": user["id"], "project_id": project_id}
    )
    if not membership:
        return None
    return membership.get("role")


def _check_signature_role_auth(user_role: str, signature_role: str):
    if user_role == "super_admin":
        return
    if signature_role == "manager":
        if user_role not in ("project_manager", "owner", "management_team"):
            raise HTTPException(status_code=403, detail="רק מנהל פרויקט או מפקח יכול לחתום בתפקיד זה")
    elif signature_role == "contractor_rep":
        if user_role != "contractor":
            raise HTTPException(status_code=403, detail="רק נציג קבלן יכול לחתום בתפקיד זה")
    elif signature_role in ("tenant", "tenant_2"):
        if user_role not in ("project_manager", "owner", "contractor", "management_team"):
            raise HTTPException(status_code=403, detail="רק מנהל פרויקט או נציג קבלן יכול להחתים דייר")


@router.put("/projects/{project_id}/handover/protocols/{protocol_id}/signatures/{role}")
async def sign_role(
    project_id: str, protocol_id: str, role: str,
    signer_name: str = Form(...),
    signature_type: str = Form(...),
    typed_name: str = Form(None),
    id_number: str = Form(None),
    signature_image: UploadFile = File(None),
    user: dict = Depends(get_current_user),
):
    if role not in VALID_SIGNATURE_ROLES:
        raise HTTPException(status_code=400, detail=f"תפקיד לא חוקי: {role}")

    user_role = await _get_user_project_role(user, project_id)
    if not user_role:
        raise HTTPException(status_code=403, detail="אין לך גישה לפרויקט זה")
    _check_signature_role_auth(user_role, role)

    protocol = await _get_protocol_or_404(protocol_id, project_id)
    _check_not_locked(protocol)

    checked, total, pct = _calculate_completion(protocol)
    if pct < SIGNING_COMPLETION_THRESHOLD:
        raise HTTPException(
            status_code=400,
            detail=f"יש להשלים לפחות 90% מסעיפי הבדיקה לפני חתימה (הושלמו {checked} מתוך {total})"
        )

    existing_sigs = _normalize_signatures(protocol)
    if role in existing_sigs and existing_sigs[role]:
        raise HTTPException(status_code=409, detail="חתימה כבר קיימת לתפקיד זה")

    if signature_type not in ("canvas", "typed"):
        raise HTTPException(status_code=400, detail="סוג חתימה לא חוקי — canvas או typed")

    signer_name = signer_name.strip()
    if not signer_name:
        raise HTTPException(status_code=400, detail="שם החותם נדרש")

    db = get_db()
    ts = _now()

    id_number_val = (id_number or "").strip() or None

    sig_data = {
        "type": signature_type,
        "signer_name": signer_name,
        "id_number": id_number_val,
        "signer_user_id": user["id"],
        "signed_at": ts,
        "ip_address": None,
    }

    if signature_type == "canvas":
        if not signature_image:
            raise HTTPException(status_code=400, detail="נדרש קובץ חתימה לסוג canvas")
        image_data = await signature_image.read()
        if not image_data or len(image_data) < 100:
            raise HTTPException(status_code=400, detail="קובץ חתימה ריק או לא תקין")
        s3_key = f"signatures/{protocol_id}/{role}.png"
        stored_ref = save_bytes(image_data, s3_key, "image/png")
        sig_data["image_key"] = stored_ref
    else:
        typed_name_val = (typed_name or "").strip()
        if not typed_name_val:
            raise HTTPException(status_code=400, detail="שם מלא נדרש לחתימה מוקלדת")
        sig_data["typed_name"] = typed_name_val

    existing_sigs[role] = sig_data

    new_status, new_locked = _recalculate_signature_status({**protocol, "signatures": existing_sigs})

    raw_sigs = protocol.get("signatures")
    if isinstance(raw_sigs, list):
        await db.handover_protocols.update_one(
            {"id": protocol_id, "project_id": project_id},
            {"$set": {"signatures": {}}}
        )

    update_set = {
        f"signatures.{role}": sig_data,
        "status": new_status,
        "locked": new_locked,
        "updated_at": ts,
    }
    if new_locked:
        update_set["signed_at"] = ts

    await db.handover_protocols.update_one(
        {"id": protocol_id, "project_id": project_id},
        {"$set": update_set}
    )

    await _audit("handover_protocol", protocol_id, f"signed_{role}", user["id"], {
        "project_id": project_id,
        "signature_role": role,
        "signature_type": signature_type,
        "signer_name": signer_name,
    })

    logger.info(f"[HANDOVER] Protocol={protocol_id} role={role} signed by user={user['id']} type={signature_type}")
    updated = await db.handover_protocols.find_one({"id": protocol_id}, {"_id": 0})
    return updated


@router.delete("/projects/{project_id}/handover/protocols/{protocol_id}/signatures/{role}")
async def delete_signature(
    project_id: str, protocol_id: str, role: str,
    user: dict = Depends(get_current_user),
):
    if role not in VALID_SIGNATURE_ROLES:
        raise HTTPException(status_code=400, detail=f"תפקיד לא חוקי: {role}")

    user_role = await _get_user_project_role(user, project_id)
    if not user_role:
        raise HTTPException(status_code=403, detail="אין לך גישה לפרויקט זה")
    if user_role not in ("project_manager", "owner", "super_admin", "management_team"):
        raise HTTPException(status_code=403, detail="רק מנהל פרויקט יכול למחוק חתימות")

    protocol = await _get_protocol_or_404(protocol_id, project_id)
    _check_not_locked(protocol)

    existing_sigs = _normalize_signatures(protocol)
    if role not in existing_sigs or not existing_sigs[role]:
        raise HTTPException(status_code=404, detail="אין חתימה לתפקיד זה")

    db = get_db()
    ts = _now()

    raw_sigs = protocol.get("signatures")
    if isinstance(raw_sigs, list):
        await db.handover_protocols.update_one(
            {"id": protocol_id, "project_id": project_id},
            {"$set": {"signatures": {}}}
        )

    await db.handover_protocols.update_one(
        {"id": protocol_id, "project_id": project_id},
        {"$unset": {f"signatures.{role}": ""}, "$set": {"updated_at": ts}}
    )

    refreshed = await db.handover_protocols.find_one({"id": protocol_id, "project_id": project_id}, {"_id": 0})
    new_status, new_locked = _recalculate_signature_status(refreshed)

    await db.handover_protocols.update_one(
        {"id": protocol_id, "project_id": project_id},
        {"$set": {"status": new_status, "locked": new_locked, "updated_at": ts}}
    )

    await _audit("handover_protocol", protocol_id, f"signature_deleted_{role}", user["id"], {
        "project_id": project_id, "deleted_role": role,
    })

    logger.info(f"[HANDOVER] Protocol={protocol_id} signature deleted for role={role} by user={user['id']}")
    updated = await db.handover_protocols.find_one({"id": protocol_id}, {"_id": 0})
    return updated


@router.get("/projects/{project_id}/handover/protocols/{protocol_id}/signatures/{role}/image")
async def get_signature_image(
    project_id: str, protocol_id: str, role: str,
    user: dict = Depends(get_current_user),
):
    await _check_handover_access(user, project_id)

    if role not in VALID_SIGNATURE_ROLES:
        raise HTTPException(status_code=400, detail=f"תפקיד לא חוקי: {role}")

    protocol = await _get_protocol_or_404(protocol_id, project_id)
    sigs = _normalize_signatures(protocol)

    if role not in sigs or not sigs[role]:
        raise HTTPException(status_code=404, detail="אין חתימה לתפקיד זה")

    sig = sigs[role]
    if sig.get("type") == "typed":
        return {"type": "typed", "typed_name": sig.get("typed_name", ""), "signer_name": sig.get("signer_name", "")}

    image_key = sig.get("image_key", "")
    if image_key:
        url = generate_url(image_key)
        return {"type": "canvas", "url": url, "signer_name": sig.get("signer_name", "")}

    raise HTTPException(status_code=404, detail="תמונת חתימה לא נמצאה")


@router.get("/projects/{project_id}/handover/protocols/{protocol_id}/pdf")
async def download_protocol_pdf(
    project_id: str, protocol_id: str,
    user: dict = Depends(get_current_user),
):
    import asyncio as _asyncio
    import re as _re
    from fastapi.responses import Response

    db = get_db()
    if not _is_super_admin(user):
        membership = await db.project_memberships.find_one(
            {"user_id": user["id"], "project_id": project_id}
        )
        if not membership or membership.get("role") not in {"owner", "project_manager", "management_team"}:
            raise HTTPException(status_code=403, detail="אין הרשאה להורדת PDF")

    protocol = await db.handover_protocols.find_one(
        {"id": protocol_id, "project_id": project_id}, {"_id": 0}
    )
    if not protocol:
        raise HTTPException(status_code=404, detail="פרוטוקול לא נמצא")

    if not protocol.get("locked"):
        raise HTTPException(status_code=400, detail="ניתן להוריד PDF רק לפרוטוקול חתום")

    from services.handover_pdf_service import generate_handover_pdf

    try:
        pdf_bytes = await _asyncio.wait_for(
            generate_handover_pdf(protocol, db),
            timeout=60
        )
    except _asyncio.TimeoutError:
        logger.error(f"[HANDOVER] PDF generation timeout for protocol={protocol_id}")
        raise HTTPException(status_code=504, detail="PDF generation timeout")
    except Exception as e:
        import traceback
        logger.error(f"[HANDOVER] PDF generation failed for protocol={protocol_id}: {e}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail="שגיאה ביצירת PDF, נסו שוב מאוחר יותר")

    from urllib.parse import quote as _quote

    snapshot = protocol.get("snapshot", {})
    apt = snapshot.get("unit_name", "") or snapshot.get("unit_number", "") or "unit"
    floor = snapshot.get("floor_name", "") or "floor"
    apt_safe = _re.sub(r'[^\w\-.]', '_', apt).strip('_') or "unit"
    floor_safe = _re.sub(r'[^\w\-.]', '_', floor).strip('_') or "floor"

    filename = f"protocol_mesira_{apt_safe}_{floor_safe}.pdf"
    safe_filename = _re.sub(r'[^a-zA-Z0-9_\-.]', '_', filename)
    content_disposition = f"attachment; filename=\"{safe_filename}\"; filename*=UTF-8''{_quote(filename)}"

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": content_disposition,
        },
    )


@router.post("/projects/{project_id}/handover/protocols/{protocol_id}/reopen")
async def reopen_protocol(project_id: str, protocol_id: str, request: Request, user: dict = Depends(get_current_user)):
    if not _is_super_admin(user):
        raise HTTPException(status_code=403, detail="רק מנהל מערכת יכול לפתוח מחדש פרוטוקול חתום")

    protocol = await _get_protocol_or_404(protocol_id, project_id)
    if protocol.get("locked") is not True and protocol.get("status") not in ("signed", "completed"):
        raise HTTPException(status_code=400, detail="ניתן לפתוח מחדש רק פרוטוקול חתום")

    body = await request.json()
    reason = body.get("reason", "").strip()
    if not reason:
        raise HTTPException(status_code=400, detail="נדרשת סיבה לפתיחה מחדש")

    db = get_db()
    ts = _now()

    sig_count = _count_signatures(protocol)
    if sig_count >= 1:
        new_status = "partially_signed"
    else:
        new_status = "in_progress"

    await db.handover_protocols.update_one(
        {"id": protocol_id, "project_id": project_id},
        {"$set": {
            "status": new_status,
            "locked": False,
            "updated_at": ts,
        },
        "$push": {
            "reopen_log": {
                "reopened_by": user["id"],
                "reopened_at": ts,
                "reason": reason,
            }
        }}
    )

    await _audit("handover_protocol", protocol_id, "reopened", user["id"], {
        "project_id": project_id, "reason": reason,
    })

    logger.info(f"[HANDOVER] Protocol={protocol_id} reopened by user={user['id']} reason={reason}")
    updated = await db.handover_protocols.find_one({"id": protocol_id}, {"_id": 0})
    return updated


@router.get("/projects/{project_id}/handover/overview")
async def handover_overview(
    project_id: str,
    building: str = Query(None),
    status: str = Query(None),
    type: str = Query(None),
    user: dict = Depends(get_current_user),
):
    await _check_handover_access(user, project_id)
    db = get_db()

    protocol_type_filter = type if type in ("initial", "final") else None

    structure_pipeline = [
        {"$match": {"project_id": project_id, "archived": {"$ne": True}}},
        {"$lookup": {
            "from": "floors",
            "let": {"bid": "$id"},
            "pipeline": [
                {"$match": {"$expr": {"$eq": ["$building_id", "$$bid"]}, "archived": {"$ne": True}}},
                {"$project": {"_id": 0, "id": 1, "building_id": 1, "name": 1, "floor_number": 1, "sort_index": 1}},
            ],
            "as": "floors",
        }},
        {"$unwind": {"path": "$floors", "preserveNullAndEmptyArrays": False}},
        {"$lookup": {
            "from": "units",
            "let": {"fid": "$floors.id"},
            "pipeline": [
                {"$match": {"$expr": {"$eq": ["$floor_id", "$$fid"]}, "archived": {"$ne": True}}},
                {"$project": {"_id": 0, "id": 1, "floor_id": 1, "building_id": 1, "unit_no": 1, "display_label": 1, "sort_index": 1, "spare_tiles_count": 1, "spare_tiles": 1}},
            ],
            "as": "units",
        }},
        {"$unwind": {"path": "$units", "preserveNullAndEmptyArrays": False}},
        {"$lookup": {
            "from": "handover_protocols",
            "let": {"uid": "$units.id"},
            "pipeline": [
                {"$match": {
                    "$expr": {"$and": [
                        {"$eq": ["$unit_id", "$$uid"]},
                        {"$eq": ["$project_id", project_id]},
                    ]},
                    **({"type": protocol_type_filter} if protocol_type_filter else {}),
                }},
                {"$project": {"_id": 0, "id": 1, "unit_id": 1, "type": 1, "status": 1, "locked": 1, "signatures": 1}},
            ],
            "as": "protocols",
        }},
        {"$project": {
            "_id": 0,
            "building_id": "$id",
            "building_name": "$name",
            "floor_id": "$floors.id",
            "floor_name": "$floors.name",
            "floor_number": "$floors.floor_number",
            "floor_sort_index": "$floors.sort_index",
            "unit_id": "$units.id",
            "unit_no": "$units.unit_no",
            "unit_display_label": "$units.display_label",
            "unit_sort_index": "$units.sort_index",
            "spare_tiles_count": "$units.spare_tiles_count",
            "spare_tiles": "$units.spare_tiles",
            "protocols": 1,
        }},
    ]

    rows = await db.buildings.aggregate(structure_pipeline).to_list(50000)

    all_building_names = sorted(set(r["building_name"] for r in rows))

    if building:
        rows = [r for r in rows if r["building_name"] == building]

    all_protocol_ids = []
    all_protocol_types = set()
    for r in rows:
        for p in r.get("protocols", []):
            all_protocol_ids.append(p["id"])
            all_protocol_types.add(p["type"])

    defect_counts = {}
    if all_protocol_ids:
        defect_pipeline = [
            {"$match": {
                "handover_protocol_id": {"$in": all_protocol_ids},
                "source": {"$in": ["handover_initial", "handover_final"]},
                "status": {"$nin": ["closed", "done", "cancelled"]},
            }},
            {"$group": {"_id": "$handover_protocol_id", "count": {"$sum": 1}}},
        ]
        async for doc in db.tasks.aggregate(defect_pipeline):
            defect_counts[doc["_id"]] = doc["count"]

    summary_signed = 0
    summary_partially_signed = 0
    summary_pending = 0
    summary_not_started = 0

    building_data = {}

    status_values = []
    if status:
        status_values = [s.strip() for s in status.split(",") if s.strip()]

    for r in rows:
        bid = r["building_id"]
        bname = r["building_name"]
        fid = r["floor_id"]
        unit_protocols = r.get("protocols", [])

        final_proto = None
        initial_proto = None
        for p in unit_protocols:
            if p["type"] == "final":
                final_proto = p
            elif p["type"] == "initial":
                initial_proto = p

        determining_proto = final_proto if final_proto else initial_proto
        effective_status = determining_proto["status"] if determining_proto else "none"

        if status_values and effective_status not in status_values:
            continue

        unit_open_defects = 0
        for p in unit_protocols:
            unit_open_defects += defect_counts.get(p["id"], 0)

        proto_list = []
        for p in unit_protocols:
            p_sigs = _normalize_signatures(p)
            p_sig_count = sum(1 for role in VALID_SIGNATURE_ROLES if role in p_sigs and p_sigs[role])
            proto_list.append({
                "id": p["id"],
                "type": p["type"],
                "status": p["status"],
                "locked": p.get("locked", False),
                "signature_count": p_sig_count,
                "signatures_total": len(VALID_SIGNATURE_ROLES),
            })

        if bid not in building_data:
            building_data[bid] = {
                "building_id": bid,
                "building_name": bname,
                "total_units": 0,
                "signed_count": 0,
                "progress_pct": 0,
                "floors": {},
            }

        building_data[bid]["total_units"] += 1

        if effective_status == "signed":
            summary_signed += 1
            building_data[bid]["signed_count"] += 1
        elif effective_status == "partially_signed":
            summary_partially_signed += 1
        elif effective_status in ("draft", "in_progress"):
            summary_pending += 1
        elif effective_status == "none":
            summary_not_started += 1

        floor_name = r.get("floor_name", "")
        try:
            floor_num = int(floor_name)
        except (ValueError, TypeError):
            floor_num = r.get("floor_number") or 0

        floor_sort = r.get("floor_sort_index") or 0

        if fid not in building_data[bid]["floors"]:
            building_data[bid]["floors"][fid] = {
                "floor": floor_num,
                "floor_name": floor_name,
                "floor_sort": floor_sort,
                "units": [],
            }

        raw_spare = r.get("spare_tiles_count")
        spare_tiles_count = raw_spare if isinstance(raw_spare, int) else None
        spare_tiles = r.get("spare_tiles")
        if not isinstance(spare_tiles, list):
            spare_tiles = None

        building_data[bid]["floors"][fid]["units"].append({
            "unit_id": r["unit_id"],
            "apartment_number": r.get("unit_display_label") or r.get("unit_no", ""),
            "status": effective_status,
            "open_defects": unit_open_defects,
            "spare_tiles_count": spare_tiles_count,
            "spare_tiles": spare_tiles,
            "protocols": proto_list,
        })

    total_units = summary_signed + summary_partially_signed + summary_pending + summary_not_started

    result_buildings = []
    for bid in sorted(building_data.keys(), key=lambda x: building_data[x]["building_name"]):
        bd = building_data[bid]
        if bd["total_units"] == 0 and (status or type):
            continue
        bd["progress_pct"] = int(bd["signed_count"] / bd["total_units"] * 100) if bd["total_units"] > 0 else 0

        sorted_floors = sorted(bd["floors"].values(), key=lambda f: f["floor_sort"], reverse=True)
        floor_list = []
        for fl in sorted_floors:
            def _unit_sort_key(u):
                apt = u["apartment_number"]
                try:
                    return (0, int(apt), apt)
                except (ValueError, TypeError):
                    return (1, 0, apt)
            fl["units"].sort(key=_unit_sort_key)
            floor_list.append({
                "floor": fl["floor"],
                "floor_name": fl["floor_name"],
                "units": fl["units"],
            })

        result_buildings.append({
            "building_id": bd["building_id"],
            "building_name": bd["building_name"],
            "total_units": bd["total_units"],
            "signed_count": bd["signed_count"],
            "progress_pct": bd["progress_pct"],
            "floors": floor_list,
        })

    available_types = []
    if "initial" in all_protocol_types:
        available_types.append("initial")
    if "final" in all_protocol_types:
        available_types.append("final")
    if not available_types:
        available_types = ["initial", "final"]

    project = await db.projects.find_one({"id": project_id}, {"_id": 0, "org_id": 1})
    org_id = project.get("org_id") if project else None

    can_manage_legal = False
    if org_id:
        if _is_super_admin(user):
            can_manage_legal = True
        else:
            org = await db.organizations.find_one({"id": org_id}, {"_id": 0, "owner_user_id": 1})
            if org and org.get("owner_user_id") == user["id"]:
                can_manage_legal = True
            else:
                mem = await db.org_memberships.find_one(
                    {"org_id": org_id, "user_id": user["id"]}, {"_id": 0, "role": 1}
                )
                if mem and mem.get("role") in ("org_admin", "owner"):
                    can_manage_legal = True

    return {
        "summary": {
            "total_units": total_units,
            "signed": summary_signed,
            "partially_signed": summary_partially_signed,
            "pending": summary_pending,
            "not_started": summary_not_started,
        },
        "buildings": result_buildings,
        "filters": {
            "buildings": all_building_names,
            "types": available_types,
        },
        "org_id": org_id,
        "can_manage_legal": can_manage_legal,
    }


@router.get("/projects/{project_id}/handover/summary")
async def handover_summary(project_id: str, user: dict = Depends(get_current_user)):
    await _check_handover_access(user, project_id)
    db = get_db()

    total_units = await db.units.count_documents({
        "project_id": {"$exists": False}
    })
    buildings = await db.buildings.find({"project_id": project_id, "archived": {"$ne": True}}, {"_id": 0, "id": 1, "name": 1}).to_list(500)
    building_ids = [b["id"] for b in buildings]

    floors = await db.floors.find(
        {"building_id": {"$in": building_ids}, "archived": {"$ne": True}},
        {"_id": 0, "id": 1, "building_id": 1}
    ).to_list(5000)
    floor_ids = [f["id"] for f in floors]
    floor_to_building = {f["id"]: f["building_id"] for f in floors}

    units = await db.units.find(
        {"floor_id": {"$in": floor_ids}, "archived": {"$ne": True}},
        {"_id": 0, "id": 1, "floor_id": 1}
    ).to_list(10000)
    total_units = len(units)

    protocols = await db.handover_protocols.find(
        {"project_id": project_id},
        {"_id": 0, "id": 1, "type": 1, "status": 1, "building_id": 1}
    ).to_list(10000)

    counts = {
        "initial_draft": 0, "initial_in_progress": 0, "initial_partially_signed": 0, "initial_signed": 0,
        "final_draft": 0, "final_in_progress": 0, "final_partially_signed": 0, "final_signed": 0,
    }
    building_breakdown = {b["id"]: {
        "building_id": b["id"], "building_name": b["name"],
        "initial_draft": 0, "initial_in_progress": 0, "initial_partially_signed": 0, "initial_signed": 0,
        "final_draft": 0, "final_in_progress": 0, "final_partially_signed": 0, "final_signed": 0,
    } for b in buildings}

    for p in protocols:
        key = f"{p['type']}_{p['status']}"
        if key in counts:
            counts[key] += 1
        bid = p.get("building_id")
        if bid in building_breakdown and key in building_breakdown[bid]:
            building_breakdown[bid][key] += 1

    open_handover_defects = await db.tasks.count_documents({
        "project_id": project_id,
        "source": {"$in": ["handover_initial", "handover_final"]},
        "status": {"$nin": ["closed", "cancelled"]},
    })

    return {
        "total_units": total_units,
        **counts,
        "open_handover_defects": open_handover_defects,
        "buildings": list(building_breakdown.values()),
    }


def _find_legal_section(protocol, section_id):
    for idx, s in enumerate(protocol.get("legal_sections", [])):
        if s.get("id") == section_id:
            return idx, s
    return None, None


@router.put("/projects/{project_id}/handover/protocols/{protocol_id}/legal-sections/{section_id}")
async def update_legal_section_body(
    project_id: str, protocol_id: str, section_id: str,
    request: Request, user: dict = Depends(get_current_user),
):
    await _check_handover_management(user, project_id)
    protocol = await _get_protocol_or_404(protocol_id, project_id)
    _check_not_locked(protocol)

    idx, section = _find_legal_section(protocol, section_id)
    if section is None:
        raise HTTPException(status_code=404, detail="נסח משפטי לא נמצא")
    if section.get("signed_at"):
        raise HTTPException(status_code=403, detail="לא ניתן לערוך נסח חתום")
    sigs_obj = section.get("signatures") or {}
    if any(slot_sig.get("signed_at") for slot_sig in sigs_obj.values() if isinstance(slot_sig, dict)):
        raise HTTPException(status_code=403, detail="לא ניתן לערוך נסח חתום")

    body = await request.json()
    new_body = (body.get("body") or "").strip()
    if not new_body:
        raise HTTPException(status_code=400, detail="תוכן הנסח נדרש")

    db = get_db()
    ts = _now()
    old_body = section.get("body", "")

    result = await db.handover_protocols.update_one(
        {"id": protocol_id, "project_id": project_id, f"legal_sections.{idx}.signed_at": None},
        {"$set": {
            f"legal_sections.{idx}.body": new_body,
            f"legal_sections.{idx}.edited": True,
            "updated_at": ts,
        }, "$push": {
            "legal_text_edit_log": {
                "section_id": section_id,
                "old_body": old_body,
                "new_body": new_body,
                "edited_by": user["id"],
                "edited_at": ts,
            }
        }}
    )
    if result.modified_count == 0:
        raise HTTPException(status_code=409, detail="הנסח נחתם במקביל — לא ניתן לערוך")

    await _audit("handover_protocol", protocol_id, "legal_section_edited", user["id"], {
        "project_id": project_id,
        "section_id": section_id,
        "section_title": section.get("title"),
    })

    logger.info(f"[HANDOVER] Protocol={protocol_id} legal section={section_id} body edited by user={user['id']}")
    updated = await db.handover_protocols.find_one({"id": protocol_id}, {"_id": 0})
    return updated


@router.put("/projects/{project_id}/handover/protocols/{protocol_id}/legal-sections/{section_id}/sign")
async def sign_legal_section(
    project_id: str, protocol_id: str, section_id: str,
    signer_name: str = Form(...),
    signature_type: str = Form(...),
    typed_name: str = Form(None),
    id_number: str = Form(None),
    signer_slot: str = Form(None),
    signature_image: UploadFile = File(None),
    user: dict = Depends(get_current_user),
):
    user_role = await _get_user_project_role(user, project_id)
    if not user_role:
        raise HTTPException(status_code=403, detail="אין לך גישה לפרויקט זה")

    protocol = await _get_protocol_or_404(protocol_id, project_id)
    _check_not_locked(protocol)

    idx, section = _find_legal_section(protocol, section_id)
    if section is None:
        raise HTTPException(status_code=404, detail="נסח משפטי לא נמצא")
    if not section.get("requires_signature"):
        raise HTTPException(status_code=400, detail="נסח זה לא דורש חתימה")

    is_dual = section.get("requires_both_tenants", False)
    num_tenants = _valid_tenant_count(protocol)

    if is_dual:
        if not signer_slot or signer_slot not in ("tenant", "tenant_2"):
            raise HTTPException(status_code=400, detail="נדרש signer_slot (tenant או tenant_2)")
        existing_sigs = section.get("signatures") or {}
        if existing_sigs.get(signer_slot, {}).get("signed_at"):
            raise HTTPException(status_code=409, detail="סעיף זה כבר נחתם")
    else:
        signer_slot = None
        if section.get("signed_at"):
            raise HTTPException(status_code=409, detail="סעיף זה כבר נחתם")

    sig_role = section.get("signature_role")
    if sig_role:
        if is_dual:
            _check_signature_role_auth(user_role, signer_slot or "tenant")
        else:
            _check_signature_role_auth(user_role, sig_role)

    if signature_type not in ("canvas", "typed"):
        raise HTTPException(status_code=400, detail="סוג חתימה לא חוקי — canvas או typed")

    signer_name = signer_name.strip()
    if not signer_name:
        raise HTTPException(status_code=400, detail="שם החותם נדרש")

    db = get_db()
    ts = _now()
    id_number_val = (id_number or "").strip() or None

    sig_data = {
        "type": signature_type,
        "signer_user_id": user["id"],
        "signed_at": ts,
        "signer_name": signer_name,
        "id_number": id_number_val,
    }

    if signature_type == "canvas":
        if not signature_image:
            raise HTTPException(status_code=400, detail="נדרש קובץ חתימה לסוג canvas")
        image_data = await signature_image.read()
        if not image_data or len(image_data) < 100:
            raise HTTPException(status_code=400, detail="קובץ חתימה ריק או לא תקין")
        suffix = f"_{signer_slot}" if signer_slot else ""
        s3_key = f"signatures/{protocol_id}/legal_{section_id}{suffix}.png"
        stored_ref = save_bytes(image_data, s3_key, "image/png")
        sig_data["image_key"] = stored_ref
    else:
        typed_name_val = (typed_name or "").strip()
        if not typed_name_val:
            raise HTTPException(status_code=400, detail="שם מלא נדרש לחתימה מוקלדת")
        sig_data["typed_name"] = typed_name_val

    if is_dual:
        update_fields = {
            f"legal_sections.{idx}.signatures.{signer_slot}": sig_data,
            "updated_at": ts,
        }
        refreshed_section = {**section}
        refreshed_sigs = dict(refreshed_section.get("signatures") or {})
        refreshed_sigs[signer_slot] = sig_data
        refreshed_section["signatures"] = refreshed_sigs
        both_done = bool(refreshed_sigs.get("tenant", {}).get("signed_at")) and (
            bool(refreshed_sigs.get("tenant_2", {}).get("signed_at")) or num_tenants < 2
        )
        if both_done:
            update_fields[f"legal_sections.{idx}.signed_at"] = ts
            refreshed_section["signed_at"] = ts

        concurrency_filter = {
            "id": protocol_id,
            "project_id": project_id,
            f"legal_sections.{idx}.signatures.{signer_slot}.signed_at": {"$exists": False},
        }
    else:
        update_fields = {
            f"legal_sections.{idx}.signature": sig_data,
            f"legal_sections.{idx}.signer_name": signer_name,
            f"legal_sections.{idx}.signed_at": ts,
            "updated_at": ts,
        }
        refreshed_section = {**section, "signed_at": ts, "signature": sig_data, "signer_name": signer_name}
        concurrency_filter = {
            "id": protocol_id,
            "project_id": project_id,
            f"legal_sections.{idx}.signed_at": None,
        }

    refreshed_legal = list(protocol.get("legal_sections", []))
    refreshed_legal[idx] = refreshed_section
    virtual_protocol = {**protocol, "legal_sections": refreshed_legal}
    new_status, new_locked = _recalculate_signature_status(virtual_protocol)
    update_fields["status"] = new_status
    update_fields["locked"] = new_locked
    if new_locked:
        update_fields["signed_at"] = ts

    result = await db.handover_protocols.update_one(concurrency_filter, {"$set": update_fields})
    if result.modified_count == 0:
        raise HTTPException(status_code=409, detail="סעיף זה כבר נחתם")

    await _audit("handover_protocol", protocol_id, "legal_section_signed", user["id"], {
        "project_id": project_id,
        "section_id": section_id,
        "section_title": section.get("title"),
        "signature_role": sig_role,
        "signer_slot": signer_slot,
        "signature_type": signature_type,
        "signer_name": signer_name,
    })

    logger.info(f"[HANDOVER] Protocol={protocol_id} legal section={section_id} slot={signer_slot} signed by user={user['id']} type={signature_type}")
    updated = await db.handover_protocols.find_one({"id": protocol_id}, {"_id": 0})
    return updated


@router.get("/projects/{project_id}/handover/protocols/{protocol_id}/legal-sections/{section_id}/signature-image")
async def get_legal_section_signature_image(
    project_id: str, protocol_id: str, section_id: str,
    signer_slot: str = None,
    user: dict = Depends(get_current_user),
):
    await _check_handover_access(user, project_id)

    protocol = await _get_protocol_or_404(protocol_id, project_id)
    _, section = _find_legal_section(protocol, section_id)
    if section is None:
        raise HTTPException(status_code=404, detail="נסח משפטי לא נמצא")

    sig = None
    sig_signer_name = ""
    if signer_slot:
        sigs = section.get("signatures") or {}
        sig = sigs.get(signer_slot)
        if sig:
            sig_signer_name = sig.get("signer_name", "")
    if not sig:
        sig = section.get("signature")
        sig_signer_name = section.get("signer_name", "")
    if not sig:
        raise HTTPException(status_code=404, detail="חתימה לא נמצאה")

    if sig.get("type") == "typed":
        return {"type": "typed", "typed_name": sig.get("typed_name", ""), "signer_name": sig_signer_name}

    image_key = sig.get("image_key", "")
    if image_key:
        url = generate_url(image_key)
        return {"type": "canvas", "url": url, "signer_name": sig_signer_name}

    raise HTTPException(status_code=404, detail="תמונת חתימה לא נמצאה")
