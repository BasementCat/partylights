import logging
import signal
import threading
import json

from app.common.lib.command import Command
from app.common.lib.network import Server
from app.common.lib.rpc import RPCServer, RPCError

from .input import Input
from . import processor


logger = logging.getLogger(__name__)


class AudioCaptureCommand(Command):
    def create_subparser(self, parser):
        sub = parser.add_parser('audiocapture', description="Capture audio from an audio device and make it available for use")
        sub.add_argument('-H', '--host', help="Hostname, ipv4/6 address, or path to unix socket (unix:///path/to/socket) to listen on")
        sub.add_argument('-p', '--port', type=int, help="Port to listen on when --host is not a unix socket")
        return 'audiocapture'

    def main(self, config, args):
        stop_event = threading.Event()
        def _sighandler(signo, frame):
            stop_event.set()
        signal.signal(signal.SIGINT, _sighandler)

        processors = [
            processor.SmoothingProcessor(config),
            processor.BeatProcessor(config),
            processor.PitchProcessor(config),
            processor.IdleProcessor(config),
        ]

        nconfig = config.get('Capture', {}).get('Bind', {})
        server = Server(args.host or nconfig.get('Host') or '127.0.0.1', port=args.port or nconfig.get('Port') or 37731)
        # Empty RPC server to ensure input is processed, but any commands are invalid
        rpcserver = RPCServer(server)
        try:
            with Input.get_input(config) as capture:
                while not stop_event.is_set():
                    res = capture.read()
                    data = {}
                    for p in processors:
                        p.process(res, data)

                    new, ready, disc = server.process(0)
                    for cl in new:
                        logger.info("New client: %s", cl.addr)
                        rpcserver.send(cl, {'type': 'welcome'})
                    for cl in ready:
                        rpcserver.process_client(cl)
                    for cl in disc:
                        logger.info("Disconnect client: %s", cl.addr)

                    data['audio'] = list(data['audio']) if data['audio'] is not None else None
                    rpcserver.send(None, {'type': 'audio', 'data': data})
        finally:
            rpcserver.close(RPCError(0, 'Quit'))
