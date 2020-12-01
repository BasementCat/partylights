import logging


logger = logging.getLogger(__name__)


class Task:
    def __init__(self, tasks, config):
        self.tasks = tasks
        self.config = config

    def setup(self):
        pass

    def run(self, data):
        pass

    def teardown(self):
        pass
