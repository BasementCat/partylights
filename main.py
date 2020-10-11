#! /usr/bin/env python3

import sys
import time
import logging
import argparse
import signal
import threading

from lib.task import TaskManager
from lib.config import load_config


logging.basicConfig(level=logging.DEBUG)


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

    tasks = TaskManager()

    from components.capture import AudioCaptureTask

    try:
        # Add tasks here so that if an exception occurs, any previously started task is stopped
        tasks.add_task(AudioCaptureTask(config))

        while not stop_event.is_set():
            tasks.check_tasks()
            time.sleep(1)
    finally:
        tasks.stop_all()


if __name__ == '__main__':
    sys.exit(main(parse_args()) or 0)
