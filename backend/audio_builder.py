"""
audio_builder.py — bilingual TTS audio builder for Quick Generate.

Ported from scripts/build_session.py. Builds L1 (word) and L2 (sentence)
cards using edge-tts and pydub, then concatenates into a single MP3.
"""
from __future__ import annotations

import hashlib
from pathlib import Path

import edge_tts
from pydub import AudioSegment

# Voice constants (same as build_session.py)
GERMAN_VOICES = ["de-DE-KatjaNeural", "de-DE-ConradNeural"]
ENGLISH_VOICE = "en-US-AriaNeural"

# Cache directory for TTS segments on Render
CACHE_DIR = Path("/tmp/rd-cache")

# Gap timing defaults (same as build_session.py)
GAPS = {
    # L1 word card
    "word_def": 1.5,   # after German word, before English translation
    "def_ex": 1.0,     # after English translation, before German example
    "ex_trans": 2.0,   # after German example, before English example
    # L2 sentence card
    "de_en": 2.0,      # after German sentence, before English translation
    # Shared
    "between": 2.5,    # between cards (wider so boundaries are audible)
    "lead_in": 0.5,    # silence at the very start
    "pre_card": 0.3,   # tiny silence before each card
}


async def tts_segment(text: str, voice: str, rate: str = "+0%") -> AudioSegment:
    """Render text to speech and return as AudioSegment. Cached on disk."""
    text = text.strip()
    if not text:
        return AudioSegment.silent(duration=0)

    key = hashlib.sha1(f"{voice}|{rate}|{text}".encode("utf-8")).hexdigest()[:20]
    path = CACHE_DIR / f"{key}.mp3"

    if not path.exists():
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        comm = edge_tts.Communicate(text, voice, rate=rate)
        await comm.save(str(path))

    return AudioSegment.from_mp3(path)


def silence(seconds: float) -> AudioSegment:
    return AudioSegment.silent(duration=int(seconds * 1000))


async def build_word_card(
    card: dict,
    voice_de: str,
    voice_en: str,
    rate: str,
) -> AudioSegment:
    """Build an L1 word card: de_word -> en_word -> de_example -> en_example."""
    de_word = await tts_segment(card["de"], voice_de, rate)
    en_word = await tts_segment(card["en"], voice_en, rate)

    audio = silence(GAPS["pre_card"]) + de_word + silence(GAPS["word_def"]) + en_word

    # Add example if available
    if card.get("de_example") and card.get("en_example"):
        de_ex = await tts_segment(card["de_example"], voice_de, rate)
        en_ex = await tts_segment(card["en_example"], voice_en, rate)
        audio += silence(GAPS["def_ex"]) + de_ex + silence(GAPS["ex_trans"]) + en_ex

    audio += silence(GAPS["between"])
    return audio


async def build_sentence_card(
    card: dict,
    voice_de: str,
    voice_en: str,
    rate: str,
) -> AudioSegment:
    """Build an L2 sentence card: de -> en."""
    de = await tts_segment(card["de"], voice_de, rate)
    en = await tts_segment(card["en"], voice_en, rate)

    return (
        silence(GAPS["pre_card"])
        + de + silence(GAPS["de_en"])
        + en + silence(GAPS["between"])
    )


async def build_session_audio(
    cards: list[dict],
    card_type: str,
    voice_de: str,
    speed: float = 1.0,
    output_path: str = "/tmp/rd-output.mp3",
) -> str:
    """Build a complete bilingual MP3 session from selected cards.

    Args:
        cards: list of card dicts (with de, en, and optionally de_example/en_example)
        card_type: "l1" (word cards) or "l2" (sentence cards)
        voice_de: German voice ID
        speed: playback speed (applied via edge-tts rate parameter)
        output_path: where to write the MP3

    Returns:
        output_path
    """
    rate = f"{int((speed - 1) * 100):+d}%"
    voice_en = ENGLISH_VOICE

    # Start with lead-in silence
    session = silence(GAPS["lead_in"])

    for i, card in enumerate(cards):
        if card_type == "l1":
            segment = await build_word_card(card, voice_de, voice_en, rate)
        else:
            segment = await build_sentence_card(card, voice_de, voice_en, rate)

        session += segment

    # Export
    session.export(output_path, format="mp3", bitrate="96k")
    return output_path
