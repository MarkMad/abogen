import importlib
import sys

import os

import pytest

# Ensure real optional dependencies are imported before tests that install stubs
# so that available packages (like ebooklib, bs4, numpy) aren't replaced with dummy modules.
for module_name in ("ebooklib", "bs4", "numpy"):
    if module_name not in sys.modules:
        try:
            importlib.import_module(module_name)
        except Exception:
            # On environments without the optional dependency, downstream tests
            # will install lightweight stubs as needed.
            pass


@pytest.fixture(autouse=True, scope="session")
def _isolate_settings_dir(tmp_path_factory: pytest.TempPathFactory):
    test_root = tmp_path_factory.mktemp("abogen-data")
    patcher = pytest.MonkeyPatch()
    for name, folder in {
        "ABOGEN_SETTINGS_DIR": "settings",
        "ABOGEN_TEMP_DIR": "cache",
        "ABOGEN_INTERNAL_CACHE_ROOT": "cache",
        "XDG_CACHE_HOME": "cache",
        "HF_HOME": "huggingface",
        "HUGGINGFACE_HUB_CACHE": "huggingface",
        "TRANSFORMERS_CACHE": "huggingface",
        "ABOGEN_OUTPUT_DIR": "outputs",
        "ABOGEN_OUTPUT_ROOT": "outputs",
        "ABOGEN_UPLOAD_ROOT": "uploads",
        "ABOGEN_VOICE_CACHE_DIR": "voices",
        "SUPERTONIC_CACHE_DIR": "supertonic",
    }.items():
        if name == "SUPERTONIC_CACHE_DIR" and os.environ.get("ABOGEN_TEST_REAL_TTS") == "1":
            # Opt-in integration tests must be able to reuse installed models.
            # Leave this unset when absent so the legacy cache can be discovered.
            continue
        patcher.setenv(name, str(test_root / folder))

    try:
        from abogen.utils import get_user_settings_dir, get_user_cache_root

        get_user_settings_dir.cache_clear()
        get_user_cache_root.cache_clear()
    except Exception:
        pass

    try:
        from abogen.normalization_settings import clear_cached_settings

        clear_cached_settings()
    except Exception:
        pass

    try:
        yield
    finally:
        patcher.undo()
        from abogen.utils import get_user_settings_dir, get_user_cache_root
        get_user_settings_dir.cache_clear()
        get_user_cache_root.cache_clear()
