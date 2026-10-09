import sys
from types import ModuleType, SimpleNamespace
from unittest.mock import Mock

import numpy as np
import pytest

from abogen.domain.enums import Language
from plugins.supertonic import pipeline


def test_supertonic3_uses_korean_language_and_chunk_defaults(monkeypatch, tmp_path):
    tts = Mock()
    tts.get_voice_style.return_value = object()
    tts.synthesize.return_value = (np.zeros(24000, dtype=np.float32), 1.0)
    monkeypatch.setitem(
        sys.modules, "supertonic", SimpleNamespace(TTS=Mock(return_value=tts))
    )
    monkeypatch.setattr(pipeline, "_configure_supertonic_gpu", lambda device: None)
    monkeypatch.setenv("SUPERTONIC_CACHE_DIR", str(tmp_path / "models"))

    instance = pipeline.SupertonicPipeline(
        language=Language.KO,
        device="cpu",
        sample_rate=24000,
    )
    list(instance("안녕하세요.", voice="F1", speed=1.0))

    assert instance.total_steps == 8
    assert instance.max_chunk_length == 120
    tts.synthesize.assert_called_once_with(
        text="안녕하세요.",
        voice_style=tts.get_voice_style.return_value,
        lang="ko",
        total_steps=8,
        speed=1.0,
        max_chunk_length=120,
        silence_duration=0.0,
        verbose=False,
    )


def test_supertonic_profile_steps_default_to_v3_quality():
    from abogen.voice_profiles import _coerce_supertonic_steps

    assert _coerce_supertonic_steps(None) == 8


@pytest.mark.parametrize(
    ("device", "expected"),
    [
        ("cpu", ["CPUExecutionProvider"]),
        ("cuda:0", ["CUDAExecutionProvider", "CPUExecutionProvider"]),
    ],
)
def test_gpu_provider_is_selected_from_requested_device(monkeypatch, device, expected):
    config = SimpleNamespace(DEFAULT_ONNX_PROVIDERS=[])
    loader = SimpleNamespace(DEFAULT_ONNX_PROVIDERS=[])
    package = ModuleType("supertonic")
    package.__path__ = []
    monkeypatch.setitem(
        sys.modules,
        "onnxruntime",
        SimpleNamespace(
            get_available_providers=lambda: [
                "CUDAExecutionProvider",
                "CPUExecutionProvider",
            ]
        ),
    )
    monkeypatch.setitem(sys.modules, "supertonic", package)
    monkeypatch.setitem(sys.modules, "supertonic.config", config)
    monkeypatch.setitem(sys.modules, "supertonic.loader", loader)

    pipeline._configure_supertonic_gpu(device)

    assert config.DEFAULT_ONNX_PROVIDERS == expected
    assert loader.DEFAULT_ONNX_PROVIDERS == expected
