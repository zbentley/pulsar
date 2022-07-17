#
# Licensed to the Apache Software Foundation (ASF) under one
# or more contributor license agreements.  See the NOTICE file
# distributed with this work for additional information
# regarding copyright ownership.  The ASF licenses this file
# to you under the Apache License, Version 2.0 (the
# "License"); you may not use this file except in compliance
# with the License.  You may obtain a copy of the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing,
# software distributed under the License is distributed on an
# "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY
# KIND, either express or implied.  See the License for the
# specific language governing permissions and limitations
# under the License.
#

cmake_minimum_required(VERSION 3.22)
project (pulsar-cpp)
set(CMAKE_MODULE_PATH ${CMAKE_MODULE_PATH} "${CMAKE_SOURCE_DIR}/cmake_modules")

execute_process(COMMAND python ${CMAKE_SOURCE_DIR}/../src/gen-pulsar-version-macro.py OUTPUT_STRIP_TRAILING_WHITESPACE OUTPUT_VARIABLE PVM)
set(PVM_COMMENT "This is generated from Version.h.in by CMAKE. DO NOT EDIT DIRECTLY")
configure_file(templates/Version.h.in include/pulsar/Version.h @ONLY)

if (VCPKG_TRIPLET)
    message(STATUS "Use vcpkg, triplet is ${VCPKG_TRIPLET}")
    set(CMAKE_PREFIX_PATH "${CMAKE_SOURCE_DIR}/vcpkg_installed/${VCPKG_TRIPLET}")
    message(STATUS "Use CMAKE_PREFIX_PATH: ${CMAKE_PREFIX_PATH}")
    set(PROTOC_PATH "${CMAKE_PREFIX_PATH}/tools/protobuf/protoc")
    message(STATUS "Use protoc: ${PROTOC_PATH}")
    set(VCPKG_DEBUG_ROOT "${CMAKE_SOURCE_DIR}/vcpkg_installed/${VCPKG_TRIPLET}/debug")
    if (CMAKE_BUILD_TYPE STREQUAL "Debug")
        set(ZLIB_ROOT ${VCPKG_DEBUG_ROOT})
        set(OPENSSL_ROOT_DIR ${VCPKG_DEBUG_ROOT})
    endif ()
endif()

find_program(CCACHE_PROGRAM ccache)
if(CCACHE_PROGRAM)
    set(CMAKE_CXX_COMPILER_LAUNCHER "ccache")
    MESSAGE(STATUS "Using CCache")
endif(CCACHE_PROGRAM)

MESSAGE(STATUS "ARCHITECTURE: ${CMAKE_SYSTEM_PROCESSOR}")

option(BUILD_DYNAMIC_LIB "Build dynamic lib" ON)
MESSAGE(STATUS "BUILD_DYNAMIC_LIB:  " ${BUILD_DYNAMIC_LIB})

option(BUILD_STATIC_LIB "Build static lib" ON)
MESSAGE(STATUS "BUILD_STATIC_LIB:  " ${BUILD_STATIC_LIB})

option(BUILD_TESTS "Build tests" ON)
MESSAGE(STATUS "BUILD_TESTS:  " ${BUILD_TESTS})

option(BUILD_PYTHON_WRAPPER "Build Pulsar Python wrapper" ON)
MESSAGE(STATUS "BUILD_PYTHON_WRAPPER:  " ${BUILD_PYTHON_WRAPPER})

option(BUILD_WIRESHARK "Build Pulsar Wireshark dissector" OFF)
MESSAGE(STATUS "BUILD_WIRESHARK:  " ${BUILD_WIRESHARK})

option(BUILD_PERF_TOOLS "Build Pulsar CLI perf producer/consumer" OFF)
MESSAGE(STATUS "BUILD_PERF_TOOLS:  " ${BUILD_PERF_TOOLS})

option(LINK_STATIC "Link against static libraries" OFF)
MESSAGE(STATUS "LINK_STATIC:  " ${LINK_STATIC})

