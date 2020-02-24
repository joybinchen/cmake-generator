import os
import re
import logging

from .utils import *
from .migration import *
from .generator import CmakeGenerator
from .target import *


# FORMAT = '%(asctime)-15s %(levelname)-8s %(module)s %(message)s'
logger, info, debug, warn, error = get_loggers(__name__)


class CmakeConverter(PathUtils):

    generators = {}

    def __init__(self, database, name, cwd, single_file=False):
        PathUtils.__init__(self, cwd, database.root_dir)
        self.db = database
        self.name = name
        self.single_file = single_file
        self.common_configs = {}

    def convert(self):
        generators = CmakeConverter.generators
        targets = self.db.targets
        linkings = self.db.linkings
        for target, command_source in linkings.items():
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

        external_dests = tuple(filter(lambda d: not d.startswith(self.directory), destinations))
        cmake_install_prefix = os.path.commonpath(external_dests) if external_dests else "/usr/local"
        generator_keys = list(generators.keys())
        for key in generator_keys:
            generator = generators[key]
            generator.set_install_prefix(cmake_install_prefix)
            directory = generator.setup_output()
            name = self.get_name_for_generator(directory)
            if name != key:
                generator.name = name
                generators[name] = generator
            generator.write_to_file()

    def generate_linked_target(self, target, command_source):
        commands = command_source.keys()
        if len(commands) > 1:
            warn("target %s created by multiple command:\n%s" % (target, commands))
        for cmd_id, files in command_source.items():
            command = self.db.command[cmd_id]
            if command.linkage == "SOURCE":
                if command.compiler in ('uic', 'moc', 'rcc'):
                    return
            generator = self.get_cmake_generator(command.cwd)
            CmakeConverter.write_command_for_linked_target(
                command, target, files, generator, self.db, self.directory)

    @staticmethod
    def write_command_for_linked_target(command, target, files, generator, db, directory):
        files = sorted(files)
        files.extend(command.missing_depends)
        linkage = command.linkage
        info("Process %s target %s" % (linkage, relpath(target, directory)))
        if linkage == 'SOURCE':
            return generator.output_custom_command(target, command, files)
        output_name = generator.name_for_lib(target)
        debug("%s %s linked by cmd #%s from %s"
              % (linkage, relpath(target, directory), command.id,
                 ' '.join([relpath(f, directory) for f in files])))
        source_files, referenced_libs, compilations, depends = CmakeConverter.classify_source_files(
            files, target, db, directory)
        generator.extract_generated_source_files(output_name, source_files, db.qt_ui_bucket, "ui", "qt5_wrap_ui")
        generator.extract_generated_source_files(output_name, source_files, db.qt_rc_bucket, "rc", "qt5_add_resources")
        generator.extract_generated_source_files(output_name, source_files, db.qt_moc_bucket, "moc", "qt5_wrap_cpp")

        command = command.copy()
        CmakeConverter.update_referenced_libs(command, referenced_libs)
        CmakeConverter.migrate_sub_compilations(command, compilations, target, output_name, db)
        generator.output_linked_target(command, source_files, target, linkage, output_name, depends)

    @staticmethod
    def classify_source_files(files, target, db, directory):
        source_files = set()
        referenced_libs = {}
        compilations = {}
        dependencies = set()
        for f in files:
            if f in db.linkings:
                dependencies.add(f)
                info('%s refer linked target %s' % (relpath(target, directory), relpath(f, directory)))
                linkage = db.target_linkage(f)
                if linkage in ('STATIC', 'SHARED', 'SOURCE'):
                    referenced_libs[f] = linkage
                else:
                    source_files.add(f)
                continue
            if f not in db.objects:
                ext = os.path.splitext(f)[1]
                if ext == '.a':
                    referenced_libs[f] = 'STATIC'
                elif ext in ('.so', '.dll'):
                    referenced_libs[f] = 'SHARED'
                else:
                    if ext not in ('.c', '.cpp', '.cc', '.java', '.qm', '.qch', '.ts', '.po'):
                        info('%s referenced %s not in linked objects as bellow\n\t%s'
                             % (relpath(target, directory), f, '\n\t'.join(db.linkings.keys())))
                    source_files.add(f)
                continue
            for source, cmd_id in db.objects[f].items():
                if db.command_linkage(cmd_id) != 'INSTALL':
                    compilations.setdefault(cmd_id, {})[source] = f
                source_files.add(source)
        return source_files, referenced_libs, compilations, dependencies

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
        if not target_sources: return
        command = self.db.command[cmd_id]
        linkage = command.linkage
        if linkage == 'LOCALE':
            self.output_locales(cmd_id, command, target_sources)
            return
        files = set()
        for target, source in target_sources.items():
            if target in self.db.linkings: continue
            for f in source:
                cmd = self.db.sources.get(f, {}).get(target, cmd_id)
                if cmd != cmd_id:
                    warn("target %s gen by command %s and %s" % (target, cmd, cmd_id))
                files.add(f)
        if files:
            files.update(command.missing_depends)
            self.output_library(cmd_id, command, sorted(files), linkage)

    def generate_migrated_install_target(self, cmd_id, destination_sources):
        command = self.db.install_command[cmd_id]
        generator = self.get_cmake_generator(command.cwd)
        install_destination = None
        files = {}
        for destination, sources in destination_sources.items():
            dest_pattern, file_pattern = destination
            if file_pattern:
                matched = get_matched_parts(file_pattern, [s for t, s in sources])
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
        generator = self.get_cmake_generator(command.cwd)
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
                generator.output_cmake_install(name, command, file_set, linkage)
            return
        for dest, file in files.items():
            install_groups = group_keys_by_vv({dest: file}, self.db.objects)
            for cmd_id, file_set in install_groups.items():
                name = destination if destination else dest
                info("Target %s installed by cmd #%s to %s" % (name, cmd_id, ' '.join([self.relpath(f) for f in files])))
                linkage = self.db.command_linkage(cmd_id) if cmd_id >= 0 else 'FILES'
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

    def get_cmake_generator(self, directory):
        if self.single_file:
            directory = self.directory
        name = self.get_name_for_generator(directory)
        generators = CmakeConverter.generators
        return self.cmake_generator(directory, name, generators)

    def cmake_generator(self, directory, name, generators):
        generator = generators.get(name)
        if generator is None:
            generator = CmakeGenerator(name, directory, self.directory, self.single_file)
            generators[name] = generator
            root_generator = self.get_root_generator()
            if root_generator != generator:
                root_generator.output_subdirectory(directory)
        return generator

    def output_locales(self, cmd_id, command, target_sources):
        groups = {}
        for target, sources in target_sources.items():
            for source in sources:
                migrate_command(target, source, groups)
        generator = self.get_cmake_generator(command.cwd)
        for (dest_pattern, src_pattern), target_sources in groups.items():
            info("cmd #%s output locale target\n\t%s"
                 % (cmd_id, '\n\t'.join(
                    ['%s <- %s' % (self.relpath(t), self.relpath(s)) for t, s in target_sources])))
            wrapper = generator.migrate_custom_targets(cmd_id, command, dest_pattern, src_pattern, target_sources)
            generator.other_installs.append(wrapper)

    def output_library(self, cmd_id, command, files, linkage):
        generator = self.get_cmake_generator(command.cwd)
        name = name_by_common_prefix(files, self.directory)
        info("cmd #%s output %s library target %s with %s"
             % (cmd_id, linkage or 'unlinked', name,
                ' '.join([self.relpath(f) for f in files])))
        generator.output_linked_target(command, files, '', linkage, name, [])


if __name__ == '__main__':
    # FORMAT = '%(asctime)-15s %(levelname)-8s %(module)s %(message)s'
    FORMAT = '%(levelname)-8s %(lineno)5d %(message)s'
    logging.basicConfig(format=FORMAT)
