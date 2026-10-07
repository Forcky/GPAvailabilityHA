"""Constants for the GP Availability integration."""
DOMAIN = "gp_availability"

# Config entry data
CONF_PROVIDER = "provider"  # key into providers.PROVIDERS
CONF_PRACTICE_ID = "practice_id"
CONF_PRACTICE_NAME = "practice_name"
CONF_TIMEZONE = "timezone"  # IANA name, or None to use the slots' own zone
CONF_BOOKING_URL = "booking_url"
CONF_APPT_TYPE_ID = "appt_type_id"
CONF_APPT_TYPE_NAME = "appt_type_name"

# Config entry options
CONF_WATCHES = "watches"  # {"<doctor id>": "<doctor name>"}; ANY_DOCTOR = any doctor
CONF_NOTIFY_TARGETS = "notify_targets"  # ["notify.mobile_app_pixel", ...]
CONF_SCAN_INTERVAL = "scan_interval"  # minutes

MAX_SCAN_INTERVAL = 60

# Pseudo-doctor id that watches every doctor at the practice.
ANY_DOCTOR = "any"

# Per-watch settings (held in the coordinator's Store, not the config entry,
# so changing them from an entity doesn't reload the integration).
DEFAULT_CUTOFF_DAYS = 14
# The whole practice has hundreds of slots a fortnight out; "anything by
# tomorrow-ish" is the useful question there.
DEFAULT_CUTOFF_DAYS_ANY = 2
MIN_CUTOFF_DAYS = 0
MAX_CUTOFF_DAYS = 60

EVENT_SLOT_AVAILABLE = "gp_availability_slot_available"

STORAGE_VERSION = 1

# How many slots to list in a notification / entity attributes.
NOTIFY_MAX_SLOTS = 5
# Book buttons (one per new slot with its own booking link) per notification.
NOTIFY_MAX_ACTIONS = 3
ATTR_MAX_SLOTS = 10
