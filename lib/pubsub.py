import logging
import queue
import fnmatch
import threading


logger = logging.getLogger(__name__)
_subscriptions = {}
_sub_lock = threading.Lock()


class Event:
    def __init__(self, event, data=None, returning=False, sender=None):
        self.event = event
        self.data = data
        self.sender = sender
        self._ret_q = queue.Queue() if returning else None
        self._ret_called = False

    def returning(self, v=None):
        if self._ret_called:
            return
        self._ret_called = True
        if self._ret_q is not None:
            self._ret_q.put(v)

    def get_returning(self):
        if self._ret_q is not None:
            try:
                return self._ret_q.get(timeout=3)
            except queue.Empty:
                logger.error("Requested return for %s did not return data", self.event)

    def unpack_name(self, ignore=1):
        out = self.event.split('.')
        for _ in range(ignore):
            if out:
                out.pop(0)

        def _unpack_rest(num):
            while len(out) < num:
                out.append(None)
            if num == 1:
                return out[0]
            return out

        cmd = out.pop(0) if out else None
        return cmd, _unpack_rest

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.returning()


class Subscription(queue.Queue):
    def __init__(self, default_timeout=None, max_iter_messages=None):
        super().__init__()
        self.default_timeout = 1 if default_timeout is None else default_timeout
        self.max_iter_messages = 10 if max_iter_messages is None else max_iter_messages

    def unsubscribe(self):
        unsubscribe(self)

    def get(self, timeout=None):
        if timeout is None:
            timeout = self.default_timeout
        try:
            return super().get(timeout=timeout)
        except queue.Empty:
            return None

    def __iter__(self):
        # If enough data is being pushed into the queue it's possible for this function to never return
        # Cap the # of messages returned in a single iteration
        # Also force a small timeout to avoid a situation where a slow pace of messages could cause an iteration to take 10s
        for _ in range(self.max_iter_messages):
            ev = self.get(timeout=0.09)
            if ev is None:
                break
            yield ev


def subscribe(*events, default_timeout=None, max_iter_messages=None):
    sub = Subscription(default_timeout=default_timeout, max_iter_messages=max_iter_messages)
    with _sub_lock:
        for ev in events:
            _subscriptions.setdefault(ev, []).append(sub)
    return sub


def unsubscribe(sub):
    with _sub_lock:
        for v in _subscriptions.values():
            if sub in v:
                v.remove(sub)


def publish(event, data=None, returning=False, sender=None, **kwargs):
    data = dict(data or {}, **kwargs)
    ev = Event(event, data=data, returning=returning, sender=sender)
    # TODO: somehow allow concurrent publish calls while preventing modification
    with _sub_lock:
        for k, v in _subscriptions.items():
            if v:
                if fnmatch.fnmatch(event, k):
                    for sub in v:
                        sub.put(ev)

    return ev.get_returning()
