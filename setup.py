from setuptools import setup, find_packages
setup(
    name="cmake-generator",
    version="0.1",
    packages=find_packages(),
    install_requires=['diff_match_patch'],
    author="Joybin Chen",
    author_email="joybinchen@gmail.com",
    description="A script to convert compile_commands.json into CMakeLists.txt",
    license="MIT",
    keywords="c c++ development compile_commands json cmake ldlogger CodeChecker",
    url="https://github.com/joybinchen/cmake-generator",
    project_urls={
        "Bug Tracker": "https://github.com/joybinchen/cmake-generator/issues",
        "Documentation": "https://github.com/joybinchen/cmake-generator",
        "Source Code": "https://github.com/joybinchen/cmake-generator",
    },
    entry_points={
        'console_scripts': [
            'json2cmake = cmake_generator.json2cmake.main:main',
        ],
    },
)
