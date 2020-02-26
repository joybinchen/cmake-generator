import os
from os.path import basename, dirname, splitext, commonpath, isabs, isfile, exists
import traceback
from .utils import PathUtils, relpath, resolve, get_loggers, basestring, cmake_resolve_binary, cmake_resolve_source

__all__ = ['CmakeTarget', 'CppTarget', 'ExecutableTarget', 'LibraryTarget', 'LocaleTarget', 'InstallTarget',
           'OutputWithIndent', 'CustomCommandTarget', 'WrappedTarget', 'ForeachTargetWrapper',
           'UserVarDefinition', 'QtWrapDefinition', 'FindPackageDefinition', 'PkgCheckModulesDefinition'
           ]

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

    def write_command(self, command, options, name, parts, tail='', line_limit=40):
        single_line = len(' '.join(parts)) < line_limit
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
        self.generated = False
        self.command = command
        self.common_configs = {}
        self.target = target
        self.sources = set()
        self.name_ = name if name else basename(target)
        self.parent = None
        self.generator = None
        self.output = None
        self.indent = 0
        self.depends = set()
        self.destinations = set()
        self.output_name = None
        if command:
            self.libs = list(command.libs)
            self.compiler = command.compiler
            self.include_binary_dir = command.include_binary_dir
            self.referenced_libs = command.referenced_libs.copy()
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

    def get_options(self):
        return []

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
        if self.generated: return
        self.generated = True
        if self.generator is None:
            raise Exception('generator is None')
        command = self.cmake_command()
        options = ' '.join(self.get_options())
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
        if len(sources) > 1:
            if not self.name():
                name, _ = self.generator.name_as_target(commonpath(sources))
                self.set_name(name)
            var_name = "%s_%s" % (self.name().upper(), install_type)
            self.output.write_command('set', var_name, '', sources)
            sources = ["${%s}" % var_name, ]
        else:
            destination_name = basename(destination)
            source_name = basename(sources[0])
            if isfile(destination) or not exists(destination) and source_name == destination_name:
                destination = dirname(destination)
                if source_name != destination_name:
                    destination += ' RENAME ' + destination_name
        self.output.write_command('install', '', install_type, sources, 'DESTINATION ' + destination)

    def cmake_resolve_source(self, path):
        return "${CMAKE_CURRENT_SOURCE_DIR}/%s" % self.generator.relpath(path)


