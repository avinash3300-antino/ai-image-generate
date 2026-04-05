"""
Main entry point for rayna-carousel.
Orchestrates: fetch data → Claude content plans (per model) → generate images → watermark.

Each of the 3 AI models gets its OWN unique content plan from Claude:
  - ideogram → Bold & Dramatic creative direction
  - flux     → Warm & Editorial creative direction
  - seedream → Clean & Modern creative direction
"""

import asyncio
import os
import time

from dotenv import load_dotenv

from config import MODELS, SLIDES_PER_PRODUCT, TEST_MODE

# ── Target filtering (set to None to use default TEST_MODE behavior) ──
TARGET_CITY_ID: int | None = 13668       # Dubai
TARGET_PRODUCT_ID: int | None = 18       # Burj Khalifa At The Top Tickets

from content_planner import plan_all_variants
from fetcher import fetch_cities, fetch_products
from generator import generate_for_model
from prompt_builder import build_prompts
from watermark import apply_watermark


def _slugify(text: str) -> str:
    """Convert a product title to a filesystem-safe slug."""
    return text.lower().strip().replace(" ", "-").replace("/", "-").replace("\\", "-")


async def run() -> None:
    """
    Main async pipeline:
    1. Fetch cities and products from the API
    2. Plan content with Claude AI — 3 DIFFERENT plans (one per model)
    3. Build image prompts per model from its unique content plan
    4. Generate images per model with its own prompts
    5. Apply watermarks per model with its own content plan
    """
    start_time = time.time()

    # --- Step 1: Fetch product data ---
    print("[INFO] Fetching available cities...")
    product_type = "tour"
    cities = await fetch_cities(product_type)

    if not cities:
        print("[ERROR] No cities returned from API. Exiting.")
        return

    # Filter to target city if specified
    if TARGET_CITY_ID:
        cities = [c for c in cities if str(c.get("city_id")) == str(TARGET_CITY_ID)]
    elif TEST_MODE:
        cities = cities[:1]

    print(f"[INFO] Found {len(cities)} city(ies). Fetching products...")

    all_products: list[dict] = []
    for city in cities:
        city_id = city.get("city_id", "")
        city_name = city.get("city_name", "Unknown")
        country_name = city.get("country_name", "")

        try:
            products = await fetch_products(
                product_type, city_id, city_name, country_name
            )
            all_products.extend(products)
        except Exception as e:
            print(f"[ERROR] Failed to fetch products for {city_name}: {e}")
            continue

    if not all_products:
        print("[ERROR] No products found. Exiting.")
        return

    # Filter to target product if specified
    if TARGET_PRODUCT_ID:
        all_products = [
            p for p in all_products
            if p.get("productId") == TARGET_PRODUCT_ID or p.get("id") == TARGET_PRODUCT_ID
        ]
    elif TEST_MODE:
        all_products = all_products[:1]

    print(f"[INFO] Processing {len(all_products)} product(s).\n")

    model_names = list(MODELS.keys())
    total_generated = 0
    total_failed = 0

    for product in all_products:
        name = product.get("name", "Unknown Product")
        city = product.get("city_name", product.get("city", ""))
        country = product.get("country_name", product.get("country", ""))
        destination = f"{city}, {country}" if country else city
        sale_price = product.get("salePrice", product.get("normalPrice", ""))
        currency = product.get("currency", "")
        price_str = f"{currency} {sale_price}" if sale_price else ""
        product_slug = _slugify(name)

        print(f"{'='*60}")
        print(f"[INFO] Product: {name}")
        print(f"[INFO] Destination: {destination}")
        print(f"[INFO] Slug: {product_slug}")
        print(f"{'='*60}")

        # --- Step 2: Plan content with Claude AI — 3 variants in parallel ---
        print("[INFO] Planning 3 unique content variants with Claude AI...")
        content_plans = await plan_all_variants(product, model_names)

        for model_name, plan in content_plans.items():
            print(f"\n  [{model_name.upper()}] Creative variant:")
            for slide in plan.get("slides", []):
                stype = slide.get("slide_type", "?")
                hl = slide.get("overlay_headline", "")
                al = slide.get("text_alignment", "left")
                print(f"    Slide {slide['slide_number']} ({stype}): {hl}  [{al}]")

        # --- Step 3 + 4: Build prompts & generate per model in parallel ---
        print(f"\n[INFO] Generating {SLIDES_PER_PRODUCT} slides x {len(MODELS)} models = "
              f"{SLIDES_PER_PRODUCT * len(MODELS)} images (each model has unique prompts)...")

        gen_tasks = []
        for model_name, model_id in MODELS.items():
            model_plan = content_plans[model_name]
            prompts = build_prompts(model_plan)
            gen_tasks.append(
                generate_for_model(model_name, model_id, prompts, product_slug)
            )

        model_results = await asyncio.gather(*gen_tasks, return_exceptions=True)

        # --- Step 5: Apply watermarks per model with its own content plan ---
        print("\n[INFO] Applying watermarks...")
        for i, result_set in enumerate(model_results):
            model_name = model_names[i]

            if isinstance(result_set, Exception):
                print(f"[ERROR] Entire {model_name} pipeline failed: {result_set}")
                total_failed += SLIDES_PER_PRODUCT
                continue

            model_plan = content_plans[model_name]

            for result in result_set:
                if result["path"] and not result["error"]:
                    output_path = apply_watermark(
                        source_path=result["path"],
                        product_slug=product_slug,
                        model_name=result["model"],
                        slide_number=result["slide"],
                        content_plan=model_plan,
                        price=price_str,
                    )
                    if output_path:
                        print(f"[SUCCESS] Saved: {output_path}")
                        total_generated += 1
                    else:
                        total_failed += 1
                else:
                    total_failed += 1
                    if result["error"]:
                        print(
                            f"[SKIP] {result['model']} slide {result['slide']} — "
                            f"{result['error']}"
                        )

        print()

    # --- Summary ---
    elapsed = time.time() - start_time
    print(f"{'='*60}")
    print(f"[DONE] Pipeline complete!")
    print(f"  Total images generated: {total_generated}")
    print(f"  Total failed/skipped:   {total_failed}")
    print(f"  Time elapsed:           {elapsed:.1f}s")
    print(f"{'='*60}")


def main() -> None:
    """Load environment variables and kick off the async pipeline."""
    load_dotenv()

    # Verify FAL_KEY
    fal_key = os.getenv("FAL_KEY")
    if not fal_key or fal_key == "your_fal_api_key_here":
        print("[ERROR] FAL_KEY is not set in .env. Please add your FAL API key.")
        return
    os.environ["FAL_KEY"] = fal_key

    # Check Anthropic key (warn only — fallback content exists)
    if not os.getenv("ANTHROPIC_API_KEY"):
        print("[WARN] ANTHROPIC_API_KEY not set. Will use fallback content templates.")

    print("[INFO] rayna-carousel starting...\n")
    asyncio.run(run())


if __name__ == "__main__":
    main()
