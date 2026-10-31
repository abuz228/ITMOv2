cmake_minimum_required(VERSION 3.20)

project(icpc_mini_judge VERSION 0.1.0 LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

add_library(judge_core
    src/judge.cpp
    src/problem_repository.cpp
    src/process_runner.cpp
)
target_include_directories(judge_core PUBLIC include)
target_compile_options(judge_core PRIVATE -Wall -Wextra -Wpedantic)

add_executable(icpc-judge src/main.cpp)
target_link_libraries(icpc-judge PRIVATE judge_core)
target_compile_options(icpc-judge PRIVATE -Wall -Wextra -Wpedantic)

include(CTest)
if(BUILD_TESTING)
    add_executable(judge-unit-tests tests/unit_tests.cpp)
    target_link_libraries(judge-unit-tests PRIVATE judge_core)
    target_compile_options(judge-unit-tests PRIVATE -Wall -Wextra -Wpedantic)

    add_test(NAME unit COMMAND judge-unit-tests)
    add_test(
        NAME cli_list
        COMMAND icpc-judge --problems-root ${CMAKE_CURRENT_SOURCE_DIR}/problems list
    )
    set_tests_properties(cli_list PROPERTIES
        PASS_REGULAR_EXPRESSION "prefix-sums"
    )

    add_test(
        NAME submit_correct
        COMMAND icpc-judge
            --problems-root ${CMAKE_CURRENT_SOURCE_DIR}/problems
            submit a-plus-b ${CMAKE_CURRENT_SOURCE_DIR}/tests/fixtures/a_plus_b_correct.cpp
    )
    set_tests_properties(submit_correct PROPERTIES
        PASS_REGULAR_EXPRESSION "Verdict: AC"
        TIMEOUT 30
    )

    add_test(
        NAME submit_wrong
        COMMAND icpc-judge
            --problems-root ${CMAKE_CURRENT_SOURCE_DIR}/problems
            submit a-plus-b ${CMAKE_CURRENT_SOURCE_DIR}/tests/fixtures/a_plus_b_wrong.cpp
    )
    set_tests_properties(submit_wrong PROPERTIES
        PASS_REGULAR_EXPRESSION "Verdict: WA"
        TIMEOUT 30
    )

    add_test(
        NAME reject_path_traversal
        COMMAND icpc-judge
            --problems-root ${CMAKE_CURRENT_SOURCE_DIR}/problems
            show ../a-plus-b
    )
    set_tests_properties(reject_path_traversal PROPERTIES WILL_FAIL TRUE)

    find_package(Python3 REQUIRED COMPONENTS Interpreter)
    add_test(
        NAME web_backend_api
        COMMAND ${CMAKE_COMMAND} -E env
            ICPC_JUDGE_BINARY=$<TARGET_FILE:icpc-judge>
            ${Python3_EXECUTABLE} ${CMAKE_CURRENT_SOURCE_DIR}/tests/test_web.py
    )
    set_tests_properties(web_backend_api PROPERTIES TIMEOUT 90)
endif()
