import threading
import logging

from flask_threaded_sockets import ThreadedWebsocketServer

from lib.task import Task
from lib.pubsub import subscribe

from .app import create_app


logger = logging.getLogger(__name__)


class WebGUITask(Task):
    def setup(self):
        self.stop_ws_event = threading.Event()
        self.open_sockets = []
        self.app = create_app(self.stop_ws_event, self.open_sockets)
        self.server = ThreadedWebsocketServer('0.0.0.0', 5000, self.app)

    def _run(self):
        self.server.serve_forever()

    def teardown(self):
        self.stop_ws_event.set()
        for e in self.open_sockets:
            if not e.wait(timeout=3):
                logger.error("A socket failed to close in time")
        self.server.shutdown()
