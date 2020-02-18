import os
from io import StringIO
import unittest
from .utils import *
from ..migration import *


class TestMigration(unittest.TestCase):
    def setUp(self):
        self.output = StringIO()
        self.generator = MockCmakeGenerator(self.output, os.getcwd())
        self.maxDiff = 1024

    def test_name_by_common_prefix(self):
        root_dir = '/git/NLP/Dictionary/Goldendict/goldendict.joybin_mod/Release'
        paths = [
            '/git/NLP/Dictionary/Goldendict/goldendict.joybin_mod/redist/goldendict.appdata.xml',
            '/git/NLP/Dictionary/Goldendict/goldendict.joybin_mod/redist/icons/goldendict.png',
        ]
        common_path = name_by_common_prefix(paths, root_dir)
        self.assertEqual(common_path, 'redist')
        root_dir = '/git/Tools/GNU-DevTools/gdb/'
        paths = [
            '/git/Tools/GNU-DevTools/gdb/contrib/xdx',
            '/git/Tools/GNU-DevTools/gdb/contrib/gdb-add-index.sh',
        ]
        common_path = name_by_common_prefix(paths, root_dir)
        self.assertEqual(common_path, 'contrib')
        paths = [
            '/git/Tools/GNU-DevTools/gdb/contrib/gdx',
            '/git/Tools/GNU-DevTools/gdb/contrib/gdb-add-index.sh',
        ]
        common_path = name_by_common_prefix(paths, root_dir)
        self.assertEqual(common_path, 'gd')

    def test_get_matched_parts(self):
        file_pattern = '/git/Tools/GNU-DevTools/gdb/%(0)s'
        files = [
            '/git/Tools/GNU-DevTools/gdb/gdb',
            '/git/Tools/GNU-DevTools/gdb/contrib/gdb-add-index.sh',
        ]
        matched = get_matched_parts(file_pattern, files)
        self.assertEqual(matched, ['gdb', 'contrib/gdb-add-index.sh'])

    def test_migrate_install_commands(self):
        install = {
            3: {"/git/goldendict/locale/ar_SA.qm": "/usr/local/share/goldendict/locale/ar_SA.qm"},
            5: {"/git/goldendict/locale/ay_WI.qm": "/usr/local/share/goldendict/locale/ay_WI.qm"},
            9: {"/git/goldendict/locale/be_BY.qm": "/usr/local/share/goldendict/locale/be_BY.qm"},
            11:{"/git/goldendict/locale/be_BY@latin.qm": "/usr/local/share/goldendict/locale/be_BY@latin.qm"},
            6:  {'/usr/local/bin/x86_64-pc-linux-gdb': '/git/gdb/gdb'},
            8:  {'/usr/local/bin/x86_64-pc-linux-gcore': '/git/gdb/gcore'},
        }
        migratables, install_commands = self.create_migratables(install)
        migrated = migrate_install_commands(migratables, install_commands, ('destination', 'id'))
        result3 = sorted(migrated[3].items())
        self.assertEqual(result3[0][0], ("/git/goldendict/locale/%(0)s.qm", "/usr/local/share/goldendict/locale/%(0)s.qm"))
        self.assertEqual(result3[0][1], [
            ("/git/goldendict/locale/ar_SA.qm", "/usr/local/share/goldendict/locale/ar_SA.qm"),
            ("/git/goldendict/locale/ay_WI.qm", "/usr/local/share/goldendict/locale/ay_WI.qm"),
            ("/git/goldendict/locale/be_BY.qm", "/usr/local/share/goldendict/locale/be_BY.qm"),
            ("/git/goldendict/locale/be_BY@latin.qm", "/usr/local/share/goldendict/locale/be_BY@latin.qm"),
        ])

        install = {
            6:  {'/usr/local/bin/x86_64-pc-linux-gdb': '/git/gdb/gdb'},
            7:  {'/usr/local/include/gdb/jit-reader.h': '/git/gdb/jit-reader.h'},
            8:  {'/usr/local/bin/x86_64-pc-linux-gcore': '/git/gdb/gcore'},
            9:  {'/usr/local/bin/x86_64-pc-linux-gdb-add-index': '/git/gdb/contrib/gdb-add-index.sh'},
            10: {'/usr/local/share/man/man1/x86_64-pc-linux-gdb.1': '/git/gdb/doc/gdb.1'},
            11: {'/usr/local/share/man/man1/x86_64-pc-linux-gdbserver.1': '/git/gdb/doc/gdbserver.1'},
            12: {'/usr/local/share/man/man1/x86_64-pc-linux-gcore.1': '/git/gdb/doc/gcore.1'},
            13: {'/usr/local/share/man/man1/x86_64-pc-linux-gdb-add-index.1': '/git/gdb/doc/gdb-add-index.1'},
            14: {'/usr/local/share/man/man5/x86_64-pc-linux-gdbinit.5': '/git/gdb/doc/gdbinit.5'},
            15: {'/usr/local/lib/libinproctrace.so': '/git/gdb/gdbserver/libinproctrace.so'},
            16: {'/usr/local/bin/x86_64-pc-linux-gdbserver': '/git/gdb/gdbserver/gdbserver'},
        }
        migratables, install_commands = self.create_migratables(install)
        migrated = migrate_install_commands(migratables, install_commands, ('destination', 'id'))
        self.assertEqual(len(migrated), 6)
        result6 = sorted(migrated[6].items())
        self.assertEqual(result6[0][0], ('/usr/local/bin/x86_64-pc-linux-%(0)s', '/git/gdb/%(0)s'))
        self.assertEqual(result6[0][1], [
            ('/usr/local/bin/x86_64-pc-linux-gdb', '/git/gdb/gdb'),
            ('/usr/local/bin/x86_64-pc-linux-gcore', '/git/gdb/gcore'),
        ])
        result10 = sorted(migrated[10].items())
        self.assertEqual(result10[0][0], ('/usr/local/share/man/man1/x86_64-pc-linux-%(0)s.1', '/git/gdb/doc/%(0)s.1'))
        self.assertEqual(result10[0][1], [
            ('/usr/local/share/man/man1/x86_64-pc-linux-gdb.1', '/git/gdb/doc/gdb.1'),
            ('/usr/local/share/man/man1/x86_64-pc-linux-gdbserver.1', '/git/gdb/doc/gdbserver.1'),
            ('/usr/local/share/man/man1/x86_64-pc-linux-gcore.1', '/git/gdb/doc/gcore.1'),
            ('/usr/local/share/man/man1/x86_64-pc-linux-gdb-add-index.1', '/git/gdb/doc/gdb-add-index.1'),
        ])
        self.assertEqual(result10[1][0], ('/usr/local/share/man/man5/x86_64-pc-linux-gdbinit.5', ''))
        self.assertEqual(result10[1][1], [
            ('/usr/local/share/man/man5/x86_64-pc-linux-gdbinit.5', '/git/gdb/doc/gdbinit.5'),
        ])

    @staticmethod
    def create_migratables(install):
        install_commands = []
        cwd = '/git/Tools/GNU-DevTools/gdb/data-directory'
        size = max(install.keys())+1
        for i in range(0, size):
            destination, source = list(install.get(i, {'%s/%s' % (cwd, i): '%s/%s' % (cwd, i)}).items())[0]
            options = ['-c', ] if os.path.splitext(source)[1] else ['-c', '-m 755']
            directory = os.path.dirname(source)
            cmd = create_command('install', id=i, cwd=directory, options=options, destination=destination)
            install_commands.append(cmd)
        migratables = [(k, list(v.keys())[0], list(v.values())[0]) for k, v in install.items()]
        return migratables, install_commands


if __name__ == '__main__':
    unittest.main()

