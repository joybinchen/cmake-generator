# cmake-generator
A simple generator to convert compile database `compile_commands.json` into `CMakeLists.txt` files.
Use [CodeChecker log -k](https://github.com/Ericsson/codechecker.git) to collect the compile database `compile_commands.json`

# ldlogger
  A customized ldlogger working like [CodeChecker log -k](https://github.com/Ericsson/codechecker.git), and with extra capability to capture you own compile commands. 
  To use it, you have to put executable-names in env `CC_LOGGER_CUSTOM`, seperating with `:`.
  And for each executable-name, put its output argument name in env `CC_LOGGER_OUTPUT_ARG_${EXECUTABLE_NAME}`. The ${EXECUTABLE_NAME} here represent the executable-name turned to upper case and all its none-alphanum characters turned into `_`.
> export CC_LOGGER_CUSTOM="dbus-binding-tool:glib-genmarshal"
> export CC_LOGGER_OUTPUT_ARG_DBUS_BINGDING_TOOL="--output"
> export CC_LOGGER_OUTPUT_ARG_GLIB_GENMARSHAL="--output"
