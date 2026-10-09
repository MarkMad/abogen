import builtins
import sys
from unittest.mock import patch

from abogen.shutdown import install_qt_hook


def test_qt_shutdown_hook_does_not_import_pyqt_when_unloaded():
    with patch.dict(sys.modules):
        sys.modules.pop("PyQt6.QtWidgets", None)
        with patch.object(
            builtins,
            "__import__",
            side_effect=AssertionError("Qt should not be imported by this hook"),
        ) as import_mock:
            install_qt_hook()

    import_mock.assert_not_called()
