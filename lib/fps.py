import logging
import time


logger = logging.getLogger(__name__)


class FPSCounter:
    def __init__(self, name, log_interval=5, log_level='info'):
        self.name = name
        self.log_interval = log_interval
        self.log_level = log_level
        self.frames = 0
        self.last_log = time.perf_counter()

    def update(self, count=1):
        self.frames += count
        self.log()

    def log(self):
        now = time.perf_counter()
        s = now - self.last_log
        if s >= self.log_interval:
            getattr(logger, self.log_level)("%s FPS: %d", self.name, self.frames / s)
            self.last_log = now
            self.frames = 0

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.update()
