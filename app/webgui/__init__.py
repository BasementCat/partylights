import logging
import textwrap
import os
import queue
# import signal
# import threading
# import json

from flask import (
    Flask,
    render_template_string,
)
from flask_sockets import Sockets
from flask_bootstrap import Bootstrap

from gevent import pywsgi
from geventwebsocket.handler import WebSocketHandler

from app.common.lib.command import Command
# from app.common.lib.network import SelectableCollection, Client #Server
# from app.common.lib.rpc import RPCClient
# from app.common.lib.fps import FPSCounter

from .lib.network import NetworkThread


logger = logging.getLogger(__name__)


def create_app():
    app = Flask(__name__)
    app.config['SECRET_KEY'] = 'shh it\'s a secret'
    sockets = Sockets(app)
    Bootstrap(app)

    network = NetworkThread()
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

    # @sockets.route('/test')
    # def test(ws):
    #     while not ws.closed:
    #         import time
    #         ws.send(str(time.time()))
    #         time.sleep(1)

    # TODO: audio recv, lights send

    @sockets.route('/lights/recv')
    def lights_recv(ws):
        q = network.connect('lights', 'recv')
        try:
            while not ws.closed:
                try:
                    ws.send(q.get(timeout=1))
                except queue.Empty:
                    pass
        except:
            logger.error("Failure", exc_info=True)
            raise
        finally:
            network.disconnect(q)

    return app


class WebGUICommand(Command):
    def create_subparser(self, parser):
        sub = parser.add_parser('webgui', description="Web GUI for monitoring & control")
        # sub.add_argument('-H', '--host', help="Hostname, ipv4/6 address, or path to unix socket (unix:///path/to/socket) to listen on")
        # sub.add_argument('-p', '--port', type=int, help="Port to listen on when --host is not a unix socket")
        return 'webgui'

    def main(self, config, args):
        app = create_app()
        server = pywsgi.WSGIServer(('', 5000), app, handler_class=WebSocketHandler)
        server.serve_forever()