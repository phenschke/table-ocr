"Batch mode functionality for large-scale OCR processing."

import io
import re
import json
import time
import collections
from typing import Union, Optional, Dict, Any, List, Tuple
from pathlib import Path
from google.genai import types
import polars as pl
from dataclasses import dataclass

from . import config as app_config
from .core import GeminiClient, pdf_pages_to_images, logger
from .parser import strip_json_codeblock

@dataclass
class BatchOCRResult:
    results_by_page: Dict[int, Dict[int, Any]]
    pdf_name: str

    def __iter__(self):
        yield self.results_by_page
        yield self.pdf_name

def create_batch_ocr_job(
    pdf_path: str,
    prompt: str,
    model_name: str = app_config.MODEL_CONFIG["default_model"],
    max_pages: Optional[int] = None,
    start_page: int = 1,
    crop_sides: int = 0,
    n_samples: int = 1,
    job_display_name: Optional[str] = None,
    generation_config: Optional[Dict[str, Any]] = None,
    response_schema=None,
    jsonl_dir: Optional[str] = None,
    display: bool = False
) -> str:
    """
    Create a batch OCR job for processing PDF pages asynchronously.
    Args:
        pdf_path: Path to PDF containing scanned images.
        prompt: Text prompt to send along with the image
        model_name: Gemini model.
        max_pages: Limit number of pages processed.
        start_page: 1-based page index to start from.
        n_samples: Number of times to OCR each page.
        job_display_name: Display name for the batch job.
        generation_config: Configuration for the generation process.
        response_schema: Schema for structured output.
        jsonl_dir: Optional directory to save the batch requests JSONL file. If None, saves in current directory.
        
    Returns:
        Batch job name for monitoring and retrieving results.
    """

    # Convert PDF pages to images
    images = pdf_pages_to_images(
        pdf_path=pdf_path,
        max_pages=max_pages,
        start_page=start_page,
        crop_sides=crop_sides,
        display=display
    )
    client = GeminiClient()

    # Define base names for jobs and files
    pdf_name_stem = Path(pdf_path).stem
    model_str = model_name.split('/')[-1]
    num_pages = len(images)
    end_page = start_page + num_pages - 1
    pages_str = f"p{start_page}-{end_page}" if num_pages > 1 else f"p{start_page}"
    base_name = f"{pdf_name_stem}_{model_str}_{pages_str}"

    # Upload images using the file API and collect file IDs
    uploaded_images = []
    for page_idx, img in enumerate(images):
        page_index = start_page + page_idx
        img_format = img.format if img.format else "PNG"
        image_filename = f"batch_image_page_{page_index}_{int(time.time())}.{img_format.lower()}"
        buf = io.BytesIO()
        img.save(buf, format=img_format)
        buf.seek(0)
        logger.info(f"Uploading image {page_idx+1}/{len(images)}: {image_filename} (in-memory)")
        uploaded_img = client.client.files.upload(
            file=buf,
            config=types.UploadFileConfig(
                display_name=f"{pdf_name_stem}_p{page_index}",
                mime_type=f"image/{img_format.lower()}"
            )
        )
        uploaded_images.append(uploaded_img)
        logger.info(f"Uploaded image {page_idx+1}/{len(images)}: {uploaded_img.name}")

    # Build batch requests referencing uploaded file IDs
    batch_requests = []
    for page_idx, uploaded_img in enumerate(uploaded_images):
        page_index = start_page + page_idx
        for sample_idx in range(n_samples):
            pdf_name = Path(pdf_path).stem
            request_key = f"{pdf_name}_page_{page_index}_sample_{sample_idx+1}"
            image_part = {"file_data": {"file_uri": uploaded_img.uri, "mime_type": uploaded_img.mime_type}}
            request = {
                "key": request_key,
                "request": {
                    "contents": [{
                        "parts": [
                            image_part,
                            {"text": prompt}
                        ]
                    }]
                }
            }
            if generation_config:
                request["request"]["generation_config"] = generation_config
            elif response_schema:
                # Add response_schema if provided and no custom generation_config
                config = {"response_mime_type": "application/json"}
                if hasattr(response_schema, "to_json_dict"):
                    config["response_schema"] = response_schema.to_json_dict()
                else:
                    config["response_schema"] = response_schema
                request["request"]["generation_config"] = config
            batch_requests.append(request)
    
    if job_display_name is None:
        job_display_name = f"ocr-batch-{base_name}"
    
    logger.info(f"Creating batch job '{job_display_name}' with {len(batch_requests)} requests...")
    
    # Create the batch requests jsonl file
    if jsonl_dir is not None:
        Path(jsonl_dir).mkdir(parents=True, exist_ok=True)
        jsonl_filename = str(Path(jsonl_dir) / f"batch_requests_{base_name}.jsonl")
    else:
        jsonl_filename = f"batch_requests_{base_name}.jsonl"
    with open(jsonl_filename, "w", encoding="utf-8") as f:
        for req in batch_requests:
            f.write(json.dumps(req, default=str) + "\n")

    # Upload batch requests jsonl file to google file API
    uploaded_file = client.client.files.upload(
        file=jsonl_filename,
        config=types.UploadFileConfig(
            display_name=f"batch-requests-{base_name}", 
            mime_type="jsonl"
        )
    )
    
    if not uploaded_file.name:
        raise ValueError("Failed to get name for uploaded batch requests file.")
        
    logger.info(f"Uploaded batch requests file: {uploaded_file.name}")
    # Create batch job with file
    batch_config = types.CreateBatchJobConfig(display_name=job_display_name)
    batch_job = client.client.batches.create(
        model=model_name,
        src=uploaded_file.name,
        config=batch_config
    )
    # Clean up local batch requests file
    #os.remove(jsonl_filename)
    
    if not batch_job.name:
        raise ValueError("Failed to create batch job or get job name.")
        
    logger.info(f"Created batch job: {batch_job.name}")
    return batch_job.name


