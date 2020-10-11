import queue
import fnmatch
import threading


class Subscription(queue.Queue):
    def __init__(self, default_timeout=None):
        super().__init__()
        self.default_timeout = 1 if default_timeout is None else default_timeout

    def unsubscribe(self):
        unsubscribe(self)

    def get(self, timeout=None):
        if timeout is None:
            timeout = self.default_timeout
        try:
            return super().get(timeout=timeout)
        except queue.Empty:
            return None, None

    def __iter__(self):
        while True:
            ev, data = self.get()
            if ev is None:
                break
            yield ev, data


_subscriptions = {}
_sub_lock = threading.Lock()


def subscribe(*events, default_timeout=None):
    sub = Subscription(default_timeout=default_timeout)
    with _sub_lock:
        for ev in events:
            _subscriptions.setdefault(ev, []).append(sub)
    return sub


def unsubscribe(sub):
    with _sub_lock:
        for v in _subscriptions.values():
            if sub in v:
                v.remove(sub)


def publish(event, data=None, **kwargs):
    ev = dict(data or {}, **kwargs)
    # TODO: somehow allow concurrent publish calls while preventing modification
    with _sub_lock:
        for k, v in _subscriptions.items():
            if v:
                if fnmatch.fnmatch(event, k):
                    for sub in v:
                        sub.put((event, ev))
