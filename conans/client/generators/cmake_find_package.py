from conans.client.generators.cmake import DepsCppCmake
from conans.client.generators.cmake_find_package_common import target_template, CMakeFindPackageCommonMacros
from conans.client.generators.cmake_multi import extend
from conans.model import Generator

find_package_header = """
include(FindPackageHandleStandardArgs)

message(STATUS "Conan: Using autogenerated Find{name}.cmake")
# Global approach
set({name}_FOUND 1)
set({name}_VERSION "{version}")

find_package_handle_standard_args({name} REQUIRED_VARS {name}_VERSION VERSION_VAR {name}_VERSION)
mark_as_advanced({name}_FOUND {name}_VERSION)

"""


assign_target_properties = """
        if({name}_INCLUDE_DIRS)
          set_target_properties({name}::{name} PROPERTIES INTERFACE_INCLUDE_DIRECTORIES "${{{name}_INCLUDE_DIRS}}")
        endif()
        set_property(TARGET {name}::{name} PROPERTY INTERFACE_LINK_LIBRARIES "${{{name}_LIBRARIES_TARGETS}};${{{name}_LINKER_FLAGS_LIST}}")
        set_property(TARGET {name}::{name} PROPERTY INTERFACE_COMPILE_DEFINITIONS ${{{name}_COMPILE_DEFINITIONS}})
        set_property(TARGET {name}::{name} PROPERTY INTERFACE_COMPILE_OPTIONS "${{{name}_COMPILE_OPTIONS_LIST}}")
"""


class CMakeFindPackageGenerator(Generator):
    template = """
{macros_and_functions}
{find_package_header_block}
{find_libraries_block}
if(NOT ${{CMAKE_VERSION}} VERSION_LESS "3.0")
    # Target approach
    if(NOT TARGET {name}::{name})
        add_library({name}::{name} INTERFACE IMPORTED GLOBAL)
        {assign_target_properties_block}
        {find_dependencies_block}
    endif()
endif()
"""

    @property
    def filename(self):
        pass

    @property
    def content(self):
        ret = {}
        for _, cpp_info in self.deps_build_info.dependencies:
            depname = cpp_info.get_name("cmake_find_package")
            ret["Find%s.cmake" % depname] = self._find_for_dep(depname, cpp_info)
        return ret

    def _find_for_dep(self, name, cpp_info):
        dep_cpp_info = cpp_info
        build_type = self.conanfile.settings.get_safe("build_type")
        if build_type:
            dep_cpp_info = extend(dep_cpp_info, build_type.lower())

        deps = DepsCppCmake(dep_cpp_info)
        lines = []
        public_deps_names = [self.deps_build_info[dep].get_name("cmake_find_package") for dep in
                             dep_cpp_info.public_deps]
        if dep_cpp_info.public_deps:
            # Here we are generating FindXXX, so find_modules=True
            lines = find_dependency_lines(public_deps_names, find_modules=True)
        find_package_header_block = find_package_header.format(name=name, version=dep_cpp_info.version)
        deps_names = ";".join(["{n}::{n}".format(n=n) for n in public_deps_names])
        find_libraries_block = target_template.format(name=name, deps=deps, build_type_suffix="", deps_names=deps_names)
        target_props = assign_target_properties.format(name=name, deps=deps, deps_names=deps_names)
        tmp = self.template.format(name=name, deps=deps,
                                   version=dep_cpp_info.version,
                                   find_dependencies_block="\n        ".join(lines),
                                   find_libraries_block=find_libraries_block,
                                   find_package_header_block=find_package_header_block,
                                   assign_target_properties_block=target_props,
                                   macros_and_functions="\n".join([
                                       CMakeFindPackageCommonMacros.conan_message,
                                       CMakeFindPackageCommonMacros.apple_frameworks_macro,
                                       CMakeFindPackageCommonMacros.conan_package_library_targets,
                                   ]))
        return tmp


def find_dependency_lines(public_deps_names, find_modules):
    lines = ["", "# Library dependencies", "include(CMakeFindDependencyMacro)"]
    for dep_name in public_deps_names:
        if find_modules:
            lines.append("\n")
            lines.append("find_dependency(%s REQUIRED)" % dep_name)
        else:
            # https://github.com/conan-io/conan/issues/4994
            # https://github.com/conan-io/conan/issues/5040
            lines.append("\n")
            lines.append('if(${CMAKE_VERSION} VERSION_LESS "3.9.0")')
            lines.append('  find_package(%s REQUIRED NO_MODULE)' % dep_name)
            lines.append("else()")
            lines.append('  find_dependency(%s REQUIRED NO_MODULE)' % dep_name)
            lines.append("endif()")
    return lines
