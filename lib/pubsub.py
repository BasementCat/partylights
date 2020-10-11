import queue
import fnmatch
import threading


class Subscription(queue.Queue):
    def __init__(self):
        super().__init__()

    def unsubscribe(self):
        unsubscribe(self)

    def get(self, timeout=1):
        try:
            return super().get(timeout=timeout)
        except queue.Empty:
            return None


_subscriptions = {}
_sub_lock = threading.Lock()


def subscribe(event):
    sub = Subscription()
    with _sub_lock:
        _subscriptions.setdefault(event, []).append(sub)
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
