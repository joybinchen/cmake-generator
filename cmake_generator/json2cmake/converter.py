from .utils import basestring, freeze, PathUtils
from .generator import CmakeGenerator
from diff_match_patch.diff_match_patch import diff_match_patch
import os
import re
import logging

diff = diff_match_patch().diff_main

# FORMAT = '%(asctime)-15s %(levelname)-8s %(module)s %(message)s'
logger = logging.getLogger(__name__)
info = logger.info
debug = logger.debug
warn = logger.warning
error = logger.error

DISALLOWED_CHARACTERS = re.compile("[^A-Za-z0-9_.+\\-]")


def get_diff_pattern(text1, text2):
    diff_result = diff(text1, text2)
    pattern = []
    lhs = rhs = ''
    fields = []
    for diff_type, diff_part in diff_result:
        if diff_type < 0:
            lhs += diff_part
        elif diff_type > 0:
            rhs += diff_part
        else:
            if lhs or rhs:
                if fields and len(pattern[-1]) <= 3:
                    delimiter = pattern.pop(-1)
                    field = fields.pop(-1)
                    fields.append((
                        field[0] + delimiter + lhs,
                        field[1] + delimiter + rhs,
                    ))
                else:
                    pattern.append('%%(%d)s' % len(fields))
                    fields.append((lhs, rhs))
                lhs = rhs = ''
            pattern.append(diff_part)
    # debug('Diff result %s for %s %s: %s' % (pattern, text1, text2, fields))
    return ''.join(pattern), fields


