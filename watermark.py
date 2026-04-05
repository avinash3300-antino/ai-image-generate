"""
Watermark module — professional Instagram ad overlay with info-rich bottom panel.

Renders Claude-generated content: headline, subline, detail bullets, price badge, logo.
Text alignment (left/center/right) is decided by Claude AI per slide.
"""

import os
import platform
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from config import LOGO_PATH, OUTPUT_DIR


# ── Fonts ─────────────────────────────────────────────────────────────

def _get_font(bold: bool = False, size: int = 40) -> ImageFont.FreeTypeFont:
    if platform.system() == "Windows":
        path = "C:/Windows/Fonts/arialbd.ttf" if bold else "C:/Windows/Fonts/arial.ttf"
    else:
        path = (
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
            if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
        )
    if os.path.exists(path):
        return ImageFont.truetype(path, size)
    return ImageFont.load_default(size=size)


def _fit_text(
    draw: ImageDraw.ImageDraw, text: str, max_w: int, bold: bool, ideal: int, floor: int = 14,
) -> ImageFont.FreeTypeFont:
    sz = ideal
    while sz > floor:
        f = _get_font(bold, sz)
        bb = draw.textbbox((0, 0), text, font=f)
        if (bb[2] - bb[0]) <= max_w:
            return f
        sz -= 2
    return _get_font(bold, floor)


def _measure(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont) -> tuple[int, int]:
    bb = draw.textbbox((0, 0), text, font=font)
    return bb[2] - bb[0], bb[3] - bb[1]


# ── Alignment helper ─────────────────────────────────────────────────

def _align_x(text_w: int, pad_x: int, inner_w: int, alignment: str) -> int:
    """Calculate x position based on alignment (left or center only)."""
    if alignment == "center":
        return pad_x + (inner_w - text_w) // 2
    return pad_x  # left (default)


def _align_sep(pad_x: int, inner_w: int, alignment: str) -> tuple[int, int]:
    """Return (x_start, x_end) for separator line based on alignment."""
    sep_len = int(inner_w * 0.3)
    if alignment == "center":
        mid = pad_x + inner_w // 2
        return mid - sep_len // 2, mid + sep_len // 2
    return pad_x, pad_x + sep_len  # left


# ── Logo ──────────────────────────────────────────────────────────────

def _load_logo(img_w: int) -> Image.Image:
    logo = Image.open(LOGO_PATH).convert("RGBA")
    tw = int(img_w * 0.20)
    th = int(tw * logo.height / logo.width)
    logo = logo.resize((tw, th), Image.LANCZOS)
    r, g, b, a = logo.split()
    a = a.point(lambda p: int(p * 0.90))
    return Image.merge("RGBA", (r, g, b, a))


# ── Extract content from plan ─────────────────────────────────────────

def _slide_content(slide_number: int, content_plan: dict, price: str, normal_price: str = "") -> dict:
    for slide in content_plan.get("slides", []):
        if slide.get("slide_number") == slide_number:
            result = {
                "headline": slide.get("overlay_headline", ""),
                "subline": slide.get("overlay_subline", ""),
                "details": slide.get("overlay_details", []),
                "alignment": slide.get("text_alignment", "left"),
            }
            if slide_number == 5 and price:
                result["price"] = price
                if normal_price:
                    result["normal_price"] = normal_price
                # Remove detail bullets that duplicate the price badge
                result["details"] = [
                    d for d in result["details"]
                    if "from" not in d.lower() or price.split()[-1] not in d
                ]
            return result
    return {"headline": "", "subline": "", "details": [], "alignment": "left"}


# ── Main ──────────────────────────────────────────────────────────────

