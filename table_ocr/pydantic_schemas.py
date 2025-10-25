"""
Pydantic-based schema definitions for OCR structured output.

This module provides Pydantic models that can be passed directly to the
google-genai SDK's response_schema parameter, replacing manual genai.types.Schema construction.

Benefits:
- Cleaner, more Pythonic schema definitions
- Type hints and IDE autocomplete
- Validation of OCR results
- Easy serialization to JSON/dict
"""
from typing import List, Optional
from pydantic import BaseModel, Field


# ============================================================================
# Base Response Structure
# ============================================================================

class TableResponse(BaseModel):
    """Base wrapper for all table-based OCR responses.

    All OCR schemas return data in this format:
    { "table": [...] }
    """
    table: List[BaseModel] = Field(
        description="Array of extracted table rows"
    )


# ============================================================================
# Example Schemas (from config.py)
# ============================================================================

class NameRegisterRowStAmtStandard(BaseModel):
    """Schema for standard name register (StAmt format)."""
    Familienname: str = Field(description="Family name/surname")
    Vornamen: str = Field(description="Given names")
    Religion: str = Field(description="Religion (often empty)")
    Sterbetag: str = Field(description="Death date (rarely provided)")
    Eintrag_Nr: str = Field(description="Entry number, may include place abbreviation")


class NameRegisterTableStAmtStandard(BaseModel):
    """Complete response schema for StAmt standard name register."""
    table: List[NameRegisterRowStAmtStandard] = Field(
        description="Extracted table rows from the name register"
    )


class NameRegisterRowStAmt4(BaseModel):
    """Schema for StAmt4 name register format."""
    Fortlaufende_Nummer: int = Field(description="Sequential number")
    Nachname: str = Field(description="Last name")
    Vornamen: str = Field(description="First names")
    Wohnort: str = Field(description="Place of residence")
    Jahrgang: int = Field(description="Year (usually 1900)")
    Nr: str = Field(alias="Nr.", description="Number")
    Bemerkung: Optional[str] = Field(default="", description="Remarks/notes")


class NameRegisterTableStAmt4(BaseModel):
    """Complete response schema for StAmt4 name register."""
    table: List[NameRegisterRowStAmt4] = Field(
        description="Extracted table rows from the name register"
    )


# ============================================================================
# Dynamic Schema Builder
# ============================================================================

def create_table_schema_from_fields(
    schema_name: str,
    fields: List[tuple[str, type, bool]]
) -> type[BaseModel]:
    """
    Dynamically create a Pydantic table schema from field definitions.

    Args:
        schema_name: Name for the generated schema class
        fields: List of (field_name, field_type, required) tuples

    Returns:
        A Pydantic BaseModel subclass representing the table row structure

    Example:
        >>> RowSchema = create_table_schema_from_fields(
        ...     "PersonRow",
        ...     [("name", str, True), ("age", int, True), ("city", str, False)]
        ... )
        >>> TableSchema = create_table_schema_class(RowSchema)
    """
    from pydantic import create_model

    # Build field definitions for row model
    row_fields = {}
    for field_name, field_type, required in fields:
        if required:
            row_fields[field_name] = (field_type, ...)
        else:
            row_fields[field_name] = (Optional[field_type], None)

    # Create the row model
    row_model = create_model(f"{schema_name}Row", **row_fields)

    # Create the table wrapper model
    table_model = create_model(
        schema_name,
        table=(List[row_model], Field(description="Extracted table rows"))
    )

    return table_model


def create_table_schema_class(row_model: type[BaseModel]) -> type[BaseModel]:
    """
    Wrap a row model in a table response structure.

    Args:
        row_model: Pydantic model representing a single table row

    Returns:
        A Pydantic model with a "table" field containing a list of row_model

    Example:
        >>> class PersonRow(BaseModel):
        ...     name: str
        ...     age: int
        >>> PersonTable = create_table_schema_class(PersonRow)
    """
    from pydantic import create_model

    return create_model(
        f"{row_model.__name__}Table",
        table=(List[row_model], Field(description="Extracted table rows"))
    )


# ============================================================================
# Type Mapping Utilities
# ============================================================================

def ui_field_type_to_python(field_type_str: str) -> type:
    """
    Convert UI field type string to Python type for Pydantic.

    Args:
        field_type_str: One of "STRING", "INTEGER", "BOOLEAN", "NUMBER"

    Returns:
        Corresponding Python type (str, int, bool, float)
    """
    type_map = {
        "STRING": str,
        "INTEGER": int,
        "BOOLEAN": bool,
        "NUMBER": float,
    }
    return type_map.get(field_type_str, str)
