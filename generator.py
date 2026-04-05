"""
Generator module — calls FAL AI models to produce images from prompts.
Runs all 3 models in parallel via asyncio. Downloads results with httpx.
"""

import asyncio
import os
import tempfile
from pathlib import Path

import fal_client
import httpx

from config import IMAGE_HEIGHT, IMAGE_WIDTH, MODELS, NEGATIVE_PROMPT


def _build_arguments(model_name: str, prompt: str) -> dict:
    """
    Build model-specific arguments dict.
    - ideogram / flux: support custom image_size as {width, height} + negative_prompt
    - seedream: uses aspect_ratio string (3:4 is closest to 4:5) and no negative_prompt
    """
    if model_name == "seedream":
        return {
            "prompt": prompt,
            "aspect_ratio": "3:4",
            "num_images": 1,
        }

    # ideogram and flux both accept image_size dict and negative_prompt
    return {
        "prompt": prompt,
        "image_size": {"width": IMAGE_WIDTH, "height": IMAGE_HEIGHT},
        "negative_prompt": NEGATIVE_PROMPT,
    }


async def _subscribe_model(
    model_id: str,
    model_name: str,
    prompt: str,
) -> str | None:
    """
    Submit a generation request to a single FAL model and return the image URL.
    Uses the native async subscribe_async for non-blocking calls.
    """
    arguments = _build_arguments(model_name, prompt)

    result = await fal_client.subscribe_async(
        model_id,
        arguments=arguments,
    )

    # FAL returns image URLs in result["images"][0]["url"]
    if isinstance(result, dict):
        images = result.get("images", [])
        if images and isinstance(images, list):
            url = images[0].get("url") if isinstance(images[0], dict) else images[0]
            return url
        # Fallback: some models nest in "output"
        output = result.get("output")
        if isinstance(output, dict):
            return output.get("url")
        if isinstance(output, list) and output:
            return output[0].get("url") if isinstance(output[0], dict) else output[0]
    return None


async def _download_image(url: str, dest: str) -> str:
    """
    Download an image from a URL and save it to dest path. Returns dest.
    """
    async with httpx.AsyncClient(timeout=60.0, follow_redirects=True) as client:
        response = await client.get(url)
        response.raise_for_status()
        Path(dest).parent.mkdir(parents=True, exist_ok=True)
        with open(dest, "wb") as f:
            f.write(response.content)
    return dest


async def generate_for_model(
    model_name: str,
    model_id: str,
    prompts: list[str],
    product_slug: str,
) -> list[dict]:
    """
    Generate all slides for one model. Returns a list of result dicts:
    [{"model": str, "slide": int, "path": str | None, "error": str | None}, ...]
    """
    results: list[dict] = []

    for idx, prompt in enumerate(prompts, start=1):
        slide_num = idx
        print(f"[INFO] Generating Slide {slide_num} with {model_name}...")

        try:
            image_url = await _subscribe_model(model_id, model_name, prompt)

            if not image_url:
                print(f"[WARN] No image URL returned for {model_name} slide {slide_num}")
                results.append({
                    "model": model_name,
                    "slide": slide_num,
                    "path": None,
                    "error": "No image URL in response",
                })
                continue

            # Save to a temp location; watermark.py will move to final output
            temp_dir = os.path.join(
                tempfile.gettempdir(), "rayna-carousel", product_slug, model_name
            )
            temp_path = os.path.join(temp_dir, f"raw_slide_{slide_num}.png")

            await _download_image(image_url, temp_path)
            print(f"[INFO] Downloaded {model_name} slide {slide_num}")

            results.append({
                "model": model_name,
                "slide": slide_num,
                "path": temp_path,
                "error": None,
            })

        except Exception as e:
            print(f"[ERROR] {model_name} slide {slide_num} failed: {e}")
            results.append({
                "model": model_name,
                "slide": slide_num,
                "path": None,
                "error": str(e),
            })

    return results


async def generate_all_models(
    prompts: list[str],
    product_slug: str,
) -> list[dict]:
    """
    Run image generation across all configured models in parallel.
    Returns a flat list of result dicts from every model.
    """
    tasks = [
        generate_for_model(model_name, model_id, prompts, product_slug)
        for model_name, model_id in MODELS.items()
    ]

    # Run all models concurrently; each model processes slides sequentially
    model_results = await asyncio.gather(*tasks, return_exceptions=True)

    all_results: list[dict] = []
    for i, result in enumerate(model_results):
        model_name = list(MODELS.keys())[i]
        if isinstance(result, Exception):
            print(f"[ERROR] Entire {model_name} pipeline failed: {result}")
            for slide_num in range(1, len(prompts) + 1):
                all_results.append({
                    "model": model_name,
                    "slide": slide_num,
                    "path": None,
                    "error": str(result),
                })
        else:
            all_results.extend(result)

    return all_results
