#pragma once

#include <chrono>
#include <filesystem>
#include <string>
#include <vector>

namespace icpc {

struct TestCase {
    std::string name;
    std::filesystem::path input_path;
    std::filesystem::path answer_path;
};

struct Problem {
    std::string id;
    std::string title;
    std::chrono::milliseconds time_limit{1000};
    std::filesystem::path statement_path;
    std::vector<TestCase> tests;
};

class ProblemRepository {
public:
    explicit ProblemRepository(std::filesystem::path root);

    [[nodiscard]] std::vector<Problem> list() const;
    [[nodiscard]] Problem get(const std::string& id) const;
    [[nodiscard]] const std::filesystem::path& root() const noexcept;

    [[nodiscard]] static bool is_valid_problem_id(const std::string& id) noexcept;

private:
    std::filesystem::path root_;
    [[nodiscard]] Problem load_problem(const std::filesystem::path& directory) const;
};

}  // namespace icpc
