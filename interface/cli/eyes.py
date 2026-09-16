from __future__ import annotations

import sys
import threading
import time


FRAMES = [
    "     *    *",
    "     *     *",
    "    *     *",
    "   *     *",
    "    *     *",
    "     *     *",
    "      -     -",
    "        *     *",
    "         *     *",
]

FPS = 24
POSE_TIME = 0.4


class Eyes:
    def __init__(self):
        self.running = False
        self.thread = None

    def start(self):
        if self.running:
            return

        self.running = True
        self.thread = threading.Thread(
            target=self._run,
            daemon=True,
        )
        self.thread.start()

    def stop(self):
        self.running = False

        if self.thread:
            self.thread.join(timeout=1)

        sys.stdout.write("\r\033[2K")
        sys.stdout.flush()

    def _run(self):
        frame_time = 1 / FPS

        while self.running:
            for frame in FRAMES:
                if not self.running:
                    break

                end = time.perf_counter() + POSE_TIME

                while self.running and time.perf_counter() < end:
                    sys.stdout.write("\r\033[2K" + frame)
                    sys.stdout.flush()
                    time.sleep(frame_time)