def get_job_state(job_name: str) -> Optional[str]:
    """
    Get the current state of a batch job.
    
    Args:
        job_name: Name of the batch job.
    
    Returns:
        Current job state or None if not available.
    """
    client = GeminiClient()
    batch_job = client.client.batches.get(name=job_name)
    if batch_job.state and batch_job.state.name:
        return batch_job.state.name
    return None


def monitor_batch_job(job_name: str, poll_interval: int = app_config.BATCH_CONFIG["poll_interval"]) -> str:
    """
    Monitor a batch job until completion.
    
    Args:
        job_name: Name of the batch job to monitor.
        poll_interval: Seconds to wait between status checks.
    
    Returns:
        Final job state.
    """
    client = GeminiClient()
    
    logger.info(f"Monitoring batch job: {job_name}")
    
    while True:
        batch_job = client.client.batches.get(name=job_name)
        if batch_job.state:
            state = batch_job.state.name
            logger.info(f"Job state: {state}")
            if state in app_config.BATCH_CONFIG["completed_states"]:
                if state == 'JOB_STATE_FAILED':
                    logger.error(f"Job failed with error: {getattr(batch_job, 'error', None)}")
                return state
        else:
            logger.info("Job state is not available yet, continuing to poll.")
        time.sleep(poll_interval)
        
        
def download_batch_results_file(batch_job_name: str, output_dir: str, overwrite: bool = True) -> str:
    """
    Download a batch results jsonl file from the Gemini file API.
    
    Args:
        batch_job_name: Name of the batch job to download results for.
        output_dir: Directory to save the downloaded file.
    
    Returns:
        Path to the downloaded file.
    """
    client = GeminiClient()
    batch_job = client.client.batches.get(name=batch_job_name)

    if batch_job.state is None or batch_job.state.name is None:
        raise ValueError("Batch job state is missing or invalid.")
    if batch_job.state.name != 'JOB_STATE_SUCCEEDED':
        raise ValueError(f"Job not succeeded. Current state: {batch_job.state.name}")
    if not batch_job.dest or not batch_job.dest.file_name:
        raise ValueError("Batch job does not have an associated results file (was it an inline request?).")

    if batch_job.display_name:
        new_file_name = batch_job.display_name + ".jsonl"
    else:
        new_file_name = batch_job.dest.file_name

    output_path = Path(output_dir) / Path(new_file_name).name

    if not overwrite and output_path.exists():
        logger.info(f"File {output_path} already exists and overwrite is False. Skipping download.")
        return str(output_path)

    logger.info(f"Downloading batch results file {batch_job.dest.file_name} to {output_path}...")
    file_content = client.client.files.download(file=batch_job.dest.file_name)
    if not file_content:
        raise ValueError("Failed to download batch results file or file is empty.")
    with open(output_path, "wb") as f:
        f.write(file_content)
    logger.info(f"Downloaded batch results file to {output_path}")
    return str(output_path)