option(USE_LOG4CXX "Build with Log4cxx support" OFF)
MESSAGE(STATUS "USE_LOG4CXX:  " ${USE_LOG4CXX})

IF (CMAKE_BUILD_TYPE STREQUAL "")
    set(CMAKE_BUILD_TYPE RelWithDebInfo)
ENDIF ()

MESSAGE(STATUS "CMAKE_BUILD_TYPE:  " ${CMAKE_BUILD_TYPE})

set(THREADS_PREFER_PTHREAD_FLAG TRUE)
find_package(Threads REQUIRED)
MESSAGE(STATUS "Threads library: " ${CMAKE_THREAD_LIBS_INIT})

set(Boost_NO_BOOST_CMAKE ON)
set(CMAKE_CXX_STANDARD 11)
set(CMAKE_C_STANDARD 11)

# Compiler specific configuration:
# https://stackoverflow.com/questions/10046114/in-cmake-how-can-i-test-if-the-compiler-is-clang
if (CMAKE_CXX_COMPILER_ID STREQUAL "MSVC")
    add_definitions(-DWIN32_LEAN_AND_MEAN -DNOGDI -D_WIN32_WINNT=0x0501 -D_CRT_SECURE_NO_WARNINGS)
    add_compile_options(/wd4244 /wd4267 /wd4018 /wd4715 /wd4251 /wd4275)
elseif (CMAKE_CXX_COMPILER_ID STREQUAL "Intel")
    # ?? Don't have this to test with
else() # GCC or Clang are mostly compatible:
    # Turn on color error messages and show additional help with errors (only available in GCC v4.9+):
    add_compile_options(-fdiagnostics-show-option -fdiagnostics-color)
    # Turn on warnings and enable warnings-as-errors:
    add_compile_options(-Wall -Wformat-security -Wvla -Werror)
    # Turn off certain warnings that are too much pain for too little gain:
    add_compile_options(-Wno-sign-compare -Wno-deprecated-declarations -Wno-error=cpp)
    if (CMAKE_SYSTEM_PROCESSOR STREQUAL "x86_64")
        add_compile_options(-msse4.2 -mpclmul)
    endif()
    # Options unique to Clang or GCC:
    if (CMAKE_CXX_COMPILER_ID MATCHES "Clang")
        add_compile_options(-Qunused-arguments)
    elseif (CMAKE_CXX_COMPILER_ID STREQUAL "GNU")
        if (CMAKE_CXX_COMPILER_VERSION VERSION_LESS 4.9)
            MESSAGE(FATAL_ERROR "GCC must be >4.9; got ${CMAKE_CXX_COMPILER_VERSION}")
        elseif (CMAKE_CXX_COMPILER_VERSION VERSION_GREATER_EQUAL 8.0)
            add_compile_options(-Wno-stringop-truncation)
        endif()
    endif()
endif()

set(CMAKE_POSITION_INDEPENDENT_CODE ON)

set(LOG_CATEGORY_NAME $ENV{LOG_CATEGORY_NAME})

if (NOT LOG_CATEGORY_NAME)
    set(LOG_CATEGORY_NAME "\"pulsar.\"")
endif(NOT LOG_CATEGORY_NAME)

add_definitions(-DLOG_CATEGORY_NAME=${LOG_CATEGORY_NAME} -DBUILDING_PULSAR -DBOOST_ALL_NO_LIB -DBOOST_ALLOW_DEPRECATED_HEADERS)

if (LINK_STATIC)
    find_library(ZLIB_LIBRARIES REQUIRED NAMES libz.a z zlib)
    find_library(Protobuf_LIBRARIES NAMES libprotobuf.a libprotobuf)
    find_library(CURL_LIBRARIES NAMES libcurl.a curl curl_a libcurl_a)
    find_library(LIB_ZSTD NAMES libzstd.a)
    find_library(LIB_SNAPPY NAMES libsnappy-shared.a libsnappy.a)
    message(STATUS "Protobuf_LIBRARIES: ${Protobuf_LIBRARIES}")
    set(COMMON_LIBS ${Protobuf_LIBRARIES} ${COMMON_LIBS})

    if (USE_LOG4CXX)
        if (LOG4CXX_USE_DYNAMIC_LIBS)
            find_library(LOG4CXX_LIBRARY_PATH log4cxx)
        else ()
            find_library(LOG4CXX_LIBRARY_PATH NAMES liblog4cxx.a)

            # Libraries needed by log4cxx to link statically with
            find_library(APR_LIBRARY_PATH NAMES libapr-1 PATHS /usr/lib /usr/local/apr/lib /usr/local/opt/apr/libexec/lib/)
            find_library(APR_UTIL_LIBRARY_PATH NAMES libaprutil-1 PATHS /usr/lib /usr/local/apr/lib /usr/local/opt/apr-util/libexec/lib/)
            find_library(EXPAT_LIBRARY_PATH NAMES libexpat expat)
            if (APPLE)
                find_library(ICONV_LIBRARY_PATH NAMES libiconv iconv)
            else ()
                set(ICONV_LIBRARY_PATH )
            endif (APPLE)
        endif (LOG4CXX_USE_DYNAMIC_LIBS)
    endif (USE_LOG4CXX)

    if (MSVC)
        add_definitions(-DCURL_STATICLIB)
    endif()

    if (UNIX AND NOT APPLE)
        set(CMAKE_FIND_LIBRARY_SUFFIXES .a)
    endif()

else()
    # Link to shared libraries
    find_package(ZLIB REQUIRED)
    # NOTE: The default MODULE mode may not find debug libraries so use CONFIG mode here
    unset(Protobuf_INCLUDE_DIRS CACHE)
    unset(Protobuf_LIBRARIES CACHE)
    find_package(Protobuf QUIET CONFIG)
    # NOTE: On Windows x86 platform, Protobuf_FOUND might be set false but Protobuf_INCLUDE_DIRS and
    # Protobuf_LIBRARIES are both found.
    if (Protobuf_INCLUDE_DIRS AND Protobuf_LIBRARIES AND NOT Protobuf_FOUND)
        set(Protobuf_FOUND TRUE)
    endif ()
    if (Protobuf_FOUND)
        message("Found Protobuf in config mode")
        message(STATUS "Protobuf_LIBRARIES: ${Protobuf_LIBRARIES}")
        message(STATUS "Protobuf_INCLUDE_DIRS: ${Protobuf_INCLUDE_DIRS}")
    else ()
        message("Failed to find Protobuf in config mode, try to find it from system path")
        find_library(Protobuf_LIBRARIES protobuf libprotobuf)
        find_path(Protobuf_INCLUDE_DIRS google/protobuf/stubs/common.h)
        message(STATUS "Protobuf_LIBRARIES: ${Protobuf_LIBRARIES}")
        message(STATUS "Protobuf_INCLUDE_DIRS: ${Protobuf_INCLUDE_DIRS}")
    endif ()

    if (${Protobuf_FOUND} AND (${CMAKE_VERSION} VERSION_GREATER 3.8))
        set(COMMON_LIBS protobuf::libprotobuf ${COMMON_LIBS})
    else ()
        set(COMMON_LIBS ${Protobuf_LIBRARIES} ${COMMON_LIBS})
    endif ()

    if (MSVC AND (${CMAKE_BUILD_TYPE} STREQUAL Debug))
        find_library(LIB_ZSTD zstdd HINTS "${VCPKG_DEBUG_ROOT}/lib")
    else ()
        find_library(LIB_ZSTD zstd)
    endif ()
    if (MSVC AND (${CMAKE_BUILD_TYPE} STREQUAL Debug))
        find_library(LIB_SNAPPY NAMES snappyd HINTS "${VCPKG_DEBUG_ROOT}/lib")
    else ()
        find_library(LIB_SNAPPY NAMES snappy libsnappy)
    endif ()

    find_package(CURL REQUIRED)
    if (${CMAKE_VERSION} VERSION_GREATER "3.12")
        set(COMMON_LIBS ${COMMON_LIBS} CURL::libcurl)
    endif ()

    if (USE_LOG4CXX)
        find_library(LOG4CXX_LIBRARY_PATH log4cxx)
        find_path(LOG4CXX_INCLUDE_PATH log4cxx/logger.h)
    endif (USE_LOG4CXX)
endif (LINK_STATIC)

SET(Boost_USE_STATIC_LIBS ${LINK_STATIC})
if (MSVC)
  set(BOOST_COMPONENTS ${BOOST_COMPONENTS} date_time)
endif()

if(BUILD_PERF_TOOLS)
    set(BOOST_COMPONENTS ${BOOST_COMPONENTS} program_options)
endif()

if (BUILD_PYTHON_WRAPPER)
    find_package(Python REQUIRED COMPONENTS Development)
    if(Python_VERSION_MAJOR GREATER_EQUAL 3)
        MESSAGE(STATUS, "Building boost-python component python${Python_VERSION_MAJOR}${Python_VERSION_MINOR}")
        set(BOOST_COMPONENTS ${BOOST_COMPONENTS} python${Python_VERSION_MAJOR}${Python_VERSION_MINOR})
    else()
        set(BOOST_COMPONENTS ${BOOST_COMPONENTS} python)
    endif()
endif (BUILD_PYTHON_WRAPPER)

set(BOOST_COMPONENTS ${BOOST_COMPONENTS} regex)
find_package(Boost REQUIRED COMPONENTS ${BOOST_COMPONENTS})

find_package(OpenSSL REQUIRED)

if (USE_LOG4CXX)
    set(CMAKE_CXX_FLAGS " -DUSE_LOG4CXX ${CMAKE_CXX_FLAGS}")
    find_path(LOG4CXX_INCLUDE_PATH log4cxx/logger.h)
endif (USE_LOG4CXX)

if (NOT APPLE AND NOT MSVC)
    # we don't set options below to build _pulsar.so
    # Hide all non-exported symbols to avoid conflicts
    add_compile_options(-fvisibility=hidden)
    if (CMAKE_COMPILER_IS_GNUCC)
        add_compile_options(-Wl,--exclude-libs,ALL)
    endif ()
endif ()

if (LIB_ZSTD)
    set(HAS_ZSTD 1)
else ()
    set(HAS_ZSTD 0)
endif ()
MESSAGE(STATUS "HAS_ZSTD: ${HAS_ZSTD}")

if (LIB_SNAPPY)
    set(HAS_SNAPPY 1)
else ()
    set(HAS_SNAPPY 0)
endif ()
MESSAGE(STATUS "HAS_SNAPPY: ${HAS_SNAPPY}")

set(ADDITIONAL_LIBRARIES $ENV{PULSAR_ADDITIONAL_LIBRARIES})
link_directories( $ENV{PULSAR_ADDITIONAL_LIBRARY_PATH} )

set(AUTOGEN_DIR ${CMAKE_BINARY_DIR}/generated)
file(MAKE_DIRECTORY ${AUTOGEN_DIR})

include_directories(
  ${CMAKE_SOURCE_DIR}
  ${CMAKE_SOURCE_DIR}/include
  ${CMAKE_BINARY_DIR}/include
  ${AUTOGEN_DIR}
  ${Boost_INCLUDE_DIR}
  ${OPENSSL_INCLUDE_DIR}
  ${ZLIB_INCLUDE_DIRS}
  ${CURL_INCLUDE_DIRS}
  ${Protobuf_INCLUDE_DIRS}
  ${LOG4CXX_INCLUDE_PATH}
  ${GTEST_INCLUDE_PATH}
  ${GMOCK_INCLUDE_PATH}
)

set(COMMON_LIBS
  ${COMMON_LIBS}
  Threads::Threads
  ${Boost_REGEX_LIBRARY}
  ${Boost_SYSTEM_LIBRARY}
  ${CURL_LIBRARIES}
  OpenSSL::SSL
  ${ZLIB_LIBRARIES}
  ${ADDITIONAL_LIBRARIES}
  ${CMAKE_DL_LIBS}
)

if (MSVC)
  set(COMMON_LIBS
    ${COMMON_LIBS}
    ${Boost_DATE_TIME_LIBRARY}
  )
endif()

if (NOT MSVC)
    set(COMMON_LIBS ${COMMON_LIBS} m)
else()
    set(COMMON_LIBS
    ${COMMON_LIBS}
    wldap32.lib
    Normaliz.lib)
endif()

if (USE_LOG4CXX)
    set(COMMON_LIBS
      ${COMMON_LIBS}
      ${LOG4CXX_LIBRARY_PATH}
      ${APR_LIBRARY_PATH}
      ${APR_UTIL_LIBRARY_PATH}
      ${EXPAT_LIBRARY_PATH}
      ${ICONV_LIBRARY_PATH}
    )
endif ()

if (HAS_ZSTD)
    set(COMMON_LIBS ${COMMON_LIBS} ${LIB_ZSTD} )
endif ()

add_definitions(-DHAS_ZSTD=${HAS_ZSTD})

if (HAS_SNAPPY)
    set(COMMON_LIBS ${COMMON_LIBS} ${LIB_SNAPPY} )
endif ()

add_definitions(-DHAS_SNAPPY=${HAS_SNAPPY})

if(NOT APPLE AND NOT MSVC)
    set(COMMON_LIBS ${COMMON_LIBS} rt)
endif ()

link_directories(${CMAKE_BINARY_DIR}/lib)

set(LIB_NAME $ENV{PULSAR_LIBRARY_NAME})
if (NOT LIB_NAME)
    set(LIB_NAME pulsar)
endif(NOT LIB_NAME)

set(CLIENT_LIBS
  ${COMMON_LIBS}
  ${LIB_NAME}
)

add_subdirectory(lib)
if(BUILD_PERF_TOOLS)
    add_subdirectory(perf)
endif(BUILD_PERF_TOOLS)

if (BUILD_DYNAMIC_LIB)
    add_subdirectory(examples)
endif()

if (BUILD_TESTS)
    add_subdirectory(tests)
endif()

if (BUILD_PYTHON_WRAPPER)
    add_subdirectory(python)
endif ()

if (BUILD_WIRESHARK)
    add_subdirectory(wireshark)
endif()

# `make format` option
if (NOT APPLE AND NOT WIN32)
    set(CLANG_FORMAT_VERSION "5.0")
endif()


find_package(ClangTools)
set(BUILD_SUPPORT_DIR "${CMAKE_SOURCE_DIR}/build-support")
add_custom_target(format python ${BUILD_SUPPORT_DIR}/run_clang_format.py
        ${CLANG_FORMAT_BIN}
        0
        ${BUILD_SUPPORT_DIR}/clang_format_exclusions.txt
        ${CMAKE_SOURCE_DIR}/lib
        ${CMAKE_SOURCE_DIR}/perf
        ${CMAKE_SOURCE_DIR}/examples
        ${CMAKE_SOURCE_DIR}/tests
        ${CMAKE_SOURCE_DIR}/include
        ${CMAKE_SOURCE_DIR}/python/src
        ${CMAKE_SOURCE_DIR}/wireshark)

# `make check-format` option (for CI test)
add_custom_target(check-format python ${BUILD_SUPPORT_DIR}/run_clang_format.py
        ${CLANG_FORMAT_BIN}
        1
        ${BUILD_SUPPORT_DIR}/clang_format_exclusions.txt
        ${CMAKE_SOURCE_DIR}/lib
        ${CMAKE_SOURCE_DIR}/perf
        ${CMAKE_SOURCE_DIR}/examples
        ${CMAKE_SOURCE_DIR}/tests
        ${CMAKE_SOURCE_DIR}/include
        ${CMAKE_SOURCE_DIR}/python/src
        ${CMAKE_SOURCE_DIR}/wireshark)
