import os
import re
import subprocess
if __name__ != '__main__':
    from .collect_cmake_vars import *
else:
    from cmake_generator.json2cmake.collect_cmake_vars import *

__all__ = ['PKG_CONFIG_LIB2PKGS', 'PKG_CONFIG_LIBS',
           'PKG_CONFIG_INCLUDE2PKGS', 'PKG_CONFIG_INCLUDE_DIRS',
           'CMAKE_LIBS', 'CMAKE_PATH_MAP', 'CMAKE_LIBRARIES', 'CMAKE_INCLUDE_DIRS']

THIS_DIR = os.path.dirname(os.path.abspath(__file__))
PARENT_DIR = os.path.dirname(THIS_DIR)
ROOT_DIR = os.path.dirname(PARENT_DIR)
INCLUDE_NAME_PATTERN = re.compile(r'^(\w+)_INCLUDE_DIRS?$')
LIBRARY_NAME_PATTERN = re.compile(r'^(\w+)_LIBRAR(Y|IES)$')
PKG_CONFIG_LIBS = {}
PKG_CONFIG_INCLUDE_DIRS = {}
PKG_CONFIG_LIB2PKGS = {}
PKG_CONFIG_INCLUDE2PKGS = {}
CMAKE_LIBS = {}
CMAKE_INCLUDE_DIRS = {}


def get_pkg_config_info(pkg_config_vars_path):
    pcs = subprocess.getoutput('pkg-config --list-all').splitlines(False)
    pcs = list(map(lambda x: x.split(' ', 1)[0], pcs))
    lines = []
    for pc in pcs:
        if not pc: continue
        try:
            command = 'pkg-config --libs ' + pc
            result = subprocess.getoutput(command).split(' ')
            libs = []
            for lib in result:
                if lib.startswith('-l'):
                    lib = os.path.normpath(lib[2:])
                    if lib: libs.append(lib)
            lines.append('%s_LIBRARIES=%s\n' % (pc, ';'.join(libs)))

            includes = []
            command = 'pkg-config --cflags ' + pc
            result = subprocess.getoutput(command).split(' ')
            for cflag in result:
                if cflag.startswith('-I'):
                    cflag = os.path.normpath(cflag[2:])
                    if cflag: includes.append(cflag)
            lines.append('%s_INCLUDE_DIRS=%s\n' % (pc, ';'.join(includes)))
        except:
            import traceback
            traceback.print_exc()
            print(command, result)
    pkg_config_vars_output = open(pkg_config_vars_path, 'w')
    pkg_config_vars_output.writelines(lines)
    pkg_config_vars_output.close()


def update_pkg_config_libs():
    pkg_config_vars_path = os.path.join(ROOT_DIR, 'pkg-config-vars.txt')
    if not os.path.isfile(pkg_config_vars_path):
        get_pkg_config_info(pkg_config_vars_path)
    lines = open(pkg_config_vars_path).readlines()
    for line in lines:
        line = line.strip()
        if not line: continue
        name, value = line.split('=', 1)
        if name.endswith('_LIBRARIES'):
            package = name[:-10]
            result = value.split(';')
            PKG_CONFIG_LIBS[package] = result
            for lib in result:
                pkgs = PKG_CONFIG_LIB2PKGS.setdefault(lib, set())
                pkgs.add(package)
                print('pkg-config --libs %s ==> %s' % (package, lib))

        if name.endswith('_INCLUDE_DIRS'):
            package = name[:-13]
            result = value.split(';')
            PKG_CONFIG_INCLUDE_DIRS[package] = result
            for include in result:
                pkgs = PKG_CONFIG_INCLUDE2PKGS.setdefault(include, set())
                pkgs.add(package)
                print('pkg-config --cflags %s ==> %s' % (package, include))


def extract_cmake_vars_to_index(cmake_vars_path):
    lines = open(cmake_vars_path).readlines()
    include_index = {}
    library_index = {}
    lineno = 0
    for line in lines:
        lineno += 1
        if not line.startswith('-- '): continue
        if line.find('=') <= 0: continue
        line = line.rstrip()[3:]
        name, value = line.split('=', 1)
        matched = INCLUDE_NAME_PATTERN.match(name)
        parts = value.split(';')
        striped_parts = set()
        for p in parts:
            if p.endswith('-NOTFOUND'): continue
            p = os.path.normpath(p)
