# Rayna Carousel — AI-Powered Instagram Carousel Generator

Automated Instagram carousel image generator for travel products. Uses **Claude AI** for creative content planning and **FAL AI** for image generation, with professional watermark overlays.

## Features

- **Two Pipelines**:
  - `main.py` — AI-generated images via FAL AI (3 models: ideogram, flux, seedream)
  - `real_main.py` — Real product photos with Claude-powered text overlays
- **Claude AI Content Planning** — Headlines, sublines, detail bullets, and alignment are all decided by Claude. Each AI model gets a unique creative direction.
- **3 Creative Variants** (AI pipeline):
  - **Ideogram** — Bold & Dramatic (center-aligned)
  - **Flux** — Warm & Editorial (left-aligned)
  - **Seedream** — Clean & Modern (center-aligned)
- **Professional Watermark Overlays** — Dark panel with headline, subline, detail bullets, price badge, discount display, and company logo
- **Discount Display** — Strikethrough original price + red "X% OFF" pill badge on CTA slide when a discount exists
- **Instagram Optimized** — 5-slide carousels in 1080x1350 (4:5 portrait) format
- **Async Pipeline** — Concurrent downloads, API calls, and image generation for performance

## Project Structure

```
Image-generate/
├── main.py                # AI image generation pipeline
├── real_main.py           # Real image pipeline (downloads + overlays)
├── config.py              # Configuration constants
├── fetcher.py             # API data fetching (cities, products, enriched feed)
├── content_planner.py     # Claude AI content planning (3 variants + enriched)
├── generator.py           # FAL AI image generation (3 models in parallel)
├── prompt_builder.py      # Extracts image prompts from content plan
├── watermark.py           # Professional overlay rendering (PIL/Pillow)
├── assets/
│   └── logo.webp          # Rayna Tours logo
├── output/                # Generated carousel images
│   └── {product-slug}/
│       ├── ideogram/      # AI model 1 output
│       ├── flux/          # AI model 2 output
│       ├── seedream/      # AI model 3 output
│       └── real/          # Real image output
├── requirements.txt       # Python dependencies
└── .env                   # API keys (not committed)
```

## Setup

### 1. Install dependencies

```bash
python -m pip install -r requirements.txt
```

### 2. Configure environment variables

Create a `.env` file:

```env
FAL_KEY=your_fal_key_here
ANTHROPIC_API_KEY=your_anthropic_key_here
```

- `FAL_KEY` — Required only for AI image pipeline (`main.py`)
- `ANTHROPIC_API_KEY` — Required for Claude content planning. Falls back to templates if not set.

### 3. Configure targets

In `config.py`:
- `TEST_MODE` — Set `True` to process only 1 city/product (for testing)
- `TARGET_CITY_ID` / `TARGET_PRODUCT_ID` — Filter specific products in `main.py`

In `real_main.py`:
- `TARGET_PRODUCT_IDS` — List of product IDs to process

## Usage

### AI-Generated Images

Generates carousel images using 3 FAL AI models with unique Claude content per model:

```bash
python main.py
```

Output: `output/{product-slug}/{model-name}/image_{1-5}.png`

### Real Product Images

Downloads real product photos from the enriched API, resizes to Instagram format, and applies Claude-generated text overlays:

```bash
python real_main.py
```

Output: `output/{product-slug}/real/image_{1-5}.png`

## Slide Layout (5 slides per product)

| Slide | Theme | Content |
|-------|-------|---------|
| 1 | **Hero** | Destination wow factor — make them stop scrolling |
| 2 | **Activities** | What they'll DO — specific attractions, experiences |
| 3 | **Value** | What they GET — inclusions, amenities, perks |
| 4 | **Social Proof / Emotion** | Ratings, reviews, trust signals |
| 5 | **CTA** | Price badge, discount (if any), booking call-to-action |

## Watermark Features

- Dark gradient + solid panel at bottom of each slide
- Auto-fitting text (shrinks to prevent overflow)
- Block-aligned detail bullets (centered as a group)
- Price badge with `anchor="mm"` for pixel-perfect centering
- Discount display: strikethrough original price + red "% OFF" pill
- Company logo (bottom-right, 20% width, 90% opacity)
- Supports left and center text alignment

## API Integrations

| Service | Purpose |
|---------|---------|
| [Rayna Tours API](https://data-projects-flax.vercel.app) | Product data, cities, enriched feed with image URLs |
| [FAL AI](https://fal.ai) | AI image generation (ideogram, flux, seedream models) |
| [Anthropic Claude](https://anthropic.com) | Content planning — headlines, copy, layout decisions |

## Dependencies

- `anthropic` — Claude AI API client
- `fal-client` — FAL AI image generation
- `httpx` — Async HTTP client
- `pillow` — Image processing and compositing
- `python-dotenv` — Environment variable loading
