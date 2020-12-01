from http.server import BaseHTTPRequestHandler
import time
import queue
import json
import os
import mimetypes


class AppClass(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path.startswith('/static'):
            self.static()
        else:
            self.dispatch('GET')

    def static(self):
        fname = os.path.join(os.path.dirname(__file__), self.path.strip('/'))
        if not os.path.exists(fname):
            self.send_error(404)
            return
        with open(fname, 'rb') as fp:
            out = fp.read()
        content_type, _ = mimetypes.guess_type(fname)
        self.send_response(200)
        if content_type:
            self.send_header('Content-type', content_type)
        self.send_header('Content-length', str(len(out)))
        self.end_headers()
        self.wfile.write(out)
        self.wfile.flush()


    def dispatch(self, method):
        fn = getattr(self, method + '_' + self.path.strip('/').replace('/', '_'), None)
        if fn is None:
            self.send_error(404)
            return
        fn()

    def _stream(self, key):
        q = queue.Queue()
        self.task.data_queues.append(q)
        try:
            self.send_response(200)
            self.send_header('Content-type', 'text/plain')
            self.end_headers()
            ts = time.time()
            while time.time() - ts < 5:
                try:
                    data = q.get(timeout=0.25).get(key)
                    if data:
                        self.wfile.write(json.dumps(data).encode('utf-8') + b'\n')
                        self.wfile.flush()
                except queue.Empty:
                    pass
        finally:
            self.task.data_queues.remove(q)

    def GET_stream_audio(self):
        self._stream('audio')

    def GET_stream_lights(self):
        self._stream('rendered_state')

    def GET_lights(self):
        # TODO: do this a different way, handle errors
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.end_headers()
        out = {
            'lights': {k: v.dump() for k, v in self.task.tasks['lights'].lights.items()},
            'state': {k: v.state for k, v in self.task.tasks['lights'].lights.items()}
        }
        self.wfile.write(json.dumps(out).encode('utf-8'))
        self.wfile.flush()

    def GET_js(self):
        out = ''
        rjs = ''
        basedir = os.path.join(os.path.dirname(__file__), 'static', 'js')
        for directory, _, filenames in os.walk(basedir):
            for filename in filenames:
                filepath = os.path.join(directory, filename)
                modname = os.path.splitext(os.path.relpath(filepath, basedir).strip('/'))[0]
                with open(filepath, 'r') as fp:
                    if filename == 'require.js':
                        rjs = fp.read()
                    else:
                        out += r"(window.pl_pre_mod=window.pl_pre_mod||{})['" + modname + "']=function(exports){\n" + fp.read() + "\n};\n"
            out += rjs
        out = out.encode('utf-8')
        self.send_response(200)
        self.send_header('Content-type', 'text/javascript')
        self.send_header('Content-length', str(len(out)))
        self.end_headers()
        self.wfile.write(out)
        self.wfile.flush()

    def GET_(self):
        with open(os.path.join(os.path.dirname(__file__), 'index.html'), 'rb') as fp:
            out = fp.read()
        self.send_response(200)
        self.send_header('Content-type', 'text/html')
        self.send_header('Content-length', str(len(out)))
        self.end_headers()
        self.wfile.write(out)
        self.wfile.flush()


