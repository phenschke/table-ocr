"""
OCR functionality using direct API calls.
"""

import asyncio
from typing import Union, Optional, Dict, Any, List, Callable
from PIL import Image
from google.genai import types

from .core import GeminiClient, prepare_image_for_gemini, pdf_pages_to_images, log_token_usage, logger
from . import config as app_config


def query_gemini_with_image(
    image: Union[str, Image.Image, bytes],
    prompt: str,
    model_name: str = app_config.MODEL_CONFIG["default_model"],
    api_key: Optional[str] = None,
    config: Optional[Dict[str, Any]] = None,
    thinking_budget: Optional[int] = app_config.MODEL_CONFIG["thinking_budget"],
    client: Optional[GeminiClient] = None,
    response_schema=None,
) -> str:
    """
    Query Google Gemini model with an image and text prompt.
    
    Args:
        image: Input image - can be:
            - str: path to image file
            - PIL.Image.Image: PIL Image object
            - bytes: raw image bytes
        prompt: Text prompt to send along with the image
        model_name: Name of the Gemini model to use
        api_key: Google AI API key. If None, will try to get from GEMINI_API_KEY environment variable
        config: Optional generation configuration dict
        client: Optional reusable GeminiClient instance
    
    Returns:
        str: Response text from the Gemini model, or 'ERROR' if the call fails
    """
    # Get or create client
    if client is None:
        client = GeminiClient(api_key=api_key)
    # Use default config if none provided
    if config is None:
        config = app_config.MODEL_CONFIG["generation_config"].copy()

    # Ensure config is a dict at this point
    assert config is not None

    # Add response_schema for structured output
    if response_schema is not None:
        config = config.copy()  # copy to avoid mutating caller's dict
        config["response_mime_type"] = "application/json"
        if hasattr(response_schema, "to_json_dict"):
            config["response_schema"] = response_schema.to_json_dict()
        else:
            config["response_schema"] = response_schema
    # Add thinking budget if provided (Gemini 2.5 models only)
    if thinking_budget is not None:
        config = config.copy()
        config["thinking_config"] = types.ThinkingConfig(
            thinking_budget=thinking_budget
        ).to_json_dict()
    # Prepare image part for Gemini API
    image_part = prepare_image_for_gemini(image)
    logger.info(f"Sending image to Gemini model '{model_name}' with prompt: {prompt}...")
    try:
        response = client.generate_content(
            model_name=model_name,
            contents=[image_part, prompt],
            generation_config=config
        )
        logger.info("Gemini API call successful.")
        log_token_usage(response, logger)
        return response.text or ""
    except Exception as e:
        logger.error(f"Gemini API call failed: {e}")
        return "ERROR"

def query_gemini_with_image_from_file(
    image_path: str,
    prompt: str,
    **kwargs,
) -> str:
    """
    Helper to query Gemini with an image from a file path.
    """
    return query_gemini_with_image(image=image_path, prompt=prompt, **kwargs)


def ocr_single_image(
    image: Union[str, Image.Image, bytes],
    prompt_template: str = "basic",
    **kwargs,
) -> str:
    """
    OCR a single image using a prompt template.
    """
    prompt = app_config.PROMPT_TEMPLATES.get(prompt_template, prompt_template)
    return query_gemini_with_image(image=image, prompt=prompt, **kwargs)


def ocr_single_page(
    pdf_path: str,
    page_num: int,
    prompt_template: str = "basic",
    **kwargs,
) -> str:
    """
    OCR a single page of a PDF.
    """
    prompt = app_config.PROMPT_TEMPLATES.get(prompt_template, prompt_template)
    images = pdf_pages_to_images(pdf_path, start_page=page_num-1, max_pages=1)
    if not images:
        return "ERROR: Could not extract image from page."
    return query_gemini_with_image(image=images[0], prompt=prompt, **kwargs)

