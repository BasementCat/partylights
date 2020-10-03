import socket
import select
import logging
import ipaddress
import os


logger = logging.getLogger(__name__)


class Disconnected(Exception):
    pass


class ServerClient:
    def __init__(self, sock):
        self.sock = sock
        self.addr = sock.getpeername()
        self.raw_buf = b''
        self.buf = []

    def write(self, data):
        if not isinstance(data, bytes):
            data = str(data).encode('utf-8')
        self.sock.sendall(data)

    def _raw_read(self):
        data = self.sock.recv(8192)
        if data == b'':
            raise Disconnected()
        self.raw_buf += data
        partial = not self.raw_buf.endswith(b'\n')
        chunks = list(filter(None, data.split(b'\n')))
        if partial:
            self.raw_buf = chunks.pop()
        for chunk in chunks:
            try:
                self.buf.append(chunk.decode('utf-8'))
            except UnicodeDecodeError:
                logger.error("Failed to decode a message: %s", repr(chunk), exc_info=True)

    def read(self):
        if self.buf:
            return self.buf.pop(0)
        return None


class Server:
    def __init__(self, addr, port=None, client_class=ServerClient):
        """\
        addr may be an ipv4/ipv6 address string or a string of the format 'unix:///path/to/socketfile' for a unix socket
        If it's an ipv4/ipv6 address, port is required
        """
        self.unix_path = None
        if addr.startswith('unix://'):
            self.server_sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            self.unix_path = addr[7:]
            self.server_sock.bind(self.unix_path)
        else:
            if not port:
                raise ValueError("Port must not be none with IP addresses")
            addr = ipaddress.ip_address(addr)
            self.server_sock = socket.socket(socket.AF_INET6 if addr.version == 6 else socket.AF_INET, socket.SOCK_STREAM)
            self.server_sock.bind((str(addr), port))

        # TODO: nonblock
        self.server_sock.listen()

        self.client_class = client_class
        self.clients = {}

    def process(self, timeout=1):
        new = []
        ready = []
        disc = []

        r, _, _ = select.select([self.server_sock] + [c.sock for c in self.clients.values()], [], [], timeout)
        for sock in r:
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
                        cl._raw_read()
                    except Disconnected:
                        disc.append(cl)
                        sock.close()
                        del self.clients[sock]
                    else:
                        ready.append(cl)

        return new, ready, disc

    def write_all(self, data):
        for cl in self.clients.values():
            cl.write(data)

    def close(self, data=None):
        if data:
            self.write_all(data)
        for cl in self.clients.values():
            cl.sock.close()
        self.server_sock.close()
        if self.unix_path and os.path.exists(self.unix_path):
            os.unlink(self.unix_path)
