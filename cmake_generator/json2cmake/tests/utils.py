import os
from cmake_generator.json2cmake.command import CompileCommand

__all__ = ['create_command', 'MockCmakeGenerator']


def create_command(compiler, **kwargs):
    command = CompileCommand(compiler, os.getcwd())
    command.__dict__.update(kwargs)
    return command


class MockCmakeGenerator:
    def __init__(self, output, directory):
        self.output = output
        self.directory = directory
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

    def relpath(self, path):
        return os.path.relpath(path, self.directory)