def ocr_pdf(
    pdf_path: str,
    prompt_template: str = "basic",
    model_name: str = app_config.MODEL_CONFIG["default_model"],
    max_pages: Optional[int] = None,
    start_page: int = 1,
    n_samples: int = 1,
    stream_output: bool = False,
    display: bool = False,
    response_schema=None,
    progress_callback=None,
) -> List[List[str]]:
    """
    OCR a (scanned) PDF with Gemini page-by-page.
    
    Args:
        progress_callback: Optional callback function(current_page, total_pages) called after each page
    """
    prompt = app_config.PROMPT_TEMPLATES.get(prompt_template, prompt_template)
    images = pdf_pages_to_images(
        pdf_path=pdf_path,
        max_pages=max_pages,
        start_page=start_page-1,
        display=display
    )

    logger.info(f"Starting OCR for {len(images)} pages using Gemini model '{model_name}' with {n_samples} samples per page...")
    client = GeminiClient()
    results: List[List[str]] = []
    total_pages = len(images)
    
    for i, img in enumerate(images):
        page_num = start_page + i
        logger.info(f"Processing page {page_num}/{start_page+len(images)-1} with {n_samples} samples...")
        
        page_results: List[str] = []
        for sample_idx in range(n_samples):
            logger.info(f"Sample {sample_idx+1}/{n_samples} for page {page_num}")
            text = query_gemini_with_image(
                image=img,
                prompt=prompt,
                model_name=model_name,
                client=client,
                response_schema=response_schema,
            )
            page_results.append(text)
            if stream_output:
                print(f"--- Page {page_num} Sample {sample_idx+1} OCR Result ---\n{text}\n")
        
        results.append(page_results)
        
        # Call progress callback if provided
        if progress_callback:
            progress_callback(i + 1, total_pages)
    
    logger.info(f"OCR complete. {len(results)} pages processed with {n_samples} samples each.")
    return results


# ============================================================================
# ASYNC/PARALLEL PROCESSING FUNCTIONS
# ============================================================================

async def aquery_gemini_with_image(
    image: Union[str, Image.Image, bytes],
    prompt: str,
    model_name: str = app_config.MODEL_CONFIG["default_model"],
    api_key: Optional[str] = None,
    config: Optional[Dict[str, Any]] = None,
    thinking_budget: Optional[int] = app_config.MODEL_CONFIG["thinking_budget"],
    client: Optional[GeminiClient] = None,
    response_schema=None,
    semaphore: Optional[asyncio.Semaphore] = None,
) -> str:
    """
    Async version of query_gemini_with_image.

    Args:
        semaphore: Optional semaphore to control concurrency and rate limiting
        (all other args same as query_gemini_with_image)

    Returns:
        str: Response text from the Gemini model, or 'ERROR' if the call fails
    """
    # Get or create client
    if client is None:
        client = GeminiClient(api_key=api_key)

    # Use default config if none provided
    if config is None:
        config = app_config.MODEL_CONFIG["generation_config"].copy()

    # Ensure config is a dict at this point
    assert config is not None

    # Add response_schema for structured output
    if response_schema is not None:
        config = config.copy()
        config["response_mime_type"] = "application/json"
        if hasattr(response_schema, "to_json_dict"):
            config["response_schema"] = response_schema.to_json_dict()
        else:
            config["response_schema"] = response_schema

    # Add thinking budget if provided (Gemini 2.5 models only)
    if thinking_budget is not None:
        config = config.copy()
        config["thinking_config"] = types.ThinkingConfig(
            thinking_budget=thinking_budget
        ).to_json_dict()

    # Prepare image part for Gemini API
    image_part = prepare_image_for_gemini(image)

    logger.info(f"[Async] Sending image to Gemini model '{model_name}' with prompt: {prompt[:50]}...")

    try:
        # Use semaphore to control concurrency if provided
        if semaphore:
            async with semaphore:
                response = await client.agenerate_content(
                    model_name=model_name,
                    contents=[image_part, prompt],
                    generation_config=config
                )
        else:
            response = await client.agenerate_content(
                model_name=model_name,
                contents=[image_part, prompt],
                generation_config=config
            )

        logger.info("[Async] Gemini API call successful.")
        log_token_usage(response, logger)
        return response.text or ""
    except Exception as e:
        logger.error(f"[Async] Gemini API call failed: {e}")
        return "ERROR"


