import os
import subprocess
from .utils import get_loggers, resolve, resolve_paths

__all__ = ['find_dependencies', ]
logger, info, debug, warn, error = get_loggers(__name__)


def find_dependencies(source, command, root_dir):
    cwd = command.cwd
    if not cwd.endswith('/'):
        cwd += '/'
    source = resolve(source, cwd)
    if not os.path.exists(source):
        return []

    depend_file = get_depend_file_name(source, cwd)
    if os.path.exists(depend_file):
        output = open(depend_file).read().strip()
    else:
        output = extract_dependencies(command, source, cwd)
        open(depend_file, 'w').write(output)
    if not output:
        return []

    output = output.replace('\\\n  ', '')
    lines = output.split('\n')
    missing_depends = collect_dependencies(lines, cwd, root_dir)
    return resolve_paths(missing_depends, root_dir)


def collect_dependencies(lines, cwd, directory):
    i = 0
    missing_depends = set()
    for line in lines:
        i += 1
        if line.find(': ') <= 0: continue
        depends = line.split(': ', 1)[1].split(' ')
        depend_list = [f if os.path.isabs(f) else cwd + f for f in depends]
        debug('Files relative to %s in %s %s\n\t%s' % (i, len(lines), directory, list(
            filter(lambda x: x.find(':') >= 0, depend_list))))
        depend_list = [os.path.relpath(f, directory) for f in depend_list]
        local_depends = list(filter(lambda x: not x.startswith('../'), depend_list))
        for f in local_depends:
            if not os.path.exists(f):
                missing_depends.add(f)
    return missing_depends


def get_depend_file_name(file_, cwd):
    depend_dir = os.path.join(cwd, '.deps')
    if not os.path.exists(depend_dir):
        os.mkdir(depend_dir)
    basename = os.path.splitext(os.path.basename(file_))[0]
    depend_file = os.path.join(cwd, '.deps', basename + '.Po')
    return depend_file


def extract_dependencies(command, source, cwd):
    command_line = compose_denpend_command(command, source)
    debug('check dependencies on %s with command:\n\t%s' % (cwd, ' '.join(command_line)))
    process = subprocess.Popen(command_line, cwd=cwd, stdout=subprocess.PIPE)
    output = process.communicate()[0].strip()
    output = output.decode('utf-8')
    return output


def compose_denpend_command(command, source):
    command_line = [command.compiler, '-MM', '-MG', source]
    command_line.extend(['-D' + p for p in command.definitions])
    command_line.extend(['-I' + p for p in command.includes])
    for p in command.system_includes:
        command_line.extend(['-isystem', p])
    for p in command.iquote_includes:
        command_line.extend(['-iquote', p])
    if '-fPIC' in command.options:
        command_line.append('-fPIC')
    return command_line
