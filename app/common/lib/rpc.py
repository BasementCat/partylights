import json
import logging


logger = logging.getLogger(__name__)


class RPCError(Exception):
    PARSE_ERROR = (-32700, "Invalid JSON")
    INVALID_REQUEST = (-32600, "The request structure is invalid")
    METHOD_NOT_FOUND = (-32601, "The requested method does not exist")
    INVALID_PARAMS = (-32602, "Invalid parameters for the requested method")
    INTERNAL_ERROR = (-32603, "Internal error")

    def __init__(self, code, message=None, data=None, id=None):
        self.id = id
        self.code = code
        self.message = message or str(code)
        self.data = data

    @property
    def as_dict(self):
        out = {'error': {'code': self.code, 'message': self.message}}
        if self.id:
            out['id'] = self.id
        if self.data:
            out['error']['data'] = self.data
        return out


class RPCServer:
    VERSION = '2.0'

    def __init__(self, netserver):
        self.netserver = netserver
        self.methods = {}

    def register_method(self, method, callback):
        self.methods[method.lower()] = callback

    def process_client(self, client):
        while True:
            data = client.readline(decode=False)
            if not data:
                break
            try:
                try:
                    try:
                        data = json.loads(data.decode('utf-8'))
                    except UnicodeDecodeError:
                        raise RPCError(*RPCError.PARSE_ERROR, data="Invalid UTF-8 String")
                    except:
                        raise RPCError(*RPCError.PARSE_ERROR)
                    if data.get('jsonrpc') != self.VERSION:
                        raise RPCError(*RPCError.INVALID_REQUEST, data="Invalid or missing version (jsonrpc property)")
                    if not data.get('method'):
                        raise RPCError(*RPCError.INVALID_REQUEST, data="Missing method")
                    method_name = data['method'].lower()
                    method = self.methods.get(method_name)
                    if not method:
                        raise RPCError(*RPCError.METHOD_NOT_FOUND)

                    res = method(method_name, **data.get('params', {}))
                    out = {'result': res}
                    if data.get('id'):
                        out['id'] = data['id']
                    self.send(client, out)

                except RPCError as e:
                    if not e.id:
                        if data and hasattr(data, 'get'):
                            e.id = data.get('id')
                    raise
                except:
                    logger.error("Failed to process a request, %s", repr(data), exc_info=True)
                    raise RPCError(data.get('id'), *RPCError.INTERNAL_ERROR)
            except RPCError as e:
                self.send(client, e)

    def send(self, client, message):
        if hasattr(message, 'as_dict'):
            message = message.as_dict
        if not isinstance(message, dict) or ('result' not in message and 'error' not in message and 'method' not in message):
            message = {'result': message}
        message['jsonrpc'] = self.VERSION
        message = json.dumps(message) + '\n'
        if client is None:
            self.netserver.write_all(message)
        else:
            client.write(message)
