#include "judge/problem_repository.hpp"

#include <algorithm>
#include <cctype>
#include <fstream>
#include <map>
#include <stdexcept>
#include <utility>

namespace fs = std::filesystem;

namespace icpc {
namespace {

std::string trim(std::string value) {
    const auto not_space = [](unsigned char ch) { return !std::isspace(ch); };
    value.erase(value.begin(), std::find_if(value.begin(), value.end(), not_space));
    value.erase(std::find_if(value.rbegin(), value.rend(), not_space).base(), value.end());
    return value;
}

std::map<std::string, std::string> read_metadata(const fs::path& path) {
    std::ifstream input(path);
    if (!input) {
        throw std::runtime_error("cannot open problem metadata: " + path.string());
    }

    std::map<std::string, std::string> values;
    std::string line;
    while (std::getline(input, line)) {
        const auto separator = line.find('=');
        if (separator == std::string::npos) {
            continue;
        }
        values[trim(line.substr(0, separator))] = trim(line.substr(separator + 1));
    }
    return values;
}

}  // namespace

ProblemRepository::ProblemRepository(fs::path root) {
    if (!fs::exists(root) || !fs::is_directory(root)) {
        throw std::runtime_error("problems directory does not exist: " + root.string());
    }
    root_ = fs::weakly_canonical(std::move(root));
}

const fs::path& ProblemRepository::root() const noexcept {
    return root_;
}

bool ProblemRepository::is_valid_problem_id(const std::string& id) noexcept {
    if (id.empty() || id.size() > 64) {
        return false;
    }
    const auto valid = [](unsigned char ch) {
        return std::isalnum(ch) || ch == '-' || ch == '_';
    };
    return std::isalnum(static_cast<unsigned char>(id.front())) &&
           std::all_of(id.begin(), id.end(), valid);
}

Problem ProblemRepository::load_problem(const fs::path& directory) const {
    const std::string id = directory.filename().string();
    if (!is_valid_problem_id(id)) {
        throw std::runtime_error("invalid problem directory name: " + id);
    }
    if (fs::is_symlink(directory)) {
        throw std::runtime_error("symbolic links are not allowed for problem directories: " + id);
    }

    const fs::path canonical_directory = fs::weakly_canonical(directory);
    if (canonical_directory.parent_path() != root_) {
        throw std::runtime_error("problem directory escapes repository root: " + id);
    }

    const fs::path metadata_path = canonical_directory / "problem.conf";
    if (!fs::is_regular_file(metadata_path) || fs::is_symlink(metadata_path)) {
        throw std::runtime_error("problem is missing safe metadata: " + id);
    }
    const auto metadata = read_metadata(metadata_path);
    const auto title_it = metadata.find("title");
    if (title_it == metadata.end() || title_it->second.empty()) {
        throw std::runtime_error("missing title for problem: " + id);
    }

    long long time_limit_ms = 1000;
    if (const auto it = metadata.find("time_limit_ms"); it != metadata.end()) {
        try {
            time_limit_ms = std::stoll(it->second);
        } catch (const std::exception&) {
            throw std::runtime_error("invalid time_limit_ms for problem: " + id);
        }
    }
    if (time_limit_ms < 50 || time_limit_ms > 10000) {
        throw std::runtime_error("time_limit_ms must be between 50 and 10000 for problem: " + id);
    }

    const fs::path statement = canonical_directory / "statement.md";
    const fs::path tests_directory = canonical_directory / "tests";
    if (!fs::is_regular_file(statement) || fs::is_symlink(statement) ||
        !fs::is_directory(tests_directory) || fs::is_symlink(tests_directory)) {
        throw std::runtime_error("problem is missing statement or tests: " + id);
    }
    const fs::path canonical_tests_directory = fs::canonical(tests_directory);
    if (canonical_tests_directory.parent_path() != canonical_directory) {
        throw std::runtime_error("tests directory escapes problem directory: " + id);
    }

    std::vector<TestCase> tests;
    for (const auto& entry : fs::directory_iterator(canonical_tests_directory)) {
        if (!entry.is_regular_file() || entry.path().extension() != ".in") {
            continue;
        }
        if (entry.is_symlink()) {
            throw std::runtime_error("symbolic links are not allowed in tests: " + id);
        }
        fs::path answer = entry.path();
        answer.replace_extension(".out");
        if (!fs::is_regular_file(answer) || fs::is_symlink(answer)) {
            throw std::runtime_error("missing answer for test: " + entry.path().string());
        }
        const fs::path canonical_input = fs::canonical(entry.path());
        const fs::path canonical_answer = fs::canonical(answer);
        if (canonical_input.parent_path() != canonical_tests_directory ||
            canonical_answer.parent_path() != canonical_tests_directory) {
            throw std::runtime_error("test file escapes tests directory: " + id);
        }
        tests.push_back({entry.path().stem().string(), canonical_input, canonical_answer});
    }
    std::sort(tests.begin(), tests.end(), [](const TestCase& left, const TestCase& right) {
        return left.name < right.name;
    });
    if (tests.empty()) {
        throw std::runtime_error("problem has no tests: " + id);
    }

    return {id, title_it->second, std::chrono::milliseconds(time_limit_ms), statement, tests};
}

std::vector<Problem> ProblemRepository::list() const {
    std::vector<Problem> problems;
    for (const auto& entry : fs::directory_iterator(root_)) {
        if (entry.is_directory() && is_valid_problem_id(entry.path().filename().string())) {
            problems.push_back(load_problem(entry.path()));
        }
    }
    std::sort(problems.begin(), problems.end(), [](const Problem& left, const Problem& right) {
        return left.id < right.id;
    });
    return problems;
}

Problem ProblemRepository::get(const std::string& id) const {
    if (!is_valid_problem_id(id)) {
        throw std::runtime_error("invalid problem id: " + id);
    }
    const fs::path directory = root_ / id;
    if (!fs::is_directory(directory)) {
        throw std::runtime_error("unknown problem: " + id);
    }
    return load_problem(directory);
}

}  // namespace icpc