#            if not p.startswith('/'): continue
            if p in ('/usr/lib/x86_64-linux-gnu/qt5/mkspecs/linux-g++', ): continue
            if p in ('', '.', '/usr/include', '/usr/local/include'): continue
            striped_parts.add(p)
        if not striped_parts: continue
        value = ';'.join(striped_parts)
        if matched is not None:
            sname = name.replace('_INCLUDE_DIRS', '_INCLUDE_DIR')
            if sname != name:
                includes = include_index.get(sname, None)
                if includes is not None:
                    continue
            lname = sname.replace('_INCLUDE_DIR', '_INCLUDE_DIRS')
            if lname != name:
                includes = include_index.get(lname, None)
                if includes is not None:
                    include_index.pop(lname)
            include_index[name] = value
        matched = LIBRARY_NAME_PATTERN.match(name)
        if matched is not None:
            sname = name.replace('_LIBRARIES', '_LIBRARY')
            lname = sname.replace('_LIBRARY', '_LIBRARIES')
            if sname != name:
                libraries = library_index.get(sname, None)
                if libraries is not None:
                    continue
            if lname != name:
                libraries = library_index.get(lname, None)
                if libraries is not None:
                    library_index.pop(lname)
            library_index[name] = value
    return include_index, library_index


def extract_include_mapping(include_index):
    global CMAKE_INCLUDE_DIRS
    items = sorted(include_index.items())
    include2pkg = {}
    CMAKE_INCLUDE_DIRS = {}
    for name, value in items:
        matched = INCLUDE_NAME_PATTERN.match(name)
        if matched is None:
            continue
        pkg_name = matched.group(1)
        if pkg_name.endswith('_OWN_PRIVATE') and pkg_name.startswith('Qt5'): continue
        if pkg_name.endswith('_OWN') and pkg_name.startswith('_Qt5'): continue
        dirs = value.split(';')
        includes = CMAKE_INCLUDE_DIRS.get(pkg_name, {})
        for d in dirs:
            if not d: continue
            # if d in ('/include', '/usr/include', '/usr/local/include', '/usr/include/x86_64-linux-gnu'): continue
            include2pkg.setdefault(d, {})[pkg_name] = name
            CMAKE_INCLUDE_DIRS.setdefault(pkg_name, includes)
            if d not in includes:
                includes[d] = name
            else:
                prev_name = includes[d]
                if prev_name.startswith(name):
                    includes[d] = name
                elif name.startswith(prev_name):
                    pass
                elif len(name) < len(prev_name):
                    includes[d] = name
            print('%s => %s %s' % (d, pkg_name, name))
        print(pkg_name, "inc=>>", includes)
        continue
    include2multipkg = dict(filter(lambda x: len(x[1]) > 1, include2pkg.items()))
    pkg2multiinclude = dict(filter(lambda x: len(x[1]) > 1, CMAKE_INCLUDE_DIRS.items()))
    return include2pkg, CMAKE_INCLUDE_DIRS


