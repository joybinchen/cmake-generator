from .utils import basestring, freeze, PathUtils

import os
import logging
import subprocess

import shlex
import json


logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
info = logger.info
debug = logger.debug
warn = logger.warning
error = logger.error


class CompilationDatabase(PathUtils):
    def __init__(self, infile):
        super(self.__class__, self).__init__('')
        self.targets = {}
        self.sources = {}
        self.objects = {}
        self.linkings = {}
        self.installs = {}
        self.install_command = []
        self.command = []
        self.input = infile
        filename = os.path.realpath(infile.name)
        if os.path.isfile(filename):
            self.cmake_filename = filename
            self.directory = os.path.dirname(filename) + '/'
        else:
            self.cmake_filename = 'autogenerated'
            self.directory = ''

    def parse_command(self, command, cwd, file_):
        if isinstance(command, basestring):
            command = shlex.split(command)
        words = iter(command)
        compiler = os.path.basename(next(words))  # remove the initial 'cc' / 'c++'
        if compiler.startswith('python'):
            compiler = os.path.basename(next(words))

        config = {}
        options = []
        definitions = []
        includes = []
        system_includes = set()
        iquote_includes = set()
        libs = set()
        linkage = 'EXECUTABLE'
        target = ''
        missing_depends = []

        if compiler == 'ccache':
            compiler = 'clang'
        if compiler == 'msgfmt':
            linkage = 'LOCALE'
        if compiler == 'git':
            for word in words:
                if word == '>':
                    linkage = 'SOURCE'
                    target = next(words)
                elif word.startswith('-'):
                    options.append(word)
                else:
                    options.append(word)
        elif compiler == 'moc':
            for word in words:
                if word == '-o':
                    linkage = 'SOURCE'
                    target = next(words)
                elif word.startswith('-'):
                    if word == '--include':
                        options.append('%s %s' % (word, next(words)))
                    else:
                        options.append(word)

        elif compiler == 'install':
            for word in words:
                if word.startswith('-'):
                    if word == '-c':
                        options.append(word)
                    if word == '-m':
                        options.append("%s %s" % (word, next(words)))
                    else:
                        options.append(word)
                elif word != file_:
                    linkage = 'INSTALL'
                    target, destination = self.resolve_destination(word, cwd, file_)
                    config['destination'] = destination

        elif compiler == 'qmake':
            for word in words:
                if word.startswith('-'):
                    if word == '-install':
                        options.append("%s %s" % (word, next(words)))
                    else:
                        options.append(word)
                elif word != file_:
                    linkage = 'INSTALL'
                    target, destination = self.resolve_destination(word, cwd, file_)
                    config['destination'] = destination

        elif compiler == 'lrelease':
            for word in words:
                if word == '-qm':
                    linkage = 'LOCALE'
                    target = next(words)
                elif word.startswith('-'):
                    options.append(word)

        elif compiler == 'glib-genmarshal':
            for word in words:
                if word == '--output':
                    linkage = 'SOURCE'
                    target = next(words)
                elif word.startswith('-'):
                    options.append(word)

        elif compiler == 'dbus-binding-tool':
            for word in words:
                if word.startswith('--output='):
                    linkage = 'SOURCE'
                    target = word[len('--output='):]
                elif word.startswith('-'):
                    options.append(word)

        elif compiler.endswith("ar"):
            for word in words:
                if not target:
                    if word.startswith('-'):
                        if 'c' in word:
                            linkage = 'STATIC'
                            target = next(words)
                    elif 'c' in word:
                        linkage = 'STATIC'
                        target = next(words)
                    else:
                        options.append(word)

        for word in words:
            if word == '-o':
                target = next(words)
            elif word.startswith('-I'):
                include = word[2:]
                includes.append(self.resolve(include, cwd))
            elif word == '-isystem':
                include = next(words)
                include = self.resolve(include, cwd)
                if include not in includes:
                    includes.append(include)
                system_includes.add(include)
            elif word == '-iquote':
                include = next(words)
                include = self.resolve(include)
                if include not in includes:
                    includes.append(include)
                iquote_includes.add(include)
            elif word.startswith('-D'):
                define = word[2:]
                if define.find('=') > 0:
                    name, value = define.split('=', 1)
                    if value:
                        define = '%s="%s"' % (name, value)
                definitions.append(define)
            elif word == '-c':
                linkage = 'OBJECT'
            elif word in ['-arch', '-include', '-x']:
                options.append('%s %s' % (word, next(words)))
            elif word in ['-MM', '-MQ', '-M', '-MP', '-MG']:
                continue
            elif word in ['-MT', '-MF', '-MQ', '-MD', '-MMD', '-ccc-gcc-name']:
                next(words)
            elif word.startswith('-L'):
                libs.add(word if len(word) > 2 else ('-L'+next(words)))
            elif word.startswith('-l'):
                libs.add(word[2:] or next(words))
            elif word in ['-g', '-O1', '-O2', '-O3']:
                continue
            elif word == '-O':
                next(words)
            elif word.startswith('-m'):
                options.append(word)
                libs.add(word)
            elif word == '-shared':
                options.append(word)
                linkage = 'SHARED'
            elif word.startswith('-'):
                options.append(word)

        config.update({
            'cwd': cwd,
            'compiler': compiler,
            'linkage': linkage,
        })
        if libs:
            config['libs'] = freeze(libs)
        if options:
            config['options'] = freeze(options)
        if definitions:
            config['definitions'] = freeze(definitions)
        if includes:
            config['includes'] = freeze(includes)
        if system_includes:
            config['system_includes'] = freeze(system_includes)
        if iquote_includes:
            config['iquote_includes'] = freeze(iquote_includes)
        if linkage == 'OBJECT':
            missing_depends = self.find_dependencies(compiler, file_, config)
            if missing_depends:
                info("OBJECT %-25s depends on missing %s"
                     % (self.relpath(target),
                        ' '.join([self.relpath(f) for f in missing_depends])))
        return config, target, missing_depends

    def resolve_destination(self, path, cwd, file_):
        target = self.resolve(path, cwd)
        if os.path.isdir(target):
            destination = target
            target = os.path.join(target, os.path.basename(file_))
        else:
            if os.path.basename(target) == os.path.basename(file_):
                destination = os.path.dirname(target)
            else:
                destination = target
        return target, destination

    def find_dependencies(self, compiler, file_, config):
        cwd = config['cwd']
        if not cwd.endswith('/'):
            cwd += '/'
        if not os.path.isabs(file_):
            file_ = cwd + file_
        if not os.path.exists(file_):
            return [file_]

        dep_command = [compiler, '-MM', '-MG', file_.encode('utf-8')]
        dep_command.extend(['-D'+p for p in config.get('definitions', ())])
        dep_command.extend(['-I'+p for p in config.get('includes', ())])
        for p in config.get('system_includes', ()):
            dep_command.extend(['-isystem', p])
        for p in config.get('iquote_includes', ()):
            dep_command.extend(['-iquote', p])
        if '-fPIC' in config.get('options', []):
            dep_command.append('-fPIC')
        # debug('check dependencies on %s with command: %s' %(cwd, ' '.join(dep_command)))
        process = subprocess.Popen(dep_command, cwd=cwd, stdout=subprocess.PIPE)
        output = process.communicate()[0].strip().decode('utf-8')
        if not output:
            return []

        depends = output.split(': ', 1)[1].replace('\\\n  ', '').split(' ')
        depend_list = [f if os.path.isabs(f) else cwd + f for f in depends]
        # debug('Files relative to %s\n\t%s' % (self.directory, '\n\t'.join(
        #      filter(lambda x: not x.startswith('/usr/'), depend_list))))
        depend_list = [os.path.relpath(f, self.directory) for f in depend_list]
        local_depends = filter(lambda x: not x.startswith('../'), depend_list)
        missing_depends = filter(lambda x: not os.path.exists(x), local_depends)
        return [self.directory + f for f in missing_depends]

    def read(self, infile=None):
        if infile is None:
            infile = self.input
        database = json.load(infile)
        cmd_dict = {}
        install_cmd_dict = {}
        for entry in database:
            self.read_command(entry, cmd_dict, install_cmd_dict)

    def read_command(self, entry, cmd_dict, install_cmd_dict):
        cwd = entry.get('directory', self.directory)
        file_ = self.resolve(entry['file'], cwd)
        arguments = shlex.split(entry.get('command', ''))
        arguments = entry.get('arguments', arguments)
        cmd, target, missing_depends = self.parse_command(arguments, cwd, file_)
        if not cmd:
            return cmd

        target = self.resolve(target, cwd)
        linkage = cmd.get('linkage')
        if linkage == 'INSTALL':
            self.update_install_index(target, cmd, file_, install_cmd_dict)
            return cmd

        cmd_id = self.update_command_index(cmd, cmd_dict, self.command, debug)
        self.update_target_index(target, cmd_id, file_, linkage)
        for depend in missing_depends:
            debug('Update missing_depends for cmd #%s: %s' % (cmd_id, depend))
            self.command[cmd_id].setdefault('missing_depends', set()).add(depend)
        return cmd

    @staticmethod
    def update_command_index(cmd, cmd_dict, cmd_list, log=None):
        command = freeze(cmd)
        cmd_id = cmd_dict.get(command)
        if cmd_id is None:
            cmd_id = len(cmd_list)
            cmd_dict[command] = cmd_id
            cmd_list.append(cmd)
            if log:
                log('New cmd #%s: %s'
                    % (cmd_id, '\n'.join(["%-10s %s" % x for x in command])))
        return cmd_id

    def update_install_index(self, target, cmd, file_, cmd_dict):
        cmd_id = self.update_command_index(cmd, cmd_dict, self.install_command)
        debug("Install cmd #%s install %-27s => %s"
              % (cmd_id, self.relpath(file_), self.relpath(target)))
        self.installs.setdefault(cmd_id, {})[target] = file_

    def update_target_index(self, target, cmd_id, file_, linkage):
        debug("entry %-35s cmd #%s => %-10s %s"
              % (self.relpath(file_), cmd_id, linkage, self.relpath(target)))
        self.sources.setdefault(file_, {})[target] = cmd_id
        self.objects.setdefault(target, {})[file_] = cmd_id
        self.targets.setdefault(cmd_id, {}).setdefault(target, set()).add(file_)
        if linkage not in ('OBJECT', 'LOCALE', None):
            self.update_linking_index(target, cmd_id, file_)

    def update_linking_index(self, target, cmd_id, file_):
        debug("Add linked target %s from %s"
              % (self.relpath(target), self.relpath(file_)))
        self.linkings.setdefault(target, {}).setdefault(cmd_id, set()).add(file_)


if __name__ == '__main__':
    # FORMAT = '%(asctime)-15s %(levelname)-8s %(module)s %(message)s'
    FORMAT = '%(levelname)-8s %(lineno)5d %(message)s'
    logging.basicConfig(format=FORMAT)
