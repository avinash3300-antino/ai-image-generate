"""
Content Planner — uses Claude AI to generate rich marketing content
from minimal product data. Claude infers realistic itinerary, inclusions,
and experience details from just the product name, city, and price.

3 DIFFERENT creative variants per product (one per AI model) so each model
generates completely unique images with unique headlines, copy, and layout.
"""

import asyncio
import json
import os

import anthropic

# ── Creative variant descriptions (one per AI model) ──────────────────

CREATIVE_VARIANTS = {
    "ideogram": {
        "name": "Bold & Dramatic",
        "alignment": "center",
        "direction": (
            "BOLD, DRAMATIC, HIGH-IMPACT style. Think National Geographic meets luxury travel ads. "
            "Use powerful single-word or two-word headlines that HIT HARD. "
            "Image prompts: dramatic drone aerials, epic wide angles, jaw-dropping scale, "
            "golden hour, rich deep shadows, cinematic color grading."
        ),
    },
    "flux": {
        "name": "Warm & Editorial",
        "alignment": "left",
        "direction": (
            "WARM, EDITORIAL, LIFESTYLE style. Think Condé Nast Traveler meets Instagram influencer. "
            "Use conversational, inviting headlines that feel personal and aspirational. "
            "Image prompts: warm golden tones, shallow depth of field, lifestyle moments, "
            "close-up details, natural light, editorial magazine quality."
        ),
    },
    "seedream": {
        "name": "Clean & Modern",
        "alignment": "center",
        "direction": (
            "CLEAN, MODERN, MINIMAL style. Think Apple ads meets premium travel brand. "
            "Use short punchy headlines with a modern edge. "
            "Image prompts: clean compositions, vibrant saturated colors, symmetrical framing, "
            "minimalist scenes, striking contrasts, contemporary feel."
        ),
    },
}


SYSTEM_MESSAGE = """\
You are a world-class travel marketing creative director for Rayna Tours, \
a premium travel and tourism company based in the UAE.

Your job: Given MINIMAL product data (name, city, country, price, url), \
use your deep knowledge of real-world travel experiences to INFER specific \
details and create compelling Instagram carousel content.

CRITICAL RULES:
1. YOU decide ALL headlines — be CREATIVE and UNIQUE. Never use generic phrases \
like "Your Journey", "What's Included", "The Experience". Every headline should \
be specific, emotional, and different.
2. The text_alignment will be provided to you — use it for ALL slides consistently.
3. All image prompts must be HYPER-SPECIFIC to this product — reference real \
places, real features, real details. NO generic scenes.
4. NEVER include text/words/logos in image prompts.

EVERY slide needs:
- "image_prompt": Hyper-specific cinematic scene for AI image generation. \
NEVER include text/words/logos in the scene.
- "overlay_headline": YOUR creative headline (2-4 words max). Be ORIGINAL.
- "overlay_subline": Supporting line (4-8 words)
- "overlay_details": List of bullet strings with REAL specific info
- "text_alignment": Will be specified — use the SAME alignment for ALL slides.

DETAIL REQUIREMENTS:
- Slides 2, 3, and 4 MUST have 5-6 detail bullets each.
- Each bullet should be descriptive (5-8 words each), NOT just 2-word labels.
- Total detail text for slides 2, 3, 4 must be at LEAST 20 words per slide.
- Example good bullet: "Private air-conditioned vehicle to hotel" (not just "Hotel Transfer")
- Example good bullet: "Skip-the-line priority entry tickets" (not just "Entry Tickets")
- Slides 1 and 5 can have 3-4 shorter detail bullets.

SLIDE THEMES (but headlines are YOUR creative choice):

Slide 1 — HERO: The destination/product wow factor. Make them stop scrolling.
Slide 2 — ACTIVITIES: What they'll actually DO. Specific real activities/attractions. \
Be VERY detailed — real ride names, real attraction names, specific experiences.
Slide 3 — VALUE: What they GET. Specific inclusions, tickets, perks. \
Be VERY detailed — exactly what's included, specific amenities, exact access levels.
Slide 4 — EMOTION: How they'll FEEL. The sensory, memorable moments. \
Be VERY detailed — specific sensory moments, exact viewpoints, unique features.
Slide 5 — ACTION: Drive the booking. Price, urgency, trust signals.

Respond ONLY with valid JSON. No markdown, no code fences, no explanation."""


