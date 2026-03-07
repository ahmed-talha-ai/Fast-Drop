# core/arabic_normalizer.py
# ═══════════════════════════════════════════════════════════════════
# 4-Stage Arabic Text Preprocessing Pipeline for Fast Drop
# Handles: Egyptian Arabic dialect, MSA, Arabizi (Franco-Arabic),
#           English, and code-switched Arabic+English input.
# Must be called on EVERY user input without exception.
# ═══════════════════════════════════════════════════════════════════
import re
import logging

logger = logging.getLogger("fastdrop.arabic")

# ── Try importing CAMeL Tools (graceful fallback if not installed) ──
try:
    from camel_tools.utils.normalize import (
        normalize_unicode,
        normalize_alef_maksura_ar,
        normalize_alef_ar,
        normalize_teh_marbuta_ar,
    )
    from camel_tools.utils.dediac import dediac_ar
    CAMEL_AVAILABLE = True
    logger.info("CAMeL Tools loaded successfully")
except ImportError:
    CAMEL_AVAILABLE = False
    logger.warning("CAMeL Tools not installed — using regex fallback normalizer")

try:
    from camel_tools.dialectid import DialectIdentifier
    dialect_id = DialectIdentifier.pretrained()
    DIALECT_ID_AVAILABLE = True
except Exception:
    DIALECT_ID_AVAILABLE = False
    logger.warning("CAMeL DialectIdentifier not available — using heuristic fallback")

try:
    from langdetect import detect_langs
    LANGDETECT_AVAILABLE = True
except ImportError:
    LANGDETECT_AVAILABLE = False

# ── Arabizi pattern: Latin text with Arabic-specific number usage ──
ARABIZI_PATTERN = re.compile(
    r"(?:^|\s)(?:[a-zA-Z23456789]+\s*)+(?:$|\s)",
    re.MULTILINE,
)

# ── Arabizi → Arabic manual transliteration map ──────────────────
# Common Franco-Arabic mappings used in Egypt
ARABIZI_MAP = {
    "2": "أ", "3": "ع", "5": "خ", "6": "ط", "7": "ح",
    "8": "غ", "9": "ق",
    "sh": "ش", "ch": "تش", "kh": "خ", "gh": "غ", "th": "ث",
    "dh": "ذ", "aa": "ا", "ee": "ي", "oo": "و",
    "a": "ا", "b": "ب", "t": "ت", "g": "ج", "j": "ج",
    "d": "د", "r": "ر", "z": "ز", "s": "س", "f": "ف",
    "q": "ق", "k": "ك", "l": "ل", "m": "م", "n": "ن",
    "h": "ه", "w": "و", "y": "ي", "i": "ي", "o": "و",
    "u": "و", "e": "ا", "p": "ب", "v": "ف",
}

# Sort by length (longer patterns first) for correct replacement
ARABIZI_SORTED = sorted(ARABIZI_MAP.items(), key=lambda x: -len(x[0]))

# ── Common Egyptian Arabic delivery terms ────────────────────────
DELIVERY_TERMS = {
    "order": "أوردر",
    "delivery": "ديليفري",
    "driver": "سواق",
    "shipment": "شحنة",
    "track": "تتبع",
    "cancel": "إلغاء",
    "address": "عنوان",
    "phone": "تليفون",
    "late": "متأخر",
    "broken": "اتكسر",
    "stolen": "اتسرق",
}


# ═══════════════════════════════════════════════
# Stage 1: Language & Script Detection
# ═══════════════════════════════════════════════
def detect_input_type(text: str) -> str:
    """
    Detect input language/script type.
    Returns: "arabic_msa" | "arabic_dialect" | "arabizi" | "mixed" | "english"
    """
    has_arabic = bool(re.search(r"[\u0600-\u06FF]", text))
    has_latin = bool(re.search(r"[a-zA-Z]", text))
    # Arabizi often uses 2,3,5,6,7,8,9 as Arabic letter substitutes
    has_arabizi_nums = bool(re.search(r"[2356789]", text)) and has_latin

    # Fast-path: pure English (no Arabic chars, no Arabizi numbers)
    if has_latin and not has_arabic and not has_arabizi_nums:
        if LANGDETECT_AVAILABLE:
            try:
                langs = detect_langs(text)
                top = langs[0]
                if top.lang == "en" and top.prob > 0.7:
                    return "english"
                if top.lang == "ar":
                    return "arabic_msa"
            except Exception:
                pass
        return "english"

    if has_arabic and has_latin:
        return "mixed"

    if has_arabic:
        # Try dialect identification with CAMeL Tools
        if DIALECT_ID_AVAILABLE:
            try:
                result = dialect_id.predict([text])
                dialect = result[0].top
                if dialect in ["CAI", "ASW", "ALX", "LUX"]:  # Egyptian cities
                    return "arabic_dialect"
            except Exception:
                pass
        # Heuristic: common Egyptian dialect words
        egyptian_markers = [
            "فين", "ازاي", "عايز", "مش", "ده", "دي", "كده",
            "دلوقتي", "ليه", "إيه", "هو", "هي", "بتاع", "أوردر",
            "بكرة", "امبارح", "النهارده", "يعني", "اهو", "خالص",
        ]
        if any(marker in text for marker in egyptian_markers):
            return "arabic_dialect"
        return "arabic_msa"

    if has_latin and has_arabizi_nums:
        return "arabizi"

    # Check for Arabizi without numbers (common patterns) — ONLY Arabizi-specific words
    arabizi_words = [
        "feen", "ezay", "msh", "bta3", "3ayez", "mesh",
        "keda", "leih", "yalla", "habibi", "dlw2ty", "mashkoor",
        "fein", "wein", "7aga", "2awi",
    ]
    text_lower = text.lower()
    arabizi_count = sum(1 for w in arabizi_words if w in text_lower)
    if arabizi_count >= 2:
        return "arabizi"

    if has_latin:
        if LANGDETECT_AVAILABLE:
            try:
                langs = detect_langs(text)
                if langs[0].lang == "ar":
                    return "arabic_msa"
            except Exception:
                pass
        return "english"

    return "english"


