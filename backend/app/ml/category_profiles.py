"""Machine-category context for one shared predictive-maintenance model.

Machine.category already exists in the application. Categories provide context
and feature expectations; they do not select separate models.
"""
CATEGORY_PROFILES = {
    "induction_motor": {"signals": ("temperature","vibration","current","load","rpm"), "failure_families": ("bearing","electrical","overheating","imbalance"), "training_sources": ("paderborn_bearing","cwru_bearing")},
    "pump": {"signals": ("temperature","vibration","current","load","pressure","flow"), "failure_families": ("bearing","cavitation","seal","overheating"), "training_sources": ()},
    "compressor": {"signals": ("temperature","vibration","current","load","pressure","flow"), "failure_families": ("bearing","overheating","pressure","valve"), "training_sources": ()},
    "conveyor": {"signals": ("temperature","vibration","current","load","speed"), "failure_families": ("bearing","motor","belt","overload"), "training_sources": ()},
    "other": {"signals": ("temperature","vibration","current","load"), "failure_families": (), "training_sources": ("nasa_cmapss","phm_gearbox")},
}
def normalize_category(value):
    value = (value or "other").strip().lower().replace(" ", "_")
    return value if value in CATEGORY_PROFILES else "other"
def profile_for_category(value):
    return CATEGORY_PROFILES[normalize_category(value)]
