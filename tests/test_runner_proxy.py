import os

from runner_proxy import process_alive


def test_process_alive_detects_current_and_missing_processes():
    assert process_alive(os.getpid())
    assert not process_alive(2_147_483_647)
