from unittest import TestCase
import json

from app.common.lib import rpc


class MockClient:
    def __init__(self, *data):
        self.addr = ('test', 123)
        self.data = list(data)
        self.written = []

    def readline(self, decode=True):
        if self.data:
            out = self.data.pop(0)
            if decode:
                out = out.decode('utf-8')
            return out

    def write(self, value):
        self.written.append(str(value))


class TestRPC(TestCase):
    def test_rpc(self):
        self.maxDiff = None
        def goodmethod(method, **kwargs):
            return kwargs
        def badmethod(method, **kwargs):
            raise rpc.RPCError(25, message="x", data="y")

        server = rpc.RPCServer(None)
        server.register_method('GoodMethod', goodmethod)
        server.register_method('BadMethod', badmethod)

        client = MockClient(
            'àéíó'.encode('latin1'),
            b'lskdfjlksdj',
            b'{"id": 3, "method": "x"}',
            b'{"jsonrpc": "sldkfj", "id": 4, "method": "x"}',
            b'{"jsonrpc": "2.0", "id": 5}',
            b'{"jsonrpc": "2.0", "id": 6, "method": "x"}',
            b'{"jsonrpc": "2.0", "id": 7, "method": "goodmethod"}',
            b'{"jsonrpc": "2.0", "id": 8, "method": "goodmethod", "params": {"foo": "bar"}}',
            b'{"jsonrpc": "2.0", "id": 9, "method": "badmethod", "params": {"foo": "bar"}}',
        )
        server.process_client(client)
        exp_res = [
            {'jsonrpc': '2.0', 'error': {'code': -32700, 'message': 'Invalid JSON', 'data': 'Invalid UTF-8 String'}},
            {'jsonrpc': '2.0', 'error': {'code': -32700, 'message': 'Invalid JSON'}},
            {'jsonrpc': '2.0', 'id': 3, 'error': {'code': -32600, 'message': 'The request structure is invalid', 'data': 'Invalid or missing version (jsonrpc property)'}},
            {'jsonrpc': '2.0', 'id': 4, 'error': {'code': -32600, 'message': 'The request structure is invalid', 'data': 'Invalid or missing version (jsonrpc property)'}},
            {'jsonrpc': '2.0', 'id': 5, 'error': {'code': -32600, 'message': 'The request structure is invalid', 'data': 'Missing method'}},
            {'jsonrpc': '2.0', 'id': 6, 'error': {'code': -32601, 'message': 'The requested method does not exist'}},
            {'jsonrpc': '2.0', 'id': 7, 'result': {}},
            {'jsonrpc': '2.0', 'id': 8, 'result': {'foo': 'bar'}},
            {'jsonrpc': '2.0', 'id': 9, 'error': {'code': 25, 'message': 'x', 'data': 'y'}},
        ]
        for i, exp in enumerate(exp_res):
            self.assertEqual(exp, json.loads(client.written[i]), "Result " + str(i + 1))
        self.assertEqual(len(exp_res), len(client.written))
