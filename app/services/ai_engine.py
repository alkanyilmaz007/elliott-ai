import os
import base64
from pathlib import Path
from typing import Optional, Dict, Tuple, List

from dotenv import load_dotenv
from openai import OpenAI

PROJECT_ROOT = Path(__file__).resolve().parents[2]
ENV_PATH = PROJECT_ROOT / ".env"
PROMPTS_DIR = Path(__file__).resolve().parent / "prompts"

load_dotenv(dotenv_path=ENV_PATH, override=True)

# GEÇİCİ ÇÖZÜM:
# Buraya kendi full OpenAI key'ini yaz.
# Sistem ayağa kalkınca tekrar .env'den okumaya döneriz.
FORCE_OPENAI_API_KEY = ""


def _read_prompt_file(name: str) -> str:
    candidates = [
        PROMPTS_DIR / name,
        PROMPTS_DIR / f"{name}.txt",
    ]
    for path in candidates:
        if path.exists():
            return path.read_text(encoding="utf-8").strip()
    return ""


def get_openai_api_key(explicit_api_key: Optional[str] = None) -> str:
    candidates = [
        explicit_api_key,
        FORCE_OPENAI_API_KEY,
        os.getenv("OPENAI_API_KEY", ""),
        os.getenv("OPEN_AI_KEY", ""),
        os.getenv("OPENAI_KEY", ""),
        os.getenv("API_KEY", ""),
    ]

    for item in candidates:
        if item and str(item).strip():
            return str(item).strip()

    raise ValueError(f"OPENAI_API_KEY bulunamadı. Beklenen .env yolu: {ENV_PATH}")


def get_openai_client(api_key: Optional[str] = None) -> OpenAI:
    key = get_openai_api_key(api_key)
    return OpenAI(api_key=key)


def image_to_data_url(image_path: str) -> Optional[str]:
    if not image_path or not os.path.exists(image_path):
        return None

    ext = image_path.lower().split(".")[-1]
    mime = "image/jpeg"
    if ext == "png":
        mime = "image/png"
    elif ext == "bmp":
        mime = "image/bmp"
    elif ext == "webp":
        mime = "image/webp"

    with open(image_path, "rb") as f:
        encoded = base64.b64encode(f.read()).decode("utf-8")
    return f"data:{mime};base64,{encoded}"


def normalize_ratio_key(raw: str) -> str:
    ratio = raw.strip().replace(",", ".")
    aliases = {
        "1.0": "1",
        "1.000": "1",
        "0.500": "0.5",
        "0.50": "0.5",
        "0.2360": "0.236",
        "0.3820": "0.382",
        "0.6180": "0.618",
        "0.7640": "0.764",
        "0.8540": "0.854",
        "1.2360": "1.236",
        "1.6180": "1.618",
        "2.2720": "2.272",
        "2.4140": "2.414",
        "2.6180": "2.618",
    }
    return aliases.get(ratio, ratio)


def parse_fib_map(fib_text: str) -> Dict[str, float]:
    result: Dict[str, float] = {}
    if not fib_text:
        return result
    for part in fib_text.split(","):
        if "=" in part:
            ratio, value = part.split("=", 1)
            ratio = normalize_ratio_key(ratio)
            try:
                result[ratio] = float(value.strip().replace(",", "."))
            except Exception:
                pass
    return result


def format_price(value: Optional[float], decimals: int = 2) -> str:
    if value is None:
        return "..."
    return f"{float(value):.{decimals}f}".replace(".", ",")


def unique_sorted_below(fibs: Dict[str, float], price: float) -> List[float]:
    return sorted({v for v in fibs.values() if v < price}, reverse=True)


def unique_sorted_above(fibs: Dict[str, float], price: float) -> List[float]:
    return sorted({v for v in fibs.values() if v > price})


def pick_above_by_priority(
    fibs: Dict[str, float],
    current_price: float,
    ratios: List[str],
    count: int = 2
) -> List[float]:
    chosen: List[float] = []

    for ratio in ratios:
        value = fibs.get(ratio)
        if value is not None and value > current_price and value not in chosen:
            chosen.append(value)
        if len(chosen) >= count:
            break

    if len(chosen) < count:
        for value in unique_sorted_above(fibs, current_price):
            if value not in chosen:
                chosen.append(value)
            if len(chosen) >= count:
                break

    return chosen[:count]


