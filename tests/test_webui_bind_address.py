from unittest.mock import Mock

import pytest

from abogen.webui import app as web_app


@pytest.mark.parametrize("override,expected", [(None, "127.0.0.1"), ("0.0.0.0", "0.0.0.0")])
def test_server_binding_defaults_to_loopback(monkeypatch, override, expected):
    monkeypatch.delenv("ABOGEN_HOST", raising=False)
    monkeypatch.delenv("ABOGEN_PORT", raising=False)
    monkeypatch.delenv("ABOGEN_DEBUG", raising=False)
    if override is not None:
        monkeypatch.setenv("ABOGEN_HOST", override)
    app = Mock()
    monkeypatch.setattr(web_app, "create_app", lambda: app)
    monkeypatch.setattr(web_app, "setup_console_logging", lambda: None)
    # main replaces the banner globally; restore it after the test.
    import flask.cli
    monkeypatch.setattr(flask.cli, "show_server_banner", flask.cli.show_server_banner)
    web_app.main()
    app.run.assert_called_once_with(host=expected, port=8808, debug=False)
