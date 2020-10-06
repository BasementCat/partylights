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


    def test_server_client_selectable(self):
        server = c1 = c2 = None
        try:
            server = network.Server('127.0.0.1', 12345)
            c1 = network.Client('127.0.0.1', 12345)
            c2 = network.Client('127.0.0.1', 12345)
            coll = network.SelectableCollection([server, c1, c2])
            self.assertEqual([], list(coll.do_select(0.01)))
            c1.connect()
            c2.connect()
            res = list(coll.do_select(0.01))
            self.assertEqual(server, res[0][0])
            self.assertEqual(1, len(res[0][1][0]))
            self.assertEqual(0, len(res[0][1][1]))
            self.assertEqual(0, len(res[0][1][2]))
            res = list(coll.do_select(0.01))
            self.assertEqual(server, res[0][0])
            self.assertEqual(1, len(res[0][1][0]))
            self.assertEqual(0, len(res[0][1][1]))
            self.assertEqual(0, len(res[0][1][2]))
            self.assertEqual([], list(coll.do_select(0.01)))
            server.write_all('foobar\n')
            c1.write('foobar1\n')
            c2.write('foobar2\n')
            res = list(coll.do_select(0.01))
            self.assertEqual(3, len(res))
            processed = set()
            for item, data in res:
                if item is server:
                    processed.add('server')
                    self.assertEqual(0, len(data[0]))
                    self.assertEqual(2, len(data[1]))
                    self.assertEqual(0, len(data[2]))
                    for c in data[1]:
                        processed.add(c.readline())
                        self.assertIsNone(c.readline())
                elif item is c1:
                    self.assertIsNone(data)
                    self.assertEqual('foobar', item.readline())
                    self.assertIsNone(item.readline())
                    processed.add('c1')
                elif item is c2:
                    self.assertIsNone(data)
                    self.assertEqual('foobar', item.readline())
                    self.assertIsNone(item.readline())
                    processed.add('c2')
            self.assertEqual(set(['server', 'c1', 'c2', 'foobar1', 'foobar2']), processed)
            self.assertEqual([], list(coll.do_select(0.01)))
            c1.close()
            c1 = None
            c2.close()
            c2 = None
            res = list(coll.do_select(0.01))
            self.assertEqual(server, res[0][0])
            self.assertEqual(0, len(res[0][1][0]))
            self.assertEqual(0, len(res[0][1][1]))
            self.assertEqual(2, len(res[0][1][2]))
            self.assertEqual([], list(coll.do_select(0.01)))
        finally:
            if server:
                server.close()
            if c1:
                c1.close()
            if c2: c2.close()
