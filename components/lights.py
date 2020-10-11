import logging
import json

# from app.common.lib.command import Command
# from app.common.lib.network import Server, ServerClient
# from app.common.lib.rpc import RPCServer, RPCError
from lib.task import Task
from lib.fps import FPSCounter
from lib.pubsub import publish, subscribe
from lib.light.models import Light, DMXLight
from lib.light.dmx import DMXDevice


logger = logging.getLogger(__name__)


# E_QUIT = (0, "Quit")
# E_EXCLUSIVE = (1, "Another client is exclusive")


# class LightServerClient(ServerClient):
#     def __init__(self, *args, **kwargs):
#         super().__init__(*args, **kwargs)
#         self.monitor = False
#         self.exclusive = set()


class LightOutputTask(Task):
    def setup(self):
        self.lights = {}
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
            for ev, data in self.events:
                parts = ev.split('.')
                parts.pop(0)
                if parts[0] == 'set_state':
                    lights = [self.lights.values()] if len(parts) == 1 else list(filter(None, [self.lights.get(parts[1])]))
                    for l in lights:
                        l.set_state(**data)
            DMXLight.send_batch(self.dmx_devices, self.lights.values())

    # def _get_lights(self, param, *lights):
    #     lights = list(filter(None, lights))
    #     if not lights:
    #         return self.lights
    #     out = {}
    #     for l in lights:
    #         if l not in self.lights:
    #             raise RPCError(*RPCError.INVALID_PARAMS, data={'param': param, 'value': l})
    #         out[l] = self.lights[l]
    #     return out

    # def cmd_lights(self, client, method, lights=None):
    #     lights = self._get_lights('lights', *(lights or []))
    #     return {'result': {name: light.dump() for name, light in lights.items()}}

    # def cmd_state(self, client, method, lights=None, state=None):
    #     lights = self._get_lights('lights', *(lights or []))
    #     light_names = set(lights.keys())

    #     for cl in self.server.clients.values():
    #         if cl.exclusive and cl is not client:
    #             failed = light_names & cl.exclusive
    #             if failed:
    #                 raise RPCError(*E_EXCLUSIVE, data={'lights': list(failed)})

    #     if state:
    #         out = {}
    #         for light in lights.values():
    #             light.set_state(**state)
    #             out[light.name] = light.diff_state
    #         self.rpcserver.send(lambda cl: cl.monitor and cl is not client, {'result': out})
    #         # The requesting client must get the results as a reply
    #         return {'result': {'type': 'state', 'data': out}}
    #     else:
    #         out = {l.name: l.state for l in lights.values()}
    #         return {'result': out}

    # def cmd_monitor(self, client, method, state=None):
    #     if state is not None:
    #         client.monitor = bool(state)
    #     return {'state': client.monitor}

    # def cmd_exclusive(self, client, method, state=None, lights=None):
    #     if state is not None:
    #         state = bool(state)
    #         light_names = set(self._get_lights('lights', *(lights or [])).keys())
    #         if state:
    #             # Can't go exclusive if any other clients are
    #             for cl in self.server.clients.values():
    #                 if cl.exclusive and cl is not client:
    #                     # Determine if this client can gain exclusivity on the lights requested
    #                     failed = cl.exclusive & light_names
    #                     if failed:
    #                         raise RPCError(*E_EXCLUSIVE, data={'lights': list(failed)})
    #             # Not failed at this point, add the list of lights to the client
    #             client.exclusive |= light_names
    #         else:
    #             client.exclusive -= light_names

    #     return {
    #         'num': len(client.exclusive),
    #         'all': client.exclusive == set(self.lights.keys()),
    #         'lights': list(client.exclusive),
    #     }
