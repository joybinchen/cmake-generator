import os
import re
import logging
from io import StringIO
from .utils import *
from .migration import get_common_values
from .target import *

logger, info, debug, warn, error = get_loggers(__name__)


class CmakeGenerator(PathUtils):
    used_names = {"": ""}

    def __init__(self, converter, name, cwd, single_file=False):
        PathUtils.__init__(self, cwd, converter.root_dir)
        self.db = converter.db
        self.name = name
        self.output = self.stream = StringIO() # open(os.path.join(cwd, 'CMakeLists.txt'), 'w')
        self.single_file = single_file
        # targets: {t.name: t, t.target: t, }
        self.targets = {}
        self.other_installs = []
        self.common_configs = {}
        self.install_prefix = '/'

    def relpath(self, path, root=None):
        return relpath(path, self.directory, root if root else self.root_dir)

    def command_linkage(self, cmd_id):
        return self.db.command_linkage(cmd_id)

    def write(self, *args, **kwargs):
        self.output.write(*args, **kwargs)
        if logger.level >= logging.DEBUG: self.output.flush()

    def set_install_prefix(self, prefix):
        self.install_prefix = prefix

    def write_to_file(self):
        self.output = open(os.path.join(self.directory, 'CMakeLists.txt'), 'w')
        self.write_project_header()
        self.output.write(self.stream.getvalue())
        cpp_targets = tuple(filter(lambda t: isinstance(t, CppTarget), self.targets))
        for arg_name in ('options', 'link_options', 'definitions',
                         'includes', 'system_includes', 'iquote_includes'):
            arg_values = [getattr(t.command, arg_name) for t in cpp_targets]
            values = get_common_values(arg_name, arg_values)
            self.common_configs[arg_name] = values
            self.output_project_common_args(arg_name, values)
        self.write_targets()

    def write_targets(self):
        for target in set(self.targets.values()):
            target.bind(self)
            target.output_target()
        for target in self.merged_wrapped_targets(self.other_installs):
            target.bind(self)
            target.output_target()

    @staticmethod
    def merged_wrapped_targets(targets):
        merged_targets = []
        for target in targets:
            if not isinstance(target, WrappedTarget):
                merged_targets.append(target)
                continue
            merged = False
            for other in merged_targets:
                if type(other) == type(target) and other.sources == target.sources:
                    for child in target.children:
                        other.append_child(child)
                    merged = True
                    break
            if not merged:
                merged_targets.append(target)
        return merged_targets

    def output_project_common_args(self, arg_name, values):
        if not values:
            return
        if arg_name.endswith('includes'):
            values = list(map(self.relpath, values))
            if arg_name == 'includes':
                self.write_command('include_directories', 'AFTER', '', values)
            elif arg_name == 'system_includes':
                self.write_command('include_directories', 'AFTER', 'SYSTEM', values)
            elif arg_name == 'iquote_includes':
                self.write_command('include_directories', 'AFTER', '', values)
        elif arg_name == 'link_options':
            self.write_command('add_link_options', '', '', values)
        elif arg_name in ('options', 'definitions'):
            self.write_command('add_compile_' + arg_name, '', '', values)

    def write_project_header(self):
        self.write('cmake_minimum_required(VERSION 2.8.8)\n')
        info("write project %s in directory \t%s" % (self.name, self.directory))
        self.write('project({} LANGUAGES C CXX)\n\n'.format(self.name))

        for target in self.targets.values():
            if target.command.use_thread:
                self.write('find_package(Threads)\n')
                break

    def custom_target_output_args(self, compiler, target):
        prefix = CustomCommandTarget.CUSTOM_TARGET_OUTPUT_CONFIG.get(compiler, ' ')
        return prefix + cmake_resolve_binary(target, self.directory)

    def cmake_resolve_source(self, path):
        return "${CMAKE_CURRENT_SOURCE_DIR}/%s" % self.relpath(path)

    def get_include_path(self, include_path):
        if include_path.startswith(self.db.directory + '/') \
                or include_path == self.db.directory:
            return os.path.relpath(include_path, self.directory)
        return include_path

    def name_for_lib(self, path):
        return PathUtils.name_for_target(self.relpath(path))

    def name_as_target(self, path):
        output_name = self.name_for_lib(path)
        name = self.use_target_name(output_name, path)
        return name, output_name

    def use_target_name(self, name, path):
        if path is None:
            path = self.resolve(name, self.directory)
        used_name = self.used_names.get(path)
        if used_name:
            return used_name
        used_path = self.used_names.get(name)
        if used_path is not None:
            info('use_target_name %s with duplicate path: %s %s on %s' % (name, path, used_path, self.directory))
            index = 2
            while True:
                candidate = '{}_{}'.format(name, index)
                if candidate not in self.used_names:
                    name = candidate
                    break
                index = index + 1
        self.used_names[name] = path
        self.used_names[path] = name
        return name

    def output_subdirectory(self, directory):
        info("Project in %s add subdirectory %s"
             % (self.db.relpath(self.directory), self.db.relpath(directory)))
        self.write("add_subdirectory(%s)\n" % self.relpath(directory))

    def output_linked_target(self, command, files, target, libtype, name, depends):
        debug("Target %s output linked %s %s for %s"
              % (name, libtype, self.relpath(target), self.joined_relpath(files)))
        if not libtype or libtype == 'EXECUTABLE':
            name = self.use_target_name(name, target)
            linked_target = ExecutableTarget(command, target, files)
        else:
            output_name = PathUtils.name_for_target(target)
            library = self.targets.get(output_name)
            if (isinstance(library, LibraryTarget)
                    and set(files) == library.sources
                    and {'STATIC', 'SHARED'} == {library.libtype, library}):
                library.libtype = ''
                self.targets[target] = library
                return
            name = self.use_target_name(name, target)
            linked_target = LibraryTarget(command, target, files, libtype)
        linked_target.set_name(name)
        linked_target.add_depends(depends)
        self.targets[name] = linked_target
        self.targets[target] = linked_target

    def write_command(self, command, options, name, parts, single_line=None):
        if single_line is None:
            single_line = len(' '.join(parts)) < 40
        delimiter = ' ' if single_line else '\n    '
        tail = '' if single_line else '\n'
        if not single_line and len(' '.join(parts)) / len(parts) < 7:
            lines = []
            for i in range(0, (len(parts) // 10) + 1):
                lines.append('\t'.join(parts[i*10:(i*10)+9]))
            content = delimiter + (delimiter.join(lines)) + tail
        else:
            content = delimiter + (delimiter.join(parts)) + tail
        self.write('%s(%s %s%s)\n' % (command, name, options, content))

    def output_includes(self, options, name, parts):
        if not parts:
            return
        parts = [self.get_include_path(include) for include in parts]
        info("Target %s includes %s %s" % (name, options, ' '.join(parts)))
        self.write_command('target_include_directories', options, name, parts)

    def output_compile_args(self, arg_type, name, parts):
        info("Target %s output compile %-11s: %s" % (name, arg_type, ' '.join(parts)))
        if not parts: return
        self.write_command('target_compile_' + arg_type, 'PRIVATE', name, parts)

    def output_custom_command(self, target, cmd_id, sources):
        config = self.db.command[cmd_id]
        name, output_name = self.name_as_target(target)
        self.targets[target] = CustomCommandTarget(config, target, sources)
        if name != output_name:
            self.targets[target].set_name(name)
        return
        info("cmd #%s output custom target %s generated from %s"
             % (cmd_id, self.relpath(target), self.joined_relpath(sources)))
        compiler = config.compiler
        options = config.options
        self.write("add_custom_command(OUTPUT %s\n\tCOMMAND %s\n\t%s\n\t%s\n\t%s\n)\n"
                          % (self.relpath(target), compiler, ' '.join(options),
                             self.cmake_resolve_source('${X}'),
                             self.custom_target_output_args(compiler, target)))

    def output_locales(self, cmd_id, command, dest_pattern, src_pattern, paths):
        if src_pattern:
            matcher = re.compile(src_pattern % {'0': '(.*)'})
            fields = [matcher.match(x[0]).groups()[0] for x in paths]
        else:
            fields = ["''"]
        info("Locales created by cmd #%s to %s" % (cmd_id, ' '.join(fields)))
        dest = dest_pattern % {'0': '${X}'}
        source = src_pattern % {'0': '${X}'}
        custom_command = CustomCommandTarget(command, dest, [source, ])
        wrapper = ForeachTargetWrapper(command, 'X', fields)
        wrapper.append_child(custom_command)
        self.other_installs.append(wrapper)
        return
        compiler = command.compiler
        output_args = self.custom_target_output_args(compiler, dest_pattern % {'0': '${X}'})
        self.write_command('foreach', '', 'X', fields)
        self.write("add_custom_command(OUTPUT %s\n\tCOMMAND %s %s\n\t%s\n\t%s\n)\n"
                   % (self.relpath(dest), compiler, ' '.join(command.options),
                      self.cmake_resolve_source(source), output_args))
        self.write('endforeach(X)\n\n')

    def output_migrated_install(self, command, dest_pattern, file_pattern, matched, var='X'):
        child_target = InstallTarget(command, dest_pattern, [file_pattern, ])
        target = ForeachTargetWrapper(command, var, matched)
        target.append_child(child_target)
        self.other_installs.append(target)

    def output_cmake_install(self, name, command, file_set, linkage):
        directories = []
        files = []
        destination = command.destination if command.destination else command.target
        for f in file_set:
            if f in self.targets:
                self.targets[f].add_destination(destination)
            elif linkage != 'EXECUTABLE' and os.path.isdir(f):
                directories.append(f)
            else:
                files.append(f)
        if directories:
            self.other_installs.append(InstallTarget(command, name, directories, 'DIRECTORY'))
        if files:
            install_type = linkage if linkage == 'EXECUTABLE' else 'FILES'
            self.other_installs.append(InstallTarget(command, name, files, install_type))


if __name__ == '__main__':
    # FORMAT = '%(asctime)-15s %(levelname)-8s %(module)s %(message)s'
    FORMAT = '%(levelname)-8s %(lineno)5d %(message)s'
    logging.basicConfig(format=FORMAT)
