"""
Prompt builder — extracts image generation prompts from Claude's content plan.
Each slide's image_prompt is already rich and product-specific.
"""

# Appended to every prompt to ensure text suppression across all FAL models
_STYLE_SUFFIX = (
    "Instagram carousel slide, travel brand photography, "
    "4:5 portrait, ultra HD, no text, no words, no letters, no logos, no watermarks"
)


def build_prompts(content_plan: dict) -> list[str]:
    """
    Extract image generation prompts from the content plan.
    Appends style suffix if not already present for consistency.

    Args:
        content_plan: Dict with 'slides' list from content_planner.plan_content()

    Returns:
        List of 5 prompt strings for FAL image generation.
    """
    prompts: list[str] = []

    for slide in content_plan["slides"]:
        prompt = slide["image_prompt"]
        # Ensure text suppression suffix is present
        if "no text" not in prompt.lower():
            prompt = f"{prompt} {_STYLE_SUFFIX}"
        prompts.append(prompt)

    return prompts
