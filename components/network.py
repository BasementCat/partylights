import logging
import json
import threading
import queue
import socket
import select
# import uuid
import time

from lib.task import Task
# from lib.light.models import Light, DMXLight
# from lib.light.dmx import DMXDevice


logger = logging.getLogger(__name__)

E_UNICODE = 1, "Your last command contained invalid UTF-8 data"
E_JSON = 2, "Your last command contained invalid JSON"
E_CMD = 3, "Invalid command"


class ClientExited(Exception):
    pass


class NetworkClient:
    def __init__(self, sock, host, port):
        self.sock = sock
        self.host = host
        self.port = port
        self.in_buffer = b''
        self.out_buffer = b''
        self.subscriptions = set()

    def read(self):
        res = self.sock.recv(8192)
        if res == b'':
            raise ClientExited()
        self.in_buffer += res
        partial = not self.in_buffer.endswith(b'\n')
        chunks = self.in_buffer.split(b'\n')
        if partial:
            self.in_buffer = chunks.pop()
        else:
            self.in_buffer = b''
        for chunk in filter(None, chunks):
            try:
                yield json.loads(chunk.decode('utf-8'))
            except UnicodeDecodeError:
                self.send_error(*E_UNICODE)
            except:
                self.send_error(*E_JSON)

    def send_error(self, code, msg, msgid=None, **data):
        self.send({'id': msgid, 'error': {'code': code, 'message': msg, 'data': data}})

    def send(self, data):
        self.out_buffer += json.dumps(data).encode('utf-8') + b'\n'

    def write(self):
        if self.out_buffer:
            self.out_buffer = self.out_buffer[self.sock.send(self.out_buffer):]


class NetworkThread(threading.Thread):
    def __init__(self, config, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.config = config
        self.stop_event = threading.Event()
        self.data_queue = queue.Queue()

        self.server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        host = self.config.get('Network', {}).get('Host', '0.0.0.0')
        port = self.config.get('Network', {}).get('Port', 37737)
        self.server.bind((
            host,
            port,
        ))
        self.server.listen(4)

        self.bcast = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.bcast.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.bcast.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        self.bcast_val = b'partylights-server:' + str(port).encode('utf-8') + b'\n'
        self.bcast_last = 0

        self.clients = {}

    def process_clients(self):
        ready, _, _ = select.select([self.server] + list(self.clients.keys()), [], [], 0)
        for sock in ready:
            if sock is self.server:
                newsock, addr = self.server.accept()
                logger.info("New connection from %s:%d", *addr)
                self.clients[newsock] = NetworkClient(newsock, *addr)
            else:
                try:
                    cl = self.clients[sock]
                    try:
                        for item in cl.read():
                            fn = getattr(self, 'cmd_' + str(item.get('command', None)))
                            if fn is None:
                                cl.send_error(*E_CMD, msgid=item.get('id'))
                            else:
                                res = fn(cl, _raw=item, **item.get('params', {}))
                                if res is not None:
                                    cl.send({'id': item.get('id'), 'result': res})
                            cl.write()
                    except ClientExited:
                        logger.info("Client disconnected: %s:%d", cl.host, cl.port)
                        del self.clients[sock]
                except KeyError:
                    sock.close()

        for cl in self.clients.values():
            cl.write()

    def run(self):
        while not self.stop_event.is_set():
            if time.time() - self.bcast_last >= 2:
                self.bcast_last = time.time()
                self.bcast.sendto(self.bcast_val, ('255.255.255.255', 37737))

            self.process_clients()
            try:
                data = self.data_queue.get(timeout=0.1)
                for cl in self.clients.values():
                    if 'audio' in cl.subscriptions:
                        cl.send({'command': 'audio', 'params': {'data': list(data.get('audio'))}})
            except queue.Empty:
                pass

        for cl in self.clients.values():
            cl.sock.close()

    def cmd_subscribe(self, cl, events=None, **kwargs):
        # TODO: validate events
        if events is not None:
            to_add = set()
            to_del = set()
            to_set = set()
            for e in events or []:
                if e.startswith('+'):
                    to_add.add(e[1:])
                elif e.startswith('-'):
                    to_del.add(e[1:])
                else:
                    to_set.add(e)
            cl.subscriptions = ((to_set or cl.subscriptions) + to_add) - to_del
        return {'events': list(cl.subscriptions)}


class NetworkTask(Task):
    def setup(self):
        self.thread = NetworkThread(self.config)
        self.thread.start()

    def run(self, data):
        self.thread.data_queue.put(data)

    def teardown(self):
        self.thread.stop_event.set()
        self.thread.join()