async def ocr_pdf_async(
    pdf_path: str,
    prompt_template: str = "basic",
    model_name: str = app_config.MODEL_CONFIG["default_model"],
    max_pages: Optional[int] = None,
    start_page: int = 1,
    n_samples: int = 1,
    response_schema=None,
    progress_callback: Optional[Callable[[int, int], None]] = None,
    max_concurrent_requests: int = 5,
) -> List[List[str]]:
    """
    OCR a PDF with Gemini using parallel/async processing.

    Args:
        pdf_path: Path to PDF file
        prompt_template: Prompt template name or actual prompt text
        model_name: Gemini model to use
        max_pages: Maximum number of pages to process
        start_page: Starting page number (1-based)
        n_samples: Number of samples per page
        response_schema: Optional Pydantic schema for structured output
        progress_callback: Optional callback(current, total) called after each page completes
        max_concurrent_requests: Maximum number of concurrent API requests (default 5)

    Returns:
        List[List[str]]: Results organized as [page][sample]
    """
    prompt = app_config.PROMPT_TEMPLATES.get(prompt_template, prompt_template)
    images = pdf_pages_to_images(
        pdf_path=pdf_path,
        max_pages=max_pages,
        start_page=start_page-1,
        display=False
    )

    total_pages = len(images)
    total_requests = total_pages * n_samples

    logger.info(
        f"Starting async OCR for {total_pages} pages using Gemini model '{model_name}' "
        f"with {n_samples} samples per page ({total_requests} total API calls, "
        f"max {max_concurrent_requests} concurrent requests)..."
    )

    # Warn if concurrency is too high (may hit rate limits)
    if max_concurrent_requests > 10:
        logger.warning(
            f"max_concurrent_requests={max_concurrent_requests} is aggressive and may hit rate limits. "
            f"Consider reducing to 5-10 if you encounter errors."
        )

    # Create a semaphore to limit concurrent requests (respects rate limits)
    semaphore = asyncio.Semaphore(max_concurrent_requests)

    # Create shared client
    client = GeminiClient()

    # Track completed pages for progress reporting
    completed_pages = set()
    pages_fully_completed = set()
    progress_lock = asyncio.Lock()

    async def process_page_sample(page_idx: int, sample_idx: int, img: Image.Image) -> tuple[int, int, str]:
        """Process a single sample for a single page."""
        page_num = start_page + page_idx
        logger.info(f"[Async] Processing page {page_num} sample {sample_idx+1}/{n_samples}")

        text = await aquery_gemini_with_image(
            image=img,
            prompt=prompt,
            model_name=model_name,
            client=client,
            response_schema=response_schema,
            semaphore=semaphore,
        )

        # Track page completion for progress callback
        async with progress_lock:
            completed_pages.add((page_idx, sample_idx))
            # Check if all samples for this page are done
            page_samples_done = sum(1 for p, _ in completed_pages if p == page_idx)
            if page_samples_done == n_samples and page_idx not in pages_fully_completed:
                pages_fully_completed.add(page_idx)
                # Report COUNT of completed pages (monotonically increasing)
                completed_count = len(pages_fully_completed)
                if progress_callback:
                    progress_callback(completed_count, total_pages)

        return page_idx, sample_idx, text

    # Create all tasks
    tasks = []
    for page_idx, img in enumerate(images):
        for sample_idx in range(n_samples):
            task = process_page_sample(page_idx, sample_idx, img)
            tasks.append(task)

    # Execute all tasks concurrently
    logger.info(f"Launching {len(tasks)} async tasks with concurrency limit of {max_concurrent_requests}...")
    try:
        results_flat = await asyncio.gather(*tasks, return_exceptions=False)
    except Exception as e:
        logger.error(f"Error during async gather: {e}")
        raise

    # Organize results by page and sample
    results: List[List[str]] = [['' for _ in range(n_samples)] for _ in range(total_pages)]
    error_count = 0
    for page_idx, sample_idx, text in results_flat:
        results[page_idx][sample_idx] = text
        if text == "ERROR":
            error_count += 1

    if error_count > 0:
        logger.warning(f"Async OCR complete with {error_count} errors out of {len(results_flat)} API calls.")
    else:
        logger.info(f"Async OCR complete successfully. {total_pages} pages processed with {n_samples} samples each.")

    return results


def ocr_pdf_parallel(
    pdf_path: str,
    prompt_template: str = "basic",
    model_name: str = app_config.MODEL_CONFIG["default_model"],
    max_pages: Optional[int] = None,
    start_page: int = 1,
    n_samples: int = 1,
    response_schema=None,
    progress_callback: Optional[Callable[[int, int], None]] = None,
    max_concurrent_requests: int = 5,
) -> List[List[str]]:
    """
    Synchronous wrapper for ocr_pdf_async. Use this from non-async code.

    This function runs the async OCR in an event loop and returns the results.
    All parameters are the same as ocr_pdf_async.
    """
    return asyncio.run(ocr_pdf_async(
        pdf_path=pdf_path,
        prompt_template=prompt_template,
        model_name=model_name,
        max_pages=max_pages,
        start_page=start_page,
        n_samples=n_samples,
        response_schema=response_schema,
        progress_callback=progress_callback,
        max_concurrent_requests=max_concurrent_requests,
    ))
