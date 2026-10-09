from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from abogen.webui.app import create_app
from abogen.webui.routes import main


def _app(tmp_path, monkeypatch, *, errors=None, submit_error=None):
    app = create_app(
        {
            "TESTING": True,
            "SECRET_KEY": "test",
            "OUTPUT_FOLDER": str(tmp_path / "output"),
            "UPLOAD_FOLDER": str(tmp_path / "uploads"),
        }
    )
    pending = SimpleNamespace(id="pending")
    service = Mock()
    service.get_pending_job.return_value = pending
    app.extensions["conversion_service"] = service
    monkeypatch.setattr(
        main,
        "apply_prepare_form",
        Mock(return_value=(None, None, [], errors or [], None, None, None, None)),
    )
    submit = Mock(side_effect=submit_error) if submit_error else Mock(return_value="job-id")
    monkeypatch.setattr(main, "submit_job", submit)
    monkeypatch.setattr(main, "render_jobs_panel", Mock(return_value="<div></div>"))
    return app, service, submit


def test_wizard_finish_returns_json_validation_error(tmp_path, monkeypatch):
    app, _, submit = _app(
        tmp_path, monkeypatch, errors=["Select at least one chapter to continue."]
    )

    response = app.test_client().post(
        "/wizard/finish",
        data={"pending_id": "pending"},
        headers={"Accept": "application/json"},
    )

    assert response.status_code == 400
    assert response.get_json() == {
        "error": "Select at least one chapter to continue."
    }
    submit.assert_not_called()


def test_wizard_finish_returns_json_when_queue_submission_fails(tmp_path, monkeypatch):
    app, _, _ = _app(
        tmp_path, monkeypatch, submit_error=RuntimeError("queue unavailable")
    )

    response = app.test_client().post(
        "/wizard/finish",
        data={"pending_id": "pending"},
        headers={"Accept": "application/json"},
    )

    assert response.status_code == 500
    assert response.get_json() == {
        "error": "Unable to queue conversion: queue unavailable"
    }


def test_wizard_finish_returns_json_for_oversized_form(tmp_path):
    app = create_app(
        {
            "TESTING": True,
            "SECRET_KEY": "test",
            "OUTPUT_FOLDER": str(tmp_path / "output"),
            "UPLOAD_FOLDER": str(tmp_path / "uploads"),
            "MAX_FORM_PARTS": 1,
        }
    )

    with app.test_client() as client:
        response = client.post(
            "/wizard/finish?pending_id=pending",
            data={"chapter-0-title": "Chapter 1", "chapter-1-title": "Chapter 2"},
            content_type="multipart/form-data",
            headers={"Accept": "application/json"},
        )

    assert response.status_code == 413
    assert response.is_json


def test_wizard_finish_returns_json_after_successful_submission(tmp_path, monkeypatch):
    app, _, submit = _app(tmp_path, monkeypatch)

    response = app.test_client().post(
        "/wizard/finish",
        data={"pending_id": "pending"},
        headers={"Accept": "application/json"},
    )

    assert response.status_code == 200
    assert response.get_json() == {
        "status": "submitted",
        "job_id": "job-id",
        "redirect_url": "/",
        "jobs_panel": "<div></div>",
    }
    submit.assert_called_once()


def test_submit_job_keeps_pending_job_when_enqueue_fails(monkeypatch):
    from abogen.webui.routes import utils

    pending = Mock(id="pending")
    service = Mock()
    service.enqueue.side_effect = RuntimeError("queue unavailable")
    monkeypatch.setattr(utils.service, "get_service", lambda: service)

    with pytest.raises(RuntimeError, match="queue unavailable"):
        utils.service.submit_job(pending)

    service.pop_pending_job.assert_not_called()
