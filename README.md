# Table OCR

Digitize table scans using the Gemini API.

## Quick Start

### Prerequisites

1. **Install uv** (fast Python package manager):
   ```bash
   # Linux/macOS
   curl -LsSf https://astral.sh/uv/install.sh | sh
   
   # Windows PowerShell
   powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
   
   # Or with pip
   pip install uv
   ```

2. **Get a Gemini API Key**: https://aistudio.google.com/app/api-keys
    - If you stay within [these limits](https://ai.google.dev/gemini-api/docs/rate-limits#current-rate-limits), API usage is free.
    - To go above these limits, you need to [set up billing in Google Cloud](https://ai.google.dev/gemini-api/docs/billing) (~300$ free credits after initial setup)

### Setup & Run (from the project root folder)

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

### Using the UI

Once running at http://localhost:8501:

1. **Create a Prompt** - Instructions and guidance for the LLM
2. **Create a Schema** - Define the output columns
3. **Create a Project** - Combine prompt + schema
4. **Upload PDFs** - Add your documents to the project. All files in a project will use the same prompt/schema
5. **Process** - Extract data from tables. Press "Details" button of a file to inspect the data extracted from individual files.

### Programmatic Usage

If you want to use the functionalities directly in your code instead of the UI:

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

## Notes
- The default model is Gemini-2.5-Flash-Lite. You can change the used model in config.py
- Problems can arise when there are remains of the previous/next page on the left/right edge of scanned images. You can try to solve this via prompting, changing the `IMAGE_PROCESSING_CONFIG` in `config.py` to automatically crop sides, or manually cropping.
- The UI stores data in the `ocr_data/` directory at the repository root (created automatically)


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

## Future Improvements:
- Enable exporting result data of whole project
- Majority voting functionality
- Set processing config via UI
- Allow changing promt in a project
- Enable non-tabular structured data extraction?
- Make OCR model interchangeable (e.g., Marker, LiteLLM)