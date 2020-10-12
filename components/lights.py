import logging
import json

from lib.task import Task
from lib.fps import FPSCounter
from lib.pubsub import publish, subscribe
from lib.light.models import Light, DMXLight
from lib.light.dmx import DMXDevice


logger = logging.getLogger(__name__)


class LightOutputTask(Task):
    def setup(self):
        self.lights = {}
        self.exclusive = {}
        for name, lconfig in self.config.get('Lights', {}).items():
            if name in self.lights:
                raise RuntimeError(f"The light {name} is defined more than once, somehow")
            self.lights[name] = Light.create_from(self.config, name, lconfig)

        self.dmx_devices = {k: DMXDevice(v) for k, v in self.config.get('DMXDevices', {}).items()}
        if not self.dmx_devices:
            raise RuntimeError("No DMX devices are configured")
        if not self.dmx_devices.get('default'):
            raise RuntimeError("The default DMX device is not configured")

        self.fps = FPSCounter('Light Server')
        self.events = subscribe('light.*')

    def _loop(self):
        with self.fps:
            for ev in self.events:
                with ev:
                    cmd, args = ev.unpack_name()
                    if cmd == 'set_state':
                        light_name = args(1)
                        lights = list(filter(None, [self.lights.get(light_name)])) if light_name else list(self.lights.values())
                        for l in lights:
                            state = {k: v for k, v in ev.data.items() if self.exclusive.get((l.name, k)) in (None, ev.sender)}
                            if state:
                                l.set_state(**state)
                    elif cmd == 'get':
                        what = args(1)
                        if what == 'lights':
                            ev.returning(self.lights)
                        elif what == 'state':
                            ev.returning({l.name: l.state for l in self.lights.values()})
                    elif cmd == 'exclusive':
                        if not ev.sender:
                            logger.warning("Can't go exclusive with no sender")
                        else:
                            exclusive_set = []
                            try:
                                for light_name in ev.data.get('lights') or self.lights.keys():
                                    light = self.lights.get(light_name)
                                    if not light:
                                        raise ValueError(f"No such light: {light_name}")
                                    if getattr(light, 'functions', None):
                                        for prop in ev.data.get('functions') or light.functions.keys():
                                            exclusive_set.append((light_name, prop))
                                    else:
                                        exclusive_set.append((light_name, None))

                                if ev.data.get('state'):
                                    for k in exclusive_set:
                                        if self.exclusive.get(k) and self.exclusive[k] != ev.sender:
                                            raise ValueError(f"Another client is exclusive for {k}")
                                    self.exclusive.update({k: ev.sender for k in exclusive_set})
                                else:
                                    self.exclusive.update({k: None for k in exclusive_set if self.exclusive.get(k) == ev.sender})
                            except ValueError as e:
                                logger.warning("Sender %s cannot be exclusive: %s", str(e))
                                ev.returning(False)
                            else:
                                ev.returning(True)
            for l in self.lights.values():
                if l.diff_state:
                    # TODO: try to not receive this, somehow
                    publish('light.state.' + l.name, l.diff_state)
            DMXLight.send_batch(self.dmx_devices, self.lights.values())
