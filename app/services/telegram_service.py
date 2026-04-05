import os
import tempfile
import textwrap
from typing import Optional

import requests

try:
    from PIL import Image as PILImage, ImageDraw, ImageFont
except Exception:
    PILImage = None
    ImageDraw = None
    ImageFont = None


FRAME_BOXES = {
    "main": (38, 34, 1018, 632),
    "fractal": (38, 34, 1018, 632),
}


def get_telegram_credentials(
    token: Optional[str] = None,
    chat_id: Optional[str] = None,
) -> tuple[str, str]:
    bot_token = (token or "").strip()
    target_chat_id = (chat_id or "").strip()

    if not bot_token:
        raise ValueError("Telegram bot token bulunamadı.")
    if not target_chat_id:
        raise ValueError("Telegram chat id bulunamadı.")

    return bot_token, target_chat_id


def send_message(
    message: str,
    token: Optional[str] = None,
    chat_id: Optional[str] = None,
    timeout: int = 30,
) -> dict:
    bot_token, target_chat_id = get_telegram_credentials(token, chat_id)

    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    response = requests.post(
        url,
        data={
            "chat_id": target_chat_id,
            "text": message,
        },
        timeout=timeout,
    )
    response.raise_for_status()
    return response.json()


def send_photo(
    image_path: str,
    caption: str = "",
    token: Optional[str] = None,
    chat_id: Optional[str] = None,
    timeout: int = 30,
) -> dict:
    if not image_path or not os.path.exists(image_path):
        raise ValueError(f"Görsel bulunamadı: {image_path}")

    bot_token, target_chat_id = get_telegram_credentials(token, chat_id)
    url = f"https://api.telegram.org/bot{bot_token}/sendPhoto"

    with open(image_path, "rb") as photo_file:
        response = requests.post(
            url,
            data={
                "chat_id": target_chat_id,
                "caption": caption,
            },
            files={"photo": photo_file},
            timeout=timeout,
        )
    response.raise_for_status()
    return response.json()


def build_analysis_message(
    instrument_name: str,
    display_levels: dict,
    analysis_text: str,
) -> str:
    return (
        f"📊 {instrument_name} Analizi\n\n"
        f"Fraktal Destek 1: {display_levels.get('fractal_support_1', '...')}\n"
        f"Fraktal Destek 2: {display_levels.get('fractal_support_2', '...')}\n"
        f"Fraktal Direnç 1: {display_levels.get('fractal_resistance_1', '...')}\n"
        f"Fraktal Direnç 2: {display_levels.get('fractal_resistance_2', '...')}\n"
        f"Ana Destek: {display_levels.get('main_support', '...')}\n"
        f"Ana Direnç: {display_levels.get('main_resistance', '...')}\n\n"
        f"Yapı Bozulma:\n{display_levels.get('invalidation', '...')}\n\n"
        f"Yorum:\n{analysis_text}"
    )


def build_signal_message(
    instrument_name: str,
    signal_text: str,
) -> str:
    return f"📍 {instrument_name} Sinyali\n\n{signal_text}"


def _get_font(size: int):
    if ImageFont is None:
        return None

    font_candidates = [
        "arial.ttf",
        "Arial.ttf",
        "DejaVuSans.ttf",
        "C:/Windows/Fonts/arial.ttf",
    ]

    for font_path in font_candidates:
        try:
            return ImageFont.truetype(font_path, size)
        except Exception:
            continue

    try:
        return ImageFont.load_default()
    except Exception:
        return None


def _fit_logo(logo_path: str, max_size=(120, 120)):
    if not logo_path or not os.path.exists(logo_path):
        return None

    logo = PILImage.open(logo_path).convert("RGBA")
    logo.thumbnail(max_size, PILImage.LANCZOS)
    return logo


def _fit_content_image(image_path: str, target_size: tuple[int, int]):
    if not image_path or not os.path.exists(image_path):
        return None

    img = PILImage.open(image_path).convert("RGBA")
    img.thumbnail(target_size, PILImage.LANCZOS)

    canvas = PILImage.new("RGBA", target_size, (0, 0, 0, 0))
    x = (target_size[0] - img.width) // 2
    y = (target_size[1] - img.height) // 2
    canvas.paste(img, (x, y), img)
    return canvas


def _rounded_mask(size: tuple[int, int], radius: int):
    mask = PILImage.new("L", size, 0)
    draw = ImageDraw.Draw(mask)
    draw.rounded_rectangle((0, 0, size[0], size[1]), radius=radius, fill=255)
    return mask


