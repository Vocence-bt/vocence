"""
Audio assessment for Vocence using AudioJudge.

Uses AudioJudge (https://github.com/Woodygan/AudioJudge) for:
- Pointwise: transcription + voice traits from one audio (prompt generation)
- Pairwise: which of two audios is more natural (evaluation).

Model: gpt-4o-audio-preview (or GPT_AUDIO_MODEL). OpenAI key only (no Google required).
"""

import asyncio
import json
import random
from typing import Any, Dict

from vocence.domain.config import GPT_AUDIO_MODEL, OPENAI_AUTH_KEY


# ---------------------------------------------------------------------------
# Prompt generation: single audio → transcription + voice traits (pointwise)
# ---------------------------------------------------------------------------

DESCRIPTION_SYSTEM = """You are an expert at describing speech for text-to-speech systems.
Analyze the audio and return a JSON object with these exact keys:
- transcription: exact words spoken (string)
- gender: one of male, female, unknown
- emotion: e.g. happy, sad, neutral, angry, calm, excited, bored
- pitch: one of high, normal, low
- tone: e.g. warm, cold, friendly, formal, casual
- environment: e.g. quiet, noise, crowd, seaside, office, outdoor
- speed: one of fast, normal, slow
- accent: e.g. american, british, neutral, other

Return ONLY valid JSON, no markdown or extra text. Example:
{"transcription": "Hello world", "gender": "male", "emotion": "neutral", "pitch": "normal", "tone": "casual", "environment": "quiet", "speed": "normal", "accent": "american"}"""


def _get_judge():
    """Lazy-create AudioJudge with OpenAI key from config (OPENAI_AUTH_KEY or OPENAI_API_KEY in .env)."""
    from audiojudge import AudioJudge
    return AudioJudge(openai_api_key=OPENAI_AUTH_KEY, google_api_key=None)


def _parse_traits_response(text: str) -> Dict[str, Any]:
    """Parse JSON from pointwise response; strip markdown if present."""
    if not text:
        return {"transcription": "", "gender": "unknown", "emotion": "neutral", "pitch": "normal", "tone": "neutral", "environment": "quiet", "speed": "normal", "accent": "neutral"}
    raw = text.strip()
    if "```" in raw:
        for part in raw.split("```"):
            part = part.strip()
            if part.startswith("json"):
                part = part[4:].strip()
            if part.startswith("{"):
                raw = part
                break
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {"transcription": raw[:500], "gender": "unknown", "emotion": "neutral", "pitch": "normal", "tone": "neutral", "environment": "quiet", "speed": "normal", "accent": "neutral"}


async def get_transcription_and_traits_async(openai_client: Any, audio_path: str) -> Dict[str, Any]:
    """Get transcription and voice traits from one audio using AudioJudge pointwise evaluation.
    
    Ignores openai_client; uses AudioJudge with OPENAI_AUTH_KEY for consistency.
    
    Returns:
        Dict with keys: transcription, gender, emotion, pitch, tone, environment, speed, accent
    """
    judge = _get_judge()
    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(
        None,
        lambda: judge.judge_audio_pointwise(
            audio_path=audio_path,
            system_prompt=DESCRIPTION_SYSTEM,
            user_prompt=None,
            model=GPT_AUDIO_MODEL,
            concatenation_method="no_concatenation",
            temperature=0.00000001,
            max_tokens=500,
        ),
    )
    if not result.get("success"):
        return _parse_traits_response("")  # fallback
    return _parse_traits_response(result.get("response", "") or "")


def format_task_prompt_for_tts(traits: Dict[str, Any]) -> str:
    """Format transcription + traits as a single text prompt for miner TTS."""
    parts = [traits.get("transcription", "")]
    for key in ("gender", "emotion", "pitch", "tone", "environment", "speed", "accent"):
        v = traits.get(key)
        if v:
            parts.append(f"{key}: {v}")
    return " | ".join(p for p in parts if p)


# ---------------------------------------------------------------------------
# Evaluation: pairwise comparison (which audio is more natural)
# ---------------------------------------------------------------------------

