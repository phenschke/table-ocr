"""
Constants and configuration values for the UI.
"""
from dataclasses import dataclass
from pathlib import Path

# Directory paths
DATA_DIR = Path("ocr_data")
RESULTS_DIR = DATA_DIR / "results"
UPLOADS_DIR = DATA_DIR / "uploads"
BATCH_DIR = DATA_DIR / "batch"

# UI Settings - DataFrame Heights
DATAFRAME_PREVIEW_HEIGHT = 400
DATAFRAME_PAGE_HEIGHT = 1200

# UI Settings - Text Area Heights
TEXTAREA_PROMPT_HEIGHT = 400
TEXTAREA_PROMPT_VIEW_HEIGHT = 300

# Status labels
STATUS_PROCESSED = "Processed"
STATUS_NOT_PROCESSED = "Awaiting OCR"
STATUS_PROCESSING = "Processing"

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
ICON_INFO = ":material/info:"
ICON_CHECK = ":material/check_circle:"
ICON_PENDING = ":material/schedule:"
ICON_CLOSE = ":material/close:"
ICON_ARROW_UP = ":material/arrow_upward:"
ICON_ARROW_DOWN = ":material/arrow_downward:"
ICON_EXPAND_MORE = ":material/expand_more:"
ICON_EXPAND_LESS = ":material/expand_less:"
ICON_HOW_TO_VOTE = ":material/how_to_vote:"
ICON_EXPORT = ":material/file_upload:"
ICON_STAR = ":material/star:"

# Color names for Streamlit status badges
COLOR_GREEN = "green"
COLOR_ORANGE = "orange"
COLOR_BLUE = "blue"
COLOR_RED = "red"
COLOR_GRAY = "gray"


@dataclass(frozen=True)
class StatusBadgeStyle:
    icon: str
    text_color: str
    background: str


STATUS_BADGE_STYLES = {
    "success": StatusBadgeStyle(icon=ICON_CHECK_CIRCLE, text_color="#136534", background="rgba(19, 101, 52, 0.12)"),
    "warning": StatusBadgeStyle(icon=ICON_WARNING, text_color="#8A6D1D", background="rgba(215, 183, 0, 0.18)"),
    "danger": StatusBadgeStyle(icon=ICON_ERROR, text_color="#8A1D1D", background="rgba(215, 0, 0, 0.12)"),
    "processing": StatusBadgeStyle(icon=ICON_HOURGLASS, text_color="#125F82", background="rgba(30, 144, 255, 0.12)"),
    "info": StatusBadgeStyle(icon=ICON_INFO, text_color="#1E3A5F", background="rgba(30, 90, 255, 0.12)"),
}
