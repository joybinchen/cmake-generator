import os
import re
import logging

__all__ = ['get_loggers', 'basestring', 'PathUtils', 'freeze', 'DISALLOWED_CHARACTERS',
           'resolve', 'relpath', 'cmake_resolve_binary']

if not hasattr(__builtins__, 'basestring'):
    basestring = str

def get_loggers(module_name):
    log = logging.getLogger(module_name)
    return log, log.info, log.debug, log.warning, log.error


logger, info, debug, warn, error = get_loggers(__name__)
DISALLOWED_CHARACTERS = re.compile("[^A-Za-z0-9_.+\\-]")


def freeze(obj):
    if isinstance(obj, dict):
        return freeze(tuple([freeze(x) for x in sorted(obj.items(), key=lambda i: i[0])]))
    if isinstance(obj, list):
        return tuple([freeze(x) for x in obj])
    if isinstance(obj, set):
        return frozenset({freeze(x) for x in obj})
    if isinstance(obj, tuple):
        return tuple([freeze(x) for x in obj])
    if hasattr(obj, '__dict__'):
        return freeze(sorted(filter(lambda it: it[1], obj.__dict__.items())))
    return obj


def resolve(path, cwd):
    if not os.path.isabs(path):
        path = os.path.join(cwd, path)
    return os.path.normcase(os.path.normpath(path))


def relpath(path, base, root=None):
    if not root:
        root = base
    if root.endswith('/') and base != '/':
        root = base[:-1]
    if path == root or path.startswith(root + '/'):
        return os.path.relpath(path, base)
    return path


def cmake_resolve_binary(path, base):
    return "${CMAKE_CURRENT_BINARY_DIR}/%s" % relpath(path, base)


class PathUtils(object):
    def __init__(self, directory):
        self.directory = ''
        self.set_directory(directory)

    def set_directory(self, directory):
        while directory.endswith('/'):
            directory = directory[:-1]
        self.directory = str(directory)

    def relpath(self, path, root=None):
        return relpath(path, self.directory, root)

    def resolve(self, path, cwd=None):
        return resolve(path, cwd if cwd else self.directory)

    def joined_relpath(self, files, delimiter=' '):
        return delimiter.join(map(self.relpath, files))

    @staticmethod
    def name_for_target(path):
        basename = os.path.basename(path)
        name = os.path.splitext(basename)[0]
        name = DISALLOWED_CHARACTERS.sub("_", name)
        name = name if not name.startswith('lib') else name[3:]
        return name


if __name__ == '__main__':
    # FORMAT = '%(asctime)-15s %(levelname)-8s %(module)s %(message)s'
    FORMAT = '%(levelname)-8s %(lineno)5d %(message)s'
    logging.basicConfig(format=FORMAT)
