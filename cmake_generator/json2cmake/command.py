import os
import shlex
from .utils import freeze, basestring, resolve, relpath, get_loggers
from .denpendency import find_dependencies


__all__ = ['Command', 'resolve_destination', 'C_COMPILERS']
logger, info, debug, warn, error = get_loggers(__name__)
C_COMPILERS = ('gcc', 'g++', 'clang', 'clang++')


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


class Command(object):
    id = None
    destination = None
    compile_c_as_cxx = False
    use_thread = False
    include_binary_dir = False
    type = ''

    def __init__(self, compiler, cwd):
        self.compiler = compiler
        self.cwd = cwd
        self.options = []
        self.link_options = []
        self.definitions = []
        self.includes = []
        self.system_includes = []
        self.iquote_includes = []
        self.libs = []
        self.referenced_libs = {}
        self.missing_depends = {}
        self.linkage = 'SOURCE'

    def __repr__(self):
        children = ', '.join('%s=%s' % it for it in sorted(filter(lambda it: it[1], self.__dict__.items())))
        return "%s{%s}" % (self.__class__.__name__, children)

    def copy(self):
        other = Command(self.compiler, self.cwd)
        other.migrate(self)
        return other

    def migrate(self, command):
        if isinstance(command, dict):
            items = command.items()
        else:
            items = command.__dict__.items()
        for k, v in items:
            value = getattr(self, k, v)
            if isinstance(value, tuple):
                value = list(value)
                setattr(self, k, value)
            elif isinstance(value, frozenset):
                value = set(value)
                setattr(self, k, value)
            if isinstance(value, list):
                for part in v:
                    if part not in value:
                        value.append(part)
            elif isinstance(value, set):
                value.update(v)
            elif v and not getattr(self, k, None):
                setattr(self, k, v)

    @staticmethod
    def parse(command_line, source, cwd, root_dir):
        if isinstance(command_line, basestring):
            command_line = shlex.split(command_line)
        words = iter(command_line)
        compiler = os.path.basename(next(words))  # remove the initial 'cc' / 'c++'
        if compiler.startswith('python'):
            compiler = os.path.basename(next(words))

        command = Command(compiler, cwd)
        target = command.parse_command(words, source, root_dir)
        target = resolve(target, cwd)
        for key in list(command.missing_depends):
            command.missing_depends[target] = command.missing_depends.pop(key)
        return command, target

    def parse_command(self, words, source, root_dir):
        if self.compiler == 'ccache':
            self.compiler = 'clang'
        if self.compiler == 'msgfmt':
            self.linkage = 'LOCALE'

        parser_function = getattr(self, 'parse_' + self.compiler.replace('-', '_'), None)
        if self.compiler.endswith("ar"):
            target = self.parse_ar(words, source)
        elif parser_function:
            target = parser_function(words, source)
        else:
            target = self.parse_cxx(words, root_dir)

        if self.compiler in ('g++', 'clang++') and source.endswith('.c'):
            self.compile_c_as_cxx = True
        return target

    def parse_cxx(self, words, root_dir, target=''):
        if self.compiler in C_COMPILERS:
            self.linkage = 'EXECUTABLE'
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
                define = next(words) if word == '-D' else word[2:]
                define = self.process_arg_define(define)
                self.definitions.append(define)
            elif word.startswith('-Wl,'):
                target = self.parse_link_option(word, target, root_dir)
            elif word == '-z' or word == '-Xlinker':
                self.link_options.append(word + ' ' + next(words))
            elif word in ('-shared',):
                self.link_options.append(word)
            elif word == '-pthread':
                self.libs.append('${CMAKE_THREAD_LIBS_INIT}')
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
                self.libs.append(word if len(word) > 2 else ('-L'+next(words)))
            elif word.startswith('-l'):
                self.libs.append(word[2:] or next(words))
            elif word in ['-g', '-O1', '-O2', '-O3']:
                continue
            elif word == '-O':
                next(words)
            elif word.startswith('-m'):
                self.options.append(word)
                self.libs.append(word)
            elif word == '-shared':
                self.options.append(word)
                self.linkage = 'SHARED'
            elif word == '-E':
                self.options.append(word)
                self.linkage = 'SOURCE'
            elif word.startswith('-'):
                self.options.append(word)

        return target

    @staticmethod
    def process_arg_define(define):
        if define.find('=') > 0:
            name, value = define.split('=', 1)
            if value[:1] == '"' and value[-1:] == '"':
                value = value[1:-1]
            elif value[:1] == "'" and value[-1:] == "'":
                value = value[1:-1]
            if value:
                define = '%s="%s"' % (name, value)
        return define

    def parse_git(self, words, source, target=''):
        for word in words:
            if word == '>':
                target = next(words)
            elif word.startswith('-'):
                self.options.append(word)
            else:
                self.options.append(word)
        return target

    def parse_rcc(self, words, source, target=''):
        for word in words:
            if word.startswith('-'):
                if word == '-o':
                    target = next(words)
                elif word == '-name':
                    self.options.append('%s %s' % (word, next(words)))
                else:
                    self.options.append(word)
            elif source != word and word != os.path.basename(source):
                warn('different source in command %s %s' % (source, word))
        return target

    def parse_moc(self, words, source, target=''):
        for word in words:
            if word == '-o':
                target = next(words)
            elif word == '--include':
                include_header = next(words)
                self.missing_depends.setdefault(target, set()).add(resolve(include_header, self.cwd))
            elif word.startswith('-'):
                if word.startswith('-D'):
                    define = next(words) if len(word) == 2 else word[2:]
                    define = self.process_arg_define(define)
                    self.definitions.append(define)
                elif word.startswith('-I'):
                    including = next(words) if len(word) == 2 else word[2:]
                    self.includes.append(resolve(including, self.cwd))
                else:
                    self.options.append(word)
        return target

    def parse_install(self, words, source, target=''):
        self.linkage = 'INSTALL'
        for word in words:
            if word.startswith('-'):
                if word == '-m':
                    mode = next(words)
                    self.options.append("%s %s" % (word, mode))
                    for m in mode:
                        if int(m) % 1 != 0:
                            self.type = 'EXECUTABLE'
                            break
                    if 'EXECUTABLE' != self.type:
                        self.type = 'FILES'
                else:
                    self.options.append(word)
            elif word != source:
                target, self.destination = resolve_destination(word, self.cwd, source)
        return target

    def parse_qmake(self, words, source, target=''):
        for word in words:
            if word.startswith('-'):
                if word == '-install':
                    self.linkage = 'INSTALL'
                    subcommand = next(words)
                    if subcommand == 'qinstall':
                        next_word = next(words)
                        if next_word == '-exe':
                            subcommand += ' ' + next_word
                            self.type = 'EXECUTABLE'
                        else:
                            # next_word is source
                            # self.type = 'FILES'
                            pass
                    self.options.append("%s %s" % (word, subcommand))
                else:
                    self.options.append(word)
            elif word != source:
                target, self.destination = resolve_destination(word, self.cwd, source)
        return target

    def parse_lrelease(self, words, source, target=''):
        for word in words:
            if word == '-qm':
                self.linkage = 'LOCALE'
                target = next(words)
            elif word.startswith('-'):
                self.options.append(word)
            elif word == source:
                pass
            else:
                pass
        return target

    def parse_glib_genmarshal(self, words, source, target=''):
        for word in words:
            if word == '--output':
                self.linkage = 'SOURCE'
                target = next(words)
            elif word.startswith('-'):
                self.options.append(word)
        return target

    def parse_dbus_binding_tool(self, words, source, target=''):
        for word in words:
            if word.startswith('--output='):
                self.linkage = 'SOURCE'
                target = word[len('--output='):]
            elif word.startswith('-'):
                self.options.append(word)
        return target

    def parse_ar(self, words, source, target=''):
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

    def update_object_command(self, source, target, root_dir):
        missing_depends = find_dependencies(source, self, root_dir)
        if missing_depends:
            info("cmd #%s created OBJECT %-25s depends on missing %s"
                 % (self.id, relpath(target, root_dir),
                    ' '.join([relpath(f, root_dir) for f in missing_depends])))
            self.missing_depends.setdefault(target, set()).update(missing_depends)
            self.include_binary_dir = True