def apply_watermark(
    source_path: str,
    product_slug: str,
    model_name: str,
    slide_number: int,
    content_plan: dict,
    price: str = "",
    normal_price: str = "",
) -> str | None:
    try:
        base = Image.open(source_path).convert("RGBA")
        W, H = base.size

        overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        draw = ImageDraw.Draw(overlay)

        content = _slide_content(slide_number, content_plan, price, normal_price)
        headline = content.get("headline", "")
        subline = content.get("subline", "")
        details = content.get("details", [])[:6]
        align = content.get("alignment", "left")

        # ── Layout constants ──
        pad_x = int(W * 0.06)
        inner_w = W - pad_x * 2
        panel_pct = 0.40 if details else 0.30
        if slide_number == 5:
            panel_pct = 0.45
            if normal_price:  # extra room for discount row
                panel_pct = 0.55
        panel_h = int(H * panel_pct)
        panel_top = H - panel_h

        # ── 1. Gradient + solid panel ──
        grad_h = int(H * 0.10)
        for i in range(grad_h):
            y = panel_top - grad_h + i
            a = int(200 * (i / grad_h))
            draw.line([(0, y), (W, y)], fill=(0, 0, 0, a))
        draw.rectangle([0, panel_top, W, H], fill=(0, 0, 0, 195))

        # ── 2. Logo (bottom-right) ──
        logo = _load_logo(W)
        logo_margin = int(W * 0.04)
        logo_x = W - logo.width - logo_margin
        logo_y = H - logo.height - logo_margin

        # ── 3. Build text top-down inside panel ──
        cursor_y = panel_top + int(panel_h * 0.08)

        # -- Price badge + discount (slide 5) --
        if slide_number == 5 and content.get("price"):
            has_discount = bool(content.get("normal_price"))

            # If discount exists, show strikethrough original price + "X% OFF" as one centered row
            if has_discount:
                np_text = content["normal_price"]
                np_font = _fit_text(draw, np_text, inner_w, bold=False, ideal=int(W * 0.032))
                np_w, np_h = _measure(draw, np_text, np_font)

                # Calculate discount percentage
                disc_text = ""
                disc_font = _get_font(bold=True, size=int(W * 0.026))
                disc_w, disc_h, disc_bp = 0, 0, int(W * 0.012)
                try:
                    np_val = float("".join(c for c in content["normal_price"] if c in "0123456789."))
                    sp_val = float("".join(c for c in content["price"] if c in "0123456789."))
                    if np_val > sp_val > 0:
                        pct = int(round((1 - sp_val / np_val) * 100))
                        if pct > 0:
                            disc_text = f"{pct}% OFF"
                            disc_w, disc_h = _measure(draw, disc_text, disc_font)
                except (ValueError, ZeroDivisionError):
                    pass

                # Total row width: strikethrough price + gap + discount pill
                gap = int(W * 0.025)
                pill_w = disc_w + disc_bp * 2 if disc_text else 0
                pill_h = disc_h + disc_bp * 2 if disc_text else 0
                total_row_w = np_w + (gap + pill_w if disc_text else 0)

                # Center the entire row
                row_x = (W - total_row_w) // 2
                row_h = max(np_h, pill_h)

                # Draw strikethrough price (vertically centered in row)
                np_y = cursor_y + (row_h - np_h) // 2
                draw.text((row_x, np_y), np_text, font=np_font, fill=(180, 180, 180))
                strike_y = np_y + np_h // 2
                draw.line(
                    [(row_x - 2, strike_y), (row_x + np_w + 2, strike_y)],
                    fill=(255, 80, 80), width=2,
                )

                # Draw discount pill (vertically centered in row)
                if disc_text:
                    pill_x = row_x + np_w + gap
                    pill_y = cursor_y + (row_h - pill_h) // 2
                    draw.rounded_rectangle(
                        [pill_x, pill_y, pill_x + pill_w, pill_y + pill_h],
                        radius=8, fill=(220, 40, 40, 230),
                    )
                    # Center text inside pill with anchor
                    draw.text(
                        (pill_x + pill_w // 2, pill_y + pill_h // 2),
                        disc_text, font=disc_font, fill=(255, 255, 255), anchor="mm",
                    )

                cursor_y += row_h + int(panel_h * 0.03)

            # Sale price badge (black)
            price_text = f"From {content['price']}"
            pr_font = _fit_text(draw, price_text, inner_w, bold=True, ideal=int(W * 0.045))
            pr_w, pr_h = _measure(draw, price_text, pr_font)
            bp_x = int(W * 0.03)    # ~p-2 horizontal padding
            bp_y = int(W * 0.015)   # ~p-2 vertical padding
            badge_w = pr_w + bp_x * 2
            badge_h = pr_h + bp_y * 2
            badge_x = (W - badge_w) // 2
            draw.rounded_rectangle(
                [badge_x, cursor_y, badge_x + badge_w, cursor_y + badge_h],
                radius=10, fill=(15, 15, 15, 240),
            )
            cx = badge_x + badge_w // 2
            cy = cursor_y + badge_h // 2
            draw.text((cx, cy), price_text, font=pr_font, fill=(255, 255, 255), anchor="mm")
            cursor_y += badge_h + int(panel_h * 0.05)

        # -- Headline (aligned) --
        if headline:
            hl_ideal = int(W * 0.085) if slide_number != 5 else int(W * 0.11)
            hl_font = _fit_text(draw, headline, inner_w, bold=True, ideal=hl_ideal)
            hl_w, hl_h = _measure(draw, headline, hl_font)
            hl_x = _align_x(hl_w, pad_x, inner_w, align)
            draw.text((hl_x, cursor_y), headline, font=hl_font, fill=(255, 255, 255))
            cursor_y += hl_h + int(panel_h * 0.04)

        # -- Subline (aligned) --
        if subline:
            sl_font = _fit_text(draw, subline, inner_w, bold=False, ideal=int(W * 0.038))
            sl_w, sl_h = _measure(draw, subline, sl_font)
            sl_x = _align_x(sl_w, pad_x, inner_w, align)
            draw.text((sl_x, cursor_y), subline, font=sl_font, fill=(210, 210, 210))
            cursor_y += sl_h + int(panel_h * 0.06)

        # -- Separator line (aligned) --
        if details:
            sep_x1, sep_x2 = _align_sep(pad_x, inner_w, align)
            draw.line(
                [(sep_x1, cursor_y), (sep_x2, cursor_y)],
                fill=(255, 255, 255, 80), width=2,
            )
            cursor_y += int(panel_h * 0.04)

        # -- Detail bullets (block-aligned) --
        # All bullets share ONE x position so they left-align as a group.
        # For "center" mode, the group itself is centered based on the widest bullet.
        if details:
            det_font = _fit_text(
                draw, max(details, key=len), inner_w - 20,
                bold=False, ideal=int(W * 0.032),
            )
            # Find the widest bullet to determine block x position
            max_bw = 0
            for item in details:
                bw, _ = _measure(draw, f"  {item}", det_font)
                if bw > max_bw:
                    max_bw = bw
            block_x = _align_x(max_bw, pad_x, inner_w, align)

            for item in details:
                bullet = f"  {item}"
                _, det_h = _measure(draw, bullet, det_font)
                if cursor_y + det_h > logo_y - 5:
                    break
                draw.text(
                    (block_x, cursor_y), bullet, font=det_font,
                    fill=(200, 200, 200, 230),
                )
                cursor_y += det_h + int(panel_h * 0.025)

        # ── 4. Composite ──
        base = Image.alpha_composite(base, overlay)
        base.paste(logo, (logo_x, logo_y), mask=logo)

        final = base.convert("RGB")
        out_dir = os.path.join(OUTPUT_DIR, product_slug, model_name)
        Path(out_dir).mkdir(parents=True, exist_ok=True)
        out_path = os.path.join(out_dir, f"image_{slide_number}.png")
        final.save(out_path, "PNG", quality=95)
        return out_path

    except Exception as e:
        print(f"[ERROR] Watermark failed for {model_name} slide {slide_number}: {e}")
        return None
