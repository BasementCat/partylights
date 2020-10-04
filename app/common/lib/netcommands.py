import logging


logger = logging.getLogger(__name__)


class CommandError(Exception):
    def __init__(self, command=None, arg=None, value=None, message=None):
        self.command = command
        self.arg = arg
        self.value = value
        self.message = message

    def __str__(self):
        out = 'ERROR'
        if self.command:
            out += f' {self.command}'
        if self.arg:
            out += f' {self.arg}'
        if self.value:
            out += f' {self.value}'
        if self.message:
            out += f' :{self.message}'
        return out + '\n'


class Command:
    def __init__(self, command, **args):
        self.command = command.upper()
        self.args = args

    def __getattr__(self, k):
        try:
            return super().__getattr__(k)
        except AttributeError:
            try:
                return self.args[k]
            except KeyError:
                raise AttributeError(k) from None

    def __str__(self):
        out = self.command
        args = self.args.copy()
        last = None
        if args:
            tlkey, tlast = list(args.items())[-1]
            if ' ' in str(tlast):
                del args[tlkey]
                last = tlast
        for arg in args.values():
            if isinstance(arg, dict):
                for k, v in arg.items():
                    out += f' {k}={v}'
            elif isinstance(arg, list):
                for v in arg:
                    out += ' ' + str(v)
            else:
                out += ' ' + str(arg)
        if last:
            out += ' :' + str(last)
        return out + '\n'


class CommandParser:
    def __init__(self, name, callback, **arguments):
        self.name = name.upper()
        self.callback = callback
        self.arguments = {}
        for arg, props in arguments.items():
            is_kv = False
            type_ = str
            num = 1
            validators = None
            if isinstance(props, list):
                if len(props) > 4:
                    raise ValueError(f"Spec for arg {arg} is too long: {props}")
                elif not props:
                    raise ValueError(f"No spec for arg {arg}")
                else:
                    if props[0] == 'kv':
                        is_kv = True
                        props.pop(0)
                    if props:
                        type_ = props.pop(0)
                    if props:
                        num = props.pop(0)
                    if props:
                        validators = props.pop(0)
            else:
                type_ = props
                num = 1

            if not type_ or not callable(type_):
                raise ValueError(f"Invalid type in spec for {arg}: {type_}")

            if num not in ('*', '+'):
                try:
                    num = int(num)
                except (TypeError, ValueError):
                    raise ValueError(f"Invalid num in spec for {arg}: {num}")

            if validators:
                if callable(validators):
                    validators = [validators]
                for i, v in enumerate(validators):
                    if not callable(v):
                        raise ValueError(f"Validator {i} ({v}) for arg {arg} is not callable")

            self.arguments[arg] = {
                'is_kv': is_kv,
                'type': type_,
                'num': num,
                'validators': validators or [],
            }

    def from_parsed(self, command, *args):
        if command.upper() != self.name:
            raise ValueError("Invalid command supplied")
        args = list(args)
        parsed = {}
        for name, spec in self.arguments.items():
            parsed[name] = {} if spec['is_kv'] else (None if spec['num'] in (0, 1) else [])
            while True:
                if not args:
                    if spec['num'] == '*':
                        break
                    elif spec['num'] == '+':
                        if not len(parsed[name]):
                            raise CommandError(command=command, arg=name, message="Not enough arguments")
                        break
                    elif spec['num'] == 0:
                        break
                    elif spec['num'] == 1:
                        if parsed[name] is None or (spec['is_kv'] and not parsed[name]):
                            raise CommandError(command=command, arg=name, message="Missing arguments")
                        break
                    else:
                        if len(parsed[name]) < spec['num']:
                            raise CommandError(command=command, arg=name, message="Not enough arguments")
                        break
                else:
                    key = None
                    value = args.pop(0)
                    if spec['is_kv']:
                        if '=' not in value:
                            raise CommandError(command=command, arg=name, value=value, message="Not a key/value pair")
                        key, value = value.split('=', 1)
                    try:
                        value = spec['type'](value)
                    except (TypeError, ValueError):
                        raise CommandError(command=command, arg=name, value=value, message="Invalid data")
                    for validator in spec['validators']:
                        # Validators must raise CommandError
                        validator(command, name, value)
                    if spec['is_kv']:
                        parsed[name][key] = value
                    elif spec['num'] in ('*', '+') or spec['num'] > 1:
                        parsed[name].append(value)
                    else:
                        parsed[name] = value

                if spec['num'] not in ('*', '+'):
                    if spec['num'] < 2:
                        if parsed[name] is not None:
                            break
                    elif len(parsed[name]) == spec['num']:
                        break

        return Command(command, **parsed)


class CommandSet:
    def __init__(self, *commands):
        self.commands = {c.name: c for c in commands}

    def parse(self, data):
        command = args = last = None
        if ' :' in data:
            data, last = args.split(' :', 1)
        if ' ' in data:
            args = data.split(' ')
            command = args.pop(0)
        else:
            command = data
        if not args:
            args = []
        if last:
            args.append(last)
        args = list(filter(None, args))
        if not command:
            raise CommandError(message="Failed to parse command string")

        command = command.upper()
        if command not in self.commands:
            raise CommandError(command=command, message="Invalid command")
        ci = self.commands[command]
        return ci, ci.from_parsed(command, *args)

    def run_for(self, client):
        while True:
            data = client.read()
            if not data:
                break
            try:
                command_instance, command = self.parse(data)
                command_instance.callback(client, command)
            except CommandError as e:
                client.write(e)
            except:
                logger.error("Unexpected error processing command from client %s\n%s", client.addr, data, exc_info=True)
                client.write("ERROR :Unexpected error\n")