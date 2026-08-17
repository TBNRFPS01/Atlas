from types import SimpleNamespace

import psutil

from automation.process import Process


def _procs(*names: str):
    return [SimpleNamespace(info={"name": n, "pid": 1, "cpu_percent": 0.0, "memory_percent": 0.0}) for n in names]


def test_process_is_running_matches_partial_name(monkeypatch) -> None:
    monkeypatch.setattr(psutil, "process_iter", lambda attrs=None: _procs("javaw.exe", "explorer.exe"))
    assert Process().is_running("java") is True


def test_process_is_running_absent(monkeypatch) -> None:
    monkeypatch.setattr(psutil, "process_iter", lambda attrs=None: _procs("explorer.exe"))
    assert Process().is_running("java") is False