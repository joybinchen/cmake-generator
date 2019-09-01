import os
from io import StringIO
import unittest
from cmake_generator.json2cmake.tests.utils import *
from cmake_generator.json2cmake.utils import freeze, resolve, resolve_paths, relpath
from cmake_generator.json2cmake.command import *

command_line_cxx = [
    "/usr/bin/ccache",
    "-x", "c++", "-g", "-O2", "-I.", "-Iconfig",
    '-DLOCALEDIR="/usr/local/share/locale"',
    "-DHAVE_CONFIG_H",
    "-I..", "-I.", "-I../include",
    "-Wall", "-Wpointer-arith", "-Wno-unused", "-Wunused-value",
    "-Wunused-function", "-Wno-switch", "-Wno-char-subscripts",
    "-Wempty-body", "-Wno-sign-compare", "-Wno-mismatched-tags",
    "-Wno-error=deprecated-register",
    "-Wformat", "-Wformat-nonliteral", "-Werror",
    "-c", "-o", "dictionary.o",
    "-MT", "dictionary.o",
    "-MMD", "-MP", "-MF", "./.deps/dictionary.Tpo",
    "dictionary.c",
]

command_line_moc = [
    '/usr/lib/qt5/bin/moc',
    '',
    '-DHAVE_X11',
    '--include',
    'build/moc_predefs.h',
    '',
    '-DPROGRAM_VERSION="1.5.0-RC2+git"',
    '-I/usr/include',
    '../mainwindow.hh',
    '-o',
    'build/moc_mainwindow.cpp',
]


