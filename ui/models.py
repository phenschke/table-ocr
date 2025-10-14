"""
UI-specific data models for project, prompt, and schema management.
"""
from dataclasses import dataclass, field
from typing import List, Dict, Optional
from datetime import datetime
from google import genai


@dataclass
class BatchJob:
    """Represents a batch processing job (UI tracking)."""
    job_name: str
    pdf_file: str
    status: str
    created_at: datetime
    completed_at: Optional[datetime] = None
    result_file_path: Optional[str] = None
    error_message: Optional[str] = None
    
    def to_dict(self) -> Dict:
        return {
            "job_name": self.job_name,
            "pdf_file": self.pdf_file,
            "status": self.status,
            "created_at": self.created_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "result_file_path": self.result_file_path,
            "error_message": self.error_message
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> "BatchJob":
        return cls(
            job_name=data["job_name"],
            pdf_file=data["pdf_file"],
            status=data["status"],
            created_at=datetime.fromisoformat(data["created_at"]),
            completed_at=datetime.fromisoformat(data["completed_at"]) if data.get("completed_at") else None,
            result_file_path=data.get("result_file_path"),
            error_message=data.get("error_message")
        )


@dataclass
class SchemaField:
    """Represents a single field in an output schema."""
    name: str
    field_type: str = "STRING"  # STRING, INTEGER, BOOLEAN, NUMBER
    required: bool = False
    
    def to_dict(self) -> Dict:
        return {
            "name": self.name,
            "field_type": self.field_type,
            "required": self.required
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> "SchemaField":
        return cls(
            name=data["name"],
            field_type=data.get("field_type", "STRING"),
            required=data.get("required", False)
        )


@dataclass
class OutputSchema:
    """Represents an output schema configuration (UI convenience wrapper)."""
    name: str
    fields: List[SchemaField]
    created_at: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict:
        return {
            "name": self.name,
            "fields": [f.to_dict() for f in self.fields],
            "created_at": self.created_at.isoformat()
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> "OutputSchema":
        return cls(
            name=data["name"],
            fields=[SchemaField.from_dict(f) for f in data["fields"]],
            created_at=datetime.fromisoformat(data.get("created_at", datetime.now().isoformat()))
        )
    
    def to_genai_schema(self) -> genai.types.Schema:
        """Convert to Google genai Schema object for use with the core API."""
        # Build properties dict
        properties = {}
        required_fields = []
        property_ordering = []
        
        for field_def in self.fields:
            property_ordering.append(field_def.name)
            if field_def.required:
                required_fields.append(field_def.name)
            
            # Map field type string to genai Type
            type_map = {
                "STRING": genai.types.Type.STRING,
                "INTEGER": genai.types.Type.INTEGER,
                "BOOLEAN": genai.types.Type.BOOLEAN,
                "NUMBER": genai.types.Type.NUMBER,
            }
            field_type = type_map.get(field_def.field_type, genai.types.Type.STRING)
            properties[field_def.name] = genai.types.Schema(type=field_type)
        
        # Create the schema with a table array structure
        return genai.types.Schema(
            type=genai.types.Type.OBJECT,
            required=["table"],
            properties={
                "table": genai.types.Schema(
                    type=genai.types.Type.ARRAY,
                    items=genai.types.Schema(
                        type=genai.types.Type.OBJECT,
                        required=required_fields,
                        property_ordering=property_ordering,
                        properties=properties,
                    ),
                ),
            },
        )
    
    def is_dataframe_serializable(self) -> bool:
        """Check if schema can be easily converted to DataFrame/CSV.
        
        Returns True if all fields are simple types (no nested structures).
        Currently, all schemas are flat by design, so this always returns True.
        This method exists for future extensibility if nested types are added.
        """
        # All current field types (STRING, INTEGER, BOOLEAN, NUMBER) are simple
        # No nested objects or arrays are currently supported
        return True


@dataclass
class Prompt:
    """Represents a prompt template (UI management)."""
    name: str
    content: str
    created_at: datetime = field(default_factory=datetime.now)
    last_modified: Optional[datetime] = None
    
    def to_dict(self) -> Dict:
        return {
            "name": self.name,
            "content": self.content,
            "created_at": self.created_at.isoformat(),
            "last_modified": self.last_modified.isoformat() if self.last_modified else None
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> "Prompt":
        return cls(
            name=data["name"],
            content=data["content"],
            created_at=datetime.fromisoformat(data.get("created_at", datetime.now().isoformat())),
            last_modified=datetime.fromisoformat(data["last_modified"]) if data.get("last_modified") else None
        )


@dataclass
class Project:
    """Represents an OCR project (UI organizational concept)."""
    name: str
    prompt_name: str
    schema_name: str
    pdf_files: List[str] = field(default_factory=list)
    batch_jobs: List[BatchJob] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict:
        return {
            "name": self.name,
            "prompt_name": self.prompt_name,
            "schema_name": self.schema_name,
            "pdf_files": self.pdf_files,
            "batch_jobs": [job.to_dict() for job in self.batch_jobs],
            "created_at": self.created_at.isoformat()
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> "Project":
        return cls(
            name=data["name"],
            prompt_name=data["prompt_name"],
            schema_name=data["schema_name"],
            pdf_files=data.get("pdf_files", []),
            batch_jobs=[BatchJob.from_dict(job) for job in data.get("batch_jobs", [])],
            created_at=datetime.fromisoformat(data.get("created_at", datetime.now().isoformat()))
        )
