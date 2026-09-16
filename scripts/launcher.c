/* The bundle's main executable: spawns `uv run gesture-mac` in the repo,
 * logs to ~/Library/Logs/gesture-mac.log, forwards Quit to the child.
 * A compiled binary inside the bundle (rather than a shell script, which
 * runs as /bin/zsh) is what makes macOS attribute the child's camera and
 * Accessibility requests to "gesture-mac". Built by scripts/make-app.sh
 * with REPO and UV baked in. */
#include <fcntl.h>
#include <signal.h>
#include <spawn.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/wait.h>
#include <unistd.h>

#ifndef REPO
#error "REPO not defined"
#endif
#ifndef UV
#error "UV not defined"
#endif

extern char **environ;
static pid_t child = 0;

static void forward(int sig) { if (child > 0) kill(child, sig); }

int main(void) {
    char log[1024];
    snprintf(log, sizeof log, "%s/Library/Logs/gesture-mac.log", getenv("HOME") ? getenv("HOME") : "/tmp");
    int fd = open(log, O_WRONLY | O_CREAT | O_APPEND, 0644);
    if (fd >= 0) { dup2(fd, 1); dup2(fd, 2); close(fd); }
    if (chdir(REPO) != 0) { perror("chdir " REPO); return 1; }
    signal(SIGTERM, forward);
    signal(SIGINT, forward);
    char *argv[] = {UV, "run", "gesture-mac", NULL};
    fprintf(stderr, "=== launch: %s run gesture-mac in %s\n", UV, REPO);
    if (posix_spawn(&child, UV, NULL, NULL, argv, environ) != 0) { perror("spawn uv"); return 1; }
    int status = 0;
    while (waitpid(child, &status, 0) < 0) {}
    return WIFEXITED(status) ? WEXITSTATUS(status) : 1;
}