def create_panel_with_frame(
    image_path: str,
    frame_path: str,
    panel_type: str,
) -> str:
    if PILImage is None:
        raise RuntimeError("Pillow kurulu değil. `python -m pip install pillow` çalıştır.")

    if not image_path or not os.path.exists(image_path):
        raise RuntimeError(f"Görsel bulunamadı: {image_path}")

    if not frame_path or not os.path.exists(frame_path):
        raise RuntimeError(f"Frame dosyası bulunamadı: {frame_path}")

    if panel_type not in FRAME_BOXES:
        raise RuntimeError(f"Geçersiz panel tipi: {panel_type}")

    frame = PILImage.open(frame_path).convert("RGBA")
    img = PILImage.open(image_path).convert("RGBA")

    x1, y1, x2, y2 = FRAME_BOXES[panel_type]
    box_w = x2 - x1
    box_h = y2 - y1

    bbox = img.getbbox()
    if bbox:
        img = img.crop(bbox)

    img_w, img_h = img.size
    scale = max(box_w / img_w, box_h / img_h)
    new_w = int(img_w * scale)
    new_h = int(img_h * scale)
    img = img.resize((new_w, new_h), PILImage.LANCZOS)

    left = (new_w - box_w) // 2
    top = (new_h - box_h) // 2
    right = left + box_w
    bottom = top + box_h
    img = img.crop((left, top, right, bottom))

    panel = PILImage.new("RGBA", frame.size, (0, 0, 0, 0))
    panel.paste(img, (x1, y1), img)
    result = PILImage.alpha_composite(panel, frame)

    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".png")
    result.save(temp_file.name, format="PNG")
    return temp_file.name


def _wrap_lines(draw, text: str, font, max_width: int, max_lines: int):
    if not text:
        return []

    words = text.split()
    if not words:
        return []

    lines = []
    current = words[0]

    for word in words[1:]:
        test = current + " " + word
        bbox = draw.textbbox((0, 0), test, font=font)
        width = bbox[2] - bbox[0]
        if width <= max_width:
            current = test
        else:
            lines.append(current)
            current = word
            if len(lines) >= max_lines:
                break

    if len(lines) < max_lines:
        lines.append(current)

    if len(lines) > max_lines:
        lines = lines[:max_lines]

    if len(lines) == max_lines:
        last = lines[-1]
        while last:
            bbox = draw.textbbox((0, 0), last + "...", font=font)
            if (bbox[2] - bbox[0]) <= max_width:
                break
            last = last[:-1]
        lines[-1] = (last + "...") if last else "..."

    return lines


def create_content_card_with_frame(
    title: str,
    body: str,
    frame_path: str,
    logo_path: str = "",
    content_image_path: str = "",
    footer_text: str = "",
) -> str:
    if PILImage is None or ImageDraw is None:
        raise RuntimeError("Pillow kurulu değil. `python -m pip install pillow` çalıştır.")

    if not frame_path or not os.path.exists(frame_path):
        raise RuntimeError(f"Frame dosyası bulunamadı: {frame_path}")

    frame = PILImage.open(frame_path).convert("RGBA")
    canvas = frame.copy()
    draw = ImageDraw.Draw(canvas)

    panel_margin_x = 36
    panel_margin_y = 36
    panel_w = frame.width - panel_margin_x * 2
    panel_h = int(frame.height * 0.56)

    panel_x1 = panel_margin_x
    panel_y1 = panel_margin_y
    panel_x2 = panel_x1 + panel_w
    panel_y2 = panel_y1 + panel_h

    panel_overlay = PILImage.new("RGBA", frame.size, (0, 0, 0, 0))
    panel_draw = ImageDraw.Draw(panel_overlay)

    panel_draw.rounded_rectangle(
        (panel_x1, panel_y1, panel_x2, panel_y2),
        radius=28,
        fill=(17, 28, 48, 228),
        outline=(102, 132, 214, 105),
        width=2,
    )

    canvas = PILImage.alpha_composite(canvas, panel_overlay)
    draw = ImageDraw.Draw(canvas)

    title_font = _get_font(30)
    body_font = _get_font(22)
    small_font = _get_font(18)

    inner_pad = 26
    gap = 22

    has_side_image = bool(content_image_path and os.path.exists(content_image_path))
    side_w = 280 if has_side_image else 0

    text_x1 = panel_x1 + inner_pad
    text_y1 = panel_y1 + inner_pad
    text_x2 = panel_x2 - inner_pad - (side_w + gap if has_side_image else 0)

    title_max_width = max(100, text_x2 - text_x1)
    title_lines = _wrap_lines(draw, title or "", title_font, title_max_width, 3)

    current_y = text_y1
    line_gap_title = 10

    for line in title_lines:
        draw.text((text_x1, current_y), line, font=title_font, fill=(248, 250, 255, 255))
        bbox = draw.textbbox((0, 0), line, font=title_font)
        current_y += (bbox[3] - bbox[1]) + line_gap_title

    divider_y = current_y + 8
    draw.line(
        (text_x1, divider_y, panel_x2 - inner_pad, divider_y),
        fill=(140, 158, 208, 135),
        width=2,
    )

    body_y = divider_y + 22
    footer_reserved = 44 if footer_text else 0
    body_max_height = panel_y2 - inner_pad - footer_reserved - body_y
    body_line_height = 34
    max_body_lines = max(3, body_max_height // body_line_height)

    body_max_width = title_max_width
    body_lines = _wrap_lines(draw, body or "", body_font, body_max_width, max_body_lines)

    current_body_y = body_y
    for line in body_lines:
        draw.text((text_x1, current_body_y), line, font=body_font, fill=(228, 235, 250, 255))
        current_body_y += body_line_height

    if has_side_image:
        image_box_w = side_w
        image_box_h = panel_h - (inner_pad * 2)
        image_x = panel_x2 - inner_pad - image_box_w
        image_y = panel_y1 + inner_pad

        box_overlay = PILImage.new("RGBA", frame.size, (0, 0, 0, 0))
        box_draw = ImageDraw.Draw(box_overlay)
        box_draw.rounded_rectangle(
            (image_x, image_y, image_x + image_box_w, image_y + image_box_h),
            radius=22,
            fill=(9, 15, 26, 120),
            outline=(120, 140, 200, 90),
            width=1,
        )
        canvas = PILImage.alpha_composite(canvas, box_overlay)

        fitted = _fit_content_image(content_image_path, (image_box_w, image_box_h))
        if fitted is not None:
            mask = _rounded_mask((image_box_w, image_box_h), 22)
            image_layer = PILImage.new("RGBA", frame.size, (0, 0, 0, 0))
            image_layer.paste(fitted, (image_x, image_y), mask)
            canvas = PILImage.alpha_composite(canvas, image_layer)

        draw = ImageDraw.Draw(canvas)

    logo = _fit_logo(logo_path, max_size=(180, 100))
    if logo:
        logo_y = panel_y2 + 80
        logo_x = 160
        canvas.paste(logo, (logo_x, logo_y), logo)

    if footer_text:
        footer_x = panel_x1 + inner_pad
        footer_y = panel_y2 - 34
        draw.text(
            (footer_x, footer_y),
            footer_text[:36],
            font=small_font,
            fill=(150, 168, 214, 215),
        )

    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".png")
    canvas.save(temp_file.name, format="PNG")
    return temp_file.name