# ═══════════════════════════════════════════════
# Stage 2: Arabizi → Arabic Transliteration
# ═══════════════════════════════════════════════
def transliterate_arabizi(text: str) -> str:
    """
    Convert Franco-Arabic (Arabizi) to Arabic script.
    Example: "feen el order bta3y" → "فين ال أوردر بتاعي"
    Uses CAMeL Tools if available, falls back to manual map.
    """
    # Try CAMeL Tools transliterator first
    try:
        from camel_tools.transliterate import Transliterator
        transliterator = Transliterator.from_name("arabeasy")
        return transliterator.transliterate(text)
    except Exception:
        pass

    # Manual fallback transliteration
    result = text.lower()

    # Replace known English delivery terms first
    for eng, arb in DELIVERY_TERMS.items():
        result = re.sub(
            rf"\b{eng}\b", arb, result, flags=re.IGNORECASE
        )

    # Apply Arabizi character mapping
    for latin, arabic in ARABIZI_SORTED:
        result = result.replace(latin, arabic)

    return result


# ═══════════════════════════════════════════════
# Stage 3: Arabic Text Normalization
# ═══════════════════════════════════════════════
def normalize_arabic(text: str) -> str:
    """
    Full normalization pipeline for Egyptian Arabic.
    Apply to any Arabic text before embedding or LLM calls.
    Sequence matters — do not reorder.
    """
    if CAMEL_AVAILABLE:
        text = normalize_unicode(text)            # Step 1: Unicode cleanup
        text = normalize_alef_ar(text)             # Step 2: آ إ أ → ا
        text = normalize_alef_maksura_ar(text)     # Step 3: ى → ي
        text = normalize_teh_marbuta_ar(text)      # Step 4: ة → ه
        text = dediac_ar(text)                     # Step 5: Remove diacritics
    else:
        # Regex fallback normalization
        text = re.sub(r"[آأإٱ]", "ا", text)       # Alef forms → ا
        text = re.sub(r"ى", "ي", text)             # Alef Maksura → Ya
        text = re.sub(r"ة", "ه", text)             # Ta Marbuta → Ha
        text = re.sub(
            r"[\u064B-\u065F\u0670]", "", text     # Remove diacritics
        )

    text = re.sub(r"[ـ]", "", text)                # Step 6: Remove kashida
    text = re.sub(r"\s+", " ", text).strip()       # Step 7: Clean whitespace
    return text


# ═══════════════════════════════════════════════
# Stage 4: Master Preprocessing Function
# ═══════════════════════════════════════════════
def prepare_user_input(text: str) -> dict:
    """
    Master function — call this on EVERY user message.
    Returns normalized text + metadata for downstream processing.

    Usage:
        meta = prepare_user_input("فين الأوردر بتاعي؟")
        normalized = meta["normalized"]
        lang = meta["response_language"]  # "ar" or "en"
    """
    original = text
    input_type = detect_input_type(text)

    # Transliterate Arabizi to Arabic
    if input_type == "arabizi":
        text = transliterate_arabizi(text)
        input_type = "arabic_dialect"  # After transliteration

    # Normalize Arabic text
    if input_type in ("arabic_dialect", "arabic_msa", "mixed"):
        text = normalize_arabic(text)

    return {
        "original": original,
        "normalized": text,
        "input_type": input_type,
        "is_arabic": input_type != "english",
        "response_language": "ar" if input_type != "english" else "en",
    }


# ═══════════════════════════════════════════════
# Status Mapping: English DB → Egyptian Arabic
# ═══════════════════════════════════════════════
STATUS_ARABIC_MAP = {
    "created": "اتعمل وبيتجهز",
    "processing": "بيتجهز دلوقتي",
    "assigned": "اتعين سواق للتوصيل",
    "picked_up": "السواق استلم الطرد",
    "out_for_delivery": "خارج للتسليم — الديليفري في الطريق إليك",
    "delivered": "اتسلم بنجاح ✅",
    "failed": "لم يتم التسليم — هنحاول تاني",
    "rescheduled": "اتأجل لموعد جديد",
    "returned": "رجع للمخزن",
}


def arabic_status(status: str) -> str:
    """Map English DB status values to Egyptian Arabic."""
    return STATUS_ARABIC_MAP.get(status.lower(), status)
