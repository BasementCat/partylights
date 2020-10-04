import logging
import signal
import threading
# import json

from app.common.lib.command import Command
# from app.common.lib.network import Server, ServerClient
# import app.common.lib.netcommands as nc

from .input import Input


logger = logging.getLogger(__name__)


# class LightServerClient(ServerClient):
#     def __init__(self, *args, **kwargs):
#         super().__init__(*args, **kwargs)
#         self.monitor = False
#         self.exclusive = set()


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

        with Input.get_input(config) as capture:
            import time
            f=0
            t=time.perf_counter()
            while not stop_event.is_set():
                res = capture.read()
                # if res is None:
                #     print(None)
                # else:
                #     print(len(res))
                f += 1
                if time.perf_counter() - t >= 1:
                    t = time.perf_counter()
                    print(f)
                    f = 0