class CppTarget(CmakeTarget):
    def __init__(self, command, target, sources=None):
        super(CppTarget, self).__init__(command, target, sources)

    def output_target(self, pattern_replace={}):
        if self.generated: return
        self.generated = True
        command = self.cmake_command()
        options = self.command_options()
        name = self.name()
        output_name = self.get_name()
        binary_dir = self.generator.binary_dir
        parts = []
        refers = []
        for s in self.sources:
            if s in self.referenced_libs: continue
            if s.startswith('${') and s.endswith('}'):
                refers.append(s)
                continue
            elif s.startswith(binary_dir + '/'):
                part = cmake_resolve_binary(s, binary_dir)
            else:
                part = self.generator.relpath(s)
            parts.append(part)
        parts = sorted(parts)
        var_name = name.replace('.', '_').upper() + '_SRCS'
        var_refer = '${%s}' % var_name
        refers.append(var_refer)
        refers = sorted(refers)
        self.output_list_definition(var_name, parts)
        if self.command.compile_c_as_cxx:
            for var_refer in refers:
                self.write_command('set_source_files_properties', 'PROPERTIES', var_refer, 'LANGUAGE CXX')
        self.write_command(command, options, name, refers)
        if output_name and (name != output_name):
            self.output.set_property('TARGET', name, 'LIBRARY_OUTPUT_NAME', output_name)
        self.output_target_config(self.name())
        if self.depends:
            depends = sorted([self.generator.name_as_target(path)[0] for path in self.depends])
            self.write_command('add_dependencies', '', name, depends)
        for destination in self.get_destinations():
            self.install_files('TARGETS', destination, self.name())
        self.output.finish()

    def get_unique_config(self, name, common_configs=None):
        configs = self.get_values(name)
        if common_configs is None:
            common_configs = self.generator.common_configs.get(name, [])
        unique_configs = list(filter(lambda x: x not in common_configs, configs))
        return unique_configs

    def get_options(self):
        return self.get_unique_config('options')

    def get_link_options(self):
        return self.get_unique_config('link_options')

    def get_definitions(self):
        return self.get_unique_config('definitions')

    def get_includes(self):
        includes = self.get_unique_config('includes')
        # print('get_includes for ', self.get_name(), includes)
        return includes

    def get_system_includes(self):
        return self.get_unique_config('system_includes')

    def get_iquote_includes(self):
        return self.get_unique_config('iquote_includes')

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
        libs = []
        for lib, linkage in self.referenced_libs.items():
            if lib in self.generator.db.linkings:
                target_name, output_name = self.generator.name_as_target(lib)
                if target_name not in libs:
                    libs.append(target_name)
            else:
                refer = self.refer_linked_target(lib, linkage)
                if refer: lib = refer
                if lib not in libs:
                    libs.append(lib)
        if libs:
            debug("Target %s using referenced libs %s" % (name, ' '.join(libs)))
        for lib in self.libs:
            if lib not in libs:
                libs.append(lib)
        if libs:
            self.write_command('target_link_libraries', 'PRIVATE', name, libs)

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

    def get_name(self):
        extname = splitext(self.target)[1]
        if extname not in ('o', 'so', 'dll', 'a'):
            return basename(self.target)
        return super(self.__class__, self).get_name()

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
            if not isabs(inc):
                inc = '${CMAKE_CURRENT_SOURCE_DIR}/' + inc
            option_arg = '-I' if PathUtils.isdir(inc) else '--include '
            values.append(option_arg + inc)
        for define in self.command.definitions:
            values.append('-D' + define)
        return values

    def output_target(self, pattern_replace={}):
        if self.generated: return
        self.generated = True
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


class UserVarDefinition(CmakeTarget):
    def __init__(self, name, sources):
        super(UserVarDefinition, self).__init__(None, name, sources)

    def cmake_command(self):
        return 'set'

    def with_components(self):
        return ''

    def output_target(self, pattern_replace={}):
        if self.generated: return
        self.generated = True
        command = self.cmake_command()
        name = self.name()
        sources = [self.generator.relpath(s % pattern_replace) for s in self.get_sources()]
        self.output.write_command(command, self.with_components(), name, sources, self.command_options(), line_limit=180)


class QtWrapDefinition(UserVarDefinition):
    def __init__(self, kind, name, sources):
        super(QtWrapDefinition, self).__init__(name, sources)
        self.kind = kind

    def cmake_command(self):
        return self.kind


class PkgCheckModulesDefinition(UserVarDefinition):
    def __init__(self, name, lib):
        super(PkgCheckModulesDefinition, self).__init__(name, [])
        self.lib = lib

    def cmake_command(self):
        return "pkg_check_modules"

    def command_options(self):
        return self.lib

    def with_components(self):
        return 'REQUIRED'


class FindPackageDefinition(UserVarDefinition):
    def __init__(self, name, mode, module):
        super(FindPackageDefinition, self).__init__(name, [])
        self.mode = mode
        if module: self.add_module(module)

    def add_module(self, module):
        if module: self.sources.add(module)

    def cmake_command(self):
        return "find_package"

    def command_options(self):
        return "REQUIRED"

    def with_components(self):
        return 'COMPONENTS' if self.sources else self.mode


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
        if self.generated: return
        self.generated = True
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
        if self.generated: return
        self.generated = True
        self.write_command('foreach', '', self.name(), self.get_sources())
        pattern_replace = pattern_replace.copy()
        pattern_replace.update({str(self.indent): '${%s}' % self.name()})
        for child in self.children:
            child.output_target(pattern_replace)
        self.write_command('endforeach', '', self.name(), [])
        self.output.finish()
