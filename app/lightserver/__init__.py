import logging
import json

from app.common.lib.command import Command
from app.common.lib.network import Server, ServerClient
import app.common.lib.netcommands as nc
from .bases import Light


logger = logging.getLogger(__name__)


class LightServerClient(ServerClient):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.monitor = False
        self.exclusive = False


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

        def validate_light(command, arg, value):
            if value != '*':
                if value not in self.lights:
                    raise nc.CommandError(command=command, arg=arg, value=value, message="Not a valid light")

        command_set = nc.CommandSet(
            nc.CommandParser('lights', self.cmd_lights, light=[str, 0, [validate_light]]),
            nc.CommandParser('state', self.cmd_state, light=[str, 0, [validate_light]], state=['kv', int, '*']),
            nc.CommandParser('monitor', self.cmd_monitor, state=[int, 0]),
            nc.CommandParser('exclusive', self.cmd_exclusive, state=[int, 0]),
        )

        nconfig = config.get('LightServer', {}).get('Bind', {})
        self.server = None
        try:
            self.server = Server(args.host or nconfig.get('Host') or '127.0.0.1', port=args.port or nconfig.get('Port') or 37730, client_class=LightServerClient)
            while True:
                new, ready, disc = self.server.process()
                for cl in new:
                    logger.info("New client: %s", cl.addr)
                    cl.write("WELCOME\n")
                for cl in ready:
                    command_set.run_for(cl)
                for cl in disc:
                    logger.info("Disconnect client: %s", cl.addr)

                # TODO: Send DMX
        except KeyboardInterrupt:
            return 0
        finally:
            if self.server:
                self.server.close('QUIT\n')

    def cmd_lights(self, client, command):
        lights = {command.light: self.lights[command.light]} if command.light else self.lights
        for name, light in lights.items():
            client.write(f"LIGHT {name} :" + json.dumps(light.dump()) + '\n')
        client.write("END\n")

    def cmd_state(self, client, command):
        lights = list(self.lights.values()) if command.light == '*' or command.light is None else [self.lights[command.light]]

        for cl in self.server.clients.values():
            if cl.exclusive and cl is not client:
                raise nc.CommandError(command=command.command, message='Another client is exclusive')

        for light in lights:
            light.set_state(**command.state)
            state = ' '.join((f'{k}={v}' for k, v in light.diff_state.items()))
            self.server.write_all(f"STATE {light.name} {state}\n", filter_fn=lambda cl: cl.monitor or cl is client)

    def cmd_monitor(self, client, command):
        if command.state is not None:
            client.monitor = bool(command.state)
        client.write(f"MONITOR {int(client.monitor)}\n")

    def cmd_exclusive(self, client, command):
        if command.state is not None:
            state = bool(command.state)
            if state:
                # Can't go exclusive if any other clients are
                for cl in self.server.clients.values():
                    if cl.exclusive and cl is not client:
                        raise nc.CommandError(command=command.command, message='Another client is exclusive')
            client.exclusive = state

        client.write(f"EXCLUSIVE {int(client.exclusive)}\n")