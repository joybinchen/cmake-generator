import os
import re
from diff_match_patch.diff_match_patch import diff_match_patch

from .utils import get_loggers, freeze, DISALLOWED_CHARACTERS

__all__ = ['get_diff_pattern', 'migrate_command', 'migrate_install_commands',
           'get_matched_parts', 'name_by_common_prefix',
           'group_keys_by_vv', 'get_common_values',
           ]
logger, info, debug, warn, error = get_loggers(__name__)
diff = diff_match_patch().diff_main


def update_diff_pattern(pattern, fields, lhs, rhs):
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


def get_diff_pattern(text1, text2, strict=False, extend=True):
    diff_result = diff(text1, text2, False)
    pattern = []
    lhs = rhs = ''
    fields = []

    lhs = rhs = ''
    for diff_type, diff_part in diff_result:
        if diff_type < 0:
            lhs += diff_part
        elif diff_type > 0:
            rhs += diff_part
        else:
            if lhs or rhs:
                update_diff_pattern(pattern, fields, lhs, rhs)
                lhs = rhs = ''
            pattern.append(diff_part)
    if lhs or rhs:
        update_diff_pattern(pattern, fields, lhs, rhs)
    # debug('Diff result %s for %s %s: %s' % (pattern, text1, text2, fields))
    if extend:
        extend_diff_pattern(pattern, fields, strict)
    return ''.join(pattern), fields


def extend_diff_pattern(pattern, fields, strict=False):
    delimiter = re.compile('[-.~_/]')
    matcher = re.compile(r'%\(([0-9])\)s')
    i = 0
    while i < len(pattern):
        part = pattern[i]
        matched = matcher.match(part)
        if not matched:
            if strict and len(fields) == 1 and i == len(pattern) - 1 and not pattern[-1].startswith('/'):
                extension = pattern.pop()
                fields[0] = tuple(f + extension for f in fields[fid])
            else:
                i += 1
            continue
        fid = int(matched.group(1))
        if i > 0:
            prev = pattern[i-1]
            prev_parts = delimiter.split(prev)
            if len(prev_parts) > 1:
                extension = prev_parts[-1]
                pos = -len(extension)
                if pos != 0: pattern[i-1] = prev[:pos]
                fields[fid] = tuple(extension + f for f in fields[fid])
        i += 1
        if i < len(pattern):
            next_ = pattern[i]
            next_parts = delimiter.split(next_)
            if len(next_parts) > 1:
                extension = next_parts[0]
                pos = len(extension)
                pattern[i] = next_[pos:]
                fields[fid] = tuple(f + extension for f in fields[fid])
    return pattern, fields


def migrate_command(target, source, groups, strict=False, max_group=1):
    if not groups:
        info('Initialize empty group with source & target\n\t%s => %s'
             % (target, source))
        groups[(target, '')] = [(target, source), ]
        return True

    for (dest, src_pattern), target_files in groups.items():
        if src_pattern:
            matcher = re.compile(src_pattern % {'0': '(.*)'})
            matched = matcher.match(source)
            if matched:
                match_groups = matched.groups()
                convert_dict = dict([(str(i), g) for i, g in
                                     zip(range(0, len(match_groups)), match_groups)])
                converted_target = dest % convert_dict
                if converted_target == target:
                    target_files.append((target, source))
                    debug(('Existed pattern\t%s\t%s\n\t' % (src_pattern, dest)) +
                          ('matches source and target\t%s\t%s\n' % (source, target)))
                    return True

    for (dest, src_pattern), target_files in groups.items():
        prev_pattern = src_pattern or target_files[0][1]
        file_pattern, file_fields = get_diff_pattern(prev_pattern, source, strict)
        if not file_fields or len(file_fields) > max_group: continue
        dest_pattern, dest_fields = get_diff_pattern(dest, target, strict)
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
                '\n\t'.join(["%s <- %s" % (t, f) for f, t in target_files[:3]])))
        target_files.append((target, source))
        if src_pattern != file_pattern:
            if src_pattern:
                matcher = re.compile(file_pattern % {'0': '(.*)'})
                for target, file_ in target_files:
                    if not matcher.match(file_):
                        return True
                info('migrate_command when %s\n\t replace\t%s\n\t ===>\t%s\n targets:\n\t%s'
                     % ((source, target),
                        (dest, src_pattern),
                        (dest_pattern, file_pattern),
                        '\n\t'.join(["%s\t%s" % x for x in target_files])))
            groups.pop((dest, src_pattern))
            groups[(dest_pattern, file_pattern)] = target_files
        return True
    info('No matching pattern %s in groups' % target)
    groups[(target, '')] = [(target, source), ]
    return True


def get_matched_parts(pattern, files):
    matcher = re.compile(pattern % {'0': '(.*)'})
    matched = []
    for file_ in files:
        match = matcher.fullmatch(file_)
        if match and match.groups():
            matched.append(match.groups()[0])
        else:
            debug('Fail to match %s in %s' % (pattern, file_))
    return matched


def name_by_common_prefix(files, root_dir):
    prefix = os.path.commonprefix(files)
    name = os.path.basename(prefix.rstrip("-_."))
    name = re.sub(DISALLOWED_CHARACTERS, "", name)
    if not name:
        relpath = os.path.relpath(prefix, root_dir)
        while relpath.startswith('../'):
            relpath = relpath[3:]
        name = relpath.rstrip("-_.").replace('/', '_').replace('.', '_')
        name = re.sub(DISALLOWED_CHARACTERS, "", name)
    return name


def migrate_install_commands(migratables, install_command, diff_keys=()):
    groups = {}
    migrated_commands = {}
    for cmd_id, target, file_ in migratables:
        command = install_command[cmd_id].copy()
        for key in diff_keys: setattr(command, key, None)
        frozen_command = freeze(command)
        new_cmd_id = migrated_commands.get(frozen_command)
        if new_cmd_id is None:
            new_cmd_id = cmd_id
            migrated_commands[frozen_command] = new_cmd_id
            install_command[new_cmd_id] = command
            command.id = new_cmd_id
        dest_groups = groups.setdefault(new_cmd_id, {})
        migrate_command(target, file_, dest_groups)
        debug('Install cmd #%d migrated into cmd #%d' % (cmd_id, new_cmd_id))
    return groups

def group_keys_by_vv(files, objects):
    """
    @objects: {key: {vk: vv, ...}, ...}
    returns {vv: {key1, key2, ...}, ...}"""
    groups = {}
    for key in files.values():
        vk2vv = objects.get(key)
        if vk2vv is None:
            if not os.path.isfile(key):
                warn('No command to create installed file: ' + key)
            groups.setdefault(-1, set()).add(key)
            continue
        vv = next(iter(vk2vv.values()))
        groups.setdefault(vv, set()).add(key)
    return groups


def get_common_values(arg_values):
    value_filter = None
    for values in arg_values:
        if values:
            if value_filter is None:
                value_filter = iter(values)
                continue
            value_filter = filter(lambda x: x in values, value_filter)
    if value_filter is None:
        common_values = []
    else:
        common_values = list(value_filter)
    return common_values