COMPARE_SYSTEM_TEMPLATE = """You are an audio naturalness judge. You will hear two audio clips.
Both are responses to the same TTS task. The task description (transcription and voice traits) is:

{task_description}

Criteria: Which clip sounds MORE NATURAL and matches the description better? Consider:
1. Speech clarity and naturalness
2. Match to the intended voice traits (gender, emotion, pitch, tone, etc.)
3. Absence of artifacts or unnatural prosody

You must pick one. Respond with exactly one line: FIRST or SECOND
- FIRST = the first audio clip you hear is better
- SECOND = the second audio clip you hear is better
Optionally add a short reasoning on the next line. The first line must be exactly FIRST or SECOND."""


def _parse_first_second(response_text: str) -> tuple[bool, int, str]:
    """Parse FIRST/SECOND from response; return (winner_is_first, confidence, reasoning)."""
    text = (response_text or "").strip().upper()
    first_line = text.split("\n")[0].strip() if text else ""
    reasoning = "\n".join(text.split("\n")[1:]).strip() if "\n" in text else ""
    winner_first = "FIRST" in first_line
    confidence = 75
    for word in first_line.split():
        if word.isdigit() and 50 <= int(word) <= 100:
            confidence = int(word)
            break
    return winner_first, confidence, reasoning or first_line


async def compare_audio_naturalness_async(
    openai_client: Any,
    audio1_path: str,
    audio2_path: str,
    task_description: str,
) -> Dict[str, Any]:
    """Compare two audios: which sounds more natural given the task (AudioJudge pairwise).
    
    Randomizes order to avoid position bias. openai_client is unused; AudioJudge uses OPENAI_AUTH_KEY.
    
    Returns:
        Dict with original_won, generated_won, confidence, reasoning, presentation_order
    """
    judge = _get_judge()
    swap = random.choice([True, False])
    if swap:
        first_path, second_path = audio2_path, audio1_path
        original_is = "second"
    else:
        first_path, second_path = audio1_path, audio2_path
        original_is = "first"
    
    system_prompt = COMPARE_SYSTEM_TEMPLATE.format(task_description=task_description)
    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(
        None,
        lambda: judge.judge_audio(
            audio1_path=first_path,
            audio2_path=second_path,
            system_prompt=system_prompt,
            user_prompt=None,
            model=GPT_AUDIO_MODEL,
            concatenation_method="no_concatenation",
            temperature=0.00000001,
            max_tokens=200,
        ),
    )
    
    if not result.get("success"):
        # Fallback: treat as tie / no decision
        return {
            "original_won": False,
            "generated_won": False,
            "confidence": 50,
            "reasoning": result.get("error", "Evaluation failed"),
            "original_artifacts": [],
            "generated_artifacts": [],
            "presentation_order": f"{'generated' if swap else 'original'} first",
        }
    
    response_text = result.get("response", "") or ""
    winner_first, confidence, reasoning = _parse_first_second(response_text)
    original_won = (winner_first and original_is == "first") or (not winner_first and original_is == "second")
    
    return {
        "original_won": original_won,
        "generated_won": not original_won,
        "confidence": confidence,
        "reasoning": reasoning,
        "original_artifacts": [],
        "generated_artifacts": [],
        "presentation_order": f"{'generated' if swap else 'original'} first",
    }


# Backward-compatible names for callers
async def generate_description_async(openai_client: Any, audio_path: str) -> str:
    """Get a TTS task prompt from one full audio (transcription + traits)."""
    traits = await get_transcription_and_traits_async(openai_client, audio_path)
    return format_task_prompt_for_tts(traits)


async def forced_choice_assessment_async(
    openai_client: Any,
    original_audio_path: str,
    generated_audio_path: str,
    task_prompt: str,
) -> Dict[str, Any]:
    """Which of the two audios is more natural (AudioJudge pairwise)."""
    return await compare_audio_naturalness_async(
        openai_client,
        original_audio_path,
        generated_audio_path,
        task_prompt,
    )
