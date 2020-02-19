import os
from io import StringIO
import unittest
from .utils import *
from ..target import *


class TestCmakeTarget(unittest.TestCase):
    def setUp(self):
        self.output = StringIO()
        self.generator = MockCmakeGenerator(self.output, os.getcwd())
        self.maxDiff = 1024

    def test_executable(self):
        """test class CmakeTarget"""
        output_text = ''
        self.assertEqual(self.output.getvalue(), output_text)
        command = create_command('clang++', includes=['/opt/abc'])
        target = ExecutableTarget(command, 'abc', ['abc.cc', 'libc.c'])
        target.add_destination('/usr/local/bin')
        target.bind(self.generator)
        target.output_target()
        output_text += '''
set(ABC_SRCS abc.cc libc.c)
add_executable(abc ${ABC_SRCS})
target_include_directories(abc PRIVATE /opt/abc)
install(TARGETS abc DESTINATION bin)
'''
        self.assertEqual(self.output.getvalue(), output_text)

    def test_library(self):
        """test class CmakeTarget"""
        output_text = ''
        self.assertEqual(self.output.getvalue(), output_text)

        command = create_command('clang++', includes=['/opt/abc'])
        target = LibraryTarget(command, 'abc', ['abc.cc', 'libc.c'])
        target.bind(self.generator)
        target.output_target()
        output_text += '''
set(ABC_SRCS abc.cc libc.c)
add_library(abc STATIC ${ABC_SRCS})
target_include_directories(abc PRIVATE /opt/abc)
'''
        self.assertEqual(self.output.getvalue(), output_text)

        target = LibraryTarget(command, 'abc', ['abc.cc', 'libc.c'], 'SHARED')
        target.bind(self.generator)
        target.output_target()
        output_text += '''
set(ABC_SRCS abc.cc libc.c)
add_library(abc SHARED ${ABC_SRCS})
target_include_directories(abc PRIVATE /opt/abc)
'''
        self.assertEqual(self.output.getvalue(), output_text)

    def test_compiler_options(self):
        """test includes attribute for targets"""
        output_text = ''
        self.assertEqual(self.output.getvalue(), output_text)

        command = create_command('clang++', options=['--test', 'something', 'short'])
        target = ExecutableTarget(command, 'abc2', ['libx.c', 'abc2.cc', ])
        target.bind(self.generator)
        target.output_target()
        output_text += '''
set(ABC2_SRCS abc2.cc libx.c)
add_executable(abc2 ${ABC2_SRCS})
target_compile_options(abc2 PRIVATE --test something short)
'''
        self.assertEqual(self.output.getvalue(), output_text)

        command = create_command('clang++', options=[
            '--test', 'something very very long', 'something very long'])
        target = ExecutableTarget(command, 'abc2', ['libx.c', 'abc2.cc', ])
        target.bind(self.generator)
        target.output_target()
        output_text += '''
set(ABC2_SRCS abc2.cc libx.c)
add_executable(abc2 ${ABC2_SRCS})
target_compile_options(abc2 PRIVATE
\t--test
\tsomething very very long
\tsomething very long
)
'''
        self.assertEqual(self.output.getvalue(), output_text)

    def test_compiler_definitions(self):
        """test includes attribute for targets"""
        output_text = ''
        self.assertEqual(self.output.getvalue(), output_text)

        command = create_command('clang++', definitions=['-Dtest=something', '-Dshort'])
        target = ExecutableTarget(command, 'abc2', ['libx.c', 'abc2.cc', ])
        target.bind(self.generator)
        target.output_target()
        output_text += '''
set(ABC2_SRCS abc2.cc libx.c)
add_executable(abc2 ${ABC2_SRCS})
target_compile_definitions(abc2 PRIVATE -Dtest=something -Dshort)
'''
        self.assertEqual(self.output.getvalue(), output_text)

        command = create_command('clang++', definitions=[
            '--test', 'something very long', 'something very very long'])
        target = ExecutableTarget(command, 'abc2', ['libx.c', 'abc2.cc', ])
        target.bind(self.generator)
        target.output_target()
        output_text += '''
set(ABC2_SRCS abc2.cc libx.c)
add_executable(abc2 ${ABC2_SRCS})
target_compile_definitions(abc2 PRIVATE
\t--test
\tsomething very long
\tsomething very very long
)
'''
        self.assertEqual(self.output.getvalue(), output_text)

    def test_includes(self):
        """test includes attribute for targets"""
        output_text = ''
        self.assertEqual(self.output.getvalue(), output_text)

        command = create_command('clang++', system_includes=['/usr/include/abc', '/usr/include/def', '/opt/abc', ])
        target = ExecutableTarget(command, 'abc2', ['libx.c', 'abc2.cc', ])
        target.bind(self.generator)
        target.output_target()
        output_text += '''
set(ABC2_SRCS abc2.cc libx.c)
add_executable(abc2 ${ABC2_SRCS})
target_include_directories(abc2 SYSTEM PRIVATE
\t/usr/include/abc
\t/usr/include/def
\t/opt/abc
)
'''
        self.assertEqual(self.output.getvalue(), output_text)

        command = create_command('clang++', iquote_includes=['/opt/abc'])
        target = ExecutableTarget(command, 'abc2', ['libx.c', 'abc2.cc', ])
        target.bind(self.generator)
        target.output_target()
        output_text += '''
set(ABC2_SRCS abc2.cc libx.c)
add_executable(abc2 ${ABC2_SRCS})
target_include_directories(abc2 BEFORE PRIVATE /opt/abc)
'''
        self.assertEqual(self.output.getvalue(), output_text)

        command = create_command('clang++', includes=['/opt/abc'], iquote_includes=['/opt/qout'],
                                 system_includes=['/usr/include/abc'])
        target = ExecutableTarget(command, 'abc2', ['libx.c', 'abc2.cc', ])
        target.bind(self.generator)
        target.output_target()
        output_text += '''
set(ABC2_SRCS abc2.cc libx.c)
add_executable(abc2 ${ABC2_SRCS})
target_include_directories(abc2 PRIVATE /opt/abc)
target_include_directories(abc2 SYSTEM PRIVATE /usr/include/abc)
target_include_directories(abc2 BEFORE PRIVATE /opt/qout)
'''
        self.assertEqual(self.output.getvalue(), output_text)


