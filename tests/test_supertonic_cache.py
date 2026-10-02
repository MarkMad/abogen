import sys
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from plugins.supertonic import pipeline


@pytest.mark.parametrize("source", ["explicit", "environment", "legacy", "app", "partial"])
def test_pipeline_model_directory_precedence(monkeypatch, tmp_path, source):
    tts = Mock()
    monkeypatch.setitem(sys.modules, "supertonic", SimpleNamespace(TTS=tts))
    monkeypatch.setattr(pipeline, "_configure_supertonic_gpu", lambda: None)
    app_cache = Mock(return_value=str(tmp_path / "app"))
    monkeypatch.setattr("abogen.utils.get_user_cache_path", app_cache)
    monkeypatch.delenv("SUPERTONIC_CACHE_DIR", raising=False)
    monkeypatch.setattr(pipeline.Path, "home", lambda: tmp_path)
    legacy_dir = tmp_path / ".cache" / "supertonic2"
    (legacy_dir / "onnx").mkdir(parents=True)
    for name in ("duration_predictor.onnx", "text_encoder.onnx", "vector_estimator.onnx", "vocoder.onnx"):
        if source != "app" and not (source == "partial" and name == "vocoder.onnx"):
            (legacy_dir / "onnx" / name).touch()
    model_dir = None
    if source in ("explicit", "environment"):
        monkeypatch.setenv("SUPERTONIC_CACHE_DIR", str(tmp_path / "environment"))
    if source == "explicit":
        model_dir = tmp_path / "explicit"
    pipeline.SupertonicPipeline(sample_rate=24000, model_dir=model_dir, auto_download=False)
    expected = model_dir if source == "explicit" else (
        legacy_dir if source == "legacy" else str(tmp_path / ("app" if source == "partial" else source))
    )
    tts.assert_called_once_with(model_dir=expected, auto_download=False)
    if source in ("app", "partial"):
        app_cache.assert_called_once_with("supertonic2")
    else:
        app_cache.assert_not_called()


@pytest.mark.parametrize("real_tts", [False, True])
@pytest.mark.parametrize("configured", [False, True])
def test_test_isolation_preserves_real_model_cache(monkeypatch, tmp_path, real_tts, configured):
    import os
    from tests.conftest import _isolate_settings_dir

    monkeypatch.setenv("ABOGEN_TEST_REAL_TTS", "1" if real_tts else "0")
    original = str(tmp_path / "installed-models")
    if configured:
        monkeypatch.setenv("SUPERTONIC_CACHE_DIR", original)
    else:
        monkeypatch.delenv("SUPERTONIC_CACHE_DIR", raising=False)
    test_root = tmp_path / "isolated"
    test_root.mkdir()
    fixture = _isolate_settings_dir.__wrapped__(SimpleNamespace(mktemp=lambda _: test_root))
    next(fixture)
    try:
        expected = (original if configured else None) if real_tts else str(test_root / "supertonic")
        assert os.environ.get("SUPERTONIC_CACHE_DIR") == expected
    finally:
        fixture.close()


def test_engine_passes_resolved_model_path(monkeypatch, tmp_path):
    import plugins.supertonic as plugin
    from abogen.tts_plugin.types import EngineConfig
    config = EngineConfig()
    loader = Mock()
    monkeypatch.setattr(plugin, "_load_supertonic_pipeline", loader)
    engine = plugin.create_engine(Mock(), tmp_path / "models", config)
    loader.assert_called_once_with(language=config.language, model_path=tmp_path / "models")
    engine.dispose()
