"""
Real Image Carousel — separate pipeline from the AI-generation main.py.
Downloads real product images from enriched API, generates Claude text
overlays, and composites them for Instagram-ready carousel output.

Usage:
    python real_main.py
"""

import asyncio
import os
import tempfile
import time
from pathlib import Path

import httpx
from dotenv import load_dotenv
from PIL import Image

from config import (
    ENRICHED_PRODUCT_TYPES,
    IMAGE_HEIGHT,
    IMAGE_WIDTH,
    OUTPUT_DIR,
    SLIDES_PER_PRODUCT,
)
from content_planner import plan_content_enriched
from fetcher import fetch_enriched_feed
from watermark import apply_watermark

# Target product IDs to process (Dubai products)
TARGET_PRODUCT_IDS: list[int] = [18, 33, 37, 39, 40, 44, 45, 47, 49]


def _slugify(text: str) -> str:
    """Convert a product title to a filesystem-safe slug."""
    return text.lower().strip().replace(" ", "-").replace("/", "-").replace("\\", "-")


async def _download_image(url: str, dest: str) -> str:
    """Download an image from a URL and save to dest. Returns dest path."""
    async with httpx.AsyncClient(timeout=60.0, follow_redirects=True) as client:
        response = await client.get(url)
        response.raise_for_status()
        Path(dest).parent.mkdir(parents=True, exist_ok=True)
        with open(dest, "wb") as f:
            f.write(response.content)
    return dest


def _resize_to_instagram(
    image_path: str, width: int = IMAGE_WIDTH, height: int = IMAGE_HEIGHT,
) -> str:
    """
    Resize and center-crop an image to Instagram 4:5 (1080x1350).
    Scales so the smaller dimension fills the target, then center-crops.
    Overwrites in-place and returns the path.
    """
    img = Image.open(image_path).convert("RGB")
    src_w, src_h = img.size
    target_ratio = width / height

    src_ratio = src_w / src_h
    if src_ratio > target_ratio:
        # Source wider — fit by height, crop width
        new_h = height
        new_w = int(src_w * (height / src_h))
    else:
        # Source taller — fit by width, crop height
        new_w = width
        new_h = int(src_h * (width / src_w))

    img = img.resize((new_w, new_h), Image.LANCZOS)

    # Center crop
    left = (new_w - width) // 2
    top = (new_h - height) // 2
    img = img.crop((left, top, left + width, top + height))

    img.save(image_path, "PNG", quality=95)
    return image_path


def _select_images(
    all_image_links: list[str], needed: int = SLIDES_PER_PRODUCT,
) -> list[str]:
    """
    Select exactly `needed` images from available links.
    If more: take first N. If fewer: cycle from beginning.
    """
    if not all_image_links:
        return []
    if len(all_image_links) >= needed:
        return all_image_links[:needed]
    # Fewer than needed — cycle
    selected = []
    for i in range(needed):
        selected.append(all_image_links[i % len(all_image_links)])
    return selected


