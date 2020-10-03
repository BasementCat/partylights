class Command:
    def create_subparser(self, parser):
        """\
        The "parser" argument to this method is the object returned by ArgumentParser.add_subparsers()
        Call "add_parser(cmd, ArgumentParserArgs)" on it, then proceed to add_argument to the resulting object
        """
        pass

    def main(self, config, args):
        return 0
