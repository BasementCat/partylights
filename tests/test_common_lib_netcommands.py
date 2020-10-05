from unittest import TestCase

from app.common.lib import netcommands as nc


class TestCommandError(TestCase):
    def test_command_error(self):
        e = nc.CommandError()
        self.assertEqual('ERROR\n', str(e))
        e = nc.CommandError(command='foo')
        self.assertEqual('ERROR foo\n', str(e))
        e = nc.CommandError(arg='bar')
        self.assertEqual('ERROR bar\n', str(e))
        e = nc.CommandError(value='baz')
        self.assertEqual('ERROR baz\n', str(e))
        e = nc.CommandError(message='foo bar')
        self.assertEqual('ERROR :foo bar\n', str(e))
        e = nc.CommandError(command='foo', arg='bar', value='baz', message='foo bar')
        self.assertEqual('ERROR foo bar baz :foo bar\n', str(e))


class TestCommand(TestCase):
    def test_command_base(self):
        c = nc.Command('foo')
        self.assertEqual('FOO', c.command)
        self.assertEqual('FOO\n', str(c))

    def test_command_args(self):
        c = nc.Command('foo', bar='baz')
        self.assertEqual('baz', c.bar)
        with self.assertRaises(AttributeError):
            _ = c.asdf
        self.assertEqual('FOO baz\n', str(c))

    def test_command_last(self):
        c = nc.Command('foo', bar='baz', a='foo bar')
        self.assertEqual('FOO baz :foo bar\n', str(c))


class TestCommandParser(TestCase):
    def test_simple(self):
        cb = lambda x: x
        p = nc.CommandParser('cmd', cb, foo=str, bar=int)
        self.assertEqual('CMD', p.name)
        self.assertEqual(cb, p.callback)
        with self.assertRaisesRegex(ValueError, 'Invalid command supplied'):
            p.from_parsed('asdf')
        with self.assertRaisesRegex(nc.CommandError, 'foo.*Missing arguments'):
            p.from_parsed('cmd')
        with self.assertRaisesRegex(nc.CommandError, 'bar.*Missing arguments'):
            p.from_parsed('cmd', 'asdf')
        with self.assertRaisesRegex(nc.CommandError, 'bar.*Invalid data'):
            p.from_parsed('cmd', 1, 'x')
        res = p.from_parsed('cmd', 'a', 5)
        self.assertEqual('CMD', res.command)
        self.assertEqual('a', res.foo)
        self.assertEqual(5, res.bar)

    def test_num_0(self):
        p = nc.CommandParser('cmd', None, foo=[str, 0])
        res = p.from_parsed('cmd')
        self.assertIsNone(res.foo)
        res = p.from_parsed('cmd', 'x')
        self.assertEqual('x', res.foo)

    def test_num_1(self):
        p = nc.CommandParser('cmd', None, foo=[str, 1])
        with self.assertRaisesRegex(nc.CommandError, 'foo.*Missing arguments'):
            p.from_parsed('cmd')
        res = p.from_parsed('cmd', 'x')
        self.assertEqual('x', res.foo)

    def test_num_x(self):
        p = nc.CommandParser('cmd', None, foo=[str, 3])
        with self.assertRaisesRegex(nc.CommandError, 'foo.*Not enough arguments'):
            p.from_parsed('cmd')
        with self.assertRaisesRegex(nc.CommandError, 'foo.*Not enough arguments'):
            p.from_parsed('cmd', 'a', 'b')

        res = p.from_parsed('cmd', 'a', 'b', 'c', 'd')
        self.assertEqual(['a', 'b', 'c'], res.foo)

    def test_num_atleast_1(self):
        p = nc.CommandParser('cmd', None, foo=[str, '+'])
        with self.assertRaisesRegex(nc.CommandError, 'foo.*Not enough arguments'):
            p.from_parsed('cmd')
        res = p.from_parsed('cmd', 'a', 'b')
        self.assertEqual(['a', 'b'], res.foo)
        res = p.from_parsed('cmd', 'a', 'b', 'c', 'd')
        self.assertEqual(['a', 'b', 'c', 'd'], res.foo)

    def test_num_any(self):
        p = nc.CommandParser('cmd', None, foo=[str, '*'])
        res = p.from_parsed('cmd')
        self.assertEqual([], res.foo)
        res = p.from_parsed('cmd', 'a', 'b')
        self.assertEqual(['a', 'b'], res.foo)
        res = p.from_parsed('cmd', 'a', 'b', 'c', 'd')
        self.assertEqual(['a', 'b', 'c', 'd'], res.foo)

    def test_kv(self):
        with self.assertRaisesRegex(ValueError, 'No spec for arg foo'):
            nc.CommandParser('cmd', None, foo=[])
        with self.assertRaisesRegex(ValueError, 'Spec for arg foo is too long'):
            nc.CommandParser('cmd', None, foo=[1, 2, 3, 4, 5])

        p = nc.CommandParser('cmd', None, foo=['kv', int])
        with self.assertRaisesRegex(nc.CommandError, 'foo.*Missing arguments'):
            p.from_parsed('cmd')
        with self.assertRaisesRegex(nc.CommandError, 'foo.*Not a key/value pair'):
            p.from_parsed('cmd', 'x')
        with self.assertRaisesRegex(nc.CommandError, 'foo.*Invalid data'):
            p.from_parsed('cmd', 'x=x')
        res = p.from_parsed('cmd', 'x=3', 'y=5')
        self.assertEqual({'x': 3}, res.foo)

        p = nc.CommandParser('cmd', None, foo=['kv', int, '*'])
        res = p.from_parsed('cmd')
        self.assertEqual({}, res.foo)
        res = p.from_parsed('cmd', 'x=3', 'y=5')
        self.assertEqual({'x': 3, 'y': 5}, res.foo)

    def test_validators(self):
        with self.assertRaisesRegex(ValueError, 'Validator.*not callable'):
            nc.CommandParser('cmd', None, foo=[int, 1, ['x']])

        vd = {}
        def validator(command, name, value):
            if value >= 10:
                raise nc.CommandError(command=command, arg=name, value=value, message="Must be <10")
            vd['command'] = command
            vd['name'] = name
            vd['value'] = value
        p = nc.CommandParser('cmd', None, foo=[int, 1, [validator]])

        with self.assertRaisesRegex(nc.CommandError, 'Must be <10'):
            p.from_parsed('cmd', '12')

        res = p.from_parsed('cmd', '9')
        self.assertEqual(9, res.foo)
        self.assertEqual('cmd', vd['command'])
        self.assertEqual('foo', vd['name'])
        self.assertEqual(9, vd['value'])

    def test_validators_autoset_err_args(self):
        vd = {}
        def validator(command, name, value):
            if value >= 10:
                raise nc.CommandError(message="Must be <10")
            vd['command'] = command
            vd['name'] = name
            vd['value'] = value
        p = nc.CommandParser('cmd', None, foo=[int, 1, [validator]])

        with self.assertRaisesRegex(nc.CommandError, 'ERROR cmd foo 12 :Must be <10'):
            p.from_parsed('cmd', '12')

    def test_validators_kv(self):
        with self.assertRaisesRegex(ValueError, 'Validator.*not callable'):
            nc.CommandParser('cmd', None, foo=['kv', int, 1, ['x']])

        vd = {}
        def validator(command, name, value):
            if value >= 10:
                raise nc.CommandError(command=command, arg=name, value=value, message="Must be <10")
            vd['command'] = command
            vd['name'] = name
            vd['value'] = value
        p = nc.CommandParser('cmd', None, foo=['kv', int, 1, [validator]])

        with self.assertRaisesRegex(nc.CommandError, 'Must be <10'):
            p.from_parsed('cmd', 'x=12')

        res = p.from_parsed('cmd', 'x=9')
        self.assertEqual({'x': 9}, res.foo)
        self.assertEqual('cmd', vd['command'])
        self.assertEqual('foo', vd['name'])
        self.assertEqual(9, vd['value'])


