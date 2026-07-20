# BATCH AI Phase 2b (2026-07-20) — model class → app category mapping.
# Model-native class (from the ONNX classifier) → app CATEGORIES value.
# SINGLE source of truth. When the model learns a new class or the app adds
# a category, edit THIS dict only. Unknown/unmapped class → "general".
MODEL_TO_APP_CATEGORY = {
    "חשמל ותקשורת": "electrical",
    "אינסטלציה": "plumbing",
    "דלתות": "doors",
    "צבע וטיח": "painting",
    "חלונות ואלומיניום": "aluminum",   # unified — no split to windows
    "ציפוי קירות חוץ": "masonry",       # exterior stone/coating
    "אריחים": "flooring",               # default; wall→masonry via surface choice
}

# Classes whose mapping the user may refine with a wall/floor choice in the FE.
SURFACE_CHOICE_CLASSES = {"אריחים"}

APP_GENERAL = "general"


def to_app_category(model_class: str) -> str:
    return MODEL_TO_APP_CATEGORY.get(model_class, APP_GENERAL)


def needs_surface_choice(model_class: str) -> bool:
    return model_class in SURFACE_CHOICE_CLASSES
