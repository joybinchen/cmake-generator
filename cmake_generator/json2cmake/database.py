import os
import logging

import shlex
import json
from .utils import *
from .migration import migrate_install_commands
from .command import Command


logger, info, debug, warn, error = get_loggers(__name__)


class CompilationDatabase(PathUtils):
    def __init__(self, infile, filename, source_dir=None, build_dir=None):
        filename = resolve(filename, os.getcwd())
        build_dir = os.path.dirname(filename) if build_dir is None else resolve(build_dir, os.getcwd())
        PathUtils.__init__(self, source_dir, source_dir)
        self.build_dir = build_dir
        # targets: {cmd_id: {target: {source, ...}, ...}, ...}
        self.targets = {}
        # sources: {source: {target: cmd_id, ...}, ...}
        self.sources = {}
        # objects: {target: {source: cmd_id, ...}, ...}
        self.objects = {}
        # linkings: {target: {cmd_id: {object_file, ...}, ...}, ...}
        self.linkings = {}
        # qt_moc_bucket: {target: {cmd_id: {object_file, ...}, ...}, ...}
        self.qt_moc_bucket = {}
        # qt_ui_bucket: {target: {cmd_id: {object_file, ...}, ...}, ...}
        self.qt_ui_bucket = {}
        # qt_rc_bucket: {target: {cmd_id: {object_file, ...}, ...}, ...}
        self.qt_rc_bucket = {}
        # installs: {cmd_id: {destination: {target, ...}, ...}, ...}
        self.installs = {}
        self.install_command = []
        self.command = []
        self.input = infile

    def binary_dir(self):
        return self.build_dir if self.build_dir else self.directory

    def command_linkage(self, cmd_id):
        return self.command[cmd_id].linkage

    def target_linkage(self, f):
        command_sources = self.linkings[f]
        if not command_sources:
            return None
        if len(command_sources) > 1:
            warn("find multiple command creating the same target: %s" % f)
        cmd_id = next(iter(command_sources.keys()))
        return self.command_linkage(cmd_id)

    def command_cwd(self, cmd_id):
        return self.command[cmd_id].cwd

    def is_generated(self, source):
        if source in self.linkings:
            command_sources = self.linkings[source]
            for cid in command_sources.keys():
                if self.command_linkage(cid) == 'SOURCE':
                    return True

    def read(self, infile=None):
        if infile is None:
            infile = self.input
        database = json.load(infile)
        cmd_dict = {}
        install_cmd_dict = {}
        for entry in database:
            if not entry: continue
            source, arguments, cwd = CompilationDatabase.read_entry(entry, self.directory)
            cmd, target = Command.parse(arguments, source, cwd, self.directory)
            if cmd:
                self.update_index(cmd, target, source, cmd_dict, install_cmd_dict)

    def update_index(self, command, target, source, cmd_dict, install_cmd_dict):
        extra_sources = sorted(command.missing_depends.get(target, set()))
        command.missing_depends.clear()
        if command.linkage == 'INSTALL':
            command = self.update_install_index(command, target, source, install_cmd_dict)
        else:
            command = self.update_target_index(command, target, source, cmd_dict)
        cmd_id = command.id
        for src in extra_sources:
            # self.update_target_index(cmd, target, src, cmd_dict)
            self.objects.setdefault(target, {})[src] = cmd_id
            self.sources.setdefault(src, {})[target] = cmd_id
            if command.linkage not in ('OBJECT', 'LOCALE', None):
                self.update_linking_index(target, cmd_id, src, self.linkings)
        CompilationDatabase.update_command_after_indexing(command, source, target, self.directory)

    @staticmethod
    def read_entry(entry, directory):
        cwd = entry.get('directory', directory)
        file_ = entry.get('file', '')
        if file_: file_ = resolve(file_, cwd)
        arguments = shlex.split(entry.get('command', ''))
        arguments = entry.get('arguments', arguments)
        return file_, arguments, cwd

    @staticmethod
    def update_command_after_indexing(cmd, source, target, root_dir):
        if cmd.linkage == 'OBJECT':
            cmd.update_object_command(source, target, root_dir)

    @staticmethod
    def update_command_index(cmd, cmd_dict, cmd_list, log=None):
        frozen_cmd = freeze(cmd)
        cmd_id = cmd_dict.get(frozen_cmd)
        if cmd_id is None:
            cmd_id = len(cmd_list)
            cmd_dict[frozen_cmd] = cmd_id
            cmd_list.append(cmd)
            cmd.id = cmd_id
            if log:
                log('New cmd #%s: %s' % (cmd_id, '\n'.join(["%-10s %s" % x for x in frozen_cmd])))
        return cmd_list[cmd_id]

    def update_install_index(self, cmd, target, source, cmd_dict):
        cmd = self.update_command_index(cmd, cmd_dict, self.install_command)
        debug("Install cmd #%s install %-27s => %s"
              % (cmd.id, self.relpath(source), self.relpath(target)))
        self.installs.setdefault(cmd.id, {})[target] = source
        return cmd

    def update_target_index(self, cmd, target, source, cmd_dict):
        cmd = self.update_command_index(cmd, cmd_dict, self.command, debug)
        cmd_id = cmd.id
        debug("entry %-35s cmd #%s => %-10s %s"
              % (self.relpath(source), cmd_id, cmd.linkage, self.relpath(target)))
        self.sources.setdefault(source, {})[target] = cmd_id
        self.objects.setdefault(target, {})[source] = cmd_id
        self.targets.setdefault(cmd_id, {}).setdefault(target, set()).add(source)
        if cmd.linkage == 'SOURCE':
            compiler = cmd.compiler
            if compiler == 'uic':
                self.update_linking_index(target, cmd_id, source, self.qt_ui_bucket)
            elif compiler == 'moc':
                self.update_linking_index(target, cmd_id, source, self.qt_moc_bucket)
            elif compiler == 'rcc':
                self.update_linking_index(target, cmd_id, source, self.qt_rc_bucket)
            else:
                self.update_linking_index(target, cmd_id, source)
        elif cmd.linkage not in ('OBJECT', 'LOCALE', None):
            self.update_linking_index(target, cmd_id, source, self.linkings)
        return cmd

    def update_linking_index(self, target, cmd_id, file_, bucket=None):
        debug("Add linked target %s from %s"
              % (self.relpath(target), self.relpath(file_)))
        self.linkings.setdefault(target, {}).setdefault(cmd_id, set()).add(file_)
        if bucket is not None:
            bucket.setdefault(target, {}).setdefault(cmd_id, set()).add(file_)

    def extract_migrated_commands(self):
        migratables = [(cmd_id, tuple(x.keys())[0], tuple(x.values())[0]) for cmd_id, x in
                       (filter(lambda x: len(x[1]) == 1, self.installs.items()))]
        for cmd_id, _, _ in migratables:
            self.installs.pop(cmd_id)
        return migrate_install_commands(migratables, self.install_command, ('destination', 'id'))


if __name__ == '__main__':
    # FORMAT = '%(asctime)-15s %(levelname)-8s %(module)s %(message)s'
    FORMAT = '%(levelname)-8s %(lineno)5d %(message)s'
    logging.basicConfig(format=FORMAT)
