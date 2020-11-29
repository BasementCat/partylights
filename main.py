#! /usr/bin/env python3

import sys
import time
import logging
import argparse
import signal
import threading

from lib.config import load_config
from lib.fps import FPSCounter


logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)


def parse_args():
    parser = argparse.ArgumentParser(description="It's time to party!")
    parser.add_argument('-c', '--config-file', help="Path to main config file")
    return parser.parse_args()


def main(args):
    config = load_config(args.config_file)

    stop_event = threading.Event()
    def _sig_handler(signo, frame):
        stop_event.set()
    signal.signal(signal.SIGINT, _sig_handler)
    signal.signal(signal.SIGTERM, _sig_handler)

    from components.capture import AudioCaptureTask
    from components.lights import LightOutputTask
    from components.mapper import MapperTask
    from components.webgui import WebGUITask
    from components.network import NetworkTask

    fps = FPSCounter('All')

    tasks = {
        'audio': AudioCaptureTask(config),
        'mapper': MapperTask(config),
        'lights': LightOutputTask(config),
        'webgui': WebGUITask(config),
        'network': NetworkTask(config),
    }
    try:
        for task in tasks.values():
            task.setup()

        while not stop_event.is_set():
            with fps:
                data = {'tasks': tasks}
                for t in tasks.values():
                    try:
                        t.run(data)
                    except:
                        logger.error("Failure in %s", t.__class__.__name__, exc_info=True)
    finally:
        # print("Exiting")
        for t in tasks.values():
            # print("Stop " + t.__class__.__name__)
            try:
                t.teardown()
            except:
                logger.error("Failed to tear down %s", t.__class__.__name__, exc_info=True)


if __name__ == '__main__':
    sys.exit(main(parse_args()) or 0)
