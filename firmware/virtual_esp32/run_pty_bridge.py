#!/usr/bin/env python3
"""Long-running linked PTY bridge used when socat is unavailable."""

from __future__ import annotations

import argparse
import os
import signal
import sys
import time
from pathlib import Path

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

from daemonize import daemonize  # noqa: E402
from pty_pair import open_linked_pty_pair  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host-link", required=True)
    parser.add_argument("--device-link", required=True)
    parser.add_argument("--daemon", action="store_true", help="Double-fork into background")
    parser.add_argument("--pid-file", default="", help="Write daemon PID here")
    parser.add_argument("--log-file", default="", help="Append stdout/stderr when daemonizing")
    args = parser.parse_args()

    if args.daemon:
        if not args.pid_file:
            print("--pid-file is required with --daemon", file=sys.stderr)
            return 2
        daemonize(
            pid_file=args.pid_file,
            stdout=args.log_file or None,
            stderr=args.log_file or None,
        )

    pair = open_linked_pty_pair()
    host_link = Path(args.host_link)
    device_link = Path(args.device_link)
    host_link.parent.mkdir(parents=True, exist_ok=True)

    for link, target in ((host_link, pair.host_port), (device_link, pair.device_port)):
        if link.exists() or link.is_symlink():
            link.unlink()
        os.symlink(target, link)

    print(f"host={pair.host_port}", flush=True)
    print(f"device={pair.device_port}", flush=True)
    print(f"host_link={host_link}", flush=True)
    print(f"device_link={device_link}", flush=True)

    stop = False

    def _stop(*_args: object) -> None:
        nonlocal stop
        stop = True

    signal.signal(signal.SIGINT, _stop)
    signal.signal(signal.SIGTERM, _stop)

    try:
        while not stop:
            time.sleep(0.2)
    finally:
        pair.close()
        for link in (host_link, device_link):
            try:
                link.unlink()
            except OSError:
                pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
