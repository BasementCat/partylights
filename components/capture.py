import logging
import signal
import threading
import json

from lib.task import Task
from lib.audio.input import Input
from lib.audio import processor


logger = logging.getLogger(__name__)


class AudioCaptureTask(Task):
    def setup(self):
        self.processors = [
            processor.SmoothingProcessor(self.config),
            processor.BeatProcessor(self.config),
            processor.PitchProcessor(self.config),
            processor.IdleProcessor(self.config),
        ]
        self.capture = Input.get_input(self.config)
        self.capture.start()

    def run(self, data):
        res = self.capture.read()
        for p in self.processors:
            p.process(res, data)
        data['audio'] = list(data['audio']) if data['audio'] is not None else None

    def teardown(self):
        self.capture.stop()
