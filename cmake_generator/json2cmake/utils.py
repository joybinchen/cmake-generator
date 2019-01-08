import os
import logging

if not hasattr(__builtins__, 'basestring'):
    basestring = str

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
info = logger.info
debug = logger.debug
warn = logger.warning
error = logger.error


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
    def __init__(self, cwd):
        if not cwd.endswith('/'):
            cwd = cwd + '/'
        self.directory = str(cwd)
        self.db = self

    def relpath(self, path):
        if self.directory and (path.startswith(self.db.directory)
                               or path == self.db.directory):
            return os.path.relpath(path, self.directory)
        return path

    def resolve(self, path, cwd=None):
        if cwd is None:
            cwd = self.directory
        if not os.path.isabs(path):
            path = os.path.join(cwd, path)
        return os.path.normcase(os.path.normpath(path))


if __name__ == '__main__':
    # FORMAT = '%(asctime)-15s %(levelname)-8s %(module)s %(message)s'
    FORMAT = '%(levelname)-8s %(lineno)5d %(message)s'
    logging.basicConfig(format=FORMAT)