def pick_below_by_priority(
    fibs: Dict[str, float],
    current_price: float,
    ratios: List[str],
    count: int = 2
) -> List[float]:
    chosen: List[float] = []

    for ratio in ratios:
        value = fibs.get(ratio)
        if value is not None and value < current_price and value not in chosen:
            chosen.append(value)
        if len(chosen) >= count:
            break

    if len(chosen) < count:
        for value in unique_sorted_below(fibs, current_price):
            if value not in chosen:
                chosen.append(value)
            if len(chosen) >= count:
                break

    return chosen[:count]


def choose_fractal_levels_with_main_fallback(
    fractal_fibs: Dict[str, float],
    main_fibs: Dict[str, float],
    current_price: float,
    fractal_pattern: str,
    fractal_subwave: str,
) -> Tuple[Optional[float], Optional[float], Optional[float], Optional[float]]:
    fs1 = fs2 = fr1 = fr2 = None

    if fractal_pattern == "Impuls" and fractal_subwave == "Wave 3":
        below = unique_sorted_below(fractal_fibs, current_price)
        fs1 = below[0] if len(below) > 0 else None
        fs2 = below[1] if len(below) > 1 else None
        above = pick_above_by_priority(fractal_fibs, current_price, ["1", "1.618","2.272","2.414","2.618"], count=2)
        fr1 = above[0] if len(above) > 0 else None
        fr2 = above[1] if len(above) > 1 else None

    elif fractal_pattern == "Impuls" and fractal_subwave == "Wave 4":
        below = pick_below_by_priority(fractal_fibs, current_price, ["0.236", "0.382", "0.5"], count=2)
        above = pick_above_by_priority(fractal_fibs, current_price, ["0.5", "0.618", "0.764"], count=2)
        fs1 = below[0] if len(below) > 0 else None
        fs2 = below[1] if len(below) > 1 else None
        fr1 = above[0] if len(above) > 0 else None
        fr2 = above[1] if len(above) > 1 else None

    elif fractal_pattern == "Impuls" and fractal_subwave == "Wave 5":
        below = unique_sorted_below(fractal_fibs, current_price)
        fs1 = below[0] if len(below) > 0 else None
        fs2 = below[1] if len(below) > 1 else None
        above = pick_above_by_priority(fractal_fibs, current_price, ["1", "1.618","2.272","2.414","2.618"], count=2)
        fr1 = above[0] if len(above) > 0 else None
        fr2 = above[1] if len(above) > 1 else None

    elif fractal_pattern == "Diagonal":
        below = unique_sorted_below(fractal_fibs, current_price)
        fs1 = below[0] if len(below) > 0 else None
        fs2 = below[1] if len(below) > 1 else None
        above = pick_above_by_priority(fractal_fibs, current_price, ["0.618", "1", "1.618"], count=2)
        fr1 = above[0] if len(above) > 0 else None
        fr2 = above[1] if len(above) > 1 else None

    elif fractal_pattern == "ABC" and fractal_subwave == "Wave C":
        below = pick_below_by_priority(fractal_fibs, current_price, ["0.618", "1", "1.236"], count=2)
        above = unique_sorted_above(fractal_fibs, current_price)
        fs1 = below[0] if len(below) > 0 else None
        fs2 = below[1] if len(below) > 1 else None
        fr1 = above[0] if len(above) > 0 else None
        fr2 = above[1] if len(above) > 1 else None

    elif fractal_pattern == "ABC" and fractal_subwave == "Wave B":
        below = pick_below_by_priority(fractal_fibs, current_price, ["0.5", "0.618", "0.764", "0.854"], count=2)
        above = pick_above_by_priority(fractal_fibs, current_price, ["1.236"], count=2)
        fs1 = below[0] if len(below) > 0 else None
        fs2 = below[1] if len(below) > 1 else None
        fr1 = above[0] if len(above) > 0 else None
        fr2 = above[1] if len(above) > 1 else None

    elif fractal_pattern == "WXY":
        if fractal_subwave == "Wave X":
            below = pick_below_by_priority(fractal_fibs, current_price, ["0.5", "0.618", "0.764", "0.854"], count=2)
            above = unique_sorted_above(fractal_fibs, current_price)
        elif fractal_subwave == "Wave Y":
            below = pick_below_by_priority(fractal_fibs, current_price, ["0.618", "1", "1.236"], count=2)
            above = unique_sorted_above(fractal_fibs, current_price)
        else:
            below = unique_sorted_below(fractal_fibs, current_price)
            above = unique_sorted_above(fractal_fibs, current_price)

        fs1 = below[0] if len(below) > 0 else None
        fs2 = below[1] if len(below) > 1 else None
        fr1 = above[0] if len(above) > 0 else None
        fr2 = above[1] if len(above) > 1 else None

    else:
        below = unique_sorted_below(fractal_fibs, current_price)
        above = unique_sorted_above(fractal_fibs, current_price)
        fs1 = below[0] if len(below) > 0 else None
        fs2 = below[1] if len(below) > 1 else None
        fr1 = above[0] if len(above) > 0 else None
        fr2 = above[1] if len(above) > 1 else None

    if fs2 is None:
        for lvl in unique_sorted_below(main_fibs, current_price):
            if fs1 is None or lvl < fs1:
                fs2 = lvl
                break

    return fs1, fs2, fr1, fr2


