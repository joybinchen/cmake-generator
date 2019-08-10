from .utils import PathUtils
import os
import re
import logging

logger = logging.getLogger(__name__)
info = logger.info
debug = logger.debug
warn = logger.warning
error = logger.error

DISALLOWED_CHARACTERS = re.compile("[^A-Za-z0-9_.+\\-]")

CUSTOM_TARGET_OUTPUT_CONFIG = {
    'glib-genmarshal': '--output ',
    'dbus-binding-tool': '--output=',
    'moc': '-o ',
    'msgfmt': '-o ',
}


class CmakeGenerator(PathUtils):
    used_names = {"": ""}

    def __init__(self, database, name, cwd, single_file=False):
        super(self.__class__, self).__init__(cwd)
        self.db = database
        self.name = name
        self.output = open(os.path.join(cwd, 'CMakeLists.txt'), 'w')
        self.single_file = single_file
        self.write_project_header()

    def write(self, *args, **kwargs):
        self.output.write(*args, **kwargs)
        if logger.level >= logging.DEBUG: self.output.flush()

    def output_project_common_args(self, arg_name, values):
        if not values:
            return
        if arg_name.endswith('includes'):
            if arg_name == 'includes':
                self.write_command('include_directories', 'AFTER', '', values)
            elif arg_name == 'system_includes':
                self.write_command('include_directories', 'AFTER', 'SYSTEM', values)
            elif arg_name == 'iquote_includes':
                self.write_command('include_directories', 'AFTER', '', values)
        elif arg_name in ('options', 'definitions'):
            self.write_command('add_compile_' + arg_name, '', '', values)

    def write_project_header(self):
        self.write('cmake_minimum_required(VERSION 2.8.8)\n')
        info("write project %s in directory \t%s" % (self.name, self.directory))
        self.write('project({} LANGUAGES C CXX)\n\n'.format(self.name))

    def custom_target_output_args(self, compiler, target):
        prefix = CUSTOM_TARGET_OUTPUT_CONFIG.get(compiler, ' ')
        return prefix + self.cmake_resolve_binary(target)

    def cmake_resolve_source(self, path):
        return "${CMAKE_CURRENT_SOURCE_DIR}/%s" % self.relpath(path)

    def cmake_resolve_binary(self, path):
        return "${CMAKE_CURRENT_BINARY_DIR}/%s" % self.relpath(path)

    def get_include_path(self, include_path):
        if include_path.startswith(self.db.directory) \
                or include_path == self.db.directory[:-1]:
            return os.path.relpath(include_path, self.directory[:-1])
        return include_path

    def name_as_target(self, path):
        relative_path = self.relpath(path).rsplit('/', 1)[-1]
        basename = os.path.basename(relative_path)
        name = basename.rsplit('.', 1)[0]
        name = DISALLOWED_CHARACTERS.sub("_", name)
        name = name if not name.startswith('lib') else name[3:]
        return self.use_target_name(name, path)

    def use_target_name(self, name, path):
        if path is None:
            path = self.resolve(name, self.directory)
        used_path = self.used_names.get(name)
        if used_path == path:
            return name
        if used_path is not None:
            index = 2
            while True:
                candidate = '{}_{}'.format(name, index)
                if candidate not in self.used_names:
                    name = candidate
                    break
                index = index + 1
        self.used_names[name] = path
        return name

    def output_subdirectory(self, directory):
        info("Project in %s add subdirectory %s"
             % (self.db.relpath(self.directory), self.db.relpath(directory)))
        self.write("add_subdirectory(%s)\n" % self.relpath(directory))

    def output_linked_target(self, cmd_id, files, target, libtype):
        name = self.name_as_target(target)
        debug("%s %s linked by cmd #%s from %s"
              % (libtype, self.relpath(target), cmd_id,
                 ' '.join([self.relpath(f) for f in files])))
        config = {k: v for (k, v) in self.db.command[cmd_id].items()}
        source_files, config = self.migrate_sub_compilations(config, files, target, name)
        debug("Target %s output linked %s %s for %s"
              % (name, libtype, self.relpath(target),
                 ' '.join([self.relpath(f) for f in source_files])))
        self.output_cmake_target(name, config, source_files, target, libtype)

    def migrate_sub_compilations(self, config, files, target, name):
        source_files = set()
        referenced_libs = set()
        compilations = {}
        for f in files:
            if f in self.db.linkings:
                refer = self.refer_linked_target(f)
                info('%s refer linked target %s'
                     % (self.relpath(target), self.relpath(refer or f)))
                if refer:
                    if refer.startswith('${CMAKE'):
                        config['include_binary_dir'] = True
                    referenced_libs.add(refer)
                else:
                    source_files.add(f)
                continue
            if f not in self.db.objects:
                if f.rsplit('.', 1)[-1] not in ('c', 'cpp', 'cc', 'java', 'qm', 'qch', 'ts', 'po'):
                    info('%s referenced %s not in linked objects as bellow\n\t%s'
                         % (self.relpath(target), f,
                            '\n\t'.join(self.db.linkings.keys())))
                source_files.add(f)
                continue
            for source, cmd_id in self.db.objects[f].items():
                if self.db.command[cmd_id].get('linkage') != 'INSTALL':
                    compilations.setdefault(cmd_id, {})[source] = f
        if referenced_libs:
            config.setdefault('referenced_libs', set()).update(referenced_libs)
        if len(compilations) > 1:
            warn("Target %s is created by multiple commands: %s"
                 % (self.db.relpath(target),
                    ' '.join(["#%s" % cmd for cmd in compilations])))
        for cmd_id, source_product in compilations.items():
            for k, v in self.db.command[cmd_id].items():
                value = config.get(k, v)
                if type(value) in (set, tuple, frozenset):
                    value = list(value)
                    config[k] = value
                if isinstance(value, list):
                    for part in v:
                        if part not in value:
                            value.append(part)
                elif v and not config.get(k):
                    config[k] = v
            for source, product in source_product.items():
                self.reduce_target(source, cmd_id, product, name)
                if source in self.db.linkings:
                    command_sources = self.db.linkings[source]
                    for cid in command_sources.keys():
                        if self.db.command[cid]['linkage'] == 'SOURCE':
                            config['include_binary_dir'] = True
                source_files.add(source)
        return source_files, config

    def refer_linked_target(self, f):
        command_sources = self.db.linkings[f]
        if not command_sources:
            return None
        if len(command_sources) > 1:
            warn("find multiple command creating the same target: %s" % f)
        cmd_id = next(iter(command_sources.keys()))
        linkage = self.db.command[cmd_id].get('linkage')
        if linkage in ('STATIC', 'SHARED'):
            return self.name_as_target(f)
        elif linkage == 'SOURCE':
            refer = self.cmake_resolve_binary(f)
            debug("refer generated source %s" % refer)
            return refer
        return None

    def reduce_target(self, source, cmd_id, product, name):
        target_sources = self.db.targets.get(cmd_id, {})
        sources = target_sources.get(product, set())
        if source in sources:
            sources.remove(source)
            if not sources:
                target_sources.pop(product)
                debug("pop %s from targets of cmd #%s"
                      % (self.relpath(product), cmd_id))
            debug("Target %s use source %-20s instead of %s"
                  % (name, self.relpath(source), self.relpath(product)))
        else:
            warn("file %s not in source list of target %s\n\t%s\n%s" % (
                source, product, '\n\t'.join(sources), cmd_id))

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

    def output_compile_args(self, arg_type, name, config):
        parts = config.get(arg_type, ())
        info("Target %s output compile %-11s: %s"
             % (name, arg_type, ' '.join(parts)))
        if not parts: return
        self.write_command('target_compile_' + arg_type, 'PRIVATE', name, parts)

    def output_custom_command(self, target, cmd_id, sources):
        config = self.db.command[cmd_id]
        info("cmd #%s output custom target %s generated from %s"
             % (cmd_id, self.relpath(target), ' '.join([self.relpath(f) for f in sources])))
        compiler = config.get('compiler')
        options = config.get('options', ())
        self.write("add_custom_command(OUTPUT %s\n\tCOMMAND %s\n\t%s\n\t%s\n\t%s\n)\n"
                          % (self.relpath(target), compiler, ' '.join(options),
                             self.cmake_resolve_source('${X}'),
                             self.custom_target_output_args(compiler, target)))

    def output_locales(self, cmd_id, config, dest_pattern, src_pattern, paths):
        if src_pattern:
            matcher = re.compile(src_pattern % {'0': '(.*)'})
            fields = [matcher.match(x[0]).groups()[0] for x in paths]
        else:
            fields = ["''"]
        info("Locales created by cmd #%s to %s" % (cmd_id, ' '.join(fields)))
        self.write_command('foreach', '', 'X', fields)
        compiler = config['compiler']
        options = config.get('options', [])
        self.write("add_custom_command(OUTPUT %s\n\tCOMMAND %s %s\n\t%s\n\t%s\n)\n"
                          % (self.relpath(dest_pattern % {'0': '${X}'}),
                             compiler, ' '.join(options),
                             self.cmake_resolve_source(src_pattern % {'0': '${X}'}),
                             self.custom_target_output_args(
                                 compiler, dest_pattern % {'0': '${X}'})))
        self.write('endforeach(X)\n\n')

    def output_migrated_install(self, dest_pattern, file_pattern, matched):
        self.write_command('foreach', '', 'X', matched)
        self.write('install(%s\t%s\n\tDESTINATION\t%s\n)\n'
                          % ('FILES', self.relpath(file_pattern % {'0': '${X}'}),
                             dest_pattern % {'0': '${X}'}))
        self.write('endforeach(X)\n\n')

    def output_cmake_install(self, name, config, files):
        install_groups = {}
        for f in files:
            source_commands = self.db.objects.get(f, None)
            if source_commands is None:
                warn('Target %s without a command to create installed file: %s'
                     % (name, self.resolve(f)))
                install_groups.setdefault(-1, set()).add(f)
                continue
            cmd_id = next(iter(source_commands.values()))
            install_groups.setdefault(cmd_id, set()).add(f)
        for cmd_id, file_set in iter(install_groups.items()):
            if cmd_id >= 0:
                command = self.db.command[cmd_id]
                linkage = command.get('linkage', 'OBJECT')
                install_type = 'PROGRAMS' if linkage == 'EXECUTABLE' else 'FILES'
            else:
                install_type = 'FILES'
            self.write('install(%s\n\t%s\n\tDESTINATION %s\n)\n'
                              % (install_type,
                                 ' '.join([self.relpath(f) for f in file_set]),
                                 config.get('destination', 'NO-DESTINATION')))

    def output_cmake_target(self, name, config, files, target, libtype):
        if not files or not name: return
        files = sorted([self.relpath(f) for f in files])
        missing_depends = config.get('missing_depends', [])
        if missing_depends:
            missing_depends = [self.relpath(f) for f in missing_depends]
            warn("Target %s depends on missing files: %s"
                 % (name, ' '.join(missing_depends)))
            files.extend(missing_depends)
            config['include_binary_dir'] = True
        name = self.use_target_name(name, target)
        info("Target %s output cmake %-13s: %s" % (name, libtype, ' '.join(files)))
        if not libtype or libtype == 'EXECUTABLE':
            self.write_command('add_executable', '', name, files)
        else:
            self.write_command('add_library', libtype, name, files)
        self.output_target_config(name, config)

    def output_target_config(self, name, config):
        self.output_compile_args('options', name, config)
        self.output_compile_args('definitions', name, config)
        if config.get('include_binary_dir'):
            self.output_includes('PRIVATE', name, ['${CMAKE_CURRENT_BINARY_DIR}'])
        self.output_includes('PRIVATE', name, config.get('includes'))
        self.output_includes('SYSTEM PRIVATE', name, config.get('system_includes'))
        self.output_includes('BEFORE PRIVATE', name, config.get('iquote_includes'))
        self.output_target_libs(name, config)

    def output_target_libs(self, name, config):
        libs = config.get('referenced_libs', set()).copy()
        if libs:
            debug("Target %s using referenced libs %s" % (name, ' '.join(libs)))
        libs.update(config.get('libs', set()))
        if libs:
            self.write_command('target_link_libraries', 'PRIVATE', name, libs)


if __name__ == '__main__':
    # FORMAT = '%(asctime)-15s %(levelname)-8s %(module)s %(message)s'
    FORMAT = '%(levelname)-8s %(lineno)5d %(message)s'
    logging.basicConfig(format=FORMAT)