USER_PROMPT_TEMPLATE = """\
Generate Instagram carousel content for this travel product.

Product: {name}
City: {city}
Country: {country}
Price: {price}
Category: {category}
URL: {url}

CREATIVE DIRECTION: {creative_direction}
TEXT ALIGNMENT: Use "{alignment}" for ALL slides.

IMPORTANT:
- All headlines must be YOUR original creative choice — never use generic \
phrases like "Your Journey", "What's Included", "The Experience", "Book Now" etc.
- Use text_alignment "{alignment}" for EVERY slide — do NOT vary it.
- Slides 2, 3, 4 MUST have 5-6 detail bullets each, with descriptive text \
(5-8 words per bullet, minimum 20 words total per slide).

Return this EXACT JSON structure:
{{
  "product_summary": "One sentence about this experience",
  "slides": [
    {{
      "slide_number": 1,
      "slide_type": "hero",
      "image_prompt": "Hyper-specific cinematic scene for THIS product. NO text/words/logos. 4:5 portrait, ultra HD.",
      "overlay_headline": "YOUR CREATIVE HEADLINE",
      "overlay_subline": "Your compelling tagline",
      "overlay_details": ["Detail 1", "Detail 2", "Detail 3", "Detail 4"],
      "text_alignment": "{alignment}"
    }},
    {{
      "slide_number": 2,
      "slide_type": "activities",
      "image_prompt": "...",
      "overlay_headline": "YOUR CREATIVE HEADLINE",
      "overlay_subline": "...",
      "overlay_details": ["Descriptive activity sentence 1", "Descriptive activity sentence 2", "Descriptive activity sentence 3", "Descriptive activity sentence 4", "Descriptive activity sentence 5"],
      "text_alignment": "{alignment}"
    }},
    {{
      "slide_number": 3,
      "slide_type": "value",
      "image_prompt": "...",
      "overlay_headline": "YOUR CREATIVE HEADLINE",
      "overlay_subline": "...",
      "overlay_details": ["Descriptive inclusion sentence 1", "Descriptive inclusion sentence 2", "Descriptive inclusion sentence 3", "Descriptive inclusion sentence 4", "Descriptive inclusion sentence 5"],
      "text_alignment": "{alignment}"
    }},
    {{
      "slide_number": 4,
      "slide_type": "emotion",
      "image_prompt": "...",
      "overlay_headline": "YOUR CREATIVE HEADLINE",
      "overlay_subline": "...",
      "overlay_details": ["Descriptive moment sentence 1", "Descriptive moment sentence 2", "Descriptive moment sentence 3", "Descriptive moment sentence 4", "Descriptive moment sentence 5"],
      "text_alignment": "{alignment}"
    }},
    {{
      "slide_number": 5,
      "slide_type": "cta",
      "image_prompt": "...",
      "overlay_headline": "YOUR CREATIVE CTA HEADLINE",
      "overlay_subline": "raynatours.com",
      "overlay_details": ["From {price}", "Trust signal 1", "Trust signal 2", "Trust signal 3"],
      "text_alignment": "{alignment}"
    }}
  ]
}}"""


