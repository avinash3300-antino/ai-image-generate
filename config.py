"""
Configuration constants for the rayna-carousel project.
Centralizes all settings: image dimensions, API endpoints, model IDs, and test flags.
"""

# Instagram 4:5 portrait format
IMAGE_WIDTH: int = 1080
IMAGE_HEIGHT: int = 1350

# Logo asset path for watermarking
LOGO_PATH: str = "assets/logo.webp"

# Directory where final images are saved
OUTPUT_DIR: str = "output"

# API endpoints for fetching travel product data
PRODUCT_API: str = "https://data-projects-flax.vercel.app/api/all-products"
CITIES_API: str = "https://data-projects-flax.vercel.app/api/available-cities"

# FAL AI model identifiers — each generates a different style
MODELS: dict[str, str] = {
    "ideogram": "fal-ai/ideogram/v3",
    "flux": "fal-ai/flux-pro/v1.1",
    "seedream": "fal-ai/bytedance/seedream/v3/text-to-image",
}

# Number of carousel slides per product per model
SLIDES_PER_PRODUCT: int = 5

# When True, fetches only 1 city and 1 product for quick testing
TEST_MODE: bool = True

# Negative prompt to suppress unwanted text/artifacts in generated images
NEGATIVE_PROMPT: str = (
    "text, watermark, logo, letters, words, writing, captions, titles, "
    "subtitles, typography, font, blurry, low quality, distorted"
)
