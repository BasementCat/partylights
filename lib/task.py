import threading
import logging
import sys


logger = logging.getLogger(__name__)

threads = []


def _call_ni(task, method, message):
    try:
        getattr(task, method)()
        logger.info(message, task.__class__.__name__)
    except NotImplementedError:
        pass
    except:
        logger.error("Calling %s.%s() failed", task.__class__.__name__, method, exc_info=True)
        # TODO: mark not running
        # TODO: if not in teardown, mark as failed (if in teardown, either we stopped so it doesn't matter or we are handling a failure already)


class Task(threading.Thread):
    def __init__(self, config, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.config = config
        self.manager = None  # Set by the manager
        self._orig_args = (self.__class__, args, kwargs)
        self.stop_event = threading.Event()
        self.failed = False
        self.running = True

        if not (hasattr(self, '_loop') or hasattr(self, '_run')):
            raise NotImplementedError("Tasks must implement _loop or _run")

    def setup(self):
        raise NotImplementedError()

    def setup_inthread(self):
        raise NotImplementedError()

    # def _loop(self):
    #     raise NotImplementedError()

    # def _run(self):
    #     raise NotImplementedError()

    def run(self):
        _call_ni(self, 'setup_inthread', "Set up %s in thread")
        try:
            if hasattr(self, '_loop'):
                while not self.stop_event.is_set():
                    self._loop()
            else:
                self._run()
        except Exception as e:
            self.failed = True
            logger.error("Task %s has failed: %s: %s", self.__class__.__name__, e.__class__.__name__, str(e), exc_info=True)
        finally:
            _call_ni(self, 'teardown_inthread', "Tear down %s in thread")
            self.running = False

    def teardown(self):
        raise NotImplementedError()

    def teardown_inthread(self):
        raise NotImplementedError()


class TaskManager:
    def __init__(self):
        self.tasks = []

    def add_task(self, task):
        task.manager = self
        self.tasks.append(task)
        self.start_task(task)

    def start_task(self, task):
        _call_ni(task, 'setup', "Set up %s")
        logger.info("Start %s", task.__class__.__name__)
        task.start()

    def stop_task(self, task, join=True):
        _call_ni(task, 'teardown', "Stop %s")
        task.stop_event.set()
        if join:
            logger.info("Join %s", task.__class__.__name__)

    def check_tasks(self):
        new_tasks = []
        dead_tasks = []
        for t in self.tasks:
            if not t.running:
                if t.failed:
                    logger.info("Task %s has failed, restarting", t.__class__.__name__)
                    dead_tasks.append(t)
                    cls, a, ka = t._orig_args
                    new_tasks.append(cls(t.config, *a, **ka))
                else:
                    logger.info("Task %s has stopped", t.__class__.__name__)
                    dead_tasks.append(t)
        for t in dead_tasks:
            self.tasks.remove(t)
        for t in new_tasks:
            self.add_task(t)

    def stop_all(self):
        for t in self.tasks:
            self.stop_task(t, join=False)
        for t in self.tasks:
            logger.info("Join %s", t.__class__.__name__)
        self.tasks = []
