from flask_threaded_sockets import ThreadedWebsocketServer

from lib.task import Task
from lib.pubsub import subscribe

from .app import create_app


class WebGUITask(Task):
    def setup(self):
        self.app = create_app()
        self.server = ThreadedWebsocketServer('0.0.0.0', 5000, self.app)

    def _run(self):
        self.server.serve_forever()

    def teardown(self):
        self.server.shutdown()
