import traceback
from .utils import get_loggers, basestring

__all__ = ['CmakeTarget', 'CppTarget', 'Executable', 'Library', 'Locale',
           'OutputWithIndent', 'CustomGenerated', 'WrappedTarget', ]

logger, info, debug, warn, error = get_loggers(__name__)


class OutputWithIndent(object):
    def __init__(self, stream, indent):
        self.stream = stream
        self.indent = indent
        self.indented = False

    def write(self, content):
        if not content: return
        if not self.indented:
            self.stream.write(self.indent)
            self.indented = True
        lines = content.split('\n') if isinstance(content, str) else content
        delimiter = '\n' + self.indent
        self.stream.write(delimiter.join(lines))

    def writeln(self, content):
        self.write(content)
        self.stream.write('\n')
        self.indented = False
        self.stream.flush()

    def finish(self):
        if self.stream:
            self.writeln(None)
        self.stream = None

    def write_command(self, command, options, name, parts):
        if isinstance(parts, basestring):
            content = ' ' + parts
        else:
            single_line = len(' '.join(parts)) < 40
            delimiter = ' ' if single_line else '\n\t' + self.indent
            tail = '' if single_line else '\n'
            if not single_line and len(' '.join(parts)) / len(parts) < 7:
                lines = []
                for i in range(0, (len(parts) // 10) + 1):
                    lines.append('\t'.join(parts[i * 10:(i * 10) + 9]))
                content = delimiter + (delimiter.join(lines)) + tail
            else:
                content = delimiter + (delimiter.join(parts)) + tail
        self.writeln('%s(%s %s%s)' % (command, name, options, content))

    def set_property(self, target_type, targets, property_name, values):
        if not isinstance(targets, basestring):
            targets = ' '.join(targets)
        if not isinstance(values, basestring):
            values = ' '.join(values)
        self.writeln(self.indent + 'set_property(%s %s PROPERTY %s %s)' % (target_type, targets, property_name, values))


class CmakeTarget(object):
    def __init__(self, command, target, sources):
        self.command = command
        self.common_configs = {}
        self.compiler = command.get('compiler', 'cmake')
        self.target = target
        self.sources = set()
        self.libs = command.get('libs', set())
        self.missing_depends = command.get('missing_depends', [])
        self.include_binary_dir = command.get('include_binary_dir', False)
        self.referenced_libs = command.get('referenced_libs', set())
        self.name_ = None
        self.directory = None
        self.parent = None
        self.generator = None
        self.output = None
        self.indent = 0
        self.depends = set()
        self.destination = None
        self.output_name = None
        if sources:
            self.add_sources(sources)
        pass

    def bind(self, generator):
        self.generator = generator
        self.common_configs = generator.common_configs
        self.output = OutputWithIndent(generator.output, '\t' * self.indent)

    def name(self):
        if self.name_ is None:
            self.name_ = self.get_name()
        return self.name_

    def get_name(self):
        name, output_name = self.generator.name_as_target(self.target)
        if self.name_ is None: traceback.print_stack()
        return output_name

    def set_name(self, name):
        self.name_ = name

    def set_command(self, command):
        self.command.update(command)

    def add_sources(self, sources):
        self.sources.update(sources)

    def get_sources(self):
        return sorted(self.sources)

    def get_values(self, name):
        values = list(self.command.get(name, []))
        for common in self.common_configs.get(name, []):
            if common in values: values.remove(common)
        return values

    def add_depends(self, depends):
        self.depends.update(depends)

    def install_target(self, destination):
        self.destination = destination

    def set_parent(self, parent):
        indent = 1 if parent else 0
        if self.parent:
            indent -= 1
        self.parent = parent
        if not indent:
            self.increase_indent(indent)

    def increase_indent(self, indent=1):
        self.indent += indent

    def cmake_command(self):
        return 'add_custom_target'

    def command_options(self):
        return ''

    def output_target(self):
        if self.generator is None:
            raise Exception('generator is None')
        command = self.cmake_command()
        options = self.get_options()
        name = self.name()
        sources = self.get_sources()
        self.output.write_command(command, options, name, sources)
        self.output.finish()

    def write_command(self, command, options, name, parts):
        return self.output.write_command(command, options, name, parts)

    def output_cmake_target(self, name, config, files, target, libtype):
        files = sorted(map(self.generator.relpath, files))
        if self.missing_depends:
            missing_depends = list(map(self.generator.relpath, self.missing_depends))
            warn("Target %s depends on missing files: %s" % (name, ' '.join(missing_depends)))
            files.extend(missing_depends)
            self.include_binary_dir = True
        if not files or not name: return
        target_name = self.generator.use_target_name(name, target)
        info("Target %s output cmake %-13s: %s" % (target_name, libtype, ' '.join(files)))
        if not libtype or libtype == 'EXECUTABLE':
            self.write_command('add_executable', '', target_name, files)
        else:
            self.write_command('add_library', libtype, target_name, files)
        self.output_target_config(target_name)

    def cmake_resolve_source(self, path):
        return "${CMAKE_CURRENT_SOURCE_DIR}/%s" % self.generator.relpath(path)


class CppTarget(CmakeTarget):
    def __init__(self, command, target, sources=None):
        super(CppTarget, self).__init__(command, target, sources)

    def output_target(self):
        command = self.cmake_command()
        options = self.command_options()
        name = self.name()
        output_name = self.get_name()
        parts = sorted(map(self.generator.relpath, filter(lambda p: p not in self.referenced_libs, self.sources)))
        var_name = name.upper() + '_SRCS'
        var_refer = '${%s}' % var_name
        self.output_list_definition(var_name, parts)
        if self.command.get('compile_c_as_cxx'):
            self.write_command('set_source_files_properties', 'PROPERTIES', var_refer, 'LANGUAGE CXX')
        self.write_command(command, options, name, var_refer)
        if name != output_name:
            self.output.set_property('TARGET', name, 'LIBRARY_OUTPUT_NAME', output_name)
        self.output_target_config(self.name())
        if self.depends:
            depends = sorted([self.generator.name_as_target(path)[0] for path in self.depends])
            self.write_command('add_dependencies', '', name, depends)
        self.output.finish()

    def get_options(self):
        return self.get_values('options')

    def get_link_options(self):
        return self.get_values('link_options')

    def get_definitions(self):
        return self.get_values('definitions')

    def get_includes(self):
        includes = self.get_values('includes')
        # print('get_includes for ', self.get_name(), includes)
        return includes

    def get_system_includes(self):
        return self.get_values('system_includes')

    def get_iquote_includes(self):
        return self.get_values('iquote_includes')

    def cmake_command(self):
        return 'add_executable'

    def output_target_config(self, name):
        self.output_compile_args('options', name, self.get_options())
        self.output_compile_args('definitions', name, self.get_definitions())
        if self.include_binary_dir:
            self.output_includes('PRIVATE', name, ['${CMAKE_CURRENT_BINARY_DIR}'])
        self.output_includes('PRIVATE', name, self.get_includes())
        self.output_includes('SYSTEM PRIVATE', name, self.get_system_includes())
        self.output_includes('BEFORE PRIVATE', name, self.get_iquote_includes())
        self.output_target_libs(name)

        link_options = self.get_link_options()
        if link_options:
            self.write_command('target_link_options', 'PRIVATE', name, link_options)

    def output_list_definition(self, name, parts):
        self.write_command('set', '', name, parts)

    def output_list_append(self, name, parts):
        self.write_command('list', name, 'APPEND', parts)

    def output_compile_args(self, arg_type, name, parts):
        if not parts: return
        info("Target %s output compile %-11s: %s" % (name, arg_type, ' '.join(parts)))
        self.write_command('target_compile_' + arg_type, 'PRIVATE', name, parts)

    def output_includes(self, options, name, parts):
        if not parts: return
        parts = list(map(self.generator.get_include_path, parts))
        info("Target %s includes %s %s" % (name, options, ' '.join(parts)))
        self.write_command('target_include_directories', options, name, parts)

    def output_target_libs(self, name):
        libs = set()
        for lib in self.referenced_libs:
            if lib in self.generator.db.linkings:
                target_name, output_name = self.generator.name_as_target(lib)
                libs.add(target_name)
            else:
                libs.add(lib)
        if libs:
            debug("Target %s using referenced libs %s" % (name, ' '.join(libs)))
        libs.update(self.libs)
        if libs:
            self.write_command('target_link_libraries', 'PRIVATE', name, sorted(libs))


class Executable(CppTarget):
    def __init__(self, command, target, sources=None):
        super(Executable, self).__init__(command, target, sources)

    def cmake_command(self):
        return 'add_executable'


class Library(CppTarget):
    def __init__(self, command, target, sources=None, libtype='STATIC'):
        super(self.__class__, self).__init__(command, target, sources)
        self.libtype = libtype

    def cmake_command(self):
        return 'add_library'

    def command_options(self):
        return self.libtype


class Locale(CmakeTarget):
    def __init__(self, command, target, sources=None):
        super(self.__class__, self).__init__(command, target, sources)


class CustomGenerated(CmakeTarget):
    CUSTOM_TARGET_OUTPUT_CONFIG = {
        'glib-genmarshal': '--output ',
        'dbus-binding-tool': '--output=',
        'moc': '-o ',
        'msgfmt': '-o ',
    }

    def __init__(self, command, target, sources=None):
        super(self.__class__, self).__init__(command, target, sources)
        self.compiler = command.get('compiler')

    def output_target(self):
        info("cmd #%s output custom target %s generated from %s"
             % (self.command['cmd_id'], self.relpath(self.target), self.joined_relpath(self.sources)))
        self.generator.write("add_custom_command(OUTPUT %s\n\tCOMMAND %s\n\t%s\n\t%s\n\t%s\n)\n"
                             % (self.generator.relpath(self.target),
                                self.compiler,
                                ' '.join(self.options),
                                self.cmake_resolve_source('${X}'),
                                self.custom_target_output_args()
                                ))

    def custom_target_output_args(self):
        prefix = CustomGenerated.CUSTOM_TARGET_OUTPUT_CONFIG.get(self.compiler, ' ')
        return prefix + self.cmake_resolve_binary(self.target)


class WrappedTarget(CmakeTarget):
    def __init__(self, command, target, sources=None):
        super(self.__class__, self).__init__(command, target, sources)
        self.children = []

    def add_child(self, child):
        child.set_parent(self)
        self.children.append(child)
