import logging
import signal
import threading
import json

# from app.common.lib.command import Command
# from app.common.lib.network import Server
# from app.common.lib.rpc import RPCServer, RPCError
from lib.task import Task
from lib.pubsub import publish
from lib.fps import FPSCounter
from lib.audio.input import Input
from lib.audio import processor


logger = logging.getLogger(__name__)


class AudioCaptureTask(Task):
    def setup(self):
        self.fps = FPSCounter('Audio Capture')
        self.processors = [
            processor.SmoothingProcessor(self.config),
            processor.BeatProcessor(self.config),
            processor.PitchProcessor(self.config),
            processor.IdleProcessor(self.config),
        ]

    def _run(self):
        with Input.get_input(self.config) as capture:
            while not self.stop_event.is_set():
                with self.fps:
                    res = capture.read()
                    data = {}
                    for p in self.processors:
                        p.process(res, data)

                    data['audio'] = list(data['audio']) if data['audio'] is not None else None
                    publish('audio', data)
