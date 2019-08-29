import os
import shlex
from .utils import basestring, resolve, relpath

__all__ = ['CompileCommand', 'resolve_destination']


def resolve_destination(path, cwd, source):
    target = resolve(path, cwd)
    if os.path.isdir(target):
        destination = target
        target = os.path.join(target, os.path.basename(source))
    else:
        if os.path.basename(target) == os.path.basename(source):
            destination = os.path.dirname(target)
        else:
            destination = target
    return target, destination


class CompileCommand(object):
    id = None
    destination = None
    compile_c_as_cxx = False
    use_thread = False
    include_binary_dir = False

    def __init__(self, compiler, cwd):
        self.compiler = compiler
        self.cwd = cwd
        self.options = []
        self.link_options = []
        self.definitions = []
        self.includes = []
        self.system_includes = []
        self.iquote_includes = []
        self.libs = set()
        self.referenced_libs = {}
        self.missing_depends = set()
        self.linkage = 'SOURCE'

    def copy(self):
        other = CompileCommand(self.compiler, self.cwd)
        other.migrate(self)
        return other

    def migrate(self, command):
        if isinstance(command, dict):
            items = command.items()
        else:
            items = command.__dict__.items()
        for k, v in items:
            value = getattr(self, k, v)
            if type(v) in (set, tuple, frozenset):
                value = list(v)
                setattr(self, k, value)
            if isinstance(v, list):
                for part in v:
                    if part not in value:
                        value.append(part)
            elif v and not getattr(self, k, None):
                setattr(self, k, v)

    def parse_command(self, words, source, root_dir):
        if self.compiler == 'ccache':
            self.compiler = 'clang'
        if self.compiler in ('gcc', 'g++', 'clang', 'clang++'):
            self.linkage = 'EXECUTABLE'
        if self.compiler == 'msgfmt':
            self.linkage = 'LOCALE'

        if self.compiler == 'git':
            target = self.parse_git(words)
        elif self.compiler == 'moc':
            target = self.parse_moc(words)
        elif self.compiler == 'install':
            target = self.parse_install(words, source, self.cwd)
        elif self.compiler == 'qmake':
            target = self.parse_qmake(words, source, self.cwd)
        elif self.compiler == 'lrelease':
            target = self.parse_lrelease(words)
        elif self.compiler == 'glib-genmarshal':
            target = self.parse_genmarshal(words)
        elif self.compiler == 'dbus-binding-tool':
            target = self.parse_dbus_binding_tool(words)
        elif self.compiler.endswith("ar"):
            target = self.parse_ar(words)
        else:
            target = self.parse_cxx(words, root_dir)

        if self.compiler in ('g++', 'clang++') and source.endswith('.c'):
            self.compile_c_as_cxx = True
        return target

    def parse_cxx(self, words, root_dir, target=''):
        for word in words:
            if word == '-o':
                target = next(words)
            elif word.startswith('-I'):
                include = resolve(word[2:], self.cwd)
                if include not in self.includes:
                    self.includes.append(include)
            elif word == '-isystem':
                include = next(words)
                include = resolve(include, self.cwd)
                if include not in self.system_includes:
                    self.system_includes.append(include)
            elif word == '-iquote':
                include = next(words)
                include = resolve(include, self.cwd)
                if include not in self.iquote_includes:
                    self.iquote_includes.append(include)
            elif word.startswith('-D'):
                define = word[2:]
                if define.find('=') > 0:
                    name, value = define.split('=', 1)
                    if value:
                        define = '%s="%s"' % (name, value)
                self.definitions.append(define)
            elif word.startswith('-Wl,'):
                target = self.parse_link_option(word, target, root_dir)
            elif word == '-z' or word == '-Xlinker':
                self.link_options.append(word + ' ' + next(words))
            elif word in ('-shared',):
                self.link_options.append(word)
            elif word == '-pthread':
                self.libs.add('${CMAKE_THREAD_LIBS_INIT}')
                self.use_thread = True
            elif word.startswith('-x') and self.compiler == 'clang':
                word = next(words) if word == '-x' else word[2:]
                if word == 'c++':
                    self.compiler = 'clang++'
                self.options.append('-x ' + word)
            elif word == '-c':
                self.linkage = 'OBJECT'
            elif word in ['-arch', '-include', '-x']:
                self.options.append('%s %s' % (word, next(words)))
            elif word in ['-MM', '-MQ', '-M', '-MP', '-MG']:
                continue
            elif word in ['-MT', '-MF', '-MQ', '-MD', '-MMD', '-ccc-gcc-name']:
                next(words)
            elif word.startswith('-L'):
                self.libs.add(word if len(word) > 2 else ('-L'+next(words)))
            elif word.startswith('-l'):
                self.libs.add(word[2:] or next(words))
            elif word in ['-g', '-O1', '-O2', '-O3']:
                continue
            elif word == '-O':
                next(words)
            elif word.startswith('-m'):
                self.options.append(word)
                self.libs.add(word)
            elif word == '-shared':
                self.options.append(word)
                self.linkage = 'SHARED'
            elif word.startswith('-'):
                self.options.append(word)

        return target

    def parse_git(self, words, target=''):
        for word in words:
            if word == '>':
                target = next(words)
            elif word.startswith('-'):
                self.options.append(word)
            else:
                self.options.append(word)
        return target

    def parse_moc(self, words, target=''):
        for word in words:
            if word == '-o':
                target = next(words)
            elif word.startswith('-'):
                if word == '--include':
                    self.options.append('%s %s' % (word, next(words)))
                else:
                    self.options.append(word)
        return target

    def parse_install(self, words, source, cwd, target=''):
        for word in words:
            if word.startswith('-'):
                if word == '-c':
                    self.options.append(word)
                if word == '-m':
                    self.options.append("%s %s" % (word, next(words)))
                else:
                    self.options.append(word)
            elif word != source:
                self.linkage = 'INSTALL'
                target, self.destination = resolve_destination(word, cwd, source)
        return target

    def parse_qmake(self, words, source, cwd, target=''):
        for word in words:
            if word.startswith('-'):
                if word == '-install':
                    self.options.append("%s %s" % (word, next(words)))
                else:
                    self.options.append(word)
            elif word != source:
                self.linkage = 'INSTALL'
                target, self.destination = resolve_destination(word, cwd, source)
        return target

    def parse_lrelease(self, words, target=''):
        for word in words:
            if word == '-qm':
                self.linkage = 'LOCALE'
                target = next(words)
            elif word.startswith('-'):
                self.options.append(word)
        return target, self.linkage, self.options

    def parse_genmarshal(self, words, target=''):
        for word in words:
            if word == '--output':
                self.linkage = 'SOURCE'
                target = next(words)
            elif word.startswith('-'):
                self.options.append(word)
        return target

    def parse_dbus_binding_tool(self, words, target=''):
        for word in words:
            if word.startswith('--output='):
                self.linkage = 'SOURCE'
                target = word[len('--output='):]
            elif word.startswith('-'):
                self.options.append(word)
        return target

    def parse_ar(self, words, target=''):
        for word in words:
            if target:
                return target
            elif word.startswith('-'):
                if 'c' in word:
                    self.linkage = 'STATIC'
                    target = next(words)
            elif 'c' in word:  # create an archive
                self.linkage = 'STATIC'
                target = next(words)
            elif 'q' in word:  # quick append to an archive
                self.linkage = 'STATIC'
                target = next(words)
            else:
                self.options.append(word)
        return target

    def parse_link_option(self, word, target, root_dir):
        if word.find('=') >= 0:
            link_option, link_option_value = word[4:].split('=', 1)
            if link_option in {'-c', '--mri-script',
                               '-T', '--script', '--default-script',
                               '--retain-symbols-file',
                               '--version-script',
                               '--dynamic-list',
                               '-h', '--soname',
                               }:
                link_option_file = resolve(link_option_value, self.cwd)
                link_option_file = relpath(link_option_file, root_dir)
                if not link_option_file.startswith('/'):
                    if link_option_file.startswith('./'):
                        link_option_file = link_option_file[2:]
                        if link_option in ('-h', '--soname'):
                            soname = resolve(link_option_value, self.cwd)
                            if not target:
                                return soname
                    link_option_file = '${CMAKE_SOURCE_DIR}/' + link_option_file
                self.link_options.append('-Wl,%s=%s' % (link_option, link_option_file))
                return target
        else:
            link_option = word[4:]
            if link_option.startswith('-O'):
                return target
            elif link_option in {'-g', }:
                return target
        if word:
            self.link_options.append(word)
        return target
