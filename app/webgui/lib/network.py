import json
import logging
import time
import threading
import queue

from app.common.lib.network import SelectableCollection, Client as NetClient
from app.common.lib.rpc import RPCClient

from .threads import Thread


logger = logging.getLogger(__name__)


class NetworkThread(Thread):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.ws_clients = {
            'audio_recv': [],
            'lights_recv': [],
            'lights_send': [],
        }

    def setup(self):
        self.conns = SelectableCollection()
        self.lock = threading.Lock()
        self.new_client = threading.Event()
        self.audio_client = None
        self.light_client = None

    def connect(self, datatype, direction):
        key = f'{datatype}_{direction}'
        if key not in self.ws_clients:
            raise RuntimeError("Invalid datatype or direction")
        q = queue.Queue()
        self.ws_clients[key].append(q)
        with self.lock:
            if datatype == 'audio':
                if not self.audio_client:
                    # TODO: configurable
                    netclient = NetClient('127.0.0.1', port=37731)
                    netclient.connect()
                    self.audio_client = RPCClient(netclient, on_notif=self._broadcast_audio)
                    self.conns.append(self.audio_client)
            elif datatype == 'lights':
                if not self.light_client:
                    # TODO: configurable
                    netclient = NetClient('127.0.0.1', port=37730)
                    netclient.connect()
                    self.light_client = RPCClient(netclient, on_notif=self._broadcast_lights)
                    self.light_client.call('monitor', state=True)
                    # TODO: separate handlers
                    # TODO: don't call state until lights returns
                    self.light_client.call('lights', callback=self._broadcast_lights)
                    self.light_client.call('state', callback=self._broadcast_lights)
                    self.conns.append(self.light_client)
        self.new_client.set()
        return q

    def disconnect(self, client):
        with self.lock:
            for coll in self.ws_clients.values():
                if client in coll:
                    coll.remove(client)
                    break

            if not self.ws_clients['audio_recv']:
                self.conns.remove(self.audio_client)
                self.audio_client.close()
                self.audio_client = None
            if not (self.ws_clients['lights_recv'] or self.ws_clients['lights_send']):
                self.conns.remove(self.light_client)
                self.light_client.close()
                self.light_client = None

    def _broadcast_audio(self, client, data):
        if data.get('error'):
            logger.error("Error in audio connection: %s", data)
            return
        for q in self.ws_clients['audio_recv']:
            q.put(json.dumps(data))

    def _broadcast_lights(self, client, data):
        if data.get('error'):
            logger.error("Error in lights connection: %s", data)
            return
        for q in self.ws_clients['lights_recv']:
            q.put(json.dumps(data))

    # TODO: lights send

    def loop(self):
        have_conns = False
        with self.lock:
            if self.conns:
                have_conns = True
                for _ in self.conns.do_select():
                    pass
        if not have_conns:
            if self.new_client.wait(timeout=1):
                self.new_client.clear()

    # def send_to_server(self, command, *args, **kwargs):
    #     if not self.sock:
    #         return
    #     data = json.dumps({'command': command, 'args': args, 'kwargs': kwargs}).encode('utf-8') + b'\n'
    #     with self.lock:
    #         sent = 0
    #         while sent < len(data):
    #             sent += self.sock.send(data[sent:])

    # def send_to_client(self, command, *args, **kwargs):
    #     remove = []
    #     for client in self.client_queues.values():
    #         if client.age > 3:
    #             remove.append(client.id)
    #         else:
    #             client.put({'command': command, 'args': args, 'kwargs': kwargs})
    #     for id in remove:
    #         del self.client_queues[id]

    # def get_for_client(self, client_id, timeout=1):
    #     out = []
    #     if client_id in self.client_queues:
    #         client = self.client_queues[client_id]
    #     else:
    #         client = self.client_queues[client_id] = Client(client_id)
    #         client.put({'command': 'LIGHTS', 'args': self.lights, 'kwargs': {}})

    #     client.ping()
    #     try:
    #         out.append(client.get(timeout=timeout))
    #         while True:
    #             out.append(client.get(block=False))
    #     except queue.Empty:
    #         pass

    #     return out

    # def get_lights(self):
    #     return self.lights

    # def configure(self, app_config):
    #     self.host = app_config.get('LIGHT_SERVER_HOST') or self.host
    #     self.port = app_config.get('LIGHT_SERVER_PORT') or self.port
    #     self.connect()