def send_analysis_bundle(
    instrument_name: str,
    display_levels: dict,
    analysis_text: str,
    signal_text: str,
    main_image_path: str,
    fractal_image_path: str,
    main_frame_path: str,
    fractal_frame_path: str,
    token: Optional[str] = None,
    chat_id: Optional[str] = None,
) -> dict:
    results = {
        "main_panel": None,
        "fractal_panel": None,
        "analysis_message": None,
        "signal_message": None,
    }

    main_panel = create_panel_with_frame(
        image_path=main_image_path,
        frame_path=main_frame_path,
        panel_type="main",
    )
    fractal_panel = create_panel_with_frame(
        image_path=fractal_image_path,
        frame_path=fractal_frame_path,
        panel_type="fractal",
    )

    results["main_panel"] = send_photo(
        image_path=main_panel,
        caption="",
        token=token,
        chat_id=chat_id,
    )

    results["fractal_panel"] = send_photo(
        image_path=fractal_panel,
        caption="",
        token=token,
        chat_id=chat_id,
    )

    analysis_message = build_analysis_message(
        instrument_name=instrument_name,
        display_levels=display_levels,
        analysis_text=analysis_text,
    )
    signal_message = build_signal_message(
        instrument_name=instrument_name,
        signal_text=signal_text,
    )

    results["analysis_message"] = send_message(
        analysis_message,
        token=token,
        chat_id=chat_id,
    )
    results["signal_message"] = send_message(
        signal_message,
        token=token,
        chat_id=chat_id,
    )

    return results


def send_news_bundle(
    title: str,
    body: str,
    frame_path: str,
    logo_path: str,
    footer_text: str,
    content_image_path: str = "",
    token: str = "",
    chat_id: str = "",
) -> dict:
    card_path = create_content_card_with_frame(
        title=title,
        body=body,
        frame_path=frame_path,
        logo_path=logo_path,
        content_image_path=content_image_path,
        footer_text=footer_text,
    )

    photo_result = send_photo(
        image_path=card_path,
        caption="",
        token=token,
        chat_id=chat_id,
    )

    return {"card": photo_result}


def send_data_bundle(
    title: str,
    body: str,
    frame_path: str,
    logo_path: str,
    footer_text: str,
    content_image_path: str = "",
    token: str = "",
    chat_id: str = "",
) -> dict:
    card_path = create_content_card_with_frame(
        title=title,
        body=body,
        frame_path=frame_path,
        logo_path=logo_path,
        content_image_path=content_image_path,
        footer_text=footer_text,
    )

    photo_result = send_photo(
        image_path=card_path,
        caption="",
        token=token,
        chat_id=chat_id,
    )

    return {"card": photo_result}