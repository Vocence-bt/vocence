"""Tests for vocence.pipeline.evaluation."""
import tempfile
import pytest
from unittest.mock import AsyncMock, MagicMock
from vocence.pipeline.evaluation import (
    generate_description_async,
    forced_choice_assessment_async,
    get_transcription_and_traits_async,
    format_task_prompt_for_tts,
)


@pytest.fixture
def temp_wav_path():
    """Minimal valid WAV file (44-byte header + a few samples)."""
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
        # Minimal WAV header + 1 sample
        f.write(b"RIFF\x24\x00\x00\x00WAVEfmt \x10\x00\x00\x00\x01\x00\x01\x00\x22\x56\x00\x00\x44\xac\x00\x00\x02\x00\x10\x00data\x00\x00\x00\x00")
        return f.name


@pytest.mark.asyncio
async def test_generate_description_returns_string(mock_openai_client, temp_wav_path):
    mock_openai_client.chat.completions.create = AsyncMock(
        return_value=MagicMock(
            choices=[MagicMock(message=MagicMock(content='{"transcription": "Hi", "gender": "male", "emotion": "neutral", "pitch": "normal", "tone": "casual", "environment": "quiet", "speed": "normal", "accent": "american"}'))]
        )
    )
    try:
        result = await generate_description_async(mock_openai_client, temp_wav_path)
        assert isinstance(result, str)
        assert "Hi" in result or "male" in result
    finally:
        import os
        if os.path.exists(temp_wav_path):
            os.remove(temp_wav_path)


@pytest.mark.asyncio
async def test_forced_choice_returns_dict(mock_openai_client, temp_wav_path):
    mock_openai_client.chat.completions.create = AsyncMock(
        return_value=MagicMock(
            choices=[MagicMock(message=MagicMock(content="FIRST\nMore natural."))]
        )
    )
    path2 = temp_wav_path + ".2.wav"
    import shutil
    shutil.copy(temp_wav_path, path2)
    try:
        result = await forced_choice_assessment_async(
            mock_openai_client, temp_wav_path, path2, "prompt"
        )
        assert "original_won" in result
        assert "generated_won" in result
        assert "confidence" in result
    finally:
        import os
        if os.path.exists(path2):
            os.remove(path2)


@pytest.mark.asyncio
async def test_get_transcription_and_traits_returns_dict(mock_openai_client, temp_wav_path):
    mock_openai_client.chat.completions.create = AsyncMock(
        return_value=MagicMock(
            choices=[MagicMock(message=MagicMock(content='{"transcription": "Hello", "gender": "female", "emotion": "happy", "pitch": "normal", "tone": "warm", "environment": "quiet", "speed": "normal", "accent": "british"}'))]
        )
    )
    try:
        result = await get_transcription_and_traits_async(mock_openai_client, temp_wav_path)
        assert result["transcription"] == "Hello"
        assert result["gender"] == "female"
        assert result["accent"] == "british"
    finally:
        import os
        if os.path.exists(temp_wav_path):
            os.remove(temp_wav_path)


def test_format_task_prompt_for_tts():
    traits = {"transcription": "Hi there", "gender": "male", "emotion": "neutral"}
    out = format_task_prompt_for_tts(traits)
    assert "Hi there" in out
    assert "gender: male" in out
    assert "emotion: neutral" in out