def choose_main_support_resistance(
    main_fibs: Dict[str, float],
    current_price: float,
    main_pattern: str,
    main_subwave: str,
    fs1: Optional[float] = None,
    fs2: Optional[float] = None,
    fr1: Optional[float] = None,
    fr2: Optional[float] = None,
) -> Tuple[Optional[float], Optional[float]]:
    main_support = None
    main_resistance = None

    if main_pattern == "ABC" and main_subwave == "Wave C":
        fib_0618 = main_fibs.get("0.618")
        fib_1236 = main_fibs.get("1.236")
        fib_1 = main_fibs.get("1")
        if fib_0618 is not None and current_price < fib_0618 and fib_1236 is not None:
            main_support = fib_1236
        elif fib_1 is not None:
            main_support = fib_1

    elif main_pattern == "ABC" and main_subwave == "Wave B":
        main_support = main_fibs.get("0.854") or main_fibs.get("0.764") or main_fibs.get("0.618")
        main_resistance = main_fibs.get("1.236")

    elif main_pattern == "Impuls" and main_subwave == "Wave 5":
        main_resistance = main_fibs.get("1") or main_fibs.get("1.618") or main_fibs.get("2.618")

    elif main_pattern == "Diagonal" and main_subwave == "Wave 5":
        main_resistance = main_fibs.get("0.618") or main_fibs.get("1") or main_fibs.get("1.618")

    if main_support is None:
        below_main = unique_sorted_below(main_fibs, current_price)
        main_support = below_main[0] if below_main else None

    if main_resistance is None:
        above_main = unique_sorted_above(main_fibs, current_price)
        main_resistance = above_main[0] if above_main else None

    fib0 = main_fibs.get("0")
    fib1 = main_fibs.get("1")

    if fs1 is not None and fs2 is not None and main_support is not None:
        if not (main_support < fs1 and main_support < fs2):
            if fib0 is not None and fib0 < fs1 and fib0 < fs2:
                main_support = fib0

    if fr1 is not None and fr2 is not None and main_resistance is not None:
        if not (main_resistance > fr1 and main_resistance > fr2):
            if fib1 is not None and fib1 > fr1 and fib1 > fr2:
                main_resistance = fib1

    return main_support, main_resistance


def decide_signal_direction(
    fractal_subwave: str,
    fractal_pattern: str,
    fractal_fibs: Dict[str, float],
    current_price: float,
    main_reverse_mode: bool,
    fractal_reverse_mode: bool,
) -> str:
    wave_direction_map = {
        "Wave 1": "BUY",
        "Wave 3": "BUY",
        "Wave 5": "BUY",
        "Wave 2": "SELL",
        "Wave 4": "SELL",
        "Wave A": "SELL",
        "Wave C": "SELL",
        "Wave W": "SELL",
        "Wave Y": "SELL",
        "Wave B": "BUY",
        "Wave X": "BUY",
    }

    direction = wave_direction_map.get(fractal_subwave, "NÖTR")

    if fractal_pattern == "WXY" and fractal_subwave == "Wave Y":
        fib0 = fractal_fibs.get("0")
        fib1236 = fractal_fibs.get("1.236")
        fib1618 = fractal_fibs.get("1.618")

        if fib0 is not None and fib1236 is not None and fib1618 is not None:
            if fib0 > fib1236 > fib1618:
                if current_price < fib1236 and current_price > fib1618:
                    direction = "BUY"
            elif fib0 < fib1236 < fib1618:
                if current_price > fib1236 and current_price < fib1618:
                    direction = "BUY"

    if direction == "NÖTR":
        return direction

    reverse_count = int(main_reverse_mode) + int(fractal_reverse_mode)
    if reverse_count % 2 == 1:
        return "SELL" if direction == "BUY" else "BUY"

    return direction