def _fallback_content(product: dict, model_name: str = "default") -> dict:
    """Generic content when Claude is unavailable."""
    name = product.get("name", "Travel Experience")
    city = product.get("city_name", product.get("city", ""))
    country = product.get("country_name", product.get("country", ""))
    destination = f"{city}, {country}" if country else city
    price = product.get("salePrice", product.get("normalPrice", ""))
    currency = product.get("currency", "")
    price_str = f"{currency} {price}" if price else ""
    category = product.get("item_group_id", product.get("type", "tour")).replace("-", " ").title()

    # Vary fallback headlines per model for some differentiation
    headlines = {
        "ideogram": [name.upper(), "DISCOVER MORE", "ALL ACCESS", "FEEL ALIVE", "START HERE"],
        "flux": [name.upper(), f"A Day in {city}", "Every Detail Covered", "Pure Magic", "Your Next Trip"],
        "seedream": [name.upper(), f"Explore {city}", "Fully Loaded", "Unforgettable", "Go Now"],
    }
    hl = headlines.get(model_name, headlines["flux"])

    return {
        "product_summary": f"Experience {name} in {destination}",
        "slides": [
            {
                "slide_number": 1, "slide_type": "hero",
                "image_prompt": f"Cinematic golden-hour aerial of {destination}, stunning skyline, warm tones, dramatic clouds. Trending Instagram travel photography. 4:5 portrait, ultra HD. No text, no logos.",
                "overlay_headline": hl[0], "overlay_subline": f"Discover {city}",
                "overlay_details": [city, country, category, f"From {price_str}"],
                "text_alignment": "center",
            },
            {
                "slide_number": 2, "slide_type": "activities",
                "image_prompt": f"Vibrant action shot of tourists enjoying {name} in {destination}. Authentic adventure, cinematic lighting. 4:5 portrait, ultra HD. No text, no logos.",
                "overlay_headline": hl[1], "overlay_subline": f"A day at {name}",
                "overlay_details": [f"Explore {name}", f"Discover {city} highlights", "Photo opportunities", "Guided experience"],
                "text_alignment": "left",
            },
            {
                "slide_number": 3, "slide_type": "value",
                "image_prompt": f"Luxury hospitality scene — premium tickets, private transfer, welcome drinks. {destination} backdrop. Warm lighting. 4:5 portrait, ultra HD. No text, no logos.",
                "overlay_headline": hl[2], "overlay_subline": "Everything you need",
                "overlay_details": ["Entry Tickets", "Hotel Transfers", "Professional Guide", "All Taxes Included"],
                "text_alignment": "left",
            },
            {
                "slide_number": 4, "slide_type": "emotion",
                "image_prompt": f"Emotional lifestyle photo — happy travelers at {name} in {destination}. Golden hour, cinematic depth. 4:5 portrait, ultra HD. No text, no logos.",
                "overlay_headline": hl[3], "overlay_subline": "Moments to remember",
                "overlay_details": ["Unforgettable memories", f"Best of {city}", "Share-worthy moments", "Once in a lifetime"],
                "text_alignment": "center",
            },
            {
                "slide_number": 5, "slide_type": "cta",
                "image_prompt": f"Stunning sunset wide shot of {destination}. Dramatic sky, clean lower third. 4:5 portrait, ultra HD. No text, no logos.",
                "overlay_headline": hl[4], "overlay_subline": "raynatours.com",
                "overlay_details": [f"From {price_str}", "Instant Confirmation", "Best Price Guarantee", "24/7 Support"],
                "text_alignment": "center",
            },
        ],
    }


