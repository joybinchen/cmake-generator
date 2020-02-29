import os
from io import StringIO
import unittest
from .utils import *
from ..utils import *
from ..generator import *


class TestCmakeGenerator(unittest.TestCase):
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

    def test_executable(self):
        output_text = ''
        self.assertEqual(self.output.getvalue(), output_text)
        generator = CmakeGenerator('gdbserver', '/git/gdb/gdbserver', '/git/gdb')
        generator.set_install_prefix('/usr/local')
        generator.output_linked_target(self.cxx_command, ['abc.c', 'def.cpp'],
                                       '/git/gdb/gdbserver/libdoit.a', 'STATIC', 'libdoit', [])
#       generator.output_linked_target(self.cxx_command, ['abc.c', 'def.cpp'],
#                                      '/git/gdb/gdbserver/libdoit.so', 'SHARED', 'libdoit', [])
        generator.output_linked_target(self.cxx_command, ['main.cpp', 'libdoit.a'],
                                       '/git/gdb/gdbserver/doit', 'EXECUTABLE', 'doit',
                                       ['/git/gdb/gdbserver/libdoit.a', ])
        generator.setup_output(self.output)

        generator.write_project_header()
        generator.output.write(generator.stream.getvalue())
        output_text += """cmake_minimum_required(VERSION 2.8.8)
project(gdbserver LANGUAGES C CXX)

"""
        self.assertEqual(self.output.getvalue(), output_text)

        generator.collect_common_configs()
        self.assertEqual(generator.common_configs, {
            'options': ['-x c++', '-Wall', '-Werror', ],
            'link_options': [],
            'definitions': ['LOCALEDIR="/usr/local/share/locale"', 'HAVE_CONFIG_H'],
            'includes': ['/git/gdb/gdbserver', '/git/gdb/gdbserver/config', '/git/gdb', '/usr/include', ],
            'iquote_includes': [],
            'system_includes': [],
        })
        generator.write_common_configs()

        output_text += """
add_compile_options(  -x c++ -Wall -Werror)


add_compile_definitions( 
\tLOCALEDIR="/usr/local/share/locale"
\tHAVE_CONFIG_H
)

set(INCLUDE_DIRS  . config .. /usr/include)
list(REMOVE_DUPLICATES  INCLUDE_DIRS)
include_directories(  ${INCLUDE_DIRS})


"""
        self.assertEqual(self.output.getvalue(), output_text)

        output_text += """
set(LIBDOIT_SRCS abc.c def.cpp)
set_source_files_properties(${LIBDOIT_SRCS} PROPERTIES LANGUAGE CXX)
add_library(libdoit STATIC ${LIBDOIT_SRCS})
set_property(TARGET libdoit PROPERTY LIBRARY_OUTPUT_NAME libdoit.a)

set(DOIT_SRCS libdoit.a main.cpp)
set_source_files_properties(${DOIT_SRCS} PROPERTIES LANGUAGE CXX)
add_executable(doit ${DOIT_SRCS})
add_dependencies(doit libdoit)
"""
        generator.write_targets()
        self.assertEqual(self.output.getvalue(), output_text)


if __name__ == '__main__':
    unittest.main()
