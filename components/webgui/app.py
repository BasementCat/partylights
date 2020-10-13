import logging
import textwrap
import os
import json
import threading

from flask import (
    Flask,
    render_template_string,
)
from flask_threaded_sockets import Sockets
from flask_bootstrap import Bootstrap

from lib.pubsub import publish, subscribe


logger = logging.getLogger(__name__)


class WSWrapper:
    def __init__(self, stop_event, open_sockets, ws, events=None):
        self.stop_event = stop_event
        self.open_sockets = open_sockets
        self.ws = ws
        self.events = events
        self.s_ev = None

    @property
    def alive(self):
        return not (self.ws.closed or self.stop_event.is_set())

    def __enter__(self):
        self.s_ev = threading.Event()
        self.open_sockets.append(self.s_ev)
        return self

    def __exit__(self, type_, value, traceback):
        if value:
            logger.error("Failure in websocket handler", exc_info=True)

        if not self.ws.closed:
            self.ws.close()
        if self.events:
            self.events.unsubscribe()
        self.s_ev.set()
        if not self.stop_event.is_set():
            self.open_sockets.remove(self.s_ev)

        return True


def create_app(stop_event, open_sockets):
    app = Flask(__name__)
    app.config['SECRET_KEY'] = 'shh it\'s a secret'
    sockets = Sockets(app)
    Bootstrap(app)

    @app.route('/')
    def index():
        return render_template_string(textwrap.dedent(r'''
            {% extends "bootstrap/base.html" %}
            {% block title %}default{% endblock %}

            {% block styles %}
                {{ super() }}
                <link rel="stylesheet" href="/static/style.css" />
            {% endblock %}

            {% block scripts %}
                {{ super() }}
                <script src="/main.js"></script>
                <script>require('main');</script>
            {% endblock %}

            {% block navbar %}
                <nav class="navbar navbar-default navbar-fixed-top">
                    <div class="container">
                        <div class="navbar-header">
                            <button type="button" class="navbar-toggle collapsed" data-toggle="collapse" data-target="#navbar" aria-expanded="false" aria-controls="navbar">
                                <span class="sr-only">Toggle navigation</span>
                                <span class="icon-bar"></span>
                                <span class="icon-bar"></span>
                                <span class="icon-bar"></span>
                            </button>
                            <a class="navbar-brand" href="#" id="nav-title"></a>
                        </div>
                        <div id="navbar" class="navbar-collapse collapse">
                            <ul class="nav navbar-nav" id="nav-left">
                            </ul>
                            <ul class="nav navbar-nav navbar-right" id="nav-right">
                            </ul>
                        </div><!--/.nav-collapse -->
                    </div>
                </nav>
            {% endblock %}

            {% block content %}
                <div class="container-fluid" id="main"></div>
            {% endblock %}
        '''))

    @app.route('/main.js')
    def main_js():
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
        return out

    # TODO: audio recv, lights send

    @sockets.route('/lights/recv')
    def lights_recv(ws):
        events = subscribe('light.state.*')
        with WSWrapper(stop_event, open_sockets, ws, events=events) as wrap:
            ws.send(json.dumps(['lights', {k: v.dump() for k, v in (publish('light.get.lights', returning=True) or {}).items()}]))
            while wrap.alive:
                for ev in events:
                    cmd, args = ev.unpack_name()
                    if cmd == 'state':
                        ws.send(json.dumps([cmd, args(1), ev.data]))

    return app