def read_jsonl_file(file_path: str) -> List[Dict]:
    """
    Read a JSONL file and return a list of dictionaries.
    
    Args:
        file_path: Path to the JSONL file.
    
    Returns:
        A list of dictionaries, each representing a line in the JSONL file.
    """
    with open(file_path, "r", encoding="utf-8") as f:
        lines = f.readlines()

    return [json.loads(line) for line in lines]


def parse_pdf_batch_results_file(file_path: str) -> BatchOCRResult:
    """
    Retrieve results from a completed batch OCR job or a local JSONL file.
    
    Args:
        file_path: Name of the completed batch job (starts with "batches/") 
                          or path to a local JSONL results file.
    
    Returns:
        A BatchOCRResult object with results_by_page and pdf_name.
    """
    
    json_lines = read_jsonl_file(file_path)

    if not json_lines:
        logger.warning("No results content found to process.")
        return BatchOCRResult(results_by_page={}, pdf_name="unknown")
    
    results_by_page = {}
    pdf_name = "unknown"

    for line in json_lines:
        if 'response' not in line:
            logger.warning("Skipping line without 'response' field.")
            continue
        # parse metadata from the request key we built when sending the batch
        key = line.get('key', '')
        parts = key.split('_')
        pdf_name = parts[0]
        page_num = int(parts[2])
        sample_num = int(parts[4])
    
        llm_output = line['response']['candidates'][0]['content']['parts'][0]['text']
        # Extract the first JSON object from the output
        data = None
        # First, strip any code block markers
        clean_output = strip_json_codeblock(llm_output)
        json_str = re.search(r'\{.*\}', clean_output, re.DOTALL)
        if json_str:
            try:
                data = json.loads(json_str.group())
            except json.JSONDecodeError:
                logger.warning(f"Could not decode JSON from LLM output. Page {page_num}, sample {sample_num}.")
                data = clean_output
        else:
            data = clean_output

        if page_num not in results_by_page:
            results_by_page[page_num] = {}
        results_by_page[page_num][sample_num] = data
    
    logger.info(f"Retrieved results for {len(results_by_page)} pages from {pdf_name}")
    return BatchOCRResult(results_by_page=results_by_page, pdf_name=pdf_name)


def ocr_pdf_batch(
    pdf_path: str,
    prompt: str,
    model_name: str = app_config.MODEL_CONFIG["default_model"],
    max_pages: Optional[int] = None,
    start_page: int = 1,
    n_samples: int = 1,
    wait_for_completion: bool = False,
    poll_interval: int = app_config.BATCH_CONFIG["poll_interval"],
    generation_config: Optional[Dict[str, Any]] = None,
    response_schema=None,
    jsonl_dir: Optional[str] = None
) -> Union[str, Dict, None]:
    """
    OCR a PDF using batch mode (50% cost, ~24h turnaround).
    
    Args:
        pdf_path: Path to PDF containing scanned images.
        prompt_template: Template name from PROMPT_TEMPLATES or "custom"
        custom_prompt: Custom prompt if prompt_template is "custom"
        model_name: Gemini model.
        max_pages: Limit number of pages processed.
        start_page: 1-based page index to start from.
        n_samples: Number of times to OCR each page.
        wait_for_completion: If True, waits for job completion and returns results.
                           If False, returns job name for manual monitoring.
        poll_interval: Seconds between status checks.
        generation_config: Configuration for the generation process.
        response_schema: Schema for structured output.
        jsonl_dir: Optional directory to save the batch requests JSONL file. If None, saves in current directory.
    
    Returns:
        If wait_for_completion=True: A dictionary of results.
        If wait_for_completion=False: Job name string for manual monitoring.
    """
    
    final_generation_config = app_config.MODEL_CONFIG["generation_config"].copy()
    if generation_config:
        final_generation_config.update(generation_config)

    job_name = create_batch_ocr_job(
        pdf_path=pdf_path,
        prompt=prompt,
        model_name=model_name,
        max_pages=max_pages,
        start_page=start_page,
        n_samples=n_samples,
        generation_config=final_generation_config,
        response_schema=response_schema,
        jsonl_dir=jsonl_dir,
    )

    if not wait_for_completion:
        return job_name

    final_state = monitor_batch_job(job_name, poll_interval)

    if final_state == 'JOB_STATE_SUCCEEDED':
        download_batch_results_file(job_name, output_dir=str(Path(pdf_path).parent))
    else:
        raise Exception(f"Batch job failed with state: {final_state}")
    