def extract_library_mapping(library_index):
    global CMAKE_LIBRARIES
    library2pkg = {}
    CMAKE_LIBRARIES = {}
    for name, value in library_index.items():
        matched = LIBRARY_NAME_PATTERN.match(name)
        if matched is None:
            continue
        if name.endswith("_LINK_LIBRARIES"): continue
        pkg_name = matched.group(1)
        if pkg_name in ('CHECK_LIBRARY_EXISTS', ): continue
        if pkg_name.endswith('_STATIC'):
            pkg_name = pkg_name[:-7]
        if name.startswith('PC_') and name.endswith('_LIBRARIES'): continue
        paths = value.split(';')
        libraries = CMAKE_LIBRARIES.get(pkg_name, {})
        for path in paths:
            if not path: continue
            if path in ('/lib', '/usr/lib', '/usr/local/lib', '/lib/ld-linux.so.2', '/usr/lib/x86_64-linux-gnu/libstdc++.so.6'): continue
            if not path.startswith('/'):
                if path in ('FALSE', 'dl', '-pthread'): continue
                if path.startswith('<'): continue
            libname = os.path.splitext(os.path.basename(path))[0]
            if libname.startswith('lib'): libname = libname[3:]
            libname = libname.replace(':', '')
            pkgs = library2pkg.get(path, {})
            for pkg, n in list(pkgs.items()):
                if pkg.upper() == path:
                    if n.upper() == name:
                        pkgs.pop(pkg)
                        prev_libraries = CMAKE_LIBRARIES.get(pkg, None)
                        if prev_libraries is not None:
                            prev_libraries.pop(path)
                            if not prev_libraries:
                                CMAKE_LIBRARIES.pop(pkg)
                elif pkg == pkg_name.upper():
                    path = None
            if path is None: continue
            pkgs[pkg_name] = name
            library2pkg.setdefault(path, pkgs)
            library2pkg.setdefault(libname, pkgs)
            CMAKE_LIBRARIES.setdefault(pkg_name, libraries)
            if path not in libraries:
                libraries[path] = name
            else:
                prev_name = libraries[path]
                if prev_name.startswith(name):
                    libraries[path] = name
                elif name.startswith(prev_name):
                    pass
                elif len(name) < len(prev_name):
                    libraries[path] = name
            print('%s => %s %s' % (path, pkg_name, name))
        if path: print(pkg_name, "lib=>>", libraries)
        continue
    library2multipkg = dict(filter(lambda x: len(x[1]) > 1, library2pkg.items()))
    pkg2multilibrary = dict(filter(lambda x: len(x[1]) > 1, CMAKE_LIBRARIES.items()))
    return library2pkg, CMAKE_LIBRARIES


def extract_include_lib_map(include2lib, lib2include, library2lib, lib2library):
    global CMAKE_PATH_MAP
    CMAKE_PATH_MAP = {}
    for library, libs in library2lib.items():
        include_dict = {}
        for lib in libs:
            includes = lib2include.get(lib, {})
            CMAKE_PATH_MAP.setdefault((library, None), {})[lib] = includes
            for path, var_name in includes.items():
                if path not in include_dict:
                    include_dict[path] = var_name
                libname = os.path.splitext(os.path.basename(library))[0]
                if libname.startswith('lib'): libname = libname[3:]
                libname = libname.replace(':', '')
                key = libname, path
                if key not in CMAKE_PATH_MAP:
                    CMAKE_PATH_MAP[key] = lib
                other_lib = CMAKE_PATH_MAP[key]
                if other_lib != lib:
                    if other_lib.find(lib) >= 0:
                        CMAKE_PATH_MAP[key] = lib
                    elif lib.find(other_lib) >= 0:
                        CMAKE_PATH_MAP[key] = other_lib
                    else:
                        dict_len = len(include_dict)

    for include, libs in include2lib.items():
        library_dict = {}
        for lib in libs:
            libraries = lib2library.get(lib, {})
            CMAKE_PATH_MAP.setdefault((None, include), {})[lib] = libraries
            for path, var_name in libraries.items():
                if path not in library_dict:
                    library_dict[path] = var_name
                libname = os.path.splitext(os.path.basename(path))[0]
                if libname.startswith('lib'): libname = libname[3:]
                libname = libname.replace(':', '')
                key = libname, include
                if key not in CMAKE_PATH_MAP:
                    CMAKE_PATH_MAP[key] = lib
                other_lib = CMAKE_PATH_MAP[key]
                if other_lib != lib:
                    if other_lib.find(lib) >= 0:
                        CMAKE_PATH_MAP[key] = lib
                    elif lib.find(other_lib) >= 0:
                        CMAKE_PATH_MAP[key] = other_lib
                    else:
                        dict_len = len(library_dict)
    for inc_lib, libraries in CMAKE_PATH_MAP.items():
        if len(libraries) == 1: continue
        if not isinstance(libraries, dict): continue
        for lib, var_name in list(libraries.items()):
            if not var_name:
                libraries.pop(lib)
    return CMAKE_PATH_MAP


