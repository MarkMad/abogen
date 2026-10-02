import threading
from dataclasses import fields

import pytest

from abogen.application.conversion_ports import ConversionCancelled
from abogen.domain.enums import Language
from abogen.webui.conversion_runner import WebUIEventsAdapter, _build_request
from abogen.webui.service import ConversionService, JobStatus


@pytest.fixture
def service(monkeypatch, tmp_path):
    monkeypatch.setenv("ABOGEN_QUEUE_STATE_PATH", str(tmp_path / "queue.json"))
    monkeypatch.setattr(ConversionService, "_ensure_worker", lambda self: None)
    return ConversionService(tmp_path / "outputs", lambda job: None)


def enqueue(service, tmp_path, **settings):
    source = tmp_path / "book.txt"
    source.write_text("A sentence.", encoding="utf-8")
    return service.enqueue(
        original_filename=source.name, stored_path=source, language=Language.EN_US,
        voice="M1", speed=1.0, use_gpu=False, subtitle_mode="Sentence",
        output_format="wav", save_mode="Save next to input file", output_folder=None,
        replace_single_newlines=False, subtitle_format="srt", total_characters=11,
        **settings,
    )


def test_cancel_queued_paused_job_finalizes_and_persists(service, tmp_path):
    job = enqueue(service, tmp_path)
    assert service.pause(job.id)
    assert job.status == JobStatus.PAUSED
    assert job.id not in service._queue
    assert service.cancel(job.id)
    assert job.status == JobStatus.CANCELLED
    assert job.finished_at is not None
    restored = ConversionService(tmp_path / "outputs", lambda job: None).get_job(job.id)
    assert restored.status == JobStatus.CANCELLED
    assert restored.finished_at == job.finished_at


@pytest.mark.parametrize("action", ["resume", "cancel"])
def test_running_job_waits_at_boundary_and_wakes(service, tmp_path, action):
    job = enqueue(service, tmp_path)
    entered = threading.Event()
    boundary = threading.Event()
    continued = threading.Event()
    paused = threading.Event()
    original_log = job.add_log

    def log(message, level="info"):
        original_log(message, level=level)
        if message == "Job paused at conversion boundary":
            paused.set()

    job.add_log = log

    def runner(current):
        entered.set()
        assert boundary.wait(3)
        try:
            WebUIEventsAdapter(current).check_cancelled()
        except ConversionCancelled:
            current.status = JobStatus.CANCELLED
            return
        continued.set()

    service._runner = runner
    service._queue.remove(job.id)
    worker = threading.Thread(target=service._run_job, args=(job,))
    worker.start()
    try:
        assert entered.wait(3)
        assert service.pause(job.id)
        assert job.status == JobStatus.RUNNING  # Current work finishes first.
        boundary.set()
        assert paused.wait(3)
        assert job.status == JobStatus.PAUSED
        assert not continued.wait(0.05)
        assert not service.delete(job.id)
        assert getattr(service, action)(job.id)
        worker.join(3)
        assert not worker.is_alive()
        assert continued.is_set() == (action == "resume")
        assert job.status == (JobStatus.COMPLETED if action == "resume" else JobStatus.CANCELLED)
        assert job.finished_at is not None
        assert job.id not in service._active_jobs
    finally:
        service.cancel(job.id)
        boundary.set()
        worker.join(3)


def test_retry_preserves_complete_conversion_request(service, tmp_path):
    job = enqueue(service, tmp_path, tts_provider="supertonic", supertonic_total_steps=9,
                  read_closing_outro=False, heteronym_overrides=[{"word": "read", "pronunciation": "red"}])
    job.status = JobStatus.FAILED
    expected = _build_request(job)
    retried = service.retry(job.id)
    assert retried is not None
    actual = _build_request(retried)
    for field in fields(expected):
        assert getattr(actual, field.name) == getattr(expected, field.name), field.name


@pytest.mark.parametrize("closing_outro", [False, True])
def test_restart_preserves_closing_outro(service, tmp_path, closing_outro):
    job = enqueue(service, tmp_path, read_closing_outro=closing_outro)
    service._persist_state()
    restored = ConversionService(tmp_path / "outputs", lambda job: None).get_job(job.id)
    assert restored.read_closing_outro is closing_outro


def test_old_queue_state_defaults_to_closing_outro(service, tmp_path):
    job = enqueue(service, tmp_path, read_closing_outro=False)
    payload = service._serialize_job(job)
    payload.pop("read_closing_outro")
    assert service._deserialize_job(payload).read_closing_outro is True