async def plan_content(product: dict, model_name: str) -> dict:
    """
    Call Claude to generate rich carousel content for a SPECIFIC model variant.
    Each model gets a different creative direction → unique headlines, prompts, alignment.
    Falls back to templates if Claude is unavailable.
    """
    name = product.get("name", "Travel Experience")
    city = product.get("city_name", product.get("city", ""))
    country = product.get("country_name", product.get("country", ""))
    price = product.get("salePrice", product.get("normalPrice", ""))
    currency = product.get("currency", "")
    price_str = f"{currency} {price}" if price else ""
    category = product.get("item_group_id", product.get("type", "tour")).replace("-", " ").title()
    url = product.get("url", "")

    variant = CREATIVE_VARIANTS.get(model_name, CREATIVE_VARIANTS["flux"])
    creative_direction = f"{variant['name']}: {variant['direction']}"
    alignment = variant.get("alignment", "left")

    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        print(f"[WARN] ANTHROPIC_API_KEY not set. Using fallback for {model_name}.")
        return _fallback_content(product, model_name)

    user_prompt = USER_PROMPT_TEMPLATE.format(
        name=name, city=city, country=country,
        price=price_str, category=category, url=url,
        creative_direction=creative_direction,
        alignment=alignment,
    )

    try:
        client = anthropic.AsyncAnthropic(api_key=api_key)
        message = await client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=2048,
            system=SYSTEM_MESSAGE,
            messages=[{"role": "user", "content": user_prompt}],
        )

        raw = message.content[0].text.strip()
        if raw.startswith("```"):
            lines = raw.split("\n")
            raw = "\n".join(lines[1:-1])

        content = json.loads(raw)

        if "slides" not in content or len(content["slides"]) != 5:
            print(f"[WARN] Claude returned bad structure for {model_name}. Using fallback.")
            return _fallback_content(product, model_name)

        for slide in content["slides"]:
            for key in ("slide_number", "image_prompt", "overlay_headline"):
                if key not in slide:
                    print(f"[WARN] Slide missing '{key}' for {model_name}. Using fallback.")
                    return _fallback_content(product, model_name)
            if not isinstance(slide.get("overlay_details"), list):
                slide["overlay_details"] = []
            # Force the model's assigned alignment (only "left" or "center")
            slide["text_alignment"] = alignment

        print(f"[INFO] Claude planned ({variant['name']}): {content.get('product_summary', 'OK')}")
        return content

    except anthropic.APIError as e:
        print(f"[ERROR] Claude API for {model_name}: {e}. Using fallback.")
        return _fallback_content(product, model_name)
    except json.JSONDecodeError as e:
        print(f"[ERROR] Claude JSON for {model_name}: {e}. Using fallback.")
        return _fallback_content(product, model_name)
    except Exception as e:
        print(f"[ERROR] Content plan for {model_name} failed: {e}. Using fallback.")
        return _fallback_content(product, model_name)


async def plan_all_variants(product: dict, model_names: list[str]) -> dict[str, dict]:
    """
    Generate content plans for ALL models in parallel.
    Returns {model_name: content_plan} dict.
    """
    tasks = [plan_content(product, name) for name in model_names]
    results = await asyncio.gather(*tasks)
    return dict(zip(model_names, results))


# ══════════════════════════════════════════════════════════════════════
# ENRICHED FEED — Real Image Carousel (separate feature)
# ══════════════════════════════════════════════════════════════════════

ENRICHED_SYSTEM_MESSAGE = """\
You are a world-class travel marketing creative director for Rayna Tours, \
a premium travel and tourism company based in the UAE.

Your job: Given RICH product data (name, city, country, price, rating, reviews, \
amenities, duration, location), create compelling Instagram carousel text \
overlays that go on top of REAL product photos.

CRITICAL RULES:
1. YOU decide ALL headlines — be CREATIVE and UNIQUE. Never use generic phrases.
2. Use text_alignment "center" for ALL slides consistently.
3. Since overlay goes on REAL photos, keep text high-contrast and readable.
4. Leverage the real data: mention actual ratings, review counts, durations, \
   specific amenities. Don't invent — use what's provided.
5. If there's a discount, HIGHLIGHT it on the CTA slide.

EVERY slide needs:
- "overlay_headline": YOUR creative headline (2-4 words max). Be ORIGINAL.
- "overlay_subline": Supporting line (4-8 words)
- "overlay_details": List of bullet strings with REAL specific info
- "text_alignment": "center" for ALL slides.

DETAIL REQUIREMENTS:
- Slides 2, 3, 4 MUST have 5-6 detail bullets each (5-8 words per bullet).
- Each bullet should be descriptive, NOT just 2-word labels.
- Slides 1 and 5 can have 3-4 shorter detail bullets.
- Use REAL data from the product — actual amenities, actual rating, actual duration.

SLIDE THEMES (but headlines are YOUR creative choice):

Slide 1 — HERO: The destination wow factor. Make them stop scrolling.
Slide 2 — ACTIVITIES: What they'll actually DO. Use real amenities/description data.
Slide 3 — VALUE: What they GET. Real inclusions, amenities, perks from data.
Slide 4 — SOCIAL PROOF: Rating, reviews, trust signals. Use actual numbers.
Slide 5 — ACTION: Price, discount if any, urgency, booking CTA.

Respond ONLY with valid JSON. No markdown, no code fences, no explanation."""


