import os
import re
import logging
from io import StringIO
from .utils import *
from .migration import get_common_values, migrate_command, name_by_common_prefix
from .target import *
from .pkgmap import *

logger, info, debug, warn, error = get_loggers(__name__)


class CmakeGenerator(PathUtils):
    used_names = {"": ""}

    def __init__(self, name, cwd, root_dir, single_file=False):
        PathUtils.__init__(self, cwd, root_dir)
        self.generated = False
        self.binary_dir = cwd
        self.name = name
        self.stream = StringIO()
        self.output = None
        self.single_file = single_file
        # targets: {t.name: t, t.target: t, }
        self.targets = {}
        self.variables = {}
        self.packages = {}
        self.other_installs = []
        self.common_configs = {}
        self.install_prefix = '/'

    def relpath(self, path, root=None):
        return relpath(path, self.directory, root if root else self.root_dir)

    def write(self, *args, **kwargs):
        if self.output is None:
            self.stream.write(*args, **kwargs)
        else:
            self.output.write(*args, **kwargs)
        if logger.level >= logging.DEBUG: self.output.flush()

    def set_install_prefix(self, prefix):
        self.install_prefix = prefix

    @staticmethod
    def guess_source_dir(directory, targets):
        group = {}
        for generated_file, target in targets.items():
            sources = target.real_sources()
            if not sources:
                sources = [generated_file, ]
            for source in sources:
                source_dir = os.path.dirname(source)
                group.setdefault(source_dir, set()).add(source)
        max_count = 0
        for source_dir, sources in group.items():
            count = len(sources)
            if max_count < count:
                directory = source_dir
                max_count = count
        return directory

    def setup_output(self, output=None):
        if self.generated: return self.directory
        directory = self.directory
        if output is None:
            directory = self.guess_source_dir(directory, self.targets)
            if self.directory != directory:
                self.binary_dir = self.directory
                self.directory = directory
            self.output = open(os.path.join(directory, 'CMakeLists.txt'), 'w')
        else:
            self.output = output
        return directory

    def write_to_file(self):
        if self.generated: return
        self.generated = True
        self.write_project_header()
        self.output.write(self.stream.getvalue())
        lib_replacement, include_replacement = self.collect_package_imports()
        self.write_find_packages()
        self.collect_common_configs()
        self.replace_with_package_vars(lib_replacement, include_replacement)
        self.write_common_configs()
        self.write_var_definitions()
        self.write_targets()

    def collect_common_configs(self):
        args_with_common = ('options', 'link_options', 'definitions',
                            'includes', 'system_includes', 'iquote_includes')
        cpp_targets = set(filter(lambda t: isinstance(t, CppTarget), self.targets.values()))
        for arg_name in args_with_common:
            arg_values = [getattr(t.command, arg_name) for t in cpp_targets]
            self.common_configs[arg_name] = get_common_values(arg_values)
        return args_with_common

    def get_lib_replacement(self, libs):
        lib2option = {}
        for option in list(libs):
            if option.startswith('-l'):
                lib = option[2:]
            elif option[:1] not in ('$', '-'):
                lib = option
            else:
                continue
            lib2option[lib] = option
        libs = sorted(lib2option.keys())

        mapping = {}
        replacement = {}
        lib2packages = {}
        for lib in list(libs):
            if lib in CMAKE_LIBS:
                package, module, var_lib, var_include = CMAKE_LIBS[lib]
                mapping[lib] = package if module is None else (package + module)
                self.generate_find_package_command(package, module, var_lib, var_include)
                replacement[lib] = ('${%s}' % var_lib) if var_lib.find("::") < 0 else var_lib
            elif lib in PKG_CONFIG_LIB2PKGS:
                packages = PKG_CONFIG_LIB2PKGS[lib]
                lib2packages[lib] = packages
                if len(packages) != 1: continue

                package = next(iter(packages))
                mapping[lib] = package
                prefix = package.upper().replace('-', '')
                var_lib = prefix + "_LIBRARIES"
                if package not in self.packages:
                    var_name = self.unique_name(var_lib)
                    if var_lib != var_name:
                        warn("Variable %s for imported library %s is occupied." % (var_lib, lib))
                    self.generate_pkg_config_command(package, prefix)
                replacement[lib] = '${%s}' % var_lib
            else:
                continue

        candidates = set()
        confirmed = set()
        for lib in self.packages.keys():
            packages = set(PKG_CONFIG_LIBS.get(lib, []))
            provided = packages.intersection(libs)
            confirmed.update(provided)
        for lib, packages in list(lib2packages.items()):
            intersection = packages.intersection(confirmed)
            if intersection:
                lib2packages[lib] = intersection
            else:
                candidates.update(packages)

        libset = set(libs)
        unconfirmed = sorted(candidates.difference(confirmed))
        for package in unconfirmed:
            needed = libset.difference(confirmed)
            if not needed:
                break
            libraries = set(PKG_CONFIG_LIBS[package])
            provided = needed.intersection(libraries)
            if not provided:
                continue
            diff = libraries.difference(libset)
            if not diff:
                prefix = package.upper().replace('-', '')
                if package not in self.packages:
                    self.generate_pkg_config_command(package, prefix)

                var_lib = prefix + "_LIBRARIES"
                var_name = self.unique_name(var_lib)
                if var_lib != var_name:
                    warn("Variable %s for imported library %s is occupied." % (var_lib, lib))
                var_lib = '${%s}' % var_lib
                for lib in provided:
                    replacement[lib] = var_lib
                    confirmed.add(lib)
                    mapping[lib] = package
        replacement = dict([(lib2option.get(x, x), y) for x, y in replacement.items()])
        return replacement

    def get_include_replacement(self, options, used_packages):
        cmake_lib_map = dict(filter(lambda x: x[0][0] is not None and x[0][1] is not None, CMAKE_PATH_MAP.items()))
        replacement = {}
        include2option = {}
        for option in sorted(options):
            if option.startswith('-I'):
                include2option[option[2:]] = option
            elif option[:1] not in ('$', '-'):
                include2option[option] = option
            else:
                continue

        includeset = set(include2option.keys())
        include2option = dict(filter(lambda x: x[0] != x[1], include2option.items()))
        needed = set(includeset)
        for include in sorted(includeset):
            provided = set()
            pkg2library = CMAKE_PATH_MAP.get((None, include), {})

            if len(pkg2library) >= 1:
                exceed = set()
                for pkg, library in pkg2library.items():
                    include2var = CMAKE_INCLUDE_DIRS.get(pkg, {})
                    includes = set(include2var.keys())
                    provided = needed.intersection(includes)
                    if not provided: continue
                    exceed = includes.difference(includeset)
                    if not exceed: break
                    else:
                        exceed_pkg = pkg
                        exceed_provided = provided
                if exceed:
                    print("include dir %s needed by " % include, exceed_pkg, exceed, exceed_provided)
                if provided:
                    replacement.update([(x, '${%s}' % include2var[x]) for x in provided])
                    needed.difference_update(provided)
                continue

            if include in PKG_CONFIG_INCLUDE2PKGS:
                exceed = set()
                packages = PKG_CONFIG_INCLUDE2PKGS[include]
                for pkg in packages:
                    includes = set(PKG_CONFIG_INCLUDE_DIRS[pkg])
                    provided = includes.intersection(needed)
                    if not provided: continue
                    exceed = includes.difference(includeset)
                    if not exceed: break
                    else:
                        exceed_pkg = pkg
                        exceed_provided = provided
                if exceed:
                    print("include dir %s needed by " % include, exceed_pkg, exceed, exceed_provided)

            if provided:
                prefix = pkg.upper()
                var_name = prefix + '_INCLUDE_DIR'
                var_include = '${%s}' % var_name
                for inc in provided:
                    replacement[inc] = var_include
                needed.difference_update(provided)
            elif include.startswith(self.root_dir): pass
            else:
                print("No lib provide include dir " + include)
        replacement = dict([(include2option.get(x, x), y) for x, y in replacement.items()])
        return replacement

    @staticmethod
    def replace_list_content(members, replacement, not_uniq=False):
        new_list = []
        for member in list(members):
            member = replacement.get(member, member)
            if not_uniq or member not in new_list:
                new_list.append(member)
        members.clear()
        if isinstance(members, set):
            members.update(new_list)
        else:
            members.extend(new_list)

    def collect_package_imports(self):
        includes = set()
        libs = set()
        include_args = ('includes', 'system_includes', 'iquote_includes')
        for arg_name in include_args:
            includes.update(self.common_configs.get(arg_name, []))
        for target in self.targets.values():
            if not isinstance(target, CppTarget): continue
            for arg_name in include_args:
                includes.update(target.get_values(arg_name))
            libs.update(target.libs)

        lib_replacement = self.get_lib_replacement(libs)

        packages = set(self.packages.keys())
        include_replacement = self.get_include_replacement(includes, packages)
        return lib_replacement, include_replacement

    def replace_with_package_vars(self, lib_replacement, include_replacement):
        for target in self.targets.values():
            if not isinstance(target, CppTarget): continue
            self.replace_list_content(target.libs, lib_replacement)
            self.replace_list_content(target.command.includes, include_replacement)
        include_args = ('includes', 'system_includes', 'iquote_includes')
        for arg_name in include_args:
            common_includes = self.common_configs.get(arg_name, None)
            if common_includes:
                self.replace_list_content(common_includes, include_replacement)

    def write_common_configs(self):
        args_with_common = ('options', 'link_options', 'definitions',
                            'includes', 'system_includes', 'iquote_includes')
        for arg_name in args_with_common:
            self.output_project_common_args(arg_name, self.common_configs[arg_name])

    def write_find_packages(self):
        for name, target in sorted(self.packages.items()):
            target.bind(self)
            target.output_target()

    def write_var_definitions(self):
        for name, target in sorted(self.variables.items()):
            target.bind(self)
            target.output_target()

    def write_targets(self):
        targets = []
        for _, target in sorted(self.targets.items()):
            for t in targets:
                if t.name() == target.name():
                    target = None
                    break
                if target.target in t.depends:
                    targets.insert(targets.index(t), target)
                    target = None
                    break
            if target is not None:
                targets.append(target)

        merged_command = {}
        target_group_by_cmd = {}
        targets_with_depends = []
        for target in targets:
            if target.depends:
                targets_with_depends.append(target)
            else:
                merged_command.setdefault(target.command.id, target.command)
                target_group_by_cmd.setdefault(target.command.id, []).append(target)
        for cmd_id, command in merged_command.items():
            target_group = target_group_by_cmd[cmd_id]
            if len(target_group) == 1:
                merged_targets = target_group
            else:
                merged_targets = self.merge_targets(cmd_id, command, target_group)
            for target in merged_targets:
                target.bind(self)
                target.output_target()
        for target in targets_with_depends:
            target.bind(self)
            target.output_target()
        migrated_targets = self.migrate_targets(self.other_installs)
        for target in migrated_targets:
            target.bind(self)
            target.output_target()

    def merge_targets(self, cmd_id, command, targets):
        groups = {}
        for target in targets:
            for source in target.sources:
                migrate_command(target.target, source, groups)
        wrappers = []
        for (dest_pattern, src_pattern), target_sources in groups.items():
            info("cmd #%s output custom built source\n\t%s"
                 % (cmd_id, '\n\t'.join(
                ['%s <- %s' % (self.relpath(t), self.relpath(s)) for t, s in target_sources])))
            wrapper = self.migrate_custom_targets(cmd_id, command, dest_pattern,
                                                  src_pattern, target_sources, "Sources")
            wrappers.append(wrapper)
        return wrappers

    @staticmethod
    def migrate_targets(targets):
        migrated = []
        for target in targets:
            if not isinstance(target, WrappedTarget):
                migrated.append(target)
                continue
            merged = False
            for other in migrated:
                if type(other) == type(target) and other.sources == target.sources:
                    for child in target.children:
                        other.append_child(child)
                    merged = True
                    break
            if not merged:
                migrated.append(target)
        return migrated

    def generate_pkg_config_command(self, lib, prefix):
        if '_' not in self.packages:
            self.packages['_'] = FindPackageDefinition('PkgConfig', '', None)
        if lib not in self.packages:
            self.packages[lib] = PkgCheckModulesDefinition(prefix, lib)

    def generate_find_package_command(self, package, module, var_lib, var_include):
        mode = 'MODULE'
        if var_lib != self.unique_name(var_lib):
            warn("Variable %s for imported library %s %s is occupied." % (var_lib, package, module))
        if var_include != self.unique_name(var_include):
            warn("Variable %s for imported library %s %s is occupied." % (var_include, package, module))
        definition = self.packages.get(package, None)
        if definition is None:
            definition = FindPackageDefinition(package, mode, module)
            self.packages[package] = definition
        if module:
            definition.add_module(module)
            self.packages[package + module] = definition
        else:
            return definition

    def output_project_common_args(self, arg_name, values):
        self.output.write('\n')
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
        if include_path.startswith(self.root_dir + '/') \
                or include_path == self.root_dir:
            return os.path.relpath(include_path, self.directory)
        return include_path

    def name_for_lib(self, path):
        return PathUtils.name_for_target(self.relpath(path))

    def name_as_target(self, path):
        output_name = self.name_for_lib(path)
        name = self.use_target_name(output_name, path)
        return name, output_name

    def use_target_name(self, name, path):
        path = resolve(path if path else name, self.directory)
        used_name = self.used_names.get(path)
        if used_name:
            return used_name
        used_path = self.used_names.get(name)
        if used_path is not None:
            info('use_target_name %s with duplicate path: %s %s on %s' % (name, path, used_path, self.directory))
            name = self.unique_name(name)
        self.used_names[name] = path
        self.used_names[path] = name
        return name

    def unique_name(self, name):
        if name in self.used_names:
            index = 2
            while True:
                candidate = '{}_{}'.format(name, index)
                if candidate not in self.used_names:
                    name = candidate
                    break
                index = index + 1
        self.used_names[name] = name
        return name

    def output_subdirectory(self, directory):
        info("Project in %s add subdirectory %s"
             % (relpath(self.directory, self.root_dir), relpath(directory, self.directory)))
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
        delimiter = ' ' if single_line else '\n\t'
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

    def output_custom_command(self, target, command, sources):
        name, output_name = self.name_as_target(target)
        self.targets[target] = CustomCommandTarget(command, target, sources)
        if name != output_name:
            self.targets[target].set_name(name)

    def output_var_definition(self, name, sources):
        self.variables[name] = UserVarDefinition(name, sources)

    def output_qt_wrapper(self, name, sources, wrapper):
        self.variables[name] = QtWrapDefinition(wrapper, name, sources)

    def extract_generated_source_files(self, name, files, bucket, depends, kind, wrapper):
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
        if sources:
            var_name = "%s_%s_SRCS" % (name, kind)
            var_name = self.unique_name(var_name)
            self.output_qt_wrapper(var_name, sources, wrapper)
            # self.output_var_definition(var_name, sources)
            files.add('${%s}' % var_name)

    def migrate_custom_targets(self, cmd_id, command, dest_pattern, src_pattern, paths, kind="Locales"):
        fields = []
        if src_pattern:
            matcher = re.compile(src_pattern % {'0': '(.*)'})
            for x in paths:
                matched = matcher.match(x[1])
                groups = matched.groups()
                fields.append(groups[0])
            #fields = [matcher.match(x[0]).groups()[0] for x in paths]
        else:
            fields.append("''")
        info("%s created by cmd #%s to %s" % (kind, cmd_id, ' '.join(fields)))
        dest = dest_pattern % {'0': '${X}'}
        source = src_pattern % {'0': '${X}'}
        custom_command = CustomCommandTarget(command, dest, [source, ])
        wrapper = ForeachTargetWrapper(command, 'X', fields)
        wrapper.append_child(custom_command)
        return wrapper

    def output_migrated_install(self, command, dest_pattern, file_pattern, matched, var='X'):
        child_target = InstallTarget(command, dest_pattern, [file_pattern, ])
        target = ForeachTargetWrapper(command, var, matched)
        target.append_child(child_target)
        self.other_installs.append(target)

    def output_cmake_install(self, name, command, file_set, linkage):
        directories = []
        files = []
        destination = command.destination if command.destination else name if name else command.target
        for f in file_set:
            if f in self.targets:
                self.targets[f].add_destination(destination)
            elif linkage != 'EXECUTABLE' and os.path.isdir(f):
                directories.append(f)
            else:
                files.append(f)
        if directories:
            target = name if name else destination
            self.other_installs.append(InstallTarget(command, target, directories, 'DIRECTORY'))
        if files:
            install_type = linkage if linkage == 'EXECUTABLE' else 'FILES'
            target = name if name else destination
            self.other_installs.append(InstallTarget(command, target, files, install_type))


if __name__ == '__main__':
    # FORMAT = '%(asctime)-15s %(levelname)-8s %(module)s %(message)s'
    FORMAT = '%(levelname)-8s %(lineno)5d %(message)s'
    logging.basicConfig(format=FORMAT)