def build_invalidation_text(
    direction: str,
    ms: Optional[float],
    mr: Optional[float],
    fs1: Optional[float],
    fs2: Optional[float],
    fr1: Optional[float],
    fr2: Optional[float],
    main_fibs: Dict[str, float],
) -> str:
    fib0 = main_fibs.get("0")
    fib1 = main_fibs.get("1")

    if direction == "BUY":
        invalid_level = ms
        if fib0 is not None and fs1 is not None and fs2 is not None:
            if fib0 < fs1 and fib0 < fs2:
                invalid_level = fib0
        return f"{format_price(invalid_level, 2)} altı yapı bozulur" if invalid_level is not None else "Yapı bozulma seviyesi hesaplanamadı."

    if direction == "SELL":
        invalid_level = mr
        if fib1 is not None and fr1 is not None and fr2 is not None:
            if fib1 > fr1 and fib1 > fr2:
                invalid_level = fib1
        return f"{format_price(invalid_level, 2)} üstü yapı bozulur" if invalid_level is not None else "Yapı bozulma seviyesi hesaplanamadı."

    return "Yapı bozulma seviyesi hesaplanamadı."


def get_signal_instrument_name(instrument: str) -> str:
    name = (instrument or "").strip()
    if name.lower() == "gold":
        return "GOLD"
    return name.upper() if name else "ENSTRUMAN"


def build_comment_and_signal(
    current_price: float,
    instrument: str,
    fs1: Optional[float],
    fs2: Optional[float],
    fr1: Optional[float],
    fr2: Optional[float],
    ms: Optional[float],
    mr: Optional[float],
    direction: str,
    fractal_pattern: str,
    fractal_subwave: str,
    fractal_fibs: Dict[str, float],
) -> Tuple[str, str]:
    if direction == "BUY" and None in (fs1, fs2, fr1, ms):
        return "BUY yorumu üretmek için seviyeler eksik.", "BUY sinyali üretmek için seviyeler eksik."

    if direction == "SELL" and None in (fs1, fr1, fr2, mr):
        return "SELL yorumu üretmek için seviyeler eksik.", "SELL sinyali üretmek için seviyeler eksik."

    instrument_text = get_signal_instrument_name(instrument)
    entry_str = format_price(current_price, 2)

    if direction == "BUY":
        if fractal_pattern == "WXY" and fractal_subwave == "Wave Y":
            fib0 = fractal_fibs.get("0")
            fib1236 = fractal_fibs.get("1.236")
            fib1618 = fractal_fibs.get("1.618")

            if fib0 is not None and fib1236 is not None and fib1618 is not None:
                is_descending_y = fib0 > fib1236 > fib1618 and current_price < fib1236 and current_price > fib1618
                is_ascending_y = fib0 < fib1236 < fib1618 and current_price > fib1236 and current_price < fib1618

                if is_descending_y or is_ascending_y:
                    best_stop = fib1618
                    target = (fib0 + fib1618) / 2.0

                    analysis_text = (
                        f"#{instrument_text} {entry_str} anlık fiyat seviyesinde bulunan enstrümanda "
                        f"Wave Y yapısı 1,236 bölgesini aştığı için klasik satış senaryosu zayıflamıştır. "
                        f"Bu nedenle beklentimiz alım yönündedir. "
                        f"En uygun zarar kes noktası {format_price(best_stop, 2)} seviyesinde olmalıdır. "
                        f"Hedef bölge ise 0 ile 1,618 seviyesi arasındaki orta nokta olan {format_price(target, 2)} seviyesidir."
                    )

                    signal_text = (
                        f"#{instrument_text} BUY\n"
                        f"Giriş: {entry_str}\n"
                        f"Hedef: {format_price(target, 2)}\n"
                        f"Zarar Kes: {format_price(best_stop, 2)}\n"
                        f"Kırılım Noktası: {format_price(best_stop, 2)}"
                    )
                    return analysis_text, signal_text

        best_stop = ms
        near_stop = fs2
        target = fr1

        analysis_text = (
            f"#{instrument_text} {entry_str} anlık fiyat seviyesinde bulunan enstrümanda "
            f"fraktal dirençleri {format_price(fr1, 2)} ve {format_price(fr2, 2)} seviyeleridir. "
            f"desteklerimiz ise {format_price(fs1, 2)} ve {format_price(fs2, 2)} dir. "
            f"Beklentimiz alım yönünde olup en uygun zarar kes noktası {format_price(best_stop, 2)} "
            f"desteği altında olmalıdır. yakın zarar kes noktası ise {format_price(near_stop, 2)} "
            f"noktasının altında uygun bir konum seçilebilir. hedefimiz ise {format_price(target, 2)} tür."
        )

        signal_text = (
            f"#{instrument_text} BUY\n"
            f"Giriş: {entry_str}\n"
            f"Hedef: {format_price(target, 2)}\n"
            f"Zarar Kes: {format_price(near_stop, 2)} altı\n"
            f"Kırılım Noktası: {format_price(best_stop, 2)}"
        )
        return analysis_text, signal_text

    if direction == "SELL":
        best_stop = mr
        near_stop = fr2
        target = fs1

        analysis_text = (
            f"#{instrument_text} {entry_str} anlık fiyat seviyesinde bulunan enstrümanda "
            f"fraktal dirençleri {format_price(fr1, 2)} ve {format_price(fr2, 2)} seviyeleridir. "
            f"desteklerimiz ise {format_price(fs1, 2)} ve {format_price(fs2, 2)} dir. "
            f"Beklentimiz satış yönünde olup en uygun zarar kes noktası {format_price(best_stop, 2)} "
            f"direnci üzerinde olmalıdır. yakın zarar kes noktası ise {format_price(near_stop, 2)} "
            f"seviyesi üzerinde uygun bir konum seçilebilir. hedefimiz ise {format_price(target, 2)} tür."
        )

        signal_text = (
            f"#{instrument_text} SELL\n"
            f"Giriş: {entry_str}\n"
            f"Hedef: {format_price(target, 2)}\n"
            f"Zarar Kes: {format_price(near_stop, 2)} üstü\n"
            f"Kırılım Noktası: {format_price(best_stop, 2)}"
        )
        return analysis_text, signal_text

    return "Bu yapı için net sinyal üretilemedi.", f"#{instrument_text} NÖTR"


