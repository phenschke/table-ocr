"""
Constants and configuration values for the UI.
"""
from pathlib import Path

# Directory paths
DATA_DIR = Path("ocr_data")
RESULTS_DIR = DATA_DIR / "results"
UPLOADS_DIR = DATA_DIR / "uploads"
BATCH_DIR = DATA_DIR / "batch"

# UI Settings - DataFrame Heights
DATAFRAME_PREVIEW_HEIGHT = 400
DATAFRAME_PAGE_HEIGHT = 600

# UI Settings - Text Area Heights
TEXTAREA_PROMPT_HEIGHT = 400
TEXTAREA_PROMPT_VIEW_HEIGHT = 300

# Status emoji
STATUS_PROCESSED = "✅"
STATUS_NOT_PROCESSED = "⏸️"
STATUS_PROCESSING = "⏳"

# Material Icons
ICON_FOLDER = ":material/folder:"
ICON_DESCRIPTION = ":material/description:"
ICON_CHAT = ":material/chat:"
ICON_TABLE_CHART = ":material/table_chart:"
ICON_DELETE = ":material/delete:"
ICON_DELETE_FOREVER = ":material/delete_forever:"
ICON_DOWNLOAD = ":material/download:"
ICON_PLAY_CIRCLE = ":material/play_circle:"
ICON_INBOX = ":material/inbox:"
ICON_LIST_ALT = ":material/list_alt:"
ICON_VISIBILITY = ":material/visibility:"
ICON_REFRESH = ":material/refresh:"
ICON_ARROW_BACK = ":material/arrow_back:"
ICON_CODE = ":material/code:"
ICON_ADD = ":material/add:"
ICON_HOURGLASS = ":material/hourglass_top:"
ICON_CHECK_CIRCLE = ":material/check_circle:"
ICON_FOLDER_OPEN = ":material/folder_open:"
ICON_SCHEDULE = ":material/schedule:"
ICON_LIGHTBULB = ":material/lightbulb:"
ICON_ERROR = ":material/error:"
ICON_ANALYTICS = ":material/analytics:"
ICON_EDIT = ":material/edit:"
ICON_SAVE = ":material/save:"
ICON_CANCEL = ":material/cancel:"
ICON_WARNING = ":material/warning:"

# Color names for Streamlit status badges
COLOR_GREEN = "green"
COLOR_ORANGE = "orange"
COLOR_BLUE = "blue"
COLOR_RED = "red"
COLOR_GRAY = "gray"