class TestInstallTarget(unittest.TestCase):
    def setUp(self):
        self.output = StringIO()
        self.generator = MockCmakeGenerator(self.output, os.getcwd())
        self.maxDiff = 1024

    def test_install(self):
        output_text = ''
        self.assertEqual(self.output.getvalue(), output_text)
        command = create_command('install', options=['-c', '-m', '644'])
        target = InstallTarget(command, '/usr/local/shared', [os.getcwd() + '/images/abc.png', 'styles/good.css'])
        target.bind(self.generator)
        target.output_target()
        output_text += '\ninstall(FILES images/abc.png styles/good.css DESTINATION shared)\n'
        self.assertEqual(self.output.getvalue(), output_text)

        target = InstallTarget(command, '/usr/shared', [os.getcwd() + '/images/abc.png', 'styles/good.css'])
        target.bind(self.generator)
        target.output_target()
        output_text += '\ninstall(FILES images/abc.png styles/good.css DESTINATION /usr/shared)\n'
        self.assertEqual(self.output.getvalue(), output_text)


class TestCustomCommandTarget(unittest.TestCase):
    def setUp(self):
        self.output = StringIO()
        self.generator = MockCmakeGenerator(self.output, os.getcwd())
        self.maxDiff = 1024

    def test_custom_command(self):
        output_text = ''
        self.assertEqual(self.output.getvalue(), output_text)
        command = create_command('moc', options=['--include build/moc_predref.h', '-I/usr/include', '-DHAS_X11'])
        target = CustomCommandTarget(command, 'build/moc_mainwindow.cpp', ['main_window.hh'])
        target.bind(self.generator)
        target.output_target()
        output_text += '''
add_custom_command(OUTPUT build/moc_mainwindow.cpp
\tCOMMAND moc --include build/moc_predref.h -I/usr/include -DHAS_X11
\t${CMAKE_CURRENT_SOURCE_DIR}/main_window.hh
\t-o build/moc_mainwindow.cpp
)
'''
        self.assertEqual(self.output.getvalue(), output_text)

        command = create_command('dbus-binding-tool', options=['--mode=glib-server', ])
        target = CustomCommandTarget(command, 'device-dbus-glue.h', ['device.xml'])
        target.bind(self.generator)
        target.output_target()
        output_text += '''
add_custom_command(OUTPUT device-dbus-glue.h
\tCOMMAND dbus-binding-tool --mode=glib-server
\t${CMAKE_CURRENT_SOURCE_DIR}/device.xml
\t--output=device-dbus-glue.h
)
'''
        self.assertEqual(self.output.getvalue(), output_text)

    def test_moc_command(self):
        output_text = ''
        self.assertEqual(self.output.getvalue(), output_text)
        command = create_command('moc', linkage='SOURCE',
                                 cwd='/git/goldendict',
                                 definitions=['HAVE_X11', 'PROGRAM_VERSION="1.5.0-RC2+git"'],
                                 includes=['/git/goldendict/build/moc_predefs.h', '/usr/include'])
        target = CustomCommandTarget(command, 'build/moc_mainwindow.cpp', ['main_window.hh'])
        generator = MockCmakeGenerator(self.output, '/git/goldendict')
        target.bind(generator)
        target.output_target()
        output_text += '''
add_custom_command(OUTPUT build/moc_mainwindow.cpp
\tCOMMAND moc --include ${CMAKE_CURRENT_SOURCE_DIR}/build/moc_predefs.h -I/usr/include -DHAVE_X11 -DPROGRAM_VERSION="1.5.0-RC2+git"
\t${CMAKE_CURRENT_SOURCE_DIR}/main_window.hh
\t-o build/moc_mainwindow.cpp
)
'''
        self.assertEqual(self.output.getvalue(), output_text)



class TestWrappedTarget(unittest.TestCase):
    def setUp(self):
        self.output = StringIO()
        self.generator = MockCmakeGenerator(self.output, os.getcwd())
        self.maxDiff = 1024

    def test_install(self):
        output_text = ''
        self.assertEqual(self.output.getvalue(), output_text)
        command = create_command('install', options=['-c', '-m', '644'])
        child_target = InstallTarget(command, '/usr/local/shared', ['styles/good%(0)s.css'])
        target = ForeachTargetWrapper(command, 'X', {'abc', 'bef', 'n'})
        target.append_child(child_target)
        self.assertEqual(len(target.children), 1)
        self.assertEqual(target.children[0].indent, 1)
        target.bind(self.generator)
        self.assertEqual(target.children[0].output.indent, '\t')
        target.children[0].output_target({'0': '${Y}'})
        output_text += '''\n\tinstall(FILES styles/good${Y}.css DESTINATION shared)'''
        self.assertEqual(self.output.getvalue(), output_text)

        target.output_target()
        output_text += '''
foreach(X abc bef n)
\tinstall(FILES styles/good${X}.css DESTINATION shared)
endforeach(X)
'''
        self.assertEqual(self.output.getvalue(), output_text)


if __name__ == '__main__':
    unittest.main()
