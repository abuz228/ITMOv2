#include "judge/judge.hpp"
#include "judge/problem_repository.hpp"

#include <cstdlib>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <iterator>
#include <stdexcept>
#include <string>
#include <vector>

namespace fs = std::filesystem;

namespace {

void print_usage() {
    std::cout
        << "ICPC Mini Judge\n\n"
        << "Usage:\n"
        << "  icpc-judge [--problems-root DIR] list\n"
        << "  icpc-judge [--problems-root DIR] show <problem-id>\n"
        << "  icpc-judge [--problems-root DIR] submit <problem-id> <solution.cpp>\n";
}

fs::path default_problems_root() {
    if (const char* configured = std::getenv("ICPC_JUDGE_PROBLEMS")) {
        return configured;
    }
    return fs::current_path() / "problems";
}

std::string read_text(const fs::path& path) {
    std::ifstream input(path);
    if (!input) {
        throw std::runtime_error("cannot read file: " + path.string());
    }
    return {std::istreambuf_iterator<char>(input), std::istreambuf_iterator<char>()};
}

}  // namespace

int main(int argc, char* argv[]) {
    try {
        std::vector<std::string> arguments(argv + 1, argv + argc);
        fs::path problems_root = default_problems_root();
        if (arguments.size() >= 2 && arguments[0] == "--problems-root") {
            problems_root = arguments[1];
            arguments.erase(arguments.begin(), arguments.begin() + 2);
        }
        if (arguments.empty()) {
            print_usage();
            return 2;
        }

        const icpc::ProblemRepository repository(problems_root);
        if (arguments[0] == "list" && arguments.size() == 1) {
            for (const auto& problem : repository.list()) {
                std::cout << problem.id << "\t" << problem.title << "\t"
                          << problem.time_limit.count() << " ms\n";
            }
            return 0;
        }

        if (arguments[0] == "show" && arguments.size() == 2) {
            const auto problem = repository.get(arguments[1]);
            std::cout << problem.id << " — " << problem.title << "\n"
                      << "Time limit: " << problem.time_limit.count() << " ms\n\n"
                      << read_text(problem.statement_path);
            return 0;
        }

        if (arguments[0] == "submit" && arguments.size() == 3) {
            const auto problem = repository.get(arguments[1]);
            const icpc::Judge judge;
            const auto result = judge.evaluate(problem, arguments[2]);
            if (!result.compiler_output.empty()) {
                std::cout << result.compiler_output;
                if (result.compiler_output.back() != '\n') {
                    std::cout << '\n';
                }
            }
            for (const auto& test : result.tests) {
                std::cout << "Test " << test.name << ": "
                          << icpc::Judge::verdict_name(test.verdict) << " ("
                          << test.elapsed_ms << " ms)\n";
            }
            std::cout << "Verdict: " << icpc::Judge::verdict_name(result.verdict) << '\n';
            // WA/CE/RE/TLE are valid judge results, not CLI infrastructure failures.
            return 0;
        }

        print_usage();
        return 2;
    } catch (const std::exception& error) {
        std::cerr << "Error: " << error.what() << '\n';
        return 2;
    }
}