class TestCommandSet(TestCase):
    def test_parse(self):
        p = nc.CommandParser('cmd', None)
        s = nc.CommandSet(p)
        with self.assertRaisesRegex(nc.CommandError, 'X.*Invalid command'):
            res = s.parse('x')
        res = s.parse('cmd')
        self.assertEqual(p, res[0])
        self.assertEqual('CMD', res[1].command)

        p = nc.CommandParser('cmd', None, foo=int)
        s = nc.CommandSet(p)
        with self.assertRaisesRegex(nc.CommandError, 'Failed to parse'):
            s.parse('')
        with self.assertRaisesRegex(nc.CommandError, 'X.*Invalid command'):
            s.parse('x 6')

        res = s.parse('cmd 6')
        self.assertEqual(p, res[0])
        self.assertEqual(6, res[1].foo)

    def test_run_for(self):
        class MockClient:
            def __init__(self, *data):
                self.addr = ('test', 123)
                self.data = list(data)
                self.written = []

            def readline(self):
                if self.data:
                    return self.data.pop(0)

            def write(self, value):
                self.written.append(str(value))

        cb_called = []
        def cb(client, command):
            cb_called.append(client)
            self.assertEqual(6, command.foo)
        p = nc.CommandParser('cmd', cb, foo=int)
        s = nc.CommandSet(p)

        c = MockClient(' ')
        s.run_for(c)
        self.assertTrue('Failed to parse' in c.written[0])

        c = MockClient('x 6')
        s.run_for(c)
        self.assertTrue('Invalid command' in c.written[0])

        c = MockClient('cmd 6')
        s.run_for(c)
        self.assertEqual([c], cb_called)
