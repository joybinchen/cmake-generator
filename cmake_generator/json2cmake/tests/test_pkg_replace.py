import os
from io import StringIO
import unittest
from ..pkg_replace import *
from ..generator import CmakeGenerator


class TestPackageMap(unittest.TestCase):
    def setUp(self):
        self.output = StringIO()
        self.generator = CmakeGenerator('get', '/tmp', '/git/goldendict')
        self.generator.output = self.output
        self.maxDiff = 5024
        self.libs = [
            'Qt5Core', 'Qt5Xml', 'Qt5Svg', 'Qt5Gui', 'Qt5X11Extras', 'Qt5Sql',
            'Qt5WebKit', 'Qt5WebKitWidgets', 'Qt5Widgets', 'Qt5Multimedia',
            'Qt5Concurrent', 'Qt5Network', 'Qt5PrintSupport', 'Qt5Help',
            'aom', 'ao', 'avformat', 'GL', 'bz2', 'dl', 'Xtst',
            '-L/usr/local/lib',
            'lzo2', 'hunspell-1.6', 'vdpau', '-lvorbisfile', '-lvorbis', 'pthread', 'Xv', 'Xext',
            'm', 'eb', 'avutil', 'avcodec', 'tiff', 'z', 'swresample', 'X11', 'ogg', 'lzma',
            '${CMAKE_THREAD_LIBS_INIT}',
        ]
        self.includes = [
            '/usr/include/x86_64-linux-gnu/qt5/QtX11Extras',
            '/usr/include/x86_64-linux-gnu/qt5/QtWebKit',
            '/usr/include/x86_64-linux-gnu/qt5/QtXml',
            '/usr/include/x86_64-linux-gnu/qt5/QtMultimedia',
            '/usr/lib/x86_64-linux-gnu/qt5/mkspecs/linux-clang',
            '/usr/include/x86_64-linux-gnu/qt5/QtGui',
            '/usr/include/x86_64-linux-gnu/qt5/QtWidgets',
            '/usr/include/x86_64-linux-gnu/qt5/QtSql',
            '/git/goldendict/Release',
            '/usr/include/x86_64-linux-gnu/qt5/QtNetwork',
            '/usr/include/x86_64-linux-gnu/qt5',
            '/usr/include/x86_64-linux-gnu/qt5/QtPrintSupport',
            '/git/goldendict/Release/build',
            '/usr/include/x86_64-linux-gnu/qt5/QtCore',
            '/usr/include/x86_64-linux-gnu/qt5/QtConcurrent',
            '/usr/local/include',
            '/git/goldendict',
            '/usr/include/x86_64-linux-gnu/qt5/QtHelp',
            '/git/goldendict/qtsingleapplication/src',
            '-I/usr/include/hunspell',
            '/usr/include/x86_64-linux-gnu/qt5/QtSvg',
            '/usr/include/x86_64-linux-gnu/qt5/QtWebKitWidgets',
            '/usr/include/libdrm',
        ]
        self.expected_packages = {
            'Qt5',
            'Qt5Concurrent',
            'Qt5Core',
            'Qt5Gui',
            'Qt5Help',
            'Qt5Multimedia',
            'Qt5Network',
            'Qt5PrintSupport',
            'Qt5Sql',
            'Qt5Svg',
            'Qt5WebKit',
            'Qt5WebKitWidgets',
            'Qt5Widgets',
            'Qt5X11Extras',
            'Qt5Xml',
            '_',
            'ao',
            'aom',
            'gl',
            'hunspell',
            'libavcodec',
            'libavformat',
            'libavutil',
            'liblzma',
            'libswresample',
            'libtiff-4',
            'ogg',
            'vdpau',
            'vorbis',
            'vorbisfile',
            'x11',
            'xext',
            'xtst',
            'xv',
            'zlib',
        }
        self.expected_lib_replacement = {
            '-lvorbis': '${VORBIS_LIBRARIES}',
            '-lvorbisfile': '${VORBISFILE_LIBRARIES}',
            'GL': '${GL_LIBRARIES}',
            'Qt5Concurrent': 'Qt5::Concurrent',
            'Qt5Core': 'Qt5::Core',
            'Qt5Gui': 'Qt5::Gui',
            'Qt5Help': 'Qt5::Help',
            'Qt5Multimedia': 'Qt5::Multimedia',
            'Qt5Network': 'Qt5::Network',
            'Qt5PrintSupport': 'Qt5::PrintSupport',
            'Qt5Sql': 'Qt5::Sql',
            'Qt5Svg': 'Qt5::Svg',
            'Qt5WebKit': 'Qt5::WebKit',
            'Qt5WebKitWidgets': 'Qt5::WebKitWidgets',
            'Qt5Widgets': 'Qt5::Widgets',
            'Qt5X11Extras': 'Qt5::X11Extras',
            'Qt5Xml': 'Qt5::Xml',
            'X11': '${X11_LIBRARIES}',
            'Xext': '${XEXT_LIBRARIES}',
            'Xtst': '${XTST_LIBRARIES}',
            'Xv': '${XV_LIBRARIES}',
            'ao': '${AO_LIBRARIES}',
            'aom': '${AOM_LIBRARIES}',
            'avcodec': '${LIBAVCODEC_LIBRARIES}',
            'avformat': '${LIBAVFORMAT_LIBRARIES}',
            'avutil': '${LIBAVUTIL_LIBRARIES}',
            'bz2': '${LIBAVFORMAT_LIBRARIES}',
            'dl': '${LIBAVUTIL_LIBRARIES}',
            'hunspell-1.6': '${HUNSPELL_LIBRARIES}',
            'lzma': '${LIBLZMA_LIBRARIES}',
            'm': '${LIBAVUTIL_LIBRARIES}',
            'ogg': '${OGG_LIBRARIES}',
            'swresample': '${LIBSWRESAMPLE_LIBRARIES}',
            'tiff': '${LIBTIFF4_LIBRARIES}',
            'vdpau': '${VDPAU_LIBRARIES}',
            'z': '${ZLIB_LIBRARIES}',
        }
        self.expected_libs = [
            'Qt5::Core',
            'Qt5::Xml',
            'Qt5::Svg',
            'Qt5::Gui',
            'Qt5::X11Extras',
            'Qt5::Sql',
            'Qt5::WebKit',
            'Qt5::WebKitWidgets',
            'Qt5::Widgets',
            'Qt5::Multimedia',
            'Qt5::Concurrent',
            'Qt5::Network',
            'Qt5::PrintSupport',
            'Qt5::Help',
            '${AOM_LIBRARIES}',
            '${AO_LIBRARIES}',
            '${LIBAVFORMAT_LIBRARIES}',
            '${GL_LIBRARIES}',
            '${LIBAVUTIL_LIBRARIES}',
            '${XTST_LIBRARIES}',
            '-L/usr/local/lib',
            'lzo2',
            '${HUNSPELL_LIBRARIES}',
            '${VDPAU_LIBRARIES}',
            '${VORBISFILE_LIBRARIES}',
            '${VORBIS_LIBRARIES}',
            'pthread',
            '${XV_LIBRARIES}',
            '${XEXT_LIBRARIES}',
            'eb',
            '${LIBAVCODEC_LIBRARIES}',
            '${LIBTIFF4_LIBRARIES}',
            '${ZLIB_LIBRARIES}',
            '${LIBSWRESAMPLE_LIBRARIES}',
            '${X11_LIBRARIES}',
            '${OGG_LIBRARIES}',
            '${LIBLZMA_LIBRARIES}',
            '${CMAKE_THREAD_LIBS_INIT}',
        ]
        self.expected_include_replacement = {
            '-I/usr/include/hunspell': '${HUNSPELL_INCLUDE_DIR}',
            '/usr/include/libdrm': '${GL_INCLUDE_DIR}',
            '/usr/include/x86_64-linux-gnu/qt5': '${Qt5Concurrent_INCLUDE_DIRS}',
            '/usr/include/x86_64-linux-gnu/qt5/QtConcurrent': '${Qt5Concurrent_INCLUDE_DIRS}',
            '/usr/include/x86_64-linux-gnu/qt5/QtCore': '${Qt5Concurrent_INCLUDE_DIRS}',
            '/usr/include/x86_64-linux-gnu/qt5/QtGui': '${Qt5Gui_INCLUDE_DIRS}',
            '/usr/include/x86_64-linux-gnu/qt5/QtHelp': '${Qt5Help_INCLUDE_DIRS}',
            '/usr/include/x86_64-linux-gnu/qt5/QtMultimedia': '${Qt5Multimedia_INCLUDE_DIRS}',
            '/usr/include/x86_64-linux-gnu/qt5/QtNetwork': '${Qt5Multimedia_INCLUDE_DIRS}',
            '/usr/include/x86_64-linux-gnu/qt5/QtPrintSupport': '${Qt5PrintSupport_INCLUDE_DIRS}',
            '/usr/include/x86_64-linux-gnu/qt5/QtSql': '${Qt5Help_INCLUDE_DIRS}',
            '/usr/include/x86_64-linux-gnu/qt5/QtSvg': '${Qt5Svg_INCLUDE_DIRS}',
            '/usr/include/x86_64-linux-gnu/qt5/QtWebKit': '${Qt5WebKitWidgets_INCLUDE_DIRS}',
            '/usr/include/x86_64-linux-gnu/qt5/QtWebKitWidgets': '${Qt5WebKitWidgets_INCLUDE_DIRS}',
            '/usr/include/x86_64-linux-gnu/qt5/QtWidgets': '${Qt5Help_INCLUDE_DIRS}',
            '/usr/include/x86_64-linux-gnu/qt5/QtX11Extras': '${Qt5X11Extras_INCLUDE_DIRS}',
            '/usr/include/x86_64-linux-gnu/qt5/QtXml': '${Qt5Xml_INCLUDE_DIRS}',
            '/usr/local/include': '${AOM_INCLUDE_DIR}',
        }
        self.expected_includes = [
            '${QT5X11EXTRAS_INCLUDE_DIR}',
            '${QT5WEBKIT_INCLUDE_DIR}',
            '${QT5XML_INCLUDE_DIR}',
            '${QT5MULTIMEDIA_INCLUDE_DIR}',
            '/usr/lib/x86_64-linux-gnu/qt5/mkspecs/linux-clang',
            '${QT5GUI_INCLUDE_DIR}',
            '${QT5WIDGETS_INCLUDE_DIR}',
            '${QT5HELP_INCLUDE_DIR}',
            '/git/goldendict/Release',
            '${QT5CORE_INCLUDE_DIR}',
            '${QT5PRINTSUPPORT_INCLUDE_DIR}',
            '/git/goldendict/Release/build',
            '${QT5CONCURRENT_INCLUDE_DIR}',
            '${AOM_INCLUDE_DIR}',
            '/git/goldendict',
            '/git/goldendict/qtsingleapplication/src',
            '${HUNSPELL_INCLUDE_DIR}',
            '${QT5SVG_INCLUDE_DIR}',
            '${QT5WEBKITWIDGETS_INCLUDE_DIR}',
            '${GL_INCLUDE_DIR}',
        ]

    def test_map2options(self):
        expected = dict([(x[2:], x) for x in filter(lambda x: x.startswith('-l'), self.libs)])
        expected.update(dict((x, x) for x in filter(lambda x: x[:1] not in ('-', '$'), self.libs)))
        lib2options = map2option(self.libs.copy())
        self.assertEqual(lib2options, expected)

    def test_find_package_for_libs(self):
        expected_cmake_packages = {
            'Qt5Concurrent': 'Qt5Concurrent',
            'Qt5Core': 'Qt5Core',
            'Qt5Gui': 'Qt5Gui',
            'Qt5Help': 'Qt5Help',
            'Qt5Multimedia': 'Qt5Multimedia',
            'Qt5Network': 'Qt5Network',
            'Qt5PrintSupport': 'Qt5PrintSupport',
            'Qt5Sql': 'Qt5Sql',
            'Qt5Svg': 'Qt5Svg',
            'Qt5WebKit': 'Qt5WebKit',
            'Qt5WebKitWidgets': 'Qt5WebKitWidgets',
            'Qt5Widgets': 'Qt5Widgets',
            'Qt5X11Extras': 'Qt5X11Extras',
            'Qt5Xml': 'Qt5Xml',
        }
        expected_pkgconfig_packages = {
            'GL': 'gl',
            'X11': 'x11',
            'Xext': 'xext',
            'Xtst': 'xtst',
            'Xv': 'xv',
            'ao': 'ao',
            'aom': 'aom',
            'avcodec': 'libavcodec',
            'avformat': 'libavformat',
            'avutil': 'libavutil',
            'bz2': 'libavformat',
            'dl': 'libavutil',
            'hunspell-1.6': 'hunspell',
            'lzma': 'liblzma',
            'm': 'libavutil',
            'ogg': 'ogg',
            'swresample': 'libswresample',
            'tiff': 'libtiff-4',
            'vdpau': 'vdpau',
            'z': 'zlib',
        }
        libs = list(self.libs)
        cmake_packages, pkgconfig_packages = find_package_for_libs(libs)
        self.assertEqual(cmake_packages, expected_cmake_packages)
        self.assertEqual(pkgconfig_packages, expected_pkgconfig_packages)

    def test_libs_replacement(self):
        libs = list(self.libs)
        old_libs = list(self.libs)
        includes = list(self.includes)
        old_includes = list(includes)
        lib_replacement = self.generator.get_lib_replacement(libs)
        packages = set(self.generator.packages.keys())
        self.assertEqual(packages, self.expected_packages)
        self.assertEqual(lib_replacement, self.expected_lib_replacement)
        self.generator.replace_list_content(libs, lib_replacement)
        self.assertEqual(libs, self.expected_libs)
        include_replacement = get_include_replacement(includes, packages)
        self.assertEqual(include_replacement, self.expected_include_replacement)
        self.generator.replace_list_content(includes, include_replacement)
        self.assertEqual(includes, self.expected_includes)
