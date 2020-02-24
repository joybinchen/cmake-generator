#! /bin/bash
pwd=$PWD
if [ ! -f cmake-vars.txt ]; then
	tmp=`mktemp -d`
	echo $tmp
	cd $tmp
	if [ ! -f $pwd/cmake-packages.txt ]; then
		echo DBus1 > cmake-packages.txt
		locate /Find |grep -e 'Find[^/]*\.cmake$' |sed 's|^.*/Find\([^/]*\)\.cmake|\1|' |sed 's|-$||' >> cmake-packages.txt
		locate Config.cmake |grep -e 'Config.cmake$'|sed 's|^.*/\([^/]*\)Config.cmake|\1|' |sed 's|-$||' >> cmake-packages.txt
		apt-file search /Find |cut -d' ' -f2- |grep -e 'Find[^/]*\.cmake$' |sed 's|^.*/Find\([^/]*\)\.cmake|\1|' |sed 's|-$||' >> cmake-packages.txt
		apt-file search Config.cmake |cut -d' ' -f2- |grep -e 'Config.cmake$'|sed 's|^.*/\([^/]*\)Config.cmake|\1|' |sed 's|-$||' >> cmake-packages.txt
		cat cmake-packages.txt |sort |uniq |grep -v Qt53D |grep -v GMock > $pwd/cmake-packages.txt
	fi
	cat > CMakeLists.txt << EOF
cmake_minimum_required(VERSION 3.10)
function(print_non_empty_value name)
	set(value \${\${name}})
	if(value)
		string(REPLACE ";" ":" tmp "\${value}")
		message(\${name}=\${tmp})
	endif()
endfunction()
function(show_find_package_result package)
	print_non_empty_value("\${package}_DIR")
	print_non_empty_value("\${package}_FOUND")
	print_non_empty_value("\${package}_EXECUTABLE")
	print_non_empty_value("\${package}_LIBRARY")
	print_non_empty_value("\${package}_LIBRARIES")
	print_non_empty_value("\${package}_LIBRARY_DIR")
	print_non_empty_value("\${package}_LIBRARY_DIRS")
	print_non_empty_value("\${package}_INCLUDE_DIR")
	print_non_empty_value("\${package}_INCLUDE_DIRS")
	string(TOUPPER "\${package}" backage)
	string(REPLACE "-" "_" backage "\${backage}")
	if(\${package} STREQUAL \${backage})
	else()
		show_find_package_result(\${backage})
	endif()
endfunction()
EOF
	sed 's|^\(.*\)$|find_package(\1 QUIET)|' $pwd/cmake-packages.txt >> CMakeLists.txt
	cat >> CMakeLists.txt << EOF
get_cmake_property(_variableNames VARIABLES)
foreach (_variableName \${_variableNames})
    message(STATUS "\${_variableName}=\${\${_variableName}}")
endforeach()
EOF
	#sed 's|^\(.*\)$|show_find_package_result(\1)|' $pwd/cmake-packages.txt >> CMakeLists.txt
	mkdir tmp
	cd tmp
	cmake -G 'Unix Makefiles' .. >$pwd/cmake-vars.txt
fi

cd $pwd
