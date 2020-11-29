import threading
import logging
from http.server import ThreadingHTTPServer

from lib.task import Task

from .app import AppClass


logger = logging.getLogger(__name__)


class WebGUITask(Task):
    def setup(self):
        self.data_queues = []
        task = self
        class AugmentedAppClass(AppClass):
            def __init__(self, *args, **kwargs):
                self.task = task
                super().__init__(*args, **kwargs)
        self.app_class = AugmentedAppClass

        self.thread = threading.Thread(target=self._run_server)
        self.thread.start()

    def run(self, data):
        for q in self.data_queues:
            q.put(data)

    def _run_server(self):
        self.httpd = ThreadingHTTPServer(('', 8000), self.app_class)
        self.httpd.serve_forever()

    def teardown(self):
        self.httpd.shutdown()
