# Build Logger

This tool can capture the build process and generate a
[JSON Compilation Database](https://clang.llvm.org/docs/JSONCompilationDatabase.html) 

## Compilation

To build the project execute
~~~~~~~
cd vendor/build-logger
make -f Makefile.manual
~~~~~~~

## Usage

Set the following environment variables:
~~~~~~~
export LD_PRELOAD=ldlogger.so
export LD_LIBRARY_PATH=`pwd`/build/lib:$LD_LIBRARY_PATH
export CC_LOGGER_GCC_LIKE="gcc:g++:clang"
#The output compilation JSON file
export CC_LOGGER_FILE=`pwd`/compilation.json
#Set this environment `true` to record linking commands
export CC_LOGGER_KEEP_LINK=true
~~~~~~~

then when you call `gcc` from a sub-shell (e.g. as a part of a Make build process),
 `compilation.json` will be created.
For example:
`bash -c "gcc -c something.c"`
will create
~~~~~~~
compilation.json:
[
	{
		"directory": "/home/john_doe/",
		"command": "/usr/bin/gcc-4.8 -c /home/john_doe/something.c",
		"file": "/home/john_doe/something.c"
	}
]
~~~~~~~



## Environment Variables

### `CC_LOGGER_GCC_LIKE` 
You can change the compilers that should be logged. 
Set `CC_LOGGER_GCC_LIKE` environment variable to a colon separated list.

 For example (default):

 ```export CC_LOGGER_GCC_LIKE="gcc:g++:clang"```

 The logger will match any compilers with `gcc`,`g++` or `clang` in their filenames.


### `CC_LOGGER_FILE`
Output file to generate compilation database into. 
This can be a relative or absolute path.

### `CC_LOGGER_JAVAC_LIKE` 
You can specify the `javac` like 
compilers that should be logged as a colon separated string list.

### `CC_LOGGER_DEF_DIRS` 
If the environment variable is defined, 
the logger will extend the  compiler argument list in the compilation 
database  with the pre-configured include paths of the logged compiler.

### `CC_LOGGER_KEEP_LINK` 
If the environment variable is true,
call to linkers like `ld:gold:ar` will also be logged into compile database. 

