"""
Central configuration file for the Gemini OCR workflow.
"""
from google import genai
from google.genai import types

# --- Model and Generation Settings ---
MODEL_CONFIG = {
    "default_model": "gemini-2.5-flash-lite",
    "generation_config": {
        "temperature": 0.6,
        "max_output_tokens": 8192,
    },
    "thinking_budget": 0,
}

# --- Batch Processing Settings ---
BATCH_CONFIG = {
    "poll_interval": 60,  # seconds
    "completed_states": {
        'JOB_STATE_SUCCEEDED',
        'JOB_STATE_FAILED',
        'JOB_STATE_CANCELLED',
        'JOB_STATE_EXPIRED'
    }
}

# --- Image Processing Settings ---
IMAGE_PROCESSING_CONFIG = {
    "default_dpi": 200,
    "grayscale": False,
    "crop_sides": 0,
}

# --- Prompt Templates ---
PROMPT_TEMPLATES = {
    "basic":
        "Transcribe the text as if you were reading it naturally.",

    "namensverzeichnisse_stamt_standard":
        """The scanned page contains a table with columns: "Familienname", "Vornamen", "Religion", "Sterbetag", "Eintrag Nr.".
        The Eintrag Nr. is always provided, and is either a number up to 4 digits (e.g., "45" or "2738"), or a number and a place abbreviation (e.g., "4/Perl." or "87/Trud." or "123 Milb.").
        The Religion column is almost always empty. The Sterbetag is only provided in rare cases. When a Sterbetag is provided, we usually have a slash in the Eintrag Nr.
        Sometimes the very edges of the scanned page can show a column from the previous or next page ("Eintrag Nr" oder "Familienname"). Ignore these. Consider only the main table on the page.
        Extract the table into the provided structure. If there is no table on the page, output an empty list.""",

    "namensverzeichnisse_stamt4":
        """The page contains a table with columns: "Fortlaufende Nummer", "Name und Vorname", "Wohnort", "Jahrgang", "Nr.", "Bemerkungen".
        The Jahrgang is always 1900.
        Extract the table into the provided structure. If there is no table, output an empty list. Often, a cell contains just a ditto ". Fill dittos appropriately.
        Sometimes, the author later added another entry within the same cell. In these cases, pay special attention and create another row with the same fortlaufende Nummer, as this refers to two different people."""
}

# --- Output Schemas ---
NameRegisterTable_StAmt_Standard = genai.types.Schema(
    type=genai.types.Type.OBJECT,
    required=["table"],
    properties={
        "table": genai.types.Schema(
            type=genai.types.Type.ARRAY,
            items=genai.types.Schema(
                type=genai.types.Type.OBJECT,
                required=["Familienname", "Vornamen", "Religion", "Sterbetag", "Eintrag_Nr"],
                property_ordering=["Familienname", "Vornamen", "Religion", "Sterbetag", "Eintrag_Nr"],
                properties={
                    "Familienname": genai.types.Schema(type=genai.types.Type.STRING),
                    "Vornamen": genai.types.Schema(type=genai.types.Type.STRING),
                    "Religion": genai.types.Schema(type=genai.types.Type.STRING),
                    "Sterbetag": genai.types.Schema(type=genai.types.Type.STRING),
                    "Eintrag_Nr": genai.types.Schema(type=genai.types.Type.STRING),
                },
            ),
        ),
    },
)

NameRegisterTable_StAmt4 = genai.types.Schema(
    type=genai.types.Type.OBJECT,
    required=["table"],
    properties={
        "table": genai.types.Schema(
            type=genai.types.Type.ARRAY,
            items=genai.types.Schema(
                type=genai.types.Type.OBJECT,
                required=["Fortlaufende_Nummer", "Nachname", "Vornamen", "Wohnort", "Jahrgang", "Nr."],
                property_ordering=["Fortlaufende_Nummer", "Nachname", "Vornamen", "Wohnort", "Jahrgang", "Nr.", "Bemerkung"],
                properties={
                    "Fortlaufende_Nummer": genai.types.Schema(type=genai.types.Type.INTEGER),
                    "Nachname": genai.types.Schema(type=genai.types.Type.STRING),
                    "Vornamen": genai.types.Schema(type=genai.types.Type.STRING),
                    "Wohnort": genai.types.Schema(type=genai.types.Type.STRING),
                    "Jahrgang": genai.types.Schema(type=genai.types.Type.INTEGER),
                    "Nr.": genai.types.Schema(type=genai.types.Type.STRING),
                    "Bemerkung": genai.types.Schema(type=genai.types.Type.STRING),
                },
            ),
        ),
    },
)
