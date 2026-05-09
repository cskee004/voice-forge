DOMAIN = "voiceforge"
VERSION = "1.0.0"

CONF_ENDPOINT = "endpoint"
CONF_MODEL = "model"
CONF_API_KEY = "api_key"
CONF_ACTIVE_CHARACTER = "active_character"
CONF_HOUSEHOLD_MEMBERS = "household_members"
CONF_WAKE_TIME = "wake_time"
CONF_SCHOOL_SCHEDULE = "school_schedule"
CONF_PARENT_NOTIFY_ENTITY = "parent_notify_entity"

DEFAULT_ENDPOINT = "http://localhost:11434/v1"
DEFAULT_MODEL = "llama3"
DEFAULT_API_KEY = "sk-voiceforge"
DEFAULT_MAX_TOKENS = 300
DEFAULT_TEMPERATURE = 0.85

CHARACTERS_DIR = "characters"
MEMORY_DIR = "voiceforge/memory"
MESSAGES_FILE = "voiceforge/messages.json"

EMERGENCY_RESPONSE = (
    "I need you to stop and listen. "
    "If this is an emergency, call 911 or your local emergency number right now. "
    "If you are safe, I am here."
)

SESSION_IDLE_TTL = 1800
MEMORY_INJECTION_LIMIT = 5
TOKEN_BUDGET = 2200