class CmakeConverter(PathUtils):

    generators = {}

    def __init__(self, database, name, cwd, single_file=False):
        super(self.__class__, self).__init__(cwd)
        self.db = database
        self.name = name
        self.single_file = single_file
        self.common_configs = {}

    def simplify_command_common_args(self, arg_name):
        common_values = None
        for values in [cmd.get(arg_name) for cmd in self.db.command]:
            if values:
                if common_values is None:
                    common_values = list(values)
                    continue
                for v in common_values:
                    if v not in values:
                        common_values.remove(v)
        if not common_values:
            return None
        self.common_configs[arg_name] = common_values
        for command in self.db.command:
            values = command.get(arg_name)
            if values is None:
                continue
            new_values = filter(lambda x: x not in common_values, values)
            command[arg_name] = freeze(tuple(new_values))
        return common_values

    def migrate_install_commands(self):
        groups = {}
        installs = list(filter(lambda x: len(x[1]) == 1, self.db.installs.items()))
        migrated_commands = {}
        for cmd_id, target_files in installs:
            self.db.installs.pop(cmd_id)
            command = self.db.install_command[cmd_id].copy()
            command.pop('destination')
            target, file_ = next(iter(target_files.items()))
            freeze_command = freeze(command)
            new_cmd_id = migrated_commands.get(freeze_command)
            if new_cmd_id is None:
                new_cmd_id = len(self.db.install_command)
                migrated_commands[freeze_command] = new_cmd_id
                self.db.install_command.append(dict(command))
            dest_groups = groups.setdefault(freeze_command, {})
            self.migrate_command(target, file_, dest_groups)
            self.db.install_command[cmd_id] = None
            debug('Install cmd #%d migrated into cmd #%d' % (cmd_id, new_cmd_id))

        for command, dest_groups in groups.items():
            cmd_id = migrated_commands[command]
            self.db.installs[cmd_id] = dest_groups

    def migrate_command(self, target, source, groups):
        if not groups:
            info('Initialize empty group with source & target\n\t%s => %s'
                 % (target, source))
            groups[(target, '')] = [(source, target), ]
            return True

        for (dest, src_pattern), file_targets in groups.items():
            if src_pattern:
                matcher = re.compile(src_pattern % {'0': '(.*)'})
                matched = matcher.match(source)
                if matched:
                    match_groups = matched.groups()
                    convert_dict = dict([(str(i), g) for i, g in
                                         zip(range(0, len(match_groups)), match_groups)])
                    converted_target = dest % convert_dict
                    if converted_target == target:
                        file_targets.append((source, target))
                        debug(('Existed pattern\t%s\t%s\n\t' % (src_pattern, dest)) +
                              ('matches source and target\t%s\t%s\n' % (source, target)))
                        return True

        for (dest, src_pattern), file_targets in groups.items():
            prev_pattern = src_pattern or file_targets[0][0]
            file_pattern, file_fields = get_diff_pattern(
                prev_pattern, source)
            if len(file_fields) != 1: continue
            dest_pattern, dest_fields = get_diff_pattern(dest, target)
            if not dest_pattern: continue
            debug('\n\t'.join([
                'Found pattern %s with fields %s for' % (dest_pattern, dest_fields),
                dest, target,
                'src_pattern=\t' + src_pattern,
                'file_pattern=\t' + file_pattern
            ]))

            field_dict = {}
            pattern_ok = True
            for field in dest_fields:
                if field not in file_fields:
                    pattern_ok = False
                    break
                field_dict[str(file_fields.index(field))] = field[1]
            if not pattern_ok: continue

            info('migrating under %s\t%s\n''got\t%s\n\t%s\n''for\t%s\n\t%s\nand\t%s'
                 % (prev_pattern, field_dict,
                    dest_pattern, target,
                    file_pattern, source,
                    '\n\t'.join(["%s <- %s" % (t, self.relpath(f))
                                 for f, t in file_targets[:3]])))
            file_targets.append((source, target))
            if src_pattern != file_pattern:
                if src_pattern:
                    matcher = re.compile(file_pattern % {'0': '(.*)'})
                    for file_, target in file_targets:
                        if not matcher.match(file_):
                            return True
                    info('migrate_command when %s\n\t replace\t%s\n\t ===>\t%s\n targets:\n\t%s'
                         % ((source, target),
                            (dest, src_pattern),
                            (dest_pattern, file_pattern),
                            '\n\t'.join(["%s\t%s" % x for x in file_targets])))
                groups.pop((dest, src_pattern))
                groups[(dest_pattern, file_pattern)] = file_targets
            return True
        info('No matching pattern %s in groups' % target)
        groups[(target, '')] = [(source, target), ]
        return True

    def convert(self):
        root_generator = self.get_root_generator()
        for arg_name in ('includes', 'system_includes', 'iquote_includes',
                         'options', 'definitions'):
            values = self.simplify_command_common_args(arg_name)
            if values:
                root_generator.output_project_common_args(arg_name, values)
        self.migrate_install_commands()
        self.write()

    def write(self):
        for (target, command_source) in self.db.linkings.items():
            commands = command_source.keys()
            if len(commands) > 1:
                warn("target %s created by multiple command:\n%s" % (
                    target, commands))
            for cmd_id, files in command_source.items():
                command = self.db.command[cmd_id]
                directory = command['cwd']
                linkage = command.get('linkage', 'OBJECT')
                info("Process %s target %s" % (linkage, self.relpath(target)))
                generator = self.get_cmake_generator(directory)
                if linkage == 'SOURCE':
                    generator.output_custom_command(target, cmd_id, files)
                else:
                    generator.output_linked_target(cmd_id, files, target, linkage)

        for cmd_id, target_sources in self.db.targets.items():
            command = self.db.command[cmd_id]
            linkage = command.get('linkage', 'OBJECT')
            if linkage == 'LOCALE':
                self.output_locales(cmd_id, command, target_sources)
                continue
            files = set()
            for target, source in target_sources.items():
                if target in self.db.linkings: continue
                for f in source:
                    cmd = self.db.sources.get(f, {}).get(target, cmd_id)
                    if cmd != cmd_id:
                        warn("target %s gen by command %s and %s" % (target, cmd, cmd_id))
                    files.add(f)
            if files:
                self.output_library(cmd_id, command, tuple(files), linkage)

        for cmd_id, target_sources in self.db.installs.items():
            files = set()
            command = self.db.install_command[cmd_id]
            for target, source in target_sources.items():
                if type(target) is basestring:
                    files.add(source)
                    continue
                # target is tuple
                if target[1]:
                    self.output_migrated_install(cmd_id, target, source)
                    continue
                if len(source) != 1:
                    warn("Install target %s fail to migrate by install cmd #%s" % (target, cmd_id))
                for f in source:
                    command['destination'] = f[0]
                    files.add(f[1])
            if files:
                self.output_install(cmd_id, command, tuple(files))

    def output_migrated_install(self, cmd_id, patterns, files):
        dest_pattern, file_pattern = patterns
        if not file_pattern:
            self.output_install(cmd_id, self.db.install_command[cmd_id], files)
        matcher = re.compile(file_pattern % {'0': '(.*)'})
        matched = []
        for file_, target in files:
            match = matcher.match(file_)
            if match.groups():
                matched.append(match.groups()[0])
            else:
                debug('Fail to match %s in %s' % (file_pattern, file_))
        command = self.db.install_command[cmd_id]
        generator = self.get_cmake_generator(command['cwd'])
        generator.output_migrated_install(dest_pattern, file_pattern, matched)

    def get_root_generator(self):
        return self.get_cmake_generator(self.db.directory)

    def get_cmake_generator(self, directory):
        if self.single_file:
            directory = self.directory
        if directory == self.directory or directory + '/' == self.directory:
            name = self.name
        else:
            name = "%s-%s" % (self.name, self.relpath(directory))
        generators = self.__class__.generators
        generator = generators.get(name)
        if generator is None:
            generator = CmakeGenerator(self.db, name, directory, self.single_file)
            generators[name] = generator
            root_generator = self.get_root_generator()
            if root_generator != generator:
                root_generator.output_subdirectory(directory)
        return generator

    def output_install(self, cmd_id, config, files):
        name = self.name_by_common_prefix(files)
        directory = config['cwd']
        generator = self.get_cmake_generator(directory)
        info("Target %s installed by cmd #%s to %s"
             % (name, cmd_id, ' '.join([self.relpath(f) for f in files])))
        generator.output_cmake_install(name, config, files)

    def output_locales(self, cmd_id, command, target_sources):
        generator = self.get_cmake_generator(command['cwd'])
        groups = {}
        for target, sources in target_sources.items():
            for source in sources:
                self.migrate_command(target, source, groups)
        for (dest_pattern, src_pattern), target_sources in groups.items():
            info("cmd #%s output locale target\n\t%s"
                 % (cmd_id, '\n\t'.join(
                    ['%s <- %s' % (self.relpath(t), self.relpath(s))
                     for t, s in target_sources])))
            generator.output_locales(
                cmd_id, command, dest_pattern, src_pattern, target_sources)

    def output_library(self, cmd_id, command, files, linkage):
        generator = self.get_cmake_generator(command['cwd'])
        name = self.name_by_common_prefix(files)
        info("cmd #%s output %s library target %s with %s"
             % (cmd_id, linkage or 'unlinked', name,
                ' '.join([self.relpath(f) for f in files])))
        generator.output_cmake_target(name, command, files, None, linkage)

    @staticmethod
    def name_by_common_prefix(files):
        prefix = os.path.commonprefix(files)
        name = os.path.basename(prefix.rstrip("-_."))
        name = re.sub(DISALLOWED_CHARACTERS, "", name)
        return name


if __name__ == '__main__':
    # FORMAT = '%(asctime)-15s %(levelname)-8s %(module)s %(message)s'
    FORMAT = '%(levelname)-8s %(lineno)5d %(message)s'
    logging.basicConfig(format=FORMAT)