ENRICHED_USER_PROMPT_TEMPLATE = """\
Generate Instagram carousel overlay content for this travel product.
The images are REAL product photos — your text will overlay on them.

Product: {name}
City: {city}
Country: {country}
Category: {category}
Price: {price}
{discount_line}
Rating: {rating}/5 ({review_count} reviews)
Duration: {duration}
Confirmation: {confirmation}
Location: {location_address}

TEXT ALIGNMENT: Use "center" for ALL slides.

Return this EXACT JSON structure:
{{
  "product_summary": "One sentence about this experience",
  "slides": [
    {{
      "slide_number": 1,
      "slide_type": "hero",
      "overlay_headline": "YOUR CREATIVE HEADLINE",
      "overlay_subline": "Your compelling tagline",
      "overlay_details": ["Detail 1", "Detail 2", "Detail 3"],
      "text_alignment": "center"
    }},
    {{
      "slide_number": 2,
      "slide_type": "activities",
      "overlay_headline": "YOUR CREATIVE HEADLINE",
      "overlay_subline": "...",
      "overlay_details": ["Activity 1", "Activity 2", "Activity 3", "Activity 4", "Activity 5"],
      "text_alignment": "center"
    }},
    {{
      "slide_number": 3,
      "slide_type": "value",
      "overlay_headline": "YOUR CREATIVE HEADLINE",
      "overlay_subline": "...",
      "overlay_details": ["Inclusion 1", "Inclusion 2", "Inclusion 3", "Inclusion 4", "Inclusion 5"],
      "text_alignment": "center"
    }},
    {{
      "slide_number": 4,
      "slide_type": "social_proof",
      "overlay_headline": "YOUR CREATIVE HEADLINE",
      "overlay_subline": "...",
      "overlay_details": ["Review fact 1", "Review fact 2", "Review fact 3", "Review fact 4", "Review fact 5"],
      "text_alignment": "center"
    }},
    {{
      "slide_number": 5,
      "slide_type": "cta",
      "overlay_headline": "YOUR CREATIVE CTA HEADLINE",
      "overlay_subline": "raynatours.com",
      "overlay_details": ["From {price}", "Trust signal 1", "Trust signal 2", "Trust signal 3"],
      "text_alignment": "center"
    }}
  ]
}}"""


def _fallback_content_enriched(product: dict) -> dict:
    """Generic content when Claude is unavailable, using enriched data."""
    name = product.get("name", "Travel Experience")
    city = product.get("city", "")
    country = product.get("country", "")
    destination = f"{city}, {country}" if country else city
    price = product.get("salePrice", product.get("normalPrice", ""))
    currency = product.get("currency", "")
    price_str = f"{currency} {price}" if price else ""
    rating = product.get("review_averageRating", product.get("listing_rating", ""))
    review_count = product.get("review_totalCount", product.get("listing_reviewCount", 0))
    duration = product.get("amenity_duration", "")

    return {
        "product_summary": f"Experience {name} in {destination}",
        "slides": [
            {
                "slide_number": 1, "slide_type": "hero",
                "overlay_headline": name.upper()[:30],
                "overlay_subline": f"Discover {city}",
                "overlay_details": [city, country, f"From {price_str}"],
                "text_alignment": "center",
            },
            {
                "slide_number": 2, "slide_type": "activities",
                "overlay_headline": "DISCOVER MORE",
                "overlay_subline": f"A day at {name}",
                "overlay_details": [
                    f"Explore {name} in {city}",
                    f"Duration: {duration}" if duration else "Full day experience",
                    "Guided tour with expert commentary",
                    "Photo opportunities at every stop",
                    "Unforgettable travel memories",
                ],
                "text_alignment": "center",
            },
            {
                "slide_number": 3, "slide_type": "value",
                "overlay_headline": "ALL INCLUDED",
                "overlay_subline": "Everything you need",
                "overlay_details": [
                    "Skip-the-line priority entry tickets",
                    "Professional guide included",
                    "Hotel pickup and drop-off available",
                    "Instant confirmation on booking",
                    "All taxes and fees included",
                ],
                "text_alignment": "center",
            },
            {
                "slide_number": 4, "slide_type": "social_proof",
                "overlay_headline": "LOVED BY ALL",
                "overlay_subline": f"Rated {rating}/5 by travelers",
                "overlay_details": [
                    f"{rating}/5 average from {review_count} reviews",
                    "Trusted by thousands of travelers",
                    "Instant tour confirmation provided",
                    "Top-rated experience in {city}",
                    "Recommended by travel experts",
                ],
                "text_alignment": "center",
            },
            {
                "slide_number": 5, "slide_type": "cta",
                "overlay_headline": "BOOK NOW",
                "overlay_subline": "raynatours.com",
                "overlay_details": [f"From {price_str}", "Instant Confirmation", "Best Price Guarantee", "24/7 Support"],
                "text_alignment": "center",
            },
        ],
    }


