from unittest import TestCase
import socket

from app.common.lib import network


class TestServer(TestCase):
    def test_server__unix(self):
        server = None
        try:
            server = network.Server('unix:///tmp/testcommonlibnetwork.sock')
            self.assertEqual(([], [], []), server.process(0.01))

            s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            s.connect('/tmp/testcommonlibnetwork.sock')

            n, r, d = server.process(0.01)
            self.assertEqual(([], []), (r, d))
            self.assertIsInstance(n[0], network.ServerClient)
            c = n[0]
            self.assertEqual(([], [], []), server.process(0.01))

            s.sendall(b'foobar\n')
            self.assertEqual(([], [c], []), server.process(0.01))
            self.assertEqual('foobar', c.readline())
            c.write('bazquux\n')
            self.assertEqual(b'bazquux\n', s.recv(16))

            s.close()
            self.assertEqual(([], [], [c]), server.process(0.01))
        finally:
            if server:
                server.close()

    def test_server__inet(self):
        server = None
        try:
            server = network.Server('127.0.0.1', 12345)
            self.assertEqual(([], [], []), server.process(0.01))

            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.connect(('127.0.0.1', 12345))

            n, r, d = server.process(0.01)
            self.assertEqual(([], []), (r, d))
            self.assertIsInstance(n[0], network.ServerClient)
            c = n[0]
            self.assertEqual(([], [], []), server.process(0.01))

            s.sendall(b'foobar\n')
            self.assertEqual(([], [c], []), server.process(0.01))
            self.assertEqual('foobar', c.readline())
            c.write('bazquux\n')
            self.assertEqual(b'bazquux\n', s.recv(16))

            s.close()
            self.assertEqual(([], [], [c]), server.process(0.01))
        finally:
            if server:
                server.close()

    def test_server__inet6(self):
        server = None
        try:
            server = network.Server('::1', 12345)
            self.assertEqual(([], [], []), server.process(0.01))

            s = socket.socket(socket.AF_INET6, socket.SOCK_STREAM)
            s.connect(('::1', 12345))

            n, r, d = server.process(0.01)
            self.assertEqual(([], []), (r, d))
            self.assertIsInstance(n[0], network.ServerClient)
            c = n[0]
            self.assertEqual(([], [], []), server.process(0.01))

            s.sendall(b'foobar\n')
            self.assertEqual(([], [c], []), server.process(0.01))
            self.assertEqual('foobar', c.readline())
            c.write('bazquux\n')
            self.assertEqual(b'bazquux\n', s.recv(16))

            s.close()
            self.assertEqual(([], [], [c]), server.process(0.01))
        finally:
            if server:
                server.close()

    def test_server__write_all_close(self):
        server = None
        try:
            server = network.Server('127.0.0.1', 12345)

            s1 = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s1.connect(('127.0.0.1', 12345))
            s2 = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s2.connect(('127.0.0.1', 12345))

            n, _, _ = server.process(0.01)
            self.assertEqual(1, len(n))
            n, _, _ = server.process(0.01)
            self.assertEqual(1, len(n))
            n, _, _ = server.process(0.01)
            self.assertEqual(0, len(n))

            server.write_all(b'test\n')
            self.assertEqual(b'test\n', s1.recv(16))
            self.assertEqual(b'test\n', s2.recv(16))

            server.close()
            self.assertEqual(b'', s1.recv(16))
            s1.close()
            self.assertEqual(b'', s2.recv(16))
            s2.close()
        finally:
            if server:
                server.close()
