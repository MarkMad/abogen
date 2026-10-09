from unittest.mock import MagicMock, patch

from abogen.application.conversion_request import ConversionRequest
from abogen.application.voice_resolver import AppVoiceResolver
from abogen.domain.voice_loader import VoiceCache


def test_resolving_kokoro_voice_allows_unspecified_speed(caplog):
    request = ConversionRequest(voice="af_alloy", tts_provider="kokoro")
    resolver = AppVoiceResolver(
        request=request,
        normalized_profiles={},
        pool=MagicMock(),
        cache=VoiceCache(),
    )

    with patch("abogen.domain.voice_utils.get_voices", return_value=("af_alloy",)), patch(
        "abogen.application.voice_resolver.resolve_voice",
        return_value="af_alloy",
    ):
        resolved = resolver.resolve("af_alloy")

    assert resolved.voice == "af_alloy"
    assert resolved.speed is None
    assert "failed to resolve" not in caplog.text.lower()
