cmake_minimum_required(VERSION 3.14)
project(hello_world)

set(CMAKE_CXX_STANDARD 17)

add_library(hello hello.cpp)

add_executable(hello_world main.cpp)
target_link_libraries(hello_world PRIVATE hello)

include(FetchContent)
FetchContent_Declare(
  googletest
  URL https://github.com/google/googletest/archive/refs/tags/v1.15.2.zip
)
FetchContent_MakeAvailable(googletest)

enable_testing()
add_executable(hello_test hello_test.cpp)
target_link_libraries(hello_test PRIVATE hello GTest::gtest_main)

include(GoogleTest)
gtest_discover_tests(hello_test)