async def run() -> None:
    """
    Main async pipeline for real-image carousel:
    1. Fetch enriched product data (with real image URLs)
    2. For each product: download → resize → Claude plan → watermark → save
    """
    start_time = time.time()

    # --- Step 1: Fetch enriched feed ---
    print("[INFO] Fetching enriched product feed...")
    products = await fetch_enriched_feed(ENRICHED_PRODUCT_TYPES)

    if not products:
        print("[ERROR] No products returned from enriched feed. Exiting.")
        return

    # Filter to target product IDs only
    if TARGET_PRODUCT_IDS:
        products = [
            p for p in products
            if p.get("id") in TARGET_PRODUCT_IDS
               or p.get("productId") in TARGET_PRODUCT_IDS
               or p.get("id") in [str(i) for i in TARGET_PRODUCT_IDS]
               or p.get("productId") in [str(i) for i in TARGET_PRODUCT_IDS]
        ]
        print(f"[INFO] Filtered to {len(products)} target product(s).")

    if not products:
        print("[ERROR] No matching products found for target IDs. Exiting.")
        return

    print(f"[INFO] Processing {len(products)} product(s).\n")

    total_generated = 0
    total_failed = 0

    for product in products:
        name = product.get("name", "Unknown Product")
        city = product.get("city", "")
        country = product.get("country", "")
        destination = f"{city}, {country}" if country else city
        sale_price = product.get("salePrice", product.get("normalPrice", ""))
        normal_price = product.get("normalPrice", "")
        currency = product.get("currency", "")
        price_str = f"{currency} {sale_price}" if sale_price else ""
        # Build normal price string for discount display (only if different from sale)
        normal_price_str = ""
        if normal_price and str(normal_price) != str(sale_price):
            normal_price_str = f"{currency} {normal_price}"
        product_slug = _slugify(name)
        all_image_links = product.get("all_image_links", [])

        print(f"{'='*60}")
        print(f"[INFO] Product: {name}")
        print(f"[INFO] Destination: {destination}")
        print(f"[INFO] Images available: {len(all_image_links)}")
        print(f"{'='*60}")

        # --- Step 2a: Select 5 images ---
        selected_urls = _select_images(all_image_links, SLIDES_PER_PRODUCT)
        if not selected_urls:
            print(f"[WARN] No images for {name}. Skipping.")
            total_failed += SLIDES_PER_PRODUCT
            continue

        # --- Step 2b: Download and resize images ---
        print(f"[INFO] Downloading {len(selected_urls)} real images...")
        temp_dir = os.path.join(
            tempfile.gettempdir(), "rayna-carousel-real", product_slug
        )
        downloaded_paths: list[str | None] = []

        for idx, url in enumerate(selected_urls, start=1):
            try:
                temp_path = os.path.join(temp_dir, f"raw_slide_{idx}.png")
                await _download_image(url, temp_path)
                _resize_to_instagram(temp_path)
                downloaded_paths.append(temp_path)
                print(f"[INFO] Downloaded & resized slide {idx}")
            except Exception as e:
                print(f"[ERROR] Failed to download slide {idx}: {e}")
                downloaded_paths.append(None)

        # --- Step 2c: Generate content plan with Claude ---
        print("[INFO] Planning content with Claude AI (enriched data)...")
        content_plan = await plan_content_enriched(product)

        print(f"\n  [REAL] Content plan:")
        for slide in content_plan.get("slides", []):
            stype = slide.get("slide_type", "?")
            hl = slide.get("overlay_headline", "")
            print(f"    Slide {slide['slide_number']} ({stype}): {hl}")

        # --- Step 2d: Apply watermarks ---
        print(f"\n[INFO] Applying watermarks on real images...")
        for idx, img_path in enumerate(downloaded_paths, start=1):
            if img_path is None:
                total_failed += 1
                continue

            output_path = apply_watermark(
                source_path=img_path,
                product_slug=product_slug,
                model_name="real",
                slide_number=idx,
                content_plan=content_plan,
                price=price_str,
                normal_price=normal_price_str,
            )
            if output_path:
                print(f"[SUCCESS] Saved: {output_path}")
                total_generated += 1
            else:
                total_failed += 1

        print()

    # --- Summary ---
    elapsed = time.time() - start_time
    print(f"{'='*60}")
    print(f"[DONE] Real image pipeline complete!")
    print(f"  Total images generated: {total_generated}")
    print(f"  Total failed/skipped:   {total_failed}")
    print(f"  Time elapsed:           {elapsed:.1f}s")
    print(f"{'='*60}")


def main() -> None:
    """Load environment variables and run the real-image pipeline."""
    load_dotenv()

    # Only Anthropic key needed (no FAL)
    if not os.getenv("ANTHROPIC_API_KEY"):
        print("[WARN] ANTHROPIC_API_KEY not set. Will use fallback content templates.")

    print("[INFO] rayna-carousel (real images) starting...\n")
    asyncio.run(run())


if __name__ == "__main__":
    main()
