# Table OCR

Digitize table scans using the Gemini API.

## Quick Start

### Prerequisites

1. **Install uv** (fast Python package manager):
   ```bash
   # Linux/macOS
   curl -LsSf https://astral.sh/uv/install.sh | sh
   
   # Windows PowerShell
   powershell -c "irm https://astral.sh/uv/install.ps1 | iex"
   
   # Or with pip
   pip install uv
   ```

2. **Get a Gemini API Key**: https://ai.google.dev/gemini-api/docs/api-key

### Setup & Run (4 Steps)

```bash
# 1. Create virtual environment
uv venv

# 2. Activate it
source .venv/bin/activate            # Linux/macOS
.venv\Scripts\activate               # Windows

# 3. Install dependencies
uv pip install -r requirements.txt

# 4. Set API key & start UI
export GEMINI_API_KEY='your-key'     # Linux/macOS (or set GEMINI_API_KEY=... on Windows)
streamlit run ui/app.py
```

**✅ Works on Linux, macOS, and Windows**

### Using the UI

Once running at http://localhost:8501:

1. **Create a Prompt** - Instructions for the AI
2. **Create a Schema** - Define what data to extract
3. **Create a Project** - Combine prompt + schema
4. **Upload PDFs** - Add your documents
5. **Process** - Extract data from tables

### Programmatic Usage (Advanced)

For developers who want to use the OCR library directly in their code:

```python
from table_ocr import ocr_pdf, create_batch_ocr_job
from google import genai

# Define your schema
schema = genai.types.Schema(
    type=genai.types.Type.OBJECT,
    properties={
        "table": genai.types.Schema(
            type=genai.types.Type.ARRAY,
            items=genai.types.Schema(
                type=genai.types.Type.OBJECT,
                properties={
                    "name": genai.types.Schema(type=genai.types.Type.STRING),
                    "date": genai.types.Schema(type=genai.types.Type.STRING),
                }
            )
        )
    }
)

# Direct processing (fast, full cost)
results = ocr_pdf(
    pdf_path="document.pdf",
    prompt_template="Extract the table data",
    response_schema=schema
)

# Batch processing (50% discount, ~24h processing time)
job_name = create_batch_ocr_job(
    pdf_path="document.pdf",
    prompt="Extract the table data",
    response_schema=schema
)
```

## Troubleshooting

### "streamlit: command not found"
Make sure you've activated your virtual environment:
```bash
source .venv/bin/activate  # Linux/macOS
.venv\Scripts\activate     # Windows
```

### "ModuleNotFoundError: No module named 'google'"
Install dependencies:
```bash
uv pip install -r requirements.txt
```

### "GEMINI_API_KEY not set"
Set your API key:
```bash
export GEMINI_API_KEY='your-key'  # Linux/macOS
set GEMINI_API_KEY=your-key       # Windows
```

## Project Structure

```
table_ocr/
├── table_ocr/          # Core OCR library
│   ├── core.py         # Gemini client, image processing
│   ├── direct.py       # Direct OCR API
│   ├── batch.py        # Batch processing API
│   └── ...
├── ui/                 # Streamlit UI application
│   ├── app.py          # Main UI (run this!)
│   ├── models.py       # UI data models
│   └── ...
├── requirements.txt    # Python dependencies
└── README.md          # This file
```

## Notes

- Problems can arise when there are remains of the previous/next page on the left/right edge of scanned images
- Use the `crop_sides` parameter in `ocr_pdf()` to handle edge artifacts
- The UI stores data in `ocr_data/` directory (created automatically)