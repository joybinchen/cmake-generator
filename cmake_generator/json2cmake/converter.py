import os
import re
import logging

from .utils import *
from .command import C_COMPILERS
from .migration import *
from .generator import CmakeGenerator
from .target import InstallTarget


# FORMAT = '%(asctime)-15s %(levelname)-8s %(module)s %(message)s'
logger, info, debug, warn, error = get_loggers(__name__)


class CmakeConverter(PathUtils):

    generators = {}

    def __init__(self, database, name, cwd, single_file=False):
        PathUtils.__init__(self, cwd, database.root_dir)
        self.db = database
        self.binary_dir = self.db.binary_dir()
        self.in_source_build = self.binary_dir == self.root_dir
        self.name = name
        self.single_file = single_file
        self.common_configs = {}

    def convert(self):
        generators = CmakeConverter.generators
        targets = self.db.targets
        linkings = sorted(self.db.linkings.items())
        for target, command_source in linkings:
            self.generate_linked_target(target, command_source)
        targets = self.db.targets
        for cmd_id, target_sources in targets.items():
            self.generate_unlinked_target(cmd_id, target_sources)
        migrated_commands = self.db.extract_migrated_commands()
        for cmd_id, destination_sources in migrated_commands.items():
            self.generate_migrated_install_target(cmd_id, destination_sources)
        installs = self.db.installs
        for cmd_id, destination_sources in installs.items():
            self.generate_install_target(cmd_id, destination_sources)
        destinations = set()
        for d in migrated_commands.values():
            for dest, _ in d.keys():
                destinations.add(dest)
        for d in self.db.installs.values():
            for dest in d.keys():
                destinations.add(dest)
        # if not destinations: return

        root_generator = self.get_root_generator()
        external_dests = tuple(filter(lambda d: not d.startswith(self.directory), destinations))
        cmake_install_prefix = os.path.commonpath(external_dests) if external_dests else "/usr/local"
        key_generators = sorted(generators.items(), key=lambda x: x[1].directory.count('/'), reverse=True)
        for key, _ in key_generators:
            generator = generators[key]
            if not generator.targets and len(generator.other_installs) == 1:
                target = generator.other_installs[0]
                if isinstance(target, InstallTarget) and len(target.sources) == 1:
                    for k, g in key_generators:
                        if generator.directory.startswith(g.directory + '/'):
                            g.other_installs.append(generator.other_installs.pop())
                            generator.generated = True
                            break
            if generator.generated: continue
            generator.set_install_prefix(cmake_install_prefix)
            directory = generator.setup_output()
            name = self.get_name_for_generator(directory)
            if name != key:
                generator.name = name
                generators[name] = generator
            generator.write_to_file()
            if root_generator != generator:
                root_generator.output_subdirectory(directory)

    def generate_linked_target(self, target, command_source):
        commands = command_source.keys()
        if len(commands) > 1:
            warn("target %s created by multiple command:\n%s" % (target, commands))
        for cmd_id, files in command_source.items():
            command = self.db.command[cmd_id]
            if command.linkage == "SOURCE":
                if command.compiler in ('uic', 'moc', 'rcc'):
                    return
            self.write_command_for_linked_target(command, target, files, self.db, self.directory)

    def write_command_for_linked_target(self, command, target, files, db, directory):
        files = list(files)
        missing_depends = command.missing_depends.get(target, set())
        files.extend(missing_depends)
        files.sort()
        linkage = command.linkage
        info("Process %s target %s" % (linkage, relpath(target, directory)))
        if linkage == 'SOURCE':
            generator = self.get_generator_for_sources(files)
            if command.compiler in C_COMPILERS:
                name = generator.name_for_lib(target)
                return generator.output_linked_target(command, files, target, 'OBJECT', name, set())
            return generator.output_custom_command(target, command, files)

        debug("%s %s linked by cmd #%s from %s"
              % (linkage, relpath(target, directory), command.id,
                 ' '.join([relpath(f, directory) for f in files])))
        sources, libs, compilations, depends = CmakeConverter.classify_source_files(files, target, db, directory)
        self.write_command_for_qt_generated_sources(target, sources, db, depends)

        generator = self.get_generator_for_sources(sources)
        name = generator.name_for_lib(target)
        command = command.copy()
        CmakeConverter.update_referenced_libs(command, libs)
        CmakeConverter.migrate_sub_compilations(command, compilations, target, name, db)
        generator.output_linked_target(command, sources, target, linkage, name, depends)

    def write_command_for_qt_generated_sources(self, target, sources, db, depends):
        ui_files = self.extract_generated_sources(sources, db.qt_ui_bucket, depends)
        rc_files = self.extract_generated_sources(sources, db.qt_rc_bucket, depends)
        moc_files = self.extract_generated_sources(sources, db.qt_moc_bucket, depends)
        generator = self.get_generator_for_sources(sources)
        name = generator.name_for_lib(target)
        if ui_files:
            sources.add(self.output_generated_sources(name, ui_files, "ui", "qt5_wrap_ui"))
        if rc_files:
            sources.add(self.output_generated_sources(name, rc_files, "rc", "qt5_add_resources"))
        if moc_files:
            sources.add(self.output_generated_sources(name, moc_files, "moc", "qt5_wrap_cpp"))

    def extract_generated_sources(self, files, bucket, depends):
        sources = set()
        targets = set()
        for file in files:
            if file in bucket:
                targets.add(file)
                for cmd_id, bucket_sources in bucket[file].items():
                    for source in bucket_sources: sources.add(source)
        if targets:
            files.difference_update(targets)
            depends.difference_update(targets)
        return sources

    def output_generated_sources(self, name, sources, kind, wrapper):
        generator = self.get_generator_for_sources(sources)
        var_name = "%s_%s_SRCS" % (name, kind)
        var_name = generator.unique_name(var_name)
        generator.output_qt_wrapper(var_name, sources, wrapper)
        # self.output_var_definition(var_name, sources)
        return '${%s}' % var_name

    @staticmethod
    def classify_source_files(files, target, db, directory):
        sources = set()
        libs = {}
        compilations = {}
        dependencies = set()
        for f in files:
            if f in db.linkings:
                dependencies.add(f)
                info('%s refer linked target %s' % (relpath(target, directory), relpath(f, directory)))
                linkage = db.target_linkage(f)
                if linkage in ('STATIC', 'SHARED', 'SOURCE'):
                    libs[f] = linkage
                else:
                    sources.add(f)
                continue
            if f not in db.objects:
                ext = os.path.splitext(f)[1]
                if ext == '.a':
                    libs[f] = 'STATIC'
                elif ext in ('.so', '.dll'):
                    libs[f] = 'SHARED'
                else:
                    if ext not in ('.c', '.cpp', '.cc', '.java', '.qm', '.qch', '.ts', '.po'):
                        info('%s referenced %s not in linked objects as bellow\n\t%s'
                             % (relpath(target, directory), f, '\n\t'.join(db.linkings.keys())))
                    sources.add(f)
                continue
            CmakeConverter.collect_depends(db, f, compilations, sources, dependencies)

        return sources, libs, compilations, dependencies

    @staticmethod
    def collect_depends(db, target, compilations, source_files, dependencies):
        source_map = db.objects.get(target, {})
        for source, cmd_id in source_map.items():
            command = db.command[cmd_id]
            extra_sources = command.missing_depends.get(target, set())
            if extra_sources:
                for f in extra_sources:
                    source_files.add(f)
                    dependencies.add(f)
                    compilations.setdefault(cmd_id, {})[f] = target
                    CmakeConverter.collect_depends(db, f, compilations, source_files, dependencies)
            source_compiler = command.compiler
            if source_compiler in ('rcc', 'uic'): continue
            source_files.add(source)
            linkage = db.command_linkage(cmd_id)
            if linkage == 'INSTALL': continue
            compilations.setdefault(cmd_id, {})[source] = target
            if source not in db.objects: continue
            dependencies.add(source)
            CmakeConverter.collect_depends(db, source, {}, set(), dependencies)

    @staticmethod
    def update_referenced_libs(config, referenced_libs):
        config.referenced_libs.update(referenced_libs)
        for refer in referenced_libs:
            if refer.startswith('${CMAKE'):
                config.include_binary_dir = True
                break

    @staticmethod
    def migrate_sub_compilations(config, compilations, target, name, db):
        if len(compilations) > 1:
            warn("Target %s is created by multiple commands: %s"
                 % (db.relpath(target), ' '.join(["#%s" % cmd for cmd in compilations])))
        for cmd_id in compilations.keys():
            config.migrate(db.command[cmd_id])
        for cmd_id, source_product in compilations.items():
            for source, product in source_product.items():
                if CmakeConverter.reduce_target(cmd_id, product, source, db.targets):
                    debug("Target %s use source %-20s instead of %s" % (name, source, product))
                if db.is_generated(source):
                    config.include_binary_dir = True

    @staticmethod
    def reduce_target(cmd_id, product, source, targets):
        target_sources = targets.get(cmd_id, {})
        sources = target_sources.get(product, set())
        if source in sources:
            sources.remove(source)
            if not sources:
                target_sources.pop(product)
                debug("cmd #%s pop its targets %s" % (cmd_id, product))
            return True
        else:
            info("file %s not in source list of target %s\n\t%s\n%s %s" % (
                source, product, '\n\t'.join(sources), cmd_id, '' if sources else target_sources))
        return False

    def generate_unlinked_target(self, cmd_id, target_sources):
        command = self.db.command[cmd_id]
        linkage = command.linkage
        if linkage == 'LOCALE':
            self.output_locales(cmd_id, command, target_sources)
            return
        files = set()
        for target, sources in target_sources.items():
            missing_depends = dict(filter(lambda x: x[1] == target, command.missing_depends.items()))
            sources = list(sources)
            sources.extend(missing_depends.keys())
            if target in self.db.linkings: continue
            for f in sources:
                cmd = self.db.sources.get(f, {}).get(target, cmd_id)
                if cmd != cmd_id:
                    warn("target %s gen by command %s and %s" % (target, cmd, cmd_id))
                files.add(f)
        if files:
            self.output_library(cmd_id, command, sorted(files), linkage)

    def generate_migrated_install_target(self, cmd_id, destination_sources):
        command = self.db.install_command[cmd_id]
        install_destination = None
        files = {}
        for destination, sources in destination_sources.items():
            dest_pattern, file_pattern = destination
            if file_pattern:
                matched = get_matched_parts(file_pattern, [s for t, s in sources])
                generator = self.get_generator_for_sources(sources)
                generator.output_migrated_install(command, dest_pattern, file_pattern, matched)
                continue
            if len(sources) != 1:
                warn("Install target %s fail to migrate by install cmd #%s" % (destination, cmd_id))
            for dest, file in sources:
                files[dest] = file
                if install_destination is None:
                    install_destination = dest
                elif install_destination != dest:
                    install_destination = ""
        if files: self.generate_install_target(cmd_id, files, install_destination)

    def generate_install_target(self, cmd_id, files, destination=''):
        command = self.db.install_command[cmd_id]
        prefix = os.path.commonprefix(list(files.keys()))
        name = prefix if prefix.endswith('/') else (os.path.dirname(prefix) + '/')
        for dest in files.keys():
            if dest[len(name):].find('/') > 0:
                name = ''
                break
        if name:
            info("Target %s installed by cmd #%s to %s" % (name, cmd_id, ' '.join([self.relpath(f) for f in files])))
            install_groups = group_keys_by_vv(files, self.db.objects)
            for cmd_id, file_set in install_groups.items():
                linkage = self.db.command_linkage(cmd_id) if cmd_id >= 0 else 'FILES'
                generator = self.get_generator_for_sources(file_set)
                generator.output_cmake_install(name, command, file_set, linkage)
            return
        for dest, file in files.items():
            install_groups = group_keys_by_vv({dest: file}, self.db.objects)
            for cmd_id, file_set in install_groups.items():
                name = destination if destination else dest
                info("Target %s installed by cmd #%s to %s" % (name, cmd_id, ' '.join([self.relpath(f) for f in files])))
                linkage = self.db.command_linkage(cmd_id) if cmd_id >= 0 else 'FILES'
                generator = self.get_generator_for_sources({file, })
                generator.output_cmake_install(name, command, {file, }, linkage)

    def get_root_generator(self):
        return self.get_cmake_generator(self.root_dir)

    def get_cmd_generator(self, cmd_id):
        return self.get_cmake_generator(self.db.command_cwd(cmd_id))

    def get_name_for_generator(self, directory):
        if directory == self.directory or directory == self.directory + '/':
            name = self.name
        else:
            name = "%s-%s" % (self.name, self.relpath(directory))
        return name

    def get_generator_for_sources(self, sources):
        dir_groups = {}
        for source in sources:
            directory = os.path.dirname(source)
            dir_groups.setdefault(directory, 0)
            dir_groups[directory] += 1
        dir_counts = sorted(dir_groups.items(), key=lambda x: x[1])
        half = len(sources) / 2
        if dir_counts[0][1] > half:
            common_dir = dir_counts[0][0]
        else:
            dir_groups.clear()
            root_dir = self.root_dir + '/'
            for directory, count in dir_counts:
                if not (directory + '/').startswith(root_dir):
                    dir_groups.setdefault(self.root_dir, 0)
                    dir_groups[self.root_dir] += count
                while (directory + '/').startswith(root_dir):
                    dir_groups.setdefault(directory, 0)
                    dir_groups[directory] += count
                    directory = os.path.dirname(directory)
            dir_counts = sorted(dir_groups.items(), key=lambda x: x[0].count('/'))
            for directory, count in dir_counts:
                if count > half: break
            common_dir = directory
        if not (common_dir+'/').startswith(self.root_dir + '/'):
            common_dir = self.root_dir
        elif not self.in_source_build and (common_dir+'/').startswith(self.binary_dir):
            common_dir = self.root_dir
        return self.get_cmake_generator(common_dir)

    def get_cmake_generator(self, directory):
        if self.single_file:
            directory = self.directory
        name = self.get_name_for_generator(directory)
        generators = CmakeConverter.generators
        return self.cmake_generator(directory, name, generators)

    def cmake_generator(self, directory, name, generators):
        generator = generators.get(name)
        if generator is None:
            relative_binary_dir = relpath(directory, self.root_dir)
            binary_dir = resolve(relative_binary_dir, self.binary_dir)
            generator = CmakeGenerator(name, directory, self.directory, binary_dir, self.single_file)
            generators[name] = generator
        return generator

    def output_locales(self, cmd_id, command, target_sources):
        groups = {}
        for target, sources in target_sources.items():
            for source in sources:
                migrate_command(target, source, groups)
        for (dest_pattern, src_pattern), target_sources in groups.items():
            info("cmd #%s output locale target\n\t%s"
                 % (cmd_id, '\n\t'.join(
                    ['%s <- %s' % (self.relpath(t), self.relpath(s)) for t, s in target_sources])))
            all_sources = set()
            for target, sources in target_sources: all_sources.add(sources)
            generator = self.get_generator_for_sources(all_sources)
            wrapper = generator.migrate_custom_targets(cmd_id, command, dest_pattern, src_pattern, target_sources)
            generator.other_installs.append(wrapper)

    def output_library(self, cmd_id, command, files, linkage):
        generator = self.get_generator_for_sources(files)
        name = name_by_common_prefix(files, self.directory)
        info("cmd #%s output %s library target %s with %s"
             % (cmd_id, linkage or 'unlinked', name,
                ' '.join([self.relpath(f) for f in files])))
        generator.output_linked_target(command, files, '', linkage, name, [])


if __name__ == '__main__':
    # FORMAT = '%(asctime)-15s %(levelname)-8s %(module)s %(message)s'
    FORMAT = '%(levelname)-8s %(lineno)5d %(message)s'
    logging.basicConfig(format=FORMAT)
