from .pkgmap import *


__all__ = ['map2option', 'find_package_for_libs', 'get_include_replacement']


def map2option(options, prefix='-l'):
    mapper = {}
    for option in list(options):
        if option.startswith(prefix):
            key = option[2:]
        elif option[:1] not in ('$', '-'):
            key = option
        else:
            continue
        mapper[key] = option
    return mapper


def find_package_for_libs(libs):
    mapping = {}
    lib2packages = {}
    cmake_packages = {}
    pkgconfig_packages = {}
    for lib in list(libs):
        if lib in CMAKE_LIBS:
            package, module, var_lib, var_include = CMAKE_LIBS[lib]
            cmake_package = package if module is None else (package + module)
            cmake_packages[lib] = cmake_package
        elif lib in PKG_CONFIG_LIB2PKGS:
            packages = PKG_CONFIG_LIB2PKGS[lib]
            lib2packages[lib] = packages
            if len(packages) == 1:
                pkgconfig_packages[lib] = next(iter(packages))

    confirmed_packages = set(cmake_packages.values())
    confirmed_packages.update(pkgconfig_packages.values())
    candidates = set()
    confirmed = set()
    for lib in confirmed_packages:
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
    unconfirmed.sort(key=lambda x: len(PKG_CONFIG_LIBS[x]))
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
            for lib in provided:
                pkgconfig_packages[lib] = package
                confirmed.add(lib)
                mapping[lib] = package
    return cmake_packages, pkgconfig_packages


def get_include_replacement(options, used_packages):
    cmake_lib_map = dict(filter(lambda x: x[0][0] is not None and x[0][1] is not None, CMAKE_PATH_MAP.items()))
    replacement = {}
    include2option = map2option(options, '-I')

    includeset = set(include2option.keys())
    include2option = dict(filter(lambda x: x[0] != x[1], include2option.items()))
    needed = set(includeset)
    for include in sorted(includeset):
        provided = set()
        pkg2library = CMAKE_PATH_MAP.get((None, include), {})
        pkg2library = dict(filter(lambda x: x[0] in used_packages, pkg2library.items()))

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
            packages = sorted(PKG_CONFIG_INCLUDE2PKGS[include])
            packages.sort(key=lambda x: len(PKG_CONFIG_INCLUDE_DIRS[x]))
            for pkg in packages:
                if pkg not in used_packages: continue
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
        else:
            print("No lib provide include dir " + include)
    replacement = dict([(include2option.get(x, x), y) for x, y in replacement.items()])
    return replacement
