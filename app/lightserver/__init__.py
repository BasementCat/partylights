from app.common.lib.command import Command


class LightServerCommand(Command):
    def create_subparser(self, parser):
        sub = parser.add_parser('lightserver', description="Run the core light server that exposes access to the lights")
        sub.add_argument('-H', '--host', help="Hostname, ipv4/6 address, or path to unix socket (unix:///path/to/socket) to listen on")
        sub.add_argument('-p', '--port', type=int, help="Port to listen on when --host is not a unix socket")
        return 'lightserver'

    def main(self, config, args):
        print(config)
        print(args)
