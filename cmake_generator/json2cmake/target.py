import os
import traceback
from .utils import PathUtils, relpath, resolve, get_loggers, basestring, cmake_resolve_binary, cmake_resolve_source

__all__ = ['CmakeTarget', 'CppTarget', 'ExecutableTarget', 'LibraryTarget', 'LocaleTarget', 'InstallTarget',
           'OutputWithIndent', 'CustomCommandTarget', 'WrappedTarget', 'ForeachTargetWrapper']

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
        self.stream.write('\n')
        self.write(content)
        self.indented = False
        self.stream.flush()

    def finish(self):
        if self.stream:
            self.writeln(None)

    def write_command(self, command, options, name, parts, tail=''):
        single_line = len(' '.join(parts)) < 40
        delimiter = ' ' if single_line else '\n\t'
        if options: options = ' ' + options
        if tail: tail = delimiter + tail
        if isinstance(parts, basestring):
            content = ' ' + parts + tail
        else:
            if not single_line:
                tail += '\n'
            if not single_line and len(' '.join(parts)) / len(parts) < 7:
                lines = []
                for i in range(0, (len(parts) // 10) + 1):
                    lines.append('\t'.join(parts[i * 10:(i * 10) + 9]))
                content = delimiter + (delimiter.join(lines)) + tail
            elif parts or tail:
                content = delimiter + (delimiter.join(parts)) + tail
            else:
                content = ''
        self.writeln('%s(%s%s%s)' % (command, name, options, content))

    def set_property(self, target_type, targets, property_name, values):
        if not isinstance(targets, basestring):
            targets = ' '.join(targets)
        if not isinstance(values, basestring):
            values = ' '.join(values)
        self.writeln(self.indent + 'set_property(%s %s PROPERTY %s %s)' % (target_type, targets, property_name, values))


class CmakeTarget(object):
    def __init__(self, command, target, sources, name=None):
        self.command = command
        self.common_configs = {}
        self.compiler = command.compiler
        self.target = target
        self.sources = set()
        self.libs = command.libs
        self.include_binary_dir = command.include_binary_dir
        self.referenced_libs = command.referenced_libs
        self.name_ = name if name else os.path.basename(target)
        self.parent = None
        self.generator = None
        self.output = None
        self.indent = 0
        self.depends = set()
        self.destinations = set()
        self.output_name = None
        if sources:
            self.add_sources(sources)

    def __repr__(self):
        children = ', '.join('%s=%s' % it for it in sorted(filter(lambda it: it[1], self.__dict__.items())))
        return "%s.%s{%s}" % (self.__class__.__name__, self.name(), children)

    def bind(self, generator):
        self.generator = generator
        self.common_configs = generator.common_configs
        self.output = OutputWithIndent(generator.output, '\t' * self.indent)

    def name(self):
        if self.name_ is None:
            self.name_ = self.get_name()
        return self.name_

    def get_name(self):
        output_name = PathUtils.name_for_target(self.target)
        if self.name_ is None: traceback.print_stack()
        return output_name

    def set_name(self, name):
        self.name_ = name

    def set_command(self, command):
        self.command.update(command)

    def set_destination(self, destination):
        self.destinations.add(destination)

    def get_destinations(self):
        destinations = []
        prefix = self.generator.install_prefix
        for destination in self.destinations:
            destinations.append(relpath(destination, prefix))
        return destinations

    def add_sources(self, sources):
        self.sources.update(sources)

    def real_sources(self):
        return self.sources

    def get_sources(self):
        return sorted(self.sources)

    def get_values(self, name):
        values = list(getattr(self.command, name))
        for common in self.common_configs.get(name, []):
            if common in values: values.remove(common)
        return values

    def add_depends(self, depends):
        self.depends.update(depends)

    def add_destination(self, destination):
        self.destinations.add(destination)

    def set_parent(self, parent):
        indent = 1 if parent else 0
        if self.parent:
            indent -= 1
        self.parent = parent
        if indent:
            self.increase_indent(indent)

    def increase_indent(self, indent=1):
        self.indent += indent

    def cmake_command(self):
        return 'add_custom_target'

    def command_options(self):
        return ''

    def output_target(self, pattern_replace={}):
        if self.generator is None:
            raise Exception('generator is None')
        command = self.cmake_command()
        options = self.get_options()
        name = self.name()
        sources = [s % pattern_replace for s in self.get_sources()]
        self.output.write_command(command, options, name, sources)
        self.output.finish()

    def write_command(self, command, options, name, parts):
        return self.output.write_command(command, options, name, parts)

    def install_files(self, install_type, destination, sources):
        if isinstance(sources, basestring):
            sources = [sources, ]
        sources = [self.generator.relpath(s) for s in sources]
        if len(sources) > 2:
            if not self.name():
                name, _ = self.generator.name_as_target(os.path.commonpath(sources))
                self.set_name(name)
            var_name = "%s_%s" % (self.name().upper(), install_type)
            self.output.write_command('set', var_name, '', sources)
            sources = ["${%s}" % var_name, ]
        self.output.write_command('install', '', install_type, sources, 'DESTINATION ' + destination)

    def cmake_resolve_source(self, path):
        return "${CMAKE_CURRENT_SOURCE_DIR}/%s" % self.generator.relpath(path)


class CppTarget(CmakeTarget):
    def __init__(self, command, target, sources=None):
        super(CppTarget, self).__init__(command, target, sources)

    def output_target(self, pattern_replace={}):
        command = self.cmake_command()
        options = self.command_options()
        name = self.name()
        output_name = self.get_name()
        binary_dir = self.generator.binary_dir
        parts = []
        for s in self.sources:
            if s in self.referenced_libs: continue
            if s.startswith(binary_dir + '/'):
                part = cmake_resolve_binary(s, binary_dir)
            else:
                part = self.generator.relpath(s)
            parts.append(part)
        parts = sorted(parts)
        var_name = name.upper() + '_SRCS'
        var_refer = '${%s}' % var_name
        self.output_list_definition(var_name, parts)
        if self.command.compile_c_as_cxx:
            self.write_command('set_source_files_properties', 'PROPERTIES', var_refer, 'LANGUAGE CXX')
        self.write_command(command, options, name, var_refer)
        if name != output_name:
            self.output.set_property('TARGET', name, 'LIBRARY_OUTPUT_NAME', output_name)
        self.output_target_config(self.name())
        if self.depends:
            depends = sorted([self.generator.name_as_target(path)[0] for path in self.depends])
            self.write_command('add_dependencies', '', name, depends)
        for destination in self.get_destinations():
            self.install_files('TARGETS', destination, self.name())
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
        return 'add_library'

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
        for lib, linkage in self.referenced_libs.items():
            if lib in self.generator.db.linkings:
                target_name, output_name = self.generator.name_as_target(lib)
                libs.add(target_name)
            else:
                refer = self.refer_linked_target(lib, linkage)
                libs.add(refer if refer else lib)
        if libs:
            debug("Target %s using referenced libs %s" % (name, ' '.join(libs)))
        libs.update(self.libs)
        if libs:
            self.write_command('target_link_libraries', 'PRIVATE', name, sorted(libs))

    def refer_linked_target(self, f, linkage):
        if linkage in ('STATIC', 'SHARED'):
            return f
        elif linkage == 'SOURCE':
            refer = cmake_resolve_binary(f, self.generator.directory, self.generator.root_dir)
            debug("refer generated source %s" % refer)
            return refer
        return None


class ExecutableTarget(CppTarget):
    def __init__(self, command, target, sources=None):
        super(ExecutableTarget, self).__init__(command, target, sources)

    def cmake_command(self):
        return 'add_executable'


class LibraryTarget(CppTarget):
    def __init__(self, command, target, sources=None, libtype='STATIC'):
        super(self.__class__, self).__init__(command, target, sources)
        self.libtype = libtype

    def cmake_command(self):
        return 'add_library'

    def command_options(self):
        return self.libtype


class LocaleTarget(CmakeTarget):
    def __init__(self, command, target, sources=None):
        super(self.__class__, self).__init__(command, target, sources)


class CustomCommandTarget(CmakeTarget):
    CUSTOM_TARGET_OUTPUT_CONFIG = {
        'glib-genmarshal': '--output ',
        'dbus-binding-tool': '--output=',
        'moc': '-o ',
        'uic': '-o ',
        'rcc': '-o ',
        'msgfmt': '-o ',
    }

    def __init__(self, command, target, sources):
        super(self.__class__, self).__init__(command, target, sources)

    def get_options(self):
        values = list(self.command.options)
        for inc in self.command.includes:
            inc = self.generator.relpath(inc)
            if not os.path.isabs(inc):
                inc = '${CMAKE_CURRENT_SOURCE_DIR}/' + inc
            option_arg = '-I' if PathUtils.isdir(inc) else '--include '
            values.append(option_arg + inc)
        for define in self.command.definitions:
            values.append('-D' + define)
        return values

    def output_target(self, pattern_replace={}):
        target = 'OUTPUT ' + self.generator.relpath(self.target % pattern_replace)
        command_line = 'COMMAND %s %s' % (self.compiler, ' '.join(self.get_options()))
        parts = []
        parts.append(command_line)
        source_parts = []
        sources = self.get_sources()
        for s in sources:
            s = s % pattern_replace
            source = cmake_resolve_source(s, self.generator.directory)
            source_parts.append(source)
        parts += source_parts
        output_args = self.custom_target_output_args()
        self.output.write_command('add_custom_command', '', target, parts, output_args)
        self.output.finish()

    def custom_target_output_args(self):
        prefix = CustomCommandTarget.CUSTOM_TARGET_OUTPUT_CONFIG.get(self.compiler, ' ')
        return prefix + relpath(self.target, self.generator.binary_dir)


class InstallTarget(CmakeTarget):
    def __init__(self, command, target, sources, linkage='FILES'):
        super(InstallTarget, self).__init__(command, target, sources)
        if linkage == 'EXECUTABLE':
            self.install_type = 'PROGRAMS'
        elif linkage == 'DIRECTORY':
            self.install_type = linkage
        else:
            self.install_type = 'FILES'
        self.destinations.add(target)

    def output_target(self, pattern_replace={}):
        for destination in self.get_destinations():
            destination = destination % pattern_replace
            sources = [s % pattern_replace for s in self.get_sources()]
            self.install_files(self.install_type, destination, sources)
        if not self.indent:
            self.output.finish()


class WrappedTarget(CmakeTarget):
    def __init__(self, command, target, sources=None):
        super(WrappedTarget, self).__init__(command, target, sources)
        self.children = []

    def append_child(self, child):
        child.set_parent(self)
        self.children.append(child)


class ForeachTargetWrapper(WrappedTarget):
    def __init__(self, command, target, sources):
        super(ForeachTargetWrapper, self).__init__(command, target, sources)

    def real_sources(self):
        sources = []
        for child in self.children:
            for source in child.get_sources():
                if source.find('${X}') >= 0:
                    pattern = source.replace('${X}', '%(X)s')
                    for part in self.sources:
                        patched = pattern % {'X': part}
                        sources.append(patched)
                else:
                    sources.append(source)
        return sources

    def bind(self, generator):
        super(ForeachTargetWrapper, self).bind(generator)
        for child in self.children:
            child.bind(generator)

    def output_target(self, pattern_replace={}):
        self.write_command('foreach', '', self.name(), self.get_sources())
        pattern_replace = pattern_replace.copy()
        pattern_replace.update({str(self.indent): '${%s}' % self.name()})
        for child in self.children:
            child.output_target(pattern_replace)
        self.write_command('endforeach', '', self.name(), [])
        self.output.finish()
