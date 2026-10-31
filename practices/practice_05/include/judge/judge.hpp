#pragma once

#include "judge/problem_repository.hpp"
#include "judge/process_runner.hpp"

#include <filesystem>
#include <string>
#include <vector>

namespace icpc {

enum class Verdict { accepted, wrong_answer, compilation_error, runtime_error, time_limit };

struct TestResult {
    std::string name;
    Verdict verdict{Verdict::runtime_error};
    long long elapsed_ms{0};
};

struct SubmissionResult {
    Verdict verdict{Verdict::runtime_error};
    std::vector<TestResult> tests;
    std::string compiler_output;
};

class Judge {
public:
    explicit Judge(std::string compiler = "g++");

    [[nodiscard]] SubmissionResult evaluate(
        const Problem& problem,
        const std::filesystem::path& solution_path) const;

    [[nodiscard]] static std::string verdict_name(Verdict verdict);

private:
    std::string compiler_;
    ProcessRunner runner_;
};

}  // namespace icpc
