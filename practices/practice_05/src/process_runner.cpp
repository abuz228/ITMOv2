#include "judge/process_runner.hpp"

#include <cerrno>
#include <chrono>
#include <csignal>
#include <fcntl.h>
#include <stdexcept>
#include <string>
#include <sys/resource.h>
#include <sys/prctl.h>
#include <sys/types.h>
#include <sys/wait.h>
#include <thread>
#include <unistd.h>

namespace fs = std::filesystem;

namespace icpc {
namespace {

[[noreturn]] void child_fail() {
    _exit(127);
}

int open_input(const fs::path& path) {
    if (path.empty()) {
        return open("/dev/null", O_RDONLY);
    }
    return open(path.c_str(), O_RDONLY | O_CLOEXEC);
}

int open_output(const fs::path& path) {
    return open(path.c_str(), O_WRONLY | O_CREAT | O_TRUNC | O_CLOEXEC, 0600);
}

void set_limit(int resource, rlim_t value) {
    const rlimit limit{value, value};
    if (setrlimit(resource, &limit) != 0) {
        child_fail();
    }
}

}  // namespace

ProcessResult ProcessRunner::run(
    const std::vector<std::string>& arguments,
    const ProcessOptions& options) const {
    if (arguments.empty() || options.stdout_path.empty() || options.stderr_path.empty()) {
        throw std::invalid_argument("process arguments and output paths are required");
    }

    const auto started = std::chrono::steady_clock::now();
    const pid_t pid = fork();
    if (pid < 0) {
        throw std::runtime_error("fork failed: " + std::to_string(errno));
    }

    if (pid == 0) {
        if (setpgid(0, 0) != 0) {
            child_fail();
        }
        if (prctl(PR_SET_NO_NEW_PRIVS, 1, 0, 0, 0) != 0) {
            child_fail();
        }
        if (!options.working_directory.empty() && chdir(options.working_directory.c_str()) != 0) {
            child_fail();
        }

        const int input_fd = open_input(options.stdin_path);
        const int output_fd = open_output(options.stdout_path);
        const int error_fd = open_output(options.stderr_path);
        if (input_fd < 0 || output_fd < 0 || error_fd < 0) {
            child_fail();
        }
        if (dup2(input_fd, STDIN_FILENO) < 0 || dup2(output_fd, STDOUT_FILENO) < 0 ||
            dup2(error_fd, STDERR_FILENO) < 0) {
            child_fail();
        }
        close(input_fd);
        close(output_fd);
        close(error_fd);

        const auto cpu_seconds = static_cast<rlim_t>((options.timeout.count() + 999) / 1000 + 1);
        set_limit(RLIMIT_CPU, cpu_seconds);
        set_limit(RLIMIT_AS, static_cast<rlim_t>(options.memory_limit_bytes));
        set_limit(RLIMIT_FSIZE, static_cast<rlim_t>(options.output_limit_bytes));
        set_limit(RLIMIT_CORE, 0);

        std::vector<char*> argv;
        argv.reserve(arguments.size() + 1);
        for (const auto& argument : arguments) {
            argv.push_back(const_cast<char*>(argument.c_str()));
        }
        argv.push_back(nullptr);
        execvp(argv.front(), argv.data());
        child_fail();
    }

    (void)setpgid(pid, pid);
    int status = 0;
    bool timed_out = false;
    while (true) {
        const pid_t result = waitpid(pid, &status, WNOHANG);
        if (result == pid) {
            break;
        }
        if (result < 0) {
            if (errno == EINTR) {
                continue;
            }
            (void)kill(-pid, SIGKILL);
            throw std::runtime_error("waitpid failed: " + std::to_string(errno));
        }
        if (std::chrono::steady_clock::now() - started >= options.timeout) {
            timed_out = true;
            (void)kill(-pid, SIGKILL);
            while (waitpid(pid, &status, 0) < 0 && errno == EINTR) {
            }
            break;
        }
        std::this_thread::sleep_for(std::chrono::milliseconds(5));
    }

    // Remove descendants left behind by a program that forked and then exited.
    (void)kill(-pid, SIGKILL);

    ProcessResult result;
    result.timed_out = timed_out;
    result.elapsed = std::chrono::duration_cast<std::chrono::milliseconds>(
        std::chrono::steady_clock::now() - started);
    if (!timed_out && WIFEXITED(status)) {
        result.exit_code = WEXITSTATUS(status);
    } else if (!timed_out && WIFSIGNALED(status)) {
        result.signal = WTERMSIG(status);
    }
    return result;
}

}  // namespace icpc
