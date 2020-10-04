import logging
import json

from app.common.lib.command import Command
from app.common.lib.network import Server, ServerClient
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
                    self.process_commands(cl)
                for cl in disc:
                    logger.info("Disconnect client: %s", cl.addr)
        except KeyboardInterrupt:
            return 0
        finally:
            if self.server:
                self.server.close('QUIT\n')

    def process_commands(self, client):
        while True:
            data = client.read()
            if not data:
                break

            if ' ' in data:
                command, args = data.split(' ', 1)
                last = None
                if ':' in args:
                    args, last = data.split(' :', 1)
                args = args.split(' ')
            else:
                command = data
                args = []
                last = None
            fn = getattr(self, 'cmd_' + command.lower(), None)
            if not fn:
                client.write(f"ERROR {command} :Invalid command\n")
                continue

            if last:
                args += last
            try:
                fn(client, command, *args)
            except TypeError as e:
                if 'positional argument' in str(e):
                    client.write(f"ERROR {command} :Missing argument(s)\n")
                else:
                    logger.error("Unexpected error running %s: %s", command, e, exc_info=True)
                    client.write(f"ERROR {command} :Unexpected error\n")
            except Exception as e:
                logger.error("Unexpected error running %s: %s", command, e, exc_info=True)
                client.write(f"ERROR {command} :Unexpected error\n")

    def cmd_lights(self, client, command, light=None, *args):
        if light:
            if light not in self.lights:
                client.write(f"ERROR {command} {light} :Invalid light\n")
                return
            lights = {light: self.lights[light]}
        else:
            lights = self.lights

        for name, light in lights.items():
            client.write(f"LIGHT {name} :" + json.dumps(light.dump()) + '\n')
        client.write("END\n")

    def cmd_state(self, client, command, light, *args):
        try:
            lights = list(self.lights.values()) if light == '*' else [self.lights[light]]
        except KeyError:
            client.write(f"ERROR {command} {light} :Invalid light\n")

        props = {}
        for a in args:
            if '=' not in a:
                client.write(f"ERROR {command} {a} :Invalid format\n")
                return
            k, v = a.split('=', 1)
            try:
                v = int(v)
            except (TypeError, ValueError):
                client.write(f"ERROR {command} {a} :Not an integer\n")
                return

            props[k] = v

        for cl in self.server.clients.values():
            if cl.exclusive and cl is not client:
                client.write(f"ERROR {command} :Another client is exclusive\n")
                return

        for light in lights:
            light.set_state(**props)
            state = ' '.join((f'{k}={v}' for k, v in light.diff_state.items()))
            self.server.write_all(f"STATE {light.name} {state}\n", filter_fn=lambda cl: cl.monitor or cl is client)

    def cmd_monitor(self, client, command, state=None, *args):
        if state is not None:
            try:
                client.monitor = bool(int(state))
            except (TypeError, ValueError):
                client.write(f"ERROR {command} {state} :Not an integer\n")
                return

        client.write(f"MONITOR {int(client.monitor)}\n")

    def cmd_exclusive(self, client, command, state=None, *args):
        if state is not None:
            try:
                state = bool(int(state))
                if state:
                    # Can't go exclusive if any other clients are
                    for cl in self.server.clients.values():
                        if cl.exclusive and cl is not client:
                            client.write(f"ERROR {command} {int(state)} :Another client is exclusive\n")
                            return
                client.exclusive = state
            except (TypeError, ValueError):
                client.write(f"ERROR {command} {state} :Not an integer\n")
                return

        client.write(f"EXCLUSIVE {int(client.exclusive)}\n")
