import subprocess
import sys

from abogen.utils import create_process


def test_create_process_drains_output_without_stdout(monkeypatch):
    monkeypatch.setattr(sys, "stdout", None)
    process = create_process(
        [
            sys.executable,
            "-c",
            "import sys; sys.stdout.write('x' * 100000)",
        ]
    )

    try:
        assert process.wait(timeout=10) == 0
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait()
        raise