#include "judge/judge.hpp"

#include <cstdlib>
#include <fstream>
#include <iterator>
#include <stdexcept>
#include <system_error>
#include <utility>
#include <vector>
#include <unistd.h>

namespace fs = std::filesystem;

namespace icpc {
namespace {

class TemporaryDirectory {
public:
    TemporaryDirectory() {
        const fs::path pattern_path = fs::temp_directory_path() / "icpc-mini-judge-XXXXXX";
        std::string pattern = pattern_path.string();
        std::vector<char> buffer(pattern.begin(), pattern.end());
        buffer.push_back('\0');
        const char* created = mkdtemp(buffer.data());
        if (created == nullptr) {
            throw std::runtime_error("cannot create temporary directory");
        }
        path_ = created;
    }

    ~TemporaryDirectory() {
        std::error_code error;
        fs::remove_all(path_, error);
    }

    TemporaryDirectory(const TemporaryDirectory&) = delete;
    TemporaryDirectory& operator=(const TemporaryDirectory&) = delete;

    [[nodiscard]] const fs::path& path() const noexcept { return path_; }

private:
    fs::path path_;
};

std::string read_limited(const fs::path& path, std::size_t limit = 64U * 1024U) {
    std::ifstream input(path, std::ios::binary);
    if (!input) {
        return {};
    }
    std::string result;
    result.resize(limit);
    input.read(result.data(), static_cast<std::streamsize>(result.size()));
    result.resize(static_cast<std::size_t>(input.gcount()));
    return result;
}

std::vector<std::string> read_tokens(const fs::path& path) {
    std::ifstream input(path);
    if (!input) {
        throw std::runtime_error("cannot read output file: " + path.string());
    }
    return {std::istream_iterator<std::string>(input), std::istream_iterator<std::string>()};
}

void validate_solution(const fs::path& path) {
    if (path.extension() != ".cpp") {
        throw std::runtime_error("solution must be a .cpp file");
    }
    if (!fs::exists(path) || !fs::is_regular_file(path)) {
        throw std::runtime_error("solution file does not exist: " + path.string());
    }
}

}  // namespace

Judge::Judge(std::string compiler) : compiler_(std::move(compiler)) {
    if (compiler_.empty()) {
        throw std::invalid_argument("compiler must not be empty");
    }
}

SubmissionResult Judge::evaluate(const Problem& problem, const fs::path& solution_path) const {
    validate_solution(solution_path);
    const fs::path canonical_solution = fs::canonical(solution_path);
    TemporaryDirectory temporary;
    const fs::path executable = temporary.path() / "submission";
    const fs::path compiler_stdout = temporary.path() / "compiler.stdout";
    const fs::path compiler_stderr = temporary.path() / "compiler.stderr";

    ProcessOptions compile_options;
    compile_options.working_directory = temporary.path();
    compile_options.stdout_path = compiler_stdout;
    compile_options.stderr_path = compiler_stderr;
    compile_options.timeout = std::chrono::seconds(15);
    compile_options.memory_limit_bytes = 1024U * 1024U * 1024U;
    compile_options.output_limit_bytes = 2U * 1024U * 1024U;

    const auto compilation = runner_.run(
        {compiler_, "-std=c++20", "-O2", "-pipe", canonical_solution.string(), "-o", executable.string()},
        compile_options);

    SubmissionResult submission;
    submission.compiler_output = read_limited(compiler_stdout) + read_limited(compiler_stderr);
    if (compilation.exit_code == 127 && submission.compiler_output.empty()) {
        throw std::runtime_error("cannot start C++ compiler: " + compiler_);
    }
    if (!compilation.exited_successfully() || !fs::is_regular_file(executable)) {
        submission.verdict = Verdict::compilation_error;
        if (compilation.timed_out) {
            submission.compiler_output += "\nCompilation timed out.\n";
        }
        return submission;
    }

    submission.verdict = Verdict::accepted;
    for (std::size_t index = 0; index < problem.tests.size(); ++index) {
        const auto& test = problem.tests[index];
        const fs::path actual = temporary.path() / ("test-" + std::to_string(index) + ".out");
        const fs::path error = temporary.path() / ("test-" + std::to_string(index) + ".err");

        ProcessOptions run_options;
        run_options.working_directory = temporary.path();
        run_options.stdin_path = test.input_path;
        run_options.stdout_path = actual;
        run_options.stderr_path = error;
        run_options.timeout = problem.time_limit;

        const auto execution = runner_.run({executable.string()}, run_options);
        Verdict verdict = Verdict::accepted;
        if (execution.timed_out) {
            verdict = Verdict::time_limit;
        } else if (!execution.exited_successfully()) {
            verdict = Verdict::runtime_error;
        } else if (read_tokens(actual) != read_tokens(test.answer_path)) {
            verdict = Verdict::wrong_answer;
        }

        submission.tests.push_back({test.name, verdict, execution.elapsed.count()});
        if (verdict != Verdict::accepted) {
            submission.verdict = verdict;
            break;
        }
    }
    return submission;
}

std::string Judge::verdict_name(Verdict verdict) {
    switch (verdict) {
        case Verdict::accepted:
            return "AC";
        case Verdict::wrong_answer:
            return "WA";
        case Verdict::compilation_error:
            return "CE";
        case Verdict::runtime_error:
            return "RE";
        case Verdict::time_limit:
            return "TLE";
    }
    return "UNKNOWN";
}

}  // namespace icpc
