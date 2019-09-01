import os
from ..command import Command
from ..generator import CmakeGenerator

__all__ = ['create_command', 'parse_command', 'MockCmakeGenerator', 'CWD', 'DIR']
DIR = os.path.dirname(__file__)
CWD = os.getcwd()


def create_command(compiler, **kwargs):
    command = Command(compiler, CWD)
    command.__dict__.update(kwargs)
    return command


def parse_command(command_line, source, cwd=CWD, root_dir=DIR):
    return Command.parse(command_line, source, cwd, root_dir)


class MockCmakeGenerator:
    def __init__(self, output, directory):
        self.output = output
        self.directory = directory
        self.root_dir = directory
        self.install_prefix = '/usr/local'
        self.common_configs = {}

    def get_include_path(self, include_path):
        if include_path == self.directory:
            return '.'
        if include_path.startswith(self.directory + '/'):
            return os.path.relpath(include_path, self.directory)
        return include_path

    def name_as_target(self, target):
        name = os.path.basename(target)
        return name, name

    relpath = CmakeGenerator.relpath
