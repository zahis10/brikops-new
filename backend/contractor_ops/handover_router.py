from fastapi import APIRouter, HTTPException, Depends, Query, Request
from datetime import datetime, timezone
import uuid
import logging

from contractor_ops.router import get_db, get_current_user, require_roles, _check_project_access, _check_project_read_access, _audit, _now, _is_super_admin

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


def _check_not_signed(protocol):
    if protocol.get("status") in ("signed", "completed"):
        raise HTTPException(status_code=403, detail="פרוטוקול חתום — לא ניתן לעריכה")


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
            "newer_version_available": False,
            "newer_version": None,
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
            "newer_version_available": False,
            "newer_version": None,
        }

    resolved_family = family_id or tpl.get("family_id")
    newer_version_available = False
    newer_version_num = None
    if resolved_family:
        newer = await db.qc_templates.find_one(
            {"family_id": resolved_family, "is_active": True, "version": {"$gt": tpl.get("version", 0)}},
            {"_id": 0, "id": 1, "version": 1}
        )
        if newer:
            newer_version_available = True
            newer_version_num = newer["version"]

    return {
        "assigned": True,
        "template_version_id": version_id,
        "template_family_id": resolved_family,
        "template_name": tpl["name"],
        "template_version": tpl["version"],
        "newer_version_available": newer_version_available,
        "newer_version": newer_version_num,
    }


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
    if project.get("org_id"):
        org = await db.organizations.find_one({"id": project["org_id"]}, {"_id": 0})
        if org:
            legal_field = f"default_handover_legal_text_{protocol_type}"
            org_legal = org.get(legal_field, "").strip()
            if org_legal:
                org_legal_text = org_legal

    company_name = ""
    company_logo_url = None
    if project.get("org_id"):
        org_doc = await db.organizations.find_one({"id": project["org_id"]}, {"_id": 0, "name": 1, "logo_url": 1})
        if org_doc:
            company_name = org_doc.get("name", "")
            company_logo_url = org_doc.get("logo_url")

    ts = _now()
    protocol_id = str(uuid.uuid4())

    protocol_doc = {
        "id": protocol_id,
        "project_id": project_id,
        "building_id": building["id"],
        "floor_id": floor["id"],
        "unit_id": unit_id,
        "type": protocol_type,
        "template_version_id": tpl.get("id"),
        "status": "draft",
        "snapshot": {
            "project_name": project.get("name", ""),
            "building_name": building.get("name", ""),
            "floor_name": floor.get("name", ""),
            "unit_name": unit.get("name", unit.get("unit_no", "")),
            "unit_number": unit.get("unit_no", ""),
            "company_name": company_name,
            "company_logo_url": company_logo_url,
        },
        "property_details": {
            "rooms": None, "storage_num": None, "parking_num": None,
            "model": None, "area": None, "balcony_area": None,
            "parking_area": None, "laundry_area": None,
        },
        "tenants": [
            {"name": "", "id_number": "", "phone": "", "email": "", "id_photo_url": None}
        ],
        "meters": {
            "water": {"reading": None, "photo_url": None},
            "electricity": {"reading": None, "photo_url": None},
        } if protocol_type == "final" else None,
        "sections": sections,
        "delivered_items": [dict(item) for item in DEFAULT_DELIVERED_ITEMS] if protocol_type == "final" else [],
        "general_notes": {"apartment": "", "storage": "", "parking": ""},
        "legal_text": org_legal_text,
        "legal_text_edited": False,
        "legal_text_edit_log": [],
        "signatures": [],
        "pdf_url": None,
        "created_by": user["id"],
        "created_at": ts,
        "updated_at": ts,
        "signed_at": None,
    }

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
    return protocol


@router.put("/projects/{project_id}/handover/protocols/{protocol_id}")
async def update_protocol(project_id: str, protocol_id: str, request: Request, user: dict = Depends(get_current_user)):
    await _check_handover_management(user, project_id)
    protocol = await _get_protocol_or_404(protocol_id, project_id)
    _check_not_signed(protocol)

    body = await request.json()
    db = get_db()
    ts = _now()
    update_fields = {"updated_at": ts}

    for field in ("property_details", "tenants", "meters", "delivered_items", "general_notes"):
        if field in body:
            update_fields[field] = body[field]

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


