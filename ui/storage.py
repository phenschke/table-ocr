"""
Simple JSON-based storage for projects, prompts, and schemas (UI persistence layer).
"""
import json
from pathlib import Path
from typing import List, Optional, Dict

from ui.models import Project, Prompt, OutputSchema


class DataStore:
    """Simple JSON file-based storage for UI data."""
    
    def __init__(self, data_dir: str = "ocr_data"):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(exist_ok=True)
        
        self.projects_file = self.data_dir / "projects.json"
        self.prompts_file = self.data_dir / "prompts.json"
        self.schemas_file = self.data_dir / "schemas.json"
        
        # Initialize files if they don't exist
        for file in [self.projects_file, self.prompts_file, self.schemas_file]:
            if not file.exists():
                file.write_text("[]")
    
    def _read_json(self, filepath: Path) -> List[Dict]:
        """Read JSON file."""
        try:
            with open(filepath, 'r') as f:
                return json.load(f)
        except (json.JSONDecodeError, FileNotFoundError):
            return []
    
    def _write_json(self, filepath: Path, data: List[Dict]):
        """Write JSON file."""
        with open(filepath, 'w') as f:
            json.dump(data, f, indent=2)
    
    # Project operations
    def get_projects(self) -> List[Project]:
        """Get all projects."""
        data = self._read_json(self.projects_file)
        return [Project.from_dict(p) for p in data]
    
    def get_project(self, name: str) -> Optional[Project]:
        """Get a project by name."""
        projects = self.get_projects()
        for p in projects:
            if p.name == name:
                return p
        return None
    
    def save_project(self, project: Project):
        """Save or update a project."""
        projects = self.get_projects()
        # Remove existing project with same name
        projects = [p for p in projects if p.name != project.name]
        projects.append(project)
        self._write_json(self.projects_file, [p.to_dict() for p in projects])
    
    def delete_project(self, name: str):
        """Delete a project."""
        projects = self.get_projects()
        projects = [p for p in projects if p.name != name]
        self._write_json(self.projects_file, [p.to_dict() for p in projects])
    
    # Prompt operations
    def get_prompts(self) -> List[Prompt]:
        """Get all prompts."""
        data = self._read_json(self.prompts_file)
        return [Prompt.from_dict(p) for p in data]
    
    def get_prompt(self, name: str) -> Optional[Prompt]:
        """Get a prompt by name."""
        prompts = self.get_prompts()
        for p in prompts:
            if p.name == name:
                return p
        return None
    
    def save_prompt(self, prompt: Prompt):
        """Save or update a prompt."""
        prompts = self.get_prompts()
        # Remove existing prompt with same name
        prompts = [p for p in prompts if p.name != prompt.name]
        prompts.append(prompt)
        self._write_json(self.prompts_file, [p.to_dict() for p in prompts])
    
    def delete_prompt(self, name: str):
        """Delete a prompt."""
        prompts = self.get_prompts()
        prompts = [p for p in prompts if p.name != name]
        self._write_json(self.prompts_file, [p.to_dict() for p in prompts])
    
    # Schema operations
    def get_schemas(self) -> List[OutputSchema]:
        """Get all schemas."""
        data = self._read_json(self.schemas_file)
        return [OutputSchema.from_dict(s) for s in data]
    
    def get_schema(self, name: str) -> Optional[OutputSchema]:
        """Get a schema by name."""
        schemas = self.get_schemas()
        for s in schemas:
            if s.name == name:
                return s
        return None
    
    def save_schema(self, schema: OutputSchema):
        """Save or update a schema."""
        schemas = self.get_schemas()
        # Remove existing schema with same name
        schemas = [s for s in schemas if s.name != schema.name]
        schemas.append(schema)
        self._write_json(self.schemas_file, [s.to_dict() for s in schemas])
    
    def delete_schema(self, name: str):
        """Delete a schema."""
        schemas = self.get_schemas()
        schemas = [s for s in schemas if s.name != name]
        self._write_json(self.schemas_file, [s.to_dict() for s in schemas])
