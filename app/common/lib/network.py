import socket
import select
import logging
import ipaddress
import os
import uuid


logger = logging.getLogger(__name__)


class Disconnected(Exception):
    pass


class ConnectableMixin:
    def _create_socket(self, addr, port, is_server):
        self.unix_path = None
        if addr.startswith('unix://'):
            sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            self.unix_path = addr[7:]
            if is_server:
                sock.setblocking(0)
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
                sock.bind(self.unix_path)
                sock.listen()
            else:
                sock.connect(self.unix_path)
        else:
            if not port:
                raise ValueError("Port must not be none with IP addresses")
            addr = ipaddress.ip_address(addr)
            sock = socket.socket(socket.AF_INET6 if addr.version == 6 else socket.AF_INET, socket.SOCK_STREAM)
            if is_server:
                sock.setblocking(0)
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
                sock.bind((str(addr), port))
                sock.listen()
            else:
                sock.connect((str(addr), port))

        return sock

    def _cleanup(self):
        if self.unix_path and os.path.exists(self.unix_path):
            os.unlink(self.unix_path)


class LineBufferedMixin:
    def _get_socket(self):
        raise NotImplementedError()

    def _read_raw(self):
        if not hasattr(self, '_raw_buf'):
            self._raw_buf = b''
        if not hasattr(self, '_line_buf'):
            self._line_buf = []
        data = self._get_socket().recv(8192)
        if data == b'':
            raise Disconnected()
        self._raw_buf += data
        partial = not self._raw_buf.endswith(b'\n')
        chunks = list(filter(None, self._raw_buf.split(b'\n')))
        if partial:
            self._raw_buf = chunks.pop()
        for chunk in chunks:
            try:
                self._line_buf.append(chunk.decode('utf-8'))
            except UnicodeDecodeError:
                logger.error("Failed to decode a message: %s", repr(chunk), exc_info=True)

    def readline(self):
        if getattr(self, '_line_buf', None):
            return self._line_buf.pop(0)


class SelectableMixin:
    @property
    def selectable_id(self):
        if not hasattr(self, '_selectable_id'):
            self._selectable_id = str(uuid.uuid4())
        return self._selectable_id

    def _get_sockets(self):
        raise NotImplementedError()

    def _notify_sockets(self, ready):
        raise NotImplementedError()


class SelectableCollection(list):
    def do_select(timeout=1):
        sock_item_map = {}
        for item in self:
            for sock in item._get_sockets():
                sock_item_map[sock] = item
        r, _, _ = select.select(list(sock_item_map.keys(), [], [], timeout))
        groups = {}
        for sock in r:
            item = sock_item_map[sock]
            groups.setdefault(item.selectable_id, (item, []))[1].append(sock)
        for item, socks in groups.values():
            yield item, item._notify_sockets(socks)


class ServerClient(LineBufferedMixin):
    def __init__(self, sock):
        self.sock = sock
        self.addr = sock.getpeername()

    def _get_socket(self):
        return self.sock

    def write(self, data):
        if not isinstance(data, bytes):
            data = str(data).encode('utf-8')
        self.sock.sendall(data)


class Server(ConnectableMixin, SelectableMixin):
    def __init__(self, addr, port=None, client_class=ServerClient):
        """\
        addr may be an ipv4/ipv6 address string or a string of the format 'unix:///path/to/socketfile' for a unix socket
        If it's an ipv4/ipv6 address, port is required
        """
        self.server_sock = self._create_socket(addr, port, True)

        self.client_class = client_class
        self.clients = {}

    def _get_sockets(self):
        return [self.server_sock] + [c.sock for c in self.clients.values()]

    def _notify_sockets(self, s_ready):
        new = []
        ready = []
        disc = []

        for sock in s_ready:
            if sock is self.server_sock:
                c_sock, c_addr = sock.accept()
                cl =self.client_class(c_sock)
                self.clients[c_sock] = cl
                new.append(cl)
            else:
                try:
                    cl = self.clients[sock]
                except KeyError:
                    logger.error("Got data from a client we are unaware of: %s (%s)", sock, sock.getpeername())
                    sock.close()
                else:
                    try:
                        cl._read_raw()
                    except Disconnected:
                        disc.append(cl)
                        sock.close()
                        del self.clients[sock]
                    else:
                        ready.append(cl)

        return new, ready, disc

    def process(self, timeout=1):
        # In cases where the SelectableCollection is not needed, just do the work ourselves
        r, _, _ = select.select(self._get_sockets(), [], [], timeout)
        return self._notify_sockets(r)

    def write_all(self, data, filter_fn=None):
        for cl in self.clients.values():
            if not filter_fn or filter_fn(cl):
                cl.write(data)

    def close(self, data=None):
        if data:
            self.write_all(data)
        for cl in self.clients.values():
            cl.sock.close()
        self.server_sock.close()
        self._cleanup()