async def plan_content_enriched(product: dict) -> dict:
    """
    Call Claude to generate carousel overlay content using ENRICHED product data.
    Unlike plan_content(), this uses richer data (reviews, amenities, duration)
    and produces a single content plan (no model variants needed for real images).
    """
    name = product.get("name", "Travel Experience")
    city = product.get("city", "")
    country = product.get("country", "")
    price = product.get("salePrice", product.get("normalPrice", ""))
    currency = product.get("currency", "")
    price_str = f"{currency} {price}" if price else ""
    category = product.get("item_group_id", product.get("type", "tour")).replace("-", " ").title()
    rating = product.get("review_averageRating", product.get("listing_rating", ""))
    review_count = product.get("review_totalCount", product.get("listing_reviewCount", 0))
    duration = product.get("amenity_duration", "")
    confirmation = product.get("amenity_confirmation", "")
    location_address = product.get("location_address", "")
    discount = product.get("price_discount", 0)
    discount_line = f"Discount: {currency} {discount} OFF" if discount and discount > 0 else ""

    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        print("[WARN] ANTHROPIC_API_KEY not set. Using fallback.")
        return _fallback_content_enriched(product)

    user_prompt = ENRICHED_USER_PROMPT_TEMPLATE.format(
        name=name, city=city, country=country,
        price=price_str, category=category,
        rating=rating, review_count=review_count,
        duration=duration, confirmation=confirmation,
        location_address=location_address,
        discount_line=discount_line,
    )

    try:
        client = anthropic.AsyncAnthropic(api_key=api_key)
        message = await client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=2048,
            system=ENRICHED_SYSTEM_MESSAGE,
            messages=[{"role": "user", "content": user_prompt}],
        )

        raw = message.content[0].text.strip()
        if raw.startswith("```"):
            lines = raw.split("\n")
            raw = "\n".join(lines[1:-1])

        content = json.loads(raw)

        if "slides" not in content or len(content["slides"]) != 5:
            print("[WARN] Claude returned bad structure for enriched. Using fallback.")
            return _fallback_content_enriched(product)

        for slide in content["slides"]:
            for key in ("slide_number", "overlay_headline"):
                if key not in slide:
                    print(f"[WARN] Slide missing '{key}' for enriched. Using fallback.")
                    return _fallback_content_enriched(product)
            if not isinstance(slide.get("overlay_details"), list):
                slide["overlay_details"] = []
            slide["text_alignment"] = "center"

        print(f"[INFO] Claude planned (enriched): {content.get('product_summary', 'OK')}")
        return content

    except anthropic.APIError as e:
        print(f"[ERROR] Claude API enriched: {e}. Using fallback.")
        return _fallback_content_enriched(product)
    except json.JSONDecodeError as e:
        print(f"[ERROR] Claude JSON enriched: {e}. Using fallback.")
        return _fallback_content_enriched(product)
    except Exception as e:
        print(f"[ERROR] Enriched content plan failed: {e}. Using fallback.")
        return _fallback_content_enriched(product)