def update_cmake_libs():
    for module in QT5MODULES:
        CMAKE_LIBS['Qt5' + module] = ('Qt5', module, 'Qt5::' + module, 'Qt5%s_INCLUDE_DIR' % module)

def update_cmake_path_map():
    global CMAKE_PATH_MAP
    global CMAKE_LIBRARIES
    global CMAKE_INCLUDE_DIRS
    if not os.path.isfile(CMAKE_VARS_PATH):
        generate_cmake_vars_file(CMAKE_VARS_PATH)

    include_index, library_index = extract_cmake_vars_to_index(CMAKE_VARS_PATH)
    include2lib, CMAKE_INCLUDE_DIRS = extract_include_mapping(include_index)
    library2lib, CMAKE_LIBRARIES = extract_library_mapping(library_index)
    CMAKE_PATH_MAP = extract_include_lib_map(include2lib, CMAKE_INCLUDE_DIRS, library2lib, CMAKE_LIBRARIES)
    return CMAKE_PATH_MAP, CMAKE_LIBRARIES, CMAKE_INCLUDE_DIRS

def reduce_cmake_libs(lib2include, include2lib):
    reduced = True
    while reduced:
        single_mapping_includes = dict(filter(lambda x: len(x[1])<=1, include2lib.items()))
        reduced = False
        for include, lib_names in single_mapping_includes.items():
            for lib in lib_names:
                includes = lib2include[lib]
                if len(includes) > 1 and include in includes:
                    includes.pop(include)
                    reduced = True
        single_mapping_libs = dict(filter(lambda x: len(x[1])<=1, lib2include.items()))
        for lib, include_names in single_mapping_libs.items():
            for include in include_names:
                includes = include2lib[include]
                if len(includes) > 1 and lib in includes:
                    includes.pop(lib)
                    reduced = True
    reduced = False
    includeset2libs = {}
    multiple_mapping_libs = dict(filter(lambda x: len(x[1]) > 1, lib2include.items()))
    for lib, includes in lib2include.items():
        frozen_includes = frozenset(includes.keys())
        includeset2libs.setdefault(frozen_includes, set()).add(lib)
    multiple_mapping_includeset = dict(filter(lambda x: len(x[1]) > 1, includeset2libs.items()))
    for includeset, libs in multiple_mapping_includeset.items():
        shortest_lib = next(iter(libs))
        for lib in libs:
            if len(lib) < len(shortest_lib):
                shortest_lib = lib
        default_include = lib2include[shortest_lib]
        for lib in libs:
            prev_include = lib2include.get(lib, None)
            if prev_include is not None:
                lib2include[lib] = default_include


    multiple_mapping_includes = dict(filter(lambda x: len(x[1]) > 1, include2lib.items()))
    include2max_mapping_lib = {}
    for include, lib_names in multiple_mapping_includes.items():
        max_mapping_lib = ""
        max_count = 0
        lib2include_len = {}
        lib2includes = {}
        for lib in lib_names:
            includes = lib2include[lib]
            count = len(includes)
            lib2include_len[lib] = count
            lib2includes[lib] = includes
            if max_count < count:
                max_count = count
                max_mapping_lib = lib
            elif max_count == count:
                if len(lib) < len(max_mapping_lib):
                    max_mapping_lib = lib
        include2max_mapping_lib[include] = max_mapping_lib
    for include, max_mapping_lib in include2max_mapping_lib.items():
        includes = lib2include[max_mapping_lib]
        if len(includes) > 1 and include in includes:
            includes.pop(include)
            reduced = True
    import pprint
    pprint.pprint(include2lib)
    pprint.pprint(lib2include)


