import unittest
import os
from io import StringIO
from .utils import *
from ..utils import *
from ..converter import *
from ..database import *


class MockGeneratorAttribute:
    def __init__(self, item, obj):
        self.item = item
        self.obj = obj

    def __call__(self, *args, **kwargs):
        print('%s.%s(%s, %s)' % (self.obj.name, self.item, args, kwargs))


class MockCmakeGenerator(PathUtils):
    def __init__(self, directory, root_dir):
        PathUtils.__init__(self, directory, root_dir)
        self.name = os.path.basename(directory)

    def setup_output(self, output=None):
        return self.directory

    def __getattr__(self, item):
        return MockGeneratorAttribute(item, self)


class TestCmakeConverter(unittest.TestCase):
    def setUp(self):
        self.maxDiff = 10240
        cwd = '/git/gdb/gdbserver'
        self.output = StringIO()
        self.cxx_command = create_command(
            'clang++', cwd=cwd, linkage='OBJECT',
            compile_c_as_cxx=True,
            missing_depends={},
            includes=resolve_paths(['.', 'config', '..', '/usr/include'], cwd),
            definitions=['LOCALEDIR="/usr/local/share/locale"', "HAVE_CONFIG_H"],
            options=["-x c++", "-Wall", "-Werror", ],
        )

    def test_converter(self):
        db = CompilationDatabase(StringIO(), '/git/gdb/cmake-build-debug/compile_commands.json', '/git/gdb')
        converter = CmakeConverter(db, 'gdb', '/git/gdb')
        CmakeConverter.generators['gdb'] = MockCmakeGenerator('/git/gdb', '/git/gdb')
        CmakeConverter.generators['gdbserver'] = MockCmakeGenerator('/git/gdb/gdbserver', '/git/gdb')
        converter.convert()
        self.assertEqual(True, True)


if __name__ == '__main__':
    unittest.main()
