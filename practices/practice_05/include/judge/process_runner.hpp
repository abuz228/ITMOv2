#pragma once

#include <chrono>
#include <cstddef>
#include <filesystem>
#include <string>
#include <vector>

namespace icpc {

struct ProcessOptions {
    std::filesystem::path working_directory;
    std::filesystem::path stdin_path;
    std::filesystem::path stdout_path;
    std::filesystem::path stderr_path;
    std::chrono::milliseconds timeout{1000};
    std::size_t memory_limit_bytes{256U * 1024U * 1024U};
    std::size_t output_limit_bytes{4U * 1024U * 1024U};
};

struct ProcessResult {
    int exit_code{-1};
    int signal{0};
    bool timed_out{false};
    std::chrono::milliseconds elapsed{0};

    [[nodiscard]] bool exited_successfully() const noexcept {
        return !timed_out && signal == 0 && exit_code == 0;
    }
};

class ProcessRunner {
public:
    [[nodiscard]] ProcessResult run(
        const std::vector<std::string>& arguments,
        const ProcessOptions& options) const;
};

}  // namespace icpc