def convert_table_schema_to_columns(schema: types.Schema) -> List[str]:
    """
    Convert a genai.types.Schema object to a list of column names.
    
    Args:
        schema: The schema object to convert.
    
    Returns:
        A list of column names.
    """
    if schema.type != types.Type.ARRAY or not schema.items or schema.items.type != types.Type.OBJECT:
        raise ValueError("Schema must be an array of objects.")
    
    return list(schema.items.properties["table"].items.property_ordering) # type: ignore
    

def parse_table_ocr_into_dataframe(ocr_results: Dict[int, Dict[int, Any]], columns: List[str], table_key: str = "table", add_row_id: bool = False) -> pl.DataFrame:
    """
    Parses the results from retrieve_pdf_batch_results into a polars DataFrame.

    Args:
        ocr_results: A dictionary where keys are page numbers and values are dictionaries
                     mapping sample numbers to OCR results.
        columns: A list of column names for the DataFrame.
        table_key: The key in the nested dictionary that holds the table data.
        add_row_id: If True, adds an incrementing unique row ID column.

    Returns:
        A polars DataFrame with the parsed data.
    """
    parsed_dfs = []
    for page, samples in ocr_results.items():
        for sample_num, data in samples.items():
            if not isinstance(data, dict) or table_key not in data:
                logger.warning(f"Skipping page {page}, sample {sample_num} due to invalid data format or missing '{table_key}' key.")
                continue
            
            table_data = data[table_key]
            
            if not table_data:
                logger.warning(f"Skipping page {page}, sample {sample_num} due to empty table data.")
                continue

            try:
                df = pl.DataFrame(table_data, schema=columns, strict=False)
                df = df.with_columns(
                    page=pl.lit(page),
                    sample=pl.lit(sample_num)
                )
                if add_row_id:
                    df = df.with_row_index(name="row_id", offset=1)
                parsed_dfs.append(df)
            except Exception as e:
                logger.error(f"Error processing page {page}, sample {sample_num}: {e}")

    if not parsed_dfs:
        # Create an empty DataFrame with the correct schema if no data was parsed
        return pl.DataFrame(schema=(["row_id"] if add_row_id else []) + columns + ["page", "sample"])


    full_df = pl.concat(parsed_dfs, how="vertical_relaxed")
    return full_df

def sum_token_counts_from_jsonl(file_path: str) -> dict:
    """
    Parses a Gemini batch results JSONL file, sums the token counts from usageMetadata,
    and returns a dictionary of the total counts for each token type.

    Args:
        file_path: Path to the JSONL results file.

    Returns:
        A dictionary with the summed token counts for each token type.
    """
    json_lines = read_jsonl_file(file_path)
    
    if not json_lines:
        logger.warning("No content found in the JSONL file.")
        return {}

    total_token_counts = collections.defaultdict(int)

    for line in json_lines:
        response_data = line.get('response')
        if response_data:
            # Handle both camelCase and snake_case for usage metadata key
            usage_metadata = response_data.get('usageMetadata', response_data.get('usage_metadata'))
            if usage_metadata:
                for token_type, count in usage_metadata.items():
                    if isinstance(count, int):
                        total_token_counts[token_type] += count
    
    return dict(total_token_counts)

def calculate_cost(
    total_token_counts: dict, 
    price_input_per_million_tokens: float, 
    price_output_per_million_tokens: float
) -> float:
    """
    Calculates the total cost for a batch job based on token counts and prices.

    Args:
        total_token_counts: A dictionary with summed token counts, 
                            like one returned by sum_token_counts_from_jsonl.
        price_input_per_million_tokens: The price in dollars per 1 million input tokens.
        price_output_per_million_tokens: The price in dollars per 1 million output tokens.

    Returns:
        The total calculated cost in dollars.
    """
    # Handle both camelCase and snake_case keys
    input_tokens = total_token_counts.get('promptTokenCount', total_token_counts.get('prompt_token_count', 0))
    output_tokens = total_token_counts.get('candidatesTokenCount', total_token_counts.get('candidates_token_count', 0))

    input_cost = (input_tokens / 1_000_000) * price_input_per_million_tokens
    output_cost = (output_tokens / 1_000_000) * price_output_per_million_tokens

    total_cost = input_cost + output_cost
    return total_cost