class TestCommand(unittest.TestCase):
    def setUp(self):
        self.output = StringIO()
        self.generator = MockCmakeGenerator(self.output, os.getcwd())
        self.maxDiff = 2048

    def test_command_cxx(self):
        """test class CmakeTarget"""
        output_text = ''
        self.assertEqual(self.output.getvalue(), output_text)
        cwd = "/git/gdb"
        source = "/git/gdb/dictionary.c"
        command_line = command_line_cxx
        command, target = parse_command(command_line, source, cwd)
        expected_target = resolve('dictionary.o', cwd)
        expected_command = create_command(
            'clang++', cwd=cwd, linkage='OBJECT',
            compile_c_as_cxx=True,
            missing_depends=set(),
            includes=resolve_paths(['.', 'config', '..', '../include'], cwd),
            definitions=['LOCALEDIR="/usr/local/share/locale"', "HAVE_CONFIG_H"],
            options=[
                "-x c++",
                "-Wall", "-Wpointer-arith", "-Wno-unused", "-Wunused-value",
                "-Wunused-function", "-Wno-switch", "-Wno-char-subscripts",
                "-Wempty-body", "-Wno-sign-compare", "-Wno-mismatched-tags",
                "-Wno-error=deprecated-register",
                "-Wformat", "-Wformat-nonliteral", "-Werror",
            ]
        )
        self.assertEqual(target, expected_target)
        self.assertEqual(command.__dict__, expected_command.__dict__)
        self.assertEqual(str(command), str(expected_command))
        self.assertEqual(freeze(command), freeze(expected_command))

        command_line = ' '.join(command_line_cxx)
        expected_command, expected_target = parse_command(command_line, source, cwd)
        self.assertEqual(target, expected_target)
        self.assertEqual(command.__dict__, expected_command.__dict__)
        self.assertEqual(str(command), str(expected_command))
        self.assertEqual(freeze(command), freeze(expected_command))

        x_pos = command_line_cxx.index('-x')
        command_line = ['/usr/bin/clang++', ] + command_line_cxx[1:x_pos] + command_line_cxx[x_pos+2:]
        command, target = parse_command(command_line, source, cwd)
        expected_command.options = expected_command.options[1:]
        self.assertEqual(target, expected_target)
        self.assertEqual(command.__dict__, expected_command.__dict__)
        self.assertEqual(str(command), str(expected_command))
        self.assertEqual(freeze(command), freeze(expected_command))

    def test_command_c(self):
        """test class CmakeTarget"""
        output_text = ''
        self.assertEqual(self.output.getvalue(), output_text)
        cwd = "/git/gdb"
        source = "/git/gdb/dictionary.c"
        x_pos = command_line_cxx.index('-x')
        command_line = command_line_cxx[:x_pos] + command_line_cxx[x_pos+2:]
        command, target = parse_command(command_line, source, cwd)
        expected_target = resolve('dictionary.o', cwd)
        expected_command = create_command(
            'clang', cwd=cwd, linkage='OBJECT',
            missing_depends=set(),
            includes=resolve_paths(['.', 'config', '..', '../include'], cwd),
            definitions=['LOCALEDIR="/usr/local/share/locale"', "HAVE_CONFIG_H"],
            options=[
                "-Wall", "-Wpointer-arith", "-Wno-unused", "-Wunused-value",
                "-Wunused-function", "-Wno-switch", "-Wno-char-subscripts",
                "-Wempty-body", "-Wno-sign-compare", "-Wno-mismatched-tags",
                "-Wno-error=deprecated-register",
                "-Wformat", "-Wformat-nonliteral", "-Werror",
            ]
        )
        self.assertEqual(target, expected_target)
        self.assertEqual(command.__dict__, expected_command.__dict__)
        self.assertEqual(str(command), str(expected_command))
        self.assertEqual(freeze(command), freeze(expected_command))

    def test_command_qmake_install(self):
        cwd = "/git/goldendict"
        command_line = "/usr/lib/qt5/bin/qmake -install qinstall -exe goldendict /usr/local/bin/goldendict"
        source = "goldendict"
        command, target = parse_command(command_line, source, cwd)
        expected_command = create_command(
            'qmake', cwd=cwd, linkage='INSTALL', type='EXECUTABLE',
            options=['-install qinstall -exe'],
            destination='/usr/local/bin',
        )
        self.assertEqual(target, '/usr/local/bin/goldendict')
        self.assertEqual(command.__dict__, expected_command.__dict__)
        self.assertEqual(str(command), str(expected_command))
        self.assertEqual(freeze(command), freeze(expected_command))

    def test_command_install(self):
        cwd = "/git/gdb/data-directory"
        command_line = "/usr/bin/install -c -m 644 ../syscalls/gdb-syscalls.dtd syscalls"
        source = "/git/gdb/syscalls/gdb-syscalls.dtd"
        command, target = parse_command(command_line, source, cwd)
        expected_command = create_command(
            'install', cwd=cwd, linkage='INSTALL', type='FILES',
            options=['-c', '-m 644'],
            destination='/git/gdb/data-directory/syscalls',
        )
        self.assertEqual(target, '/git/gdb/data-directory/syscalls')
        self.assertEqual(command.__dict__, expected_command.__dict__)
        self.assertEqual(str(command), str(expected_command))
        self.assertEqual(freeze(command), freeze(expected_command))
        cwd = "/git/gdb/gdbserver"
        command_line = "/usr/bin/install -c /git/gdb/gdb/gdbserver /usr/local/bin/x86_64-pc-linux-gdbserver"
        source = "/git/gdb/gdb/gdbserver"
        command, target = parse_command(command_line, source, cwd)
        expected_command = create_command(
            'install', cwd=cwd, linkage='INSTALL',
            options=['-c', ],
            destination='/usr/local/bin/x86_64-pc-linux-gdbserver',
        )
        self.assertEqual(target, '/usr/local/bin/x86_64-pc-linux-gdbserver')
        self.assertEqual(command.__dict__, expected_command.__dict__)
        self.assertEqual(str(command), str(expected_command))
        self.assertEqual(freeze(command), freeze(expected_command))

    def test_command_moc(self):
        cwd = '/git/goldendict'
        command_line = command_line_moc
        source = '/git/goldendict/mainwindow.hh'
        command, target = parse_command(command_line, source, cwd)
        command_line = ' '.join(command_line)
        command2, target2 = parse_command(command_line, source, cwd)
        self.assertEqual(target, target2)
        self.assertEqual(command.__dict__, command2.__dict__)
        expected_command = create_command(
            'moc', cwd=cwd, linkage='SOURCE',
            definitions=['HAVE_X11', 'PROGRAM_VERSION="1.5.0-RC2+git"'],
            includes=['/git/goldendict/build/moc_predefs.h', '/usr/include'],
        )
        self.assertEqual(target, '/git/goldendict/build/moc_mainwindow.cpp')
        self.assertEqual(command.__dict__, expected_command.__dict__)
        self.assertEqual(str(command), str(expected_command))
        self.assertEqual(freeze(command), freeze(expected_command))


if __name__ == '__main__':
    unittest.main()

