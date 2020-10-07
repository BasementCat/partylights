from unittest import TestCase
import json

from app.common.lib import rpc


class MockClient:
    def __init__(self, *data, write_callback=None):
        self.addr = ('test', 123)
        self.data = list(data)
        self.write_callback = write_callback
        self.written = []

    def readline(self, decode=True):
        if self.data:
            out = self.data.pop(0)
            if decode:
                out = out.decode('utf-8')
            return out

    def write(self, value):
        self.written.append(str(value))
        if self.write_callback:
            res = self.write_callback(value)
            if res is not None:
                self.data.append(res)


class TestRPC(TestCase):
    def test_rpc_server(self):
        self.maxDiff = None
        def goodmethod(client, method, **kwargs):
            return kwargs
        def badmethod(client, method, **kwargs):
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

    def test_rpc_client(self):
        data = []
        netclient = MockClient(b'{"jsonrpc": "2.0", "result": "welcome"}')
        def _notif(rc, d):
            data.append(d)
        client = rpc.RPCClient(netclient, on_notif=_notif)
        client.process()
        self.assertEqual([{'jsonrpc': '2.0', 'result': 'welcome'}], data)

        data = []
        def _wcb(s):
            d = json.loads(s)
            return json.dumps({'jsonrpc': '2.0', 'id': d['id'], 'result': {'method': d['method'], 'params': d['params']}}).encode('utf-8')
        netclient = MockClient(write_callback=_wcb)
        def _cb(rc, d):
            data.append(d)
        client = rpc.RPCClient(netclient)
        client.process()
        self.assertEqual([], data)
        client.call('testmethod', foo='bar', baz=17, callback=_cb)
        client.process()
        self.assertEqual(1, len(data))
        self.assertTrue(bool(data[0]['id']))
        self.assertEqual({'method': 'testmethod', 'params': {'foo': 'bar', 'baz': 17}}, data[0]['result'])

    def test_rpc_client_promise(self):
        data = []
        testdata = ['successdata', 'errordata']
        def _wcb(s):
            d = json.loads(s)
            td = testdata.pop(0)
            out = {'jsonrpc': '2.0', 'id': d['id']}
            k = 'error' if td.startswith('errordata') else 'result'
            out[k] = td
            return json.dumps(out).encode('utf-8')
        netclient = MockClient(write_callback=_wcb)
        def _scb(rc, d):
            data.append(('success', d))
        def _ecb(rc, d):
            data.append(('error', d))
        def _dcb(rc, d):
            data.append(('done', set(d.keys())))
        client = rpc.RPCClient(netclient)
        client.process()
        self.assertEqual([], data)
        client.call('testmethod').success(_scb).error(_ecb).done(_dcb)
        client.process()
        client.call('testmethod').success(_scb).error(_ecb).done(_dcb)
        client.process()
        self.assertEqual(
            [
                ('success', 'successdata'),
                ('done', set(('jsonrpc', 'id', 'result'))),
                ('error', 'errordata'),
                ('done', set(('jsonrpc', 'id', 'error'))),
            ],
            data
        )