def build_ai_prompt(
    instrument: str,
    current_price: float,
    main_pattern: str,
    main_subwave: str,
    fractal_pattern: str,
    fractal_subwave: str,
) -> str:
    rules_text = _read_prompt_file("elliott_rules")
    scenarios_text = _read_prompt_file("elliott_scenarios")
    style_text = _read_prompt_file("style_examples")

    return f"""
Senin görevin yorum yazmak değil, iki görselde görünen Fibonacci fiyat seviyelerini DÜZGÜN ÇIKARMAKTIR.

Enstrüman:
- {instrument}

Anlık fiyat:
- {current_price}

Ana dalga görseli:
- Pattern: {main_pattern}
- Sub Wave: {main_subwave}

Fraktal dalga görseli:
- Pattern: {fractal_pattern}
- Sub Wave: {fractal_subwave}

Kurallar:
{rules_text}

Senaryolar:
{scenarios_text}

Stil örnekleri:
{style_text}

Görev:
1. ANA DALGA görselinde görünen tüm Fibonacci seviyelerini oran=fiyat formatında çıkar.
2. FRAKTAL DALGA görselinde görünen tüm Fibonacci seviyelerini oran=fiyat formatında çıkar.
3. Oran ve fiyatı birlikte yaz.
4. Yorum yazma.
5. Destek/direnç seçme.
6. Sadece seviyeleri çıkar.
7. Fiyatlarda ondalık basamakları koru.

Format:
MAIN_FIBS: 0=...,0.236=...,0.382=...,0.5=...,0.618=...,0.764=...,0.854=...,1=...,1.236=...,1.618=...,2.272=...,2.414=...,2.618=...
FRACTAL_FIBS: 0=...,0.236=...,0.382=...,0.5=...,0.618=...,0.764=...,0.854=...,1=...,1.236=...,1.618=...,2.272=...,2.414=...,2.618=...
OBSERVATION: kısa not
"""


