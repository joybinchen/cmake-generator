import os
import logging

__all__ = ['get_loggers', 'basestring', 'PathUtils', 'freeze']

if not hasattr(__builtins__, 'basestring'):
    basestring = str

def get_loggers(module_name):
    log = logging.getLogger(module_name)
    return log, log.info, log.debug, log.warning, log.error


logger, info, debug, warn, error = get_loggers(__name__)


def freeze(obj):
    if isinstance(obj, dict):
        return freeze(tuple([freeze(x) for x in sorted(obj.items(), key=lambda i: i[0])]))
    if isinstance(obj, list):
        return tuple([freeze(x) for x in obj])
    if isinstance(obj, set):
        return frozenset({freeze(x) for x in obj})
    if isinstance(obj, tuple):
        return tuple([freeze(x) for x in obj])
    return obj


class PathUtils(object):
    def __init__(self, directory):
        self.directory = ''
        self.set_directory(directory)
        self.db = self

    def set_directory(self, directory):
        while directory.endswith('/'):
            directory = directory[:-1]
        self.directory = str(directory)

    def relpath(self, path):
        if self.directory and (path.startswith(self.db.directory + '/')
                               or path == self.db.directory
                               or path.startswith(os.path.dirname(self.db.directory) + '/')):
            return os.path.relpath(path, self.directory)
        return path

    def resolve(self, path, cwd=None):
        if cwd is None:
            cwd = self.directory
        if not os.path.isabs(path):
            path = os.path.join(cwd, path)
        return os.path.normcase(os.path.normpath(path))

    def joined_relpath(self, files, delimiter=' '):
        return delimiter.join(map(self.relpath, files))


if __name__ == '__main__':
    # FORMAT = '%(asctime)-15s %(levelname)-8s %(module)s %(message)s'
    FORMAT = '%(levelname)-8s %(lineno)5d %(message)s'
    logging.basicConfig(format=FORMAT)