QT5MODULES = (
    "3DAnimation", "3DCore", "3DExtras", "3DInput", "3DLogic", "3DQuick", "3DQuickAnimation",
    "3DQuickExtras", "3DQuickInput", "3DQuickRender", "3DQuickScene2D", "3DRender", "Bluetooth",
    "Charts", "Concurrent", "Contacts", "Core", "DBus", "Designer", "GStreamer", "Gui", "Help",
    "LinguistTools", "Location", "Multimedia", "MultimediaWidgets", "Network", "Nfc", "OpenGL",
    "OpenGLExtensions", "Organizer", "Positioning", "PrintSupport", "Qml", "Quick", "QuickControls2",
    "QuickTest", "QuickWidgets", "Script", "ScriptTools", "Sensors", "SerialPort", "Sql", "Svg",
    "Test", "TextToSpeech", "UiPlugin", "UiTools", "Versit", "VersitOrganizer", "WaylandClient",
    "WaylandCompositor", "WebChannel", "WebEngine", "WebEngineCore", "WebEngineWidgets", "WebKit",
    "WebKitWidgets", "WebSockets", "WebView", "Widgets", "X11Extras", "Xml", "XmlPatterns",
)

update_cmake_libs()
CMAKE_PATH_MAP, CMAKE_LIBRARIES, CMAKE_INCLUDE_DIRS = update_cmake_path_map()

update_pkg_config_libs()

if __name__ == '__main__':
    from cmake_generator.json2cmake.generator import CmakeGenerator
    generator = CmakeGenerator('get', '/tmp', '/git/NLP/Dictionary/Goldendict/goldendict.joybin_mod')
    libs = [
        'Qt5Core', 'Qt5Xml', 'Qt5Svg', 'Qt5Gui', 'Qt5X11Extras', 'Qt5Sql',
        'Qt5WebKit', 'Qt5WebKitWidgets', 'Qt5Widgets', 'Qt5Multimedia',
        'Qt5Concurrent', 'Qt5Network', 'Qt5PrintSupport', 'Qt5Help',
        'aom', 'ao', 'avformat', 'GL', 'bz2', 'dl', 'Xtst',
        '-L/usr/local/lib', 'lzo2', 'hunspell-1.6', 'vdpau', '-lvorbisfile', '-lvorbis', 'pthread', 'Xv', 'Xext',
        'm', 'eb', 'avutil', 'avcodec', 'tiff', 'z', 'swresample', 'X11', 'ogg', 'lzma',
        '${CMAKE_THREAD_LIBS_INIT}',
    ]
    includes = {
        '/usr/include/x86_64-linux-gnu/qt5/QtX11Extras',
        '/usr/include/x86_64-linux-gnu/qt5/QtWebKit',
        '/usr/include/x86_64-linux-gnu/qt5/QtXml',
        '/usr/include/x86_64-linux-gnu/qt5/QtMultimedia',
        '/usr/lib/x86_64-linux-gnu/qt5/mkspecs/linux-clang',
        '/usr/include/x86_64-linux-gnu/qt5/QtGui',
        '/usr/include/x86_64-linux-gnu/qt5/QtWidgets',
        '/usr/include/x86_64-linux-gnu/qt5/QtSql',
        '/git/NLP/Dictionary/Goldendict/goldendict.joybin_mod/Release',
        '/usr/include/x86_64-linux-gnu/qt5/QtNetwork',
        '/usr/include/x86_64-linux-gnu/qt5',
        '/usr/include/x86_64-linux-gnu/qt5/QtPrintSupport',
        '/git/NLP/Dictionary/Goldendict/goldendict.joybin_mod/Release/build',
        '/usr/include/x86_64-linux-gnu/qt5/QtCore',
        '/usr/include/x86_64-linux-gnu/qt5/QtConcurrent',
        '/usr/local/include',
        '/git/NLP/Dictionary/Goldendict/goldendict.joybin_mod',
        '/usr/include/x86_64-linux-gnu/qt5/QtHelp',
        '/git/NLP/Dictionary/Goldendict/goldendict.joybin_mod/qtsingleapplication/src',
        '-I/usr/include/hunspell',
        '/usr/include/x86_64-linux-gnu/qt5/QtSvg',
        '/usr/include/x86_64-linux-gnu/qt5/QtWebKitWidgets',
        '/usr/include/libdrm',
    }
    lib_replacement = generator.get_lib_replacement(libs)
    old_libs = list(libs)
    generator.replace_list_content(libs, lib_replacement)
    packages = set(generator.packages.keys())
    include_replacement = generator.get_include_replacement(includes, packages)
    old_includes = list(includes)
    generator.replace_list_content(includes, include_replacement)
    import pprint
    pprint.pprint(include_replacement)
