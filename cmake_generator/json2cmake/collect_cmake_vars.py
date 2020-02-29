#! /usr/bin/env python3
import os
from os.path import abspath, dirname, basename, isfile
import subprocess
import re
import tempfile
import shutil

__all__ = ['generate_cmake_vars_file', 'CMAKE_VARS_PATH']
CWD = os.getcwd()
THIS_DIR = dirname(os.path.abspath(__file__))
PARENT_DIR = dirname(THIS_DIR)
ROOT_DIR = dirname(PARENT_DIR)
CMAKE_VARS_PATH = os.path.join(CWD, 'cmake-vars.txt')
CMAKE_FILE_HEADER = """
cmake_minimum_required(VERSION 3.10)
find_package(Qt5 COMPONENTS Core)
"""
CMAKE_FILE_BOTTOM = """
get_cmake_property(_variableNames VARIABLES)
foreach (_variableName ${_variableNames})
	message(STATUS "${_variableName}=${${_variableName}}")
endforeach()
"""


def generate_cmake_vars_file(cmake_vars_path):
	packages = set()
	regex = re.compile(r'^.*/Find([^/]*)\.cmake$')
	lines = subprocess.getoutput('locate /Find').splitlines(False)
	for line in lines:
		matched = regex.match(line)
		if matched:
			packages.add(matched.group(1))

	regex = re.compile(r'^.*/([^/]*)Config.cmake')
	lines = subprocess.getoutput('locate Config.cmake').splitlines(False)
	for line in lines:
		matched = regex.match(line)
		if matched:
			packages.add(matched.group(1))
	package_list = sorted(filter(lambda x: x.find('Qt53D') < 0 and x.find('GMock') < 0, packages))
	tmpdir = tempfile.mkdtemp(prefix="cmake-generator.", dir=CWD)
	print('using', tmpdir)
	cmake_lists_content = '\n'.join('find_package(%s QUIET)' % p for p in package_list)
	cmake_lists_file = open(os.path.join(tmpdir, 'CMakeLists.txt'), 'w')
	cmake_lists_file.write(CMAKE_FILE_HEADER + cmake_lists_content + CMAKE_FILE_BOTTOM)
	print(cmake_lists_content)
	os.chdir(tmpdir)
	output = subprocess.getoutput("cmake -G 'Unix Makefiles' .")
	print(output)
	open(cmake_vars_path, 'w').write(output)
	os.chdir(CWD)
	shutil.rmtree(tmpdir)



if __name__ == '__main__' or not isfile(CMAKE_VARS_PATH):
	generate_cmake_vars_file(CMAKE_VARS_PATH)
