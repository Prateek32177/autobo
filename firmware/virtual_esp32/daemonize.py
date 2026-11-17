"""Double-fork daemonization so background helpers survive the launching shell."""

from __future__ import annotations

import os
import sys
from pathlib import Path


def daemonize(*, pid_file: str | Path, stdin=None, stdout=None, stderr=None) -> None:
    """Become a session-leader daemon; write the final PID to ``pid_file``.

    Parent and intermediate processes exit immediately. Safe on macOS/Linux.
    """
    pid_path = Path(pid_file)
    pid_path.parent.mkdir(parents=True, exist_ok=True)

    if os.fork() > 0:
        os._exit(0)

    os.setsid()

    if os.fork() > 0:
        os._exit(0)

    pid_path.write_text(f"{os.getpid()}\n", encoding="utf-8")

    os.chdir("/")
    os.umask(0)

    devnull = open(os.devnull, "r+b", buffering=0)  # noqa: SIM115
    sin = open(stdin, "rb", buffering=0) if stdin else devnull  # noqa: SIM115
    sout = open(stdout, "ab", buffering=0) if stdout else devnull  # noqa: SIM115
    serr = open(stderr, "ab", buffering=0) if stderr else sout  # noqa: SIM115

    os.dup2(sin.fileno(), sys.stdin.fileno())
    os.dup2(sout.fileno(), sys.stdout.fileno())
    os.dup2(serr.fileno(), sys.stderr.fileno())
