import logging
import json

from app.common.lib.command import Command
from app.common.lib.network import Server, ServerClient
from app.common.lib.rpc import RPCServer, RPCError
from app.common.lib.fps import FPSCounter
from .bases import Light, DMXLight
from .dmx import DMXDevice


logger = logging.getLogger(__name__)


E_QUIT = (0, "Quit")
E_EXCLUSIVE = (1, "Another client is exclusive")


class LightServerClient(ServerClient):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.monitor = False
        self.exclusive = set()


class LightServerCommand(Command):
    def create_subparser(self, parser):
        sub = parser.add_parser('lightserver', description="Run the core light server that exposes access to the lights")
        sub.add_argument('-H', '--host', help="Hostname, ipv4/6 address, or path to unix socket (unix:///path/to/socket) to listen on")
        sub.add_argument('-p', '--port', type=int, help="Port to listen on when --host is not a unix socket")
        return 'lightserver'

    def main(self, config, args):
        self.lights = {}
        for name, lconfig in config.get('Lights', {}).items():
            if name in self.lights:
                raise RuntimeError(f"The light {name} is defined more than once, somehow")
            self.lights[name] = Light.create_from(config, name, lconfig)

        dmx_devices = {k: DMXDevice(v) for k, v in config.get('DMXDevices', {}).items()}
        if not dmx_devices:
            raise RuntimeError("No DMX devices are configured")
        if not dmx_devices.get('default'):
            raise RuntimeError("The default DMX device is not configured")

        fps = FPSCounter('Light Server')

        nconfig = config.get('LightServer', {}).get('Bind', {})
        self.server = None
        self.rpcserver = None
        try:
            self.server = Server(args.host or nconfig.get('Host') or '127.0.0.1', port=args.port or nconfig.get('Port') or 37730, client_class=LightServerClient)
            self.rpcserver = RPCServer(self.server)
            self.rpcserver.register_method('lights', self.cmd_lights)
            self.rpcserver.register_method('state', self.cmd_state)
            self.rpcserver.register_method('monitor', self.cmd_monitor)
            self.rpcserver.register_method('exclusive', self.cmd_exclusive)
            while True:
                with fps:
                    new, ready, disc = self.server.process()
                    for cl in new:
                        logger.info("New client: %s", cl.addr)
                        self.rpcserver.send(cl, {'type': 'welcome'})
                    for cl in ready:
                        self.rpcserver.process_client(cl)
                    for cl in disc:
                        logger.info("Disconnect client: %s", cl.addr)

                    DMXLight.send_batch(dmx_devices, self.lights.values())
        except KeyboardInterrupt:
            return 0
        finally:
            if self.rpcserver:
                self.rpcserver.close(RPCError(*E_QUIT))
            else:
                self.server.close()

    def _get_lights(self, param, *lights):
        lights = list(filter(None, lights))
        if not lights:
            return self.lights
        out = {}
        for l in lights:
            if l not in self.lights:
                raise RPCError(*RPCError.INVALID_PARAMS, data={'param': param, 'value': l})
            out[l] = self.lights[l]
        return out

    def cmd_lights(self, client, method, lights=None):
        lights = self._get_lights('lights', *(lights or []))
        return {'result': {name: light.dump() for name, light in lights.items()}}

    def cmd_state(self, client, method, lights=None, state=None):
        lights = self._get_lights('lights', *(lights or []))
        light_names = set(lights.keys())

        for cl in self.server.clients.values():
            if cl.exclusive and cl is not client:
                failed = light_names & cl.exclusive
                if failed:
                    raise RPCError(*E_EXCLUSIVE, data={'lights': list(failed)})

        if state:
            out = {}
            for light in lights.values():
                light.set_state(**state)
                out[light.name] = light.diff_state
            self.rpcserver.send(lambda cl: cl.monitor and cl is not client, {'result': out})
            # The requesting client must get the results as a reply
            return {'result': {'type': 'state', 'data': out}}
        else:
            out = {l.name: l.state for l in lights.values()}
            return {'result': out}

    def cmd_monitor(self, client, method, state=None):
        if state is not None:
            client.monitor = bool(state)
        return {'state': client.monitor}

    def cmd_exclusive(self, client, method, state=None, lights=None):
        if state is not None:
            state = bool(state)
            light_names = set(self._get_lights('lights', *(lights or [])).keys())
            if state:
                # Can't go exclusive if any other clients are
                for cl in self.server.clients.values():
                    if cl.exclusive and cl is not client:
                        # Determine if this client can gain exclusivity on the lights requested
                        failed = cl.exclusive & light_names
                        if failed:
                            raise RPCError(*E_EXCLUSIVE, data={'lights': list(failed)})
                # Not failed at this point, add the list of lights to the client
                client.exclusive |= light_names
            else:
                client.exclusive -= light_names

        return {
            'num': len(client.exclusive),
            'all': client.exclusive == set(self.lights.keys()),
            'lights': list(client.exclusive),
        }