@router.put("/projects/{project_id}/handover/protocols/{protocol_id}/sections/{section_id}/items/{item_id}")
async def update_item(
    project_id: str, protocol_id: str, section_id: str, item_id: str,
    request: Request, user: dict = Depends(get_current_user),
):
    await _check_handover_management(user, project_id)
    protocol = await _get_protocol_or_404(protocol_id, project_id)
    _check_not_signed(protocol)

    body = await request.json()
    db = get_db()
    ts = _now()

    section_found = False
    item_found = False
    for section in protocol.get("sections", []):
        if section["section_id"] != section_id:
            continue
        section_found = True
        for item in section.get("items", []):
            if item["item_id"] != item_id:
                continue
            item_found = True
            break
        break

    if not section_found:
        raise HTTPException(status_code=404, detail="חלק לא נמצא בפרוטוקול")
    if not item_found:
        raise HTTPException(status_code=404, detail="פריט לא נמצא בחלק")

    update_ops = {"$set": {"updated_at": ts}}
    has_item_change = False

    if "status" in body:
        new_status = body["status"]
        if new_status not in VALID_ITEM_STATUSES:
            raise HTTPException(status_code=400, detail=f"סטטוס לא חוקי: {new_status}")
        update_ops["$set"]["sections.$[sec].items.$[itm].status"] = new_status
        has_item_change = True

    if "notes" in body:
        update_ops["$set"]["sections.$[sec].items.$[itm].notes"] = body["notes"]
        has_item_change = True

    if "photos" in body:
        update_ops["$set"]["sections.$[sec].items.$[itm].photos"] = body["photos"]
        has_item_change = True

    if not has_item_change:
        raise HTTPException(status_code=400, detail="לא סופקו שדות לעדכון")

    if protocol.get("status") == "draft":
        update_ops["$set"]["status"] = "in_progress"

    array_filters = [
        {"sec.section_id": section_id},
        {"itm.item_id": item_id},
    ]

    await db.handover_protocols.update_one(
        {"id": protocol_id, "project_id": project_id},
        update_ops,
        array_filters=array_filters,
    )

    updated = await db.handover_protocols.find_one({"id": protocol_id, "project_id": project_id}, {"_id": 0})
    return updated


@router.post("/projects/{project_id}/handover/protocols/{protocol_id}/items/{item_id}/create-defect")
async def create_defect_from_item(
    project_id: str, protocol_id: str, item_id: str,
    user: dict = Depends(get_current_user),
):
    await _check_handover_management(user, project_id)
    protocol = await _get_protocol_or_404(protocol_id, project_id)
    _check_not_signed(protocol)

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


@router.post("/projects/{project_id}/handover/protocols/{protocol_id}/sign")
async def sign_protocol(project_id: str, protocol_id: str, request: Request, user: dict = Depends(get_current_user)):
    await _check_handover_management(user, project_id)
    protocol = await _get_protocol_or_404(protocol_id, project_id)
    _check_not_signed(protocol)

    body = await request.json()
    signatures = body.get("signatures", [])

    has_tenant = any(s.get("role") == "tenant" for s in signatures)
    has_company = any(s.get("role") == "company_rep" for s in signatures)

    if not has_tenant or not has_company:
        raise HTTPException(status_code=400, detail="נדרשת חתימה של דייר אחד לפחות ונציג חברה אחד לפחות")

    for sig in signatures:
        if not sig.get("name") or not sig.get("signature_data"):
            raise HTTPException(status_code=400, detail="שם וחתימה נדרשים לכל חותם")

    db = get_db()
    ts = _now()

    await db.handover_protocols.update_one(
        {"id": protocol_id, "project_id": project_id},
        {"$set": {
            "status": "signed",
            "signed_at": ts,
            "updated_at": ts,
            "signatures": signatures,
        }}
    )

    await _audit("handover_protocol", protocol_id, "signed", user["id"], {
        "project_id": project_id,
        "signature_count": len(signatures),
    })

    logger.info(f"[HANDOVER] Protocol={protocol_id} signed by user={user['id']} with {len(signatures)} signatures")
    updated = await db.handover_protocols.find_one({"id": protocol_id}, {"_id": 0})
    return updated


@router.post("/projects/{project_id}/handover/protocols/{protocol_id}/reopen")
async def reopen_protocol(project_id: str, protocol_id: str, request: Request, user: dict = Depends(get_current_user)):
    if not _is_super_admin(user):
        raise HTTPException(status_code=403, detail="רק מנהל מערכת יכול לפתוח מחדש פרוטוקול חתום")

    protocol = await _get_protocol_or_404(protocol_id, project_id)
    if protocol.get("status") not in ("signed", "completed"):
        raise HTTPException(status_code=400, detail="ניתן לפתוח מחדש רק פרוטוקול חתום")

    body = await request.json()
    reason = body.get("reason", "").strip()
    if not reason:
        raise HTTPException(status_code=400, detail="נדרשת סיבה לפתיחה מחדש")

    db = get_db()
    ts = _now()

    await db.handover_protocols.update_one(
        {"id": protocol_id, "project_id": project_id},
        {"$set": {
            "status": "in_progress",
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
        "initial_draft": 0, "initial_in_progress": 0, "initial_signed": 0,
        "final_draft": 0, "final_in_progress": 0, "final_signed": 0,
    }
    building_breakdown = {b["id"]: {
        "building_id": b["id"], "building_name": b["name"],
        "initial_draft": 0, "initial_in_progress": 0, "initial_signed": 0,
        "final_draft": 0, "final_in_progress": 0, "final_signed": 0,
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