def call_openai_for_fibs(
    main_image_path: str,
    fractal_image_path: str,
    instrument: str,
    current_price: float,
    main_pattern: str,
    main_subwave: str,
    fractal_pattern: str,
    fractal_subwave: str,
    api_key: Optional[str] = None,
) -> str:
    client = get_openai_client(api_key=api_key)

    main_image = image_to_data_url(main_image_path)
    fractal_image = image_to_data_url(fractal_image_path)

    if not main_image or not fractal_image:
        raise ValueError("Ana ve fraktal görseller zorunlu.")

    content = [{"type": "input_text", "text": build_ai_prompt(
        instrument=instrument,
        current_price=current_price,
        main_pattern=main_pattern,
        main_subwave=main_subwave,
        fractal_pattern=fractal_pattern,
        fractal_subwave=fractal_subwave,
    )}]
    content.append({"type": "input_image", "image_url": main_image})
    content.append({"type": "input_image", "image_url": fractal_image})

    response = client.responses.create(
        model="gpt-4.1-mini",
        input=[{"role": "user", "content": content}],
    )

    text = response.output_text.strip()
    if not text:
        raise ValueError("AI boş cevap döndürdü.")
    return text


def parse_ai_output(text: str) -> Tuple[Dict[str, float], Dict[str, float], str]:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    parsed = {}

    for line in lines:
        if ":" in line:
            key, value = line.split(":", 1)
            parsed[key.strip().upper()] = value.strip()

    main_fibs = parse_fib_map(parsed.get("MAIN_FIBS", ""))
    fractal_fibs = parse_fib_map(parsed.get("FRACTAL_FIBS", ""))
    observation = parsed.get("OBSERVATION", "")

    return main_fibs, fractal_fibs, observation


def run_full_analysis(
    main_image_path: str,
    fractal_image_path: str,
    instrument: str,
    current_price: float,
    main_pattern: str,
    main_subwave: str,
    fractal_pattern: str,
    fractal_subwave: str,
    main_reverse_mode: bool = False,
    fractal_reverse_mode: bool = False,
    api_key: Optional[str] = None,
) -> Dict:
    raw_text = call_openai_for_fibs(
        main_image_path=main_image_path,
        fractal_image_path=fractal_image_path,
        instrument=instrument,
        current_price=current_price,
        main_pattern=main_pattern,
        main_subwave=main_subwave,
        fractal_pattern=fractal_pattern,
        fractal_subwave=fractal_subwave,
        api_key=api_key,
    )

    main_fibs, fractal_fibs, observation = parse_ai_output(raw_text)

    if not main_fibs or not fractal_fibs:
        raise ValueError("AI çıktısı parse edilemedi.")

    fs1, fs2, fr1, fr2 = choose_fractal_levels_with_main_fallback(
        fractal_fibs=fractal_fibs,
        main_fibs=main_fibs,
        current_price=current_price,
        fractal_pattern=fractal_pattern,
        fractal_subwave=fractal_subwave,
    )

    ms, mr = choose_main_support_resistance(
        main_fibs=main_fibs,
        current_price=current_price,
        main_pattern=main_pattern,
        main_subwave=main_subwave,
        fs1=fs1,
        fs2=fs2,
        fr1=fr1,
        fr2=fr2,
    )

    direction = decide_signal_direction(
        fractal_subwave=fractal_subwave,
        fractal_pattern=fractal_pattern,
        fractal_fibs=fractal_fibs,
        current_price=current_price,
        main_reverse_mode=main_reverse_mode,
        fractal_reverse_mode=fractal_reverse_mode,
    )

    invalidation_text = build_invalidation_text(
        direction=direction,
        ms=ms,
        mr=mr,
        fs1=fs1,
        fs2=fs2,
        fr1=fr1,
        fr2=fr2,
        main_fibs=main_fibs,
    )

    analysis_text, signal_text = build_comment_and_signal(
        current_price=current_price,
        instrument=instrument,
        fs1=fs1,
        fs2=fs2,
        fr1=fr1,
        fr2=fr2,
        ms=ms,
        mr=mr,
        direction=direction,
        fractal_pattern=fractal_pattern,
        fractal_subwave=fractal_subwave,
        fractal_fibs=fractal_fibs,
    )

    return {
        "raw_ai_text": raw_text,
        "observation": observation,
        "main_fibs": main_fibs,
        "fractal_fibs": fractal_fibs,
        "levels": {
            "fs1": fs1,
            "fs2": fs2,
            "fr1": fr1,
            "fr2": fr2,
            "ms": ms,
            "mr": mr,
            "direction": direction,
        },
        "display": {
            "fractal_support_1": format_price(fs1, 2),
            "fractal_support_2": format_price(fs2, 2),
            "fractal_resistance_1": format_price(fr1, 2),
            "fractal_resistance_2": format_price(fr2, 2),
            "main_support": format_price(ms, 2),
            "main_resistance": format_price(mr, 2),
            "invalidation": invalidation_text,
        },
        "analysis_text": analysis_text,
        "signal_text": signal_text,
    }