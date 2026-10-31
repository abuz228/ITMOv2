#include "judge/problem_repository.hpp"

#include <cstdlib>
#include <iostream>

namespace {

void require(bool condition, const char* message) {
    if (!condition) {
        std::cerr << "FAILED: " << message << '\n';
        std::exit(1);
    }
}

}  // namespace

int main() {
    using icpc::ProblemRepository;
    require(ProblemRepository::is_valid_problem_id("a-plus-b"), "normal id is valid");
    require(ProblemRepository::is_valid_problem_id("graphs_01"), "underscore id is valid");
    require(!ProblemRepository::is_valid_problem_id("../secret"), "path traversal is rejected");
    require(!ProblemRepository::is_valid_problem_id("/absolute"), "absolute path is rejected");
    require(!ProblemRepository::is_valid_problem_id("-leading"), "leading punctuation is rejected");
    require(!ProblemRepository::is_valid_problem_id(""), "empty id is rejected");
    std::cout << "All unit tests passed\n";
}
