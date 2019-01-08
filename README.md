# cmake-generator
A simple generator to convert compile database `compile_commands.json` into `CMakeLists.txt` files.
Use [CodeChecker log -k](https://github.com/Ericsson/codechecker.git) to collect the compile database `compile_commands.json`

# ldlogger
  A customized ldlogger working like [CodeChecker log -k](https://github.com/Ericsson/codechecker.git), and with extra capability to capture you own compile commands. 
  This tool is able to capture gcc and java like commands just as CodeChecker log.
  Execute make in ldlogger directory.
  Copy ldlogger_64.so into x64 library path, and rename it ldlogger.so.
  Copy ldlogger_32.so into x32 library_path, and rename it ldlogger.so, if capturing 32bit executable is needed.
  To capture customized commands, you have to put their Executable-Name in env `CC_LOGGER_CUSTOM`. Multiple Executable-Name should be separating with delimiter `:`.
  For each executable-name, put its output argument name in env `CC_LOGGER_OUTPUT_ARG_${EXECUTABLE_NAME}`, and put its non input file option in `CC_LOGGER_OPTION_ARG_${Executable_Name}`. The ${Executable_Name} here represent the Executable-Name with all its none-alphanum characters converted into underscore `_`.

# compile_commands
  The shell script `compile_commands` is working as a wrapper for ldlogger.so.
  This script exports necessary environs, and run make command to capture compile commands into compile database `compile_commands.json`. Put your customized env export in it.
  For examples, put following export commands in compile_commands to capture qmake, dbus-binding-tool and glib-genmarshal with meaningful input and output file recognized in the outcome compile database.

> export CC_LOGGER_CUSTOM_LIKE="qmake:dbus-binding-tool:glib-genmarshal"
> export CC_LOGGER_OUTPUT_ARG_dbus_binding_tool="--output"
> export CC_LOGGER_OUTPUT_ARG_glib_genmarshal="--output"
> export CC_LOGGER_OUTPUT_ARG_qmake='$-1'
> export CC_LOGGER_OPTION_ARG_qmake="-install"

# cmake-generator
    A helper script to make clean and cupture compile commands.