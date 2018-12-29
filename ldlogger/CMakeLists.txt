cmake_minimum_required(VERSION 2.8.8)
project(cmake-generator LANGUAGES C CXX)

add_library(ldlogger_64 SHARED
    src/ldlogger-tool-gcc.c
    src/ldlogger-hooks.c
    src/ldlogger-logger.c
    src/ldlogger-tool.c
    src/ldlogger-tool-javac.c
    src/ldlogger-tool-custom.c
    src/ldlogger-util.c
)

target_compile_options(ldlogger_64 PRIVATE
    -m64
    -std=c89
    -ansi
    -pedantic
    -Wall
    -Wextra
    -Wno-strict-aliasing
    -fno-exceptions
    -fPIC
    -fomit-frame-pointer
    -fvisibility=hidden
    -shared
    -Wl,--no-as-needed
)

target_compile_definitions(ldlogger_64 PRIVATE
    _GNU_SOURCE
)

target_link_libraries(ldlogger_64 PRIVATE
    -m64
    dl
)

add_executable(ldlogger 
    src/ldlogger-logger.c
    src/ldlogger-tool-gcc.c
    src/ldlogger-tool.c
    src/ldlogger-util.c
    src/ldlogger-tool-javac.c
    src/ldlogger-tool-custom.c
)

target_compile_options(ldlogger PRIVATE
    -m32
    -std=c89
    -ansi
    -pedantic
    -Wall
    -Wextra
)

target_compile_definitions(ldlogger PRIVATE
    _GNU_SOURCE
    __LOGGER_MAIN__
)

target_link_libraries(ldlogger PRIVATE
    -m32
)

add_library(ldlogger_32 SHARED
    src/ldlogger-tool-gcc.c
    src/ldlogger-hooks.c
    src/ldlogger-logger.c
    src/ldlogger-tool.c
    src/ldlogger-tool-javac.c
    src/ldlogger-util.c
    src/ldlogger-tool-custom.c
)

target_compile_options(ldlogger_32 PRIVATE
    -m32
    -std=c89
    -ansi
    -pedantic
    -Wall
    -Wextra
    -Wno-strict-aliasing
    -fno-exceptions
    -fPIC
    -fomit-frame-pointer
    -fvisibility=hidden
    -shared
    -Wl,--no-as-needed
)

target_compile_definitions(ldlogger_32 PRIVATE
    _GNU_SOURCE
)

target_link_libraries(ldlogger_32 PRIVATE
    -m32
    dl
)

