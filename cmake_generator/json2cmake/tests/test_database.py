import unittest
import os
from io import StringIO
from .utils import *
from ..utils import *
from ..database import *


class TestCompilationDatabase(unittest.TestCase):
    def test_db_parse_empty_json(self):
        infile = StringIO('[]')
        db = CompilationDatabase(infile, '/git/gdb/compile_commands.json')
        db.read()
        self.assertEqual(db.directory, '/git/gdb')
        self.assertEqual(db.root_dir, '/git/gdb')
        self.assertEqual(db.objects, {})
        self.assertEqual(db.linkings, {})
        self.assertEqual(db.targets, {})
        self.assertEqual(db.installs, {})
        self.assertEqual(db.command, [])
        self.assertEqual(db.install_command, [])

    def test_db_parse(self):
        infile = StringIO(r'''[
    {
		"directory": "/git/gdb",
		"command": "/usr/bin/g++ -g -O2 -I. -Iconfig -DTUI=1 -I/usr/include -Werror -c -o ada-lang.o ada-lang.c",
		"file": "ada-lang.c"
    },
    {}
]''')
        db = CompilationDatabase(infile, '/git/gdb/compile_commands.json')
        db.read()
        self.assertEqual(db.directory, '/git/gdb')
        self.assertEqual(db.root_dir, '/git/gdb')
        self.assertEqual(db.objects, {'/git/gdb/ada-lang.o': {'/git/gdb/ada-lang.c': 0}})
        self.assertEqual(db.linkings, {})
        self.assertEqual(db.targets, {0: {'/git/gdb/ada-lang.o': {'/git/gdb/ada-lang.c'}}})
        self.assertEqual(db.installs, {})
        self.assertEqual(len(db.command), 1)
        self.assertEqual(db.install_command, [])


if __name__ == '__main__':
    unittest.main()
