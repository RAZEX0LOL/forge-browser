/* This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. https://mozilla.org/MPL/2.0/ */
/* Keep double-click launches away from the person's regular Firefox profile. */
#include <mach-o/dyld.h>
#include <sys/stat.h>
#include <sys/time.h>
#include <fcntl.h>
#include <errno.h>
#include <limits.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

/* Explicit local diagnostics only: no arguments, URLs, paths or environment
 * values are recorded. Ignore unsafe destinations and never fail a launch. */
static void trace_launch(const char *stage, int argc, int explicit_profile, int error) {
  int saved_errno = errno;
  const char *path = getenv("FORGE_LAUNCH_TRACE");
  char temporary[PATH_MAX] = {0};
  size_t length = confstr(_CS_DARWIN_USER_TEMP_DIR, temporary, sizeof(temporary));
  const char *candidate = path;
  if (candidate && !strncmp(candidate, "/private/var/", 13) && !strncmp(temporary, "/var/", 5)) { candidate += 8; }
  size_t path_length = path ? strlen(path) : 0;
  /* Opening a protected folder can wait for a macOS privacy prompt, even with
   * O_NONBLOCK. Diagnostics must never introduce that wait into a restart. */
  int safe = candidate && length > 1 && length <= sizeof(temporary) &&
             !strncmp(candidate, temporary, length - 1) && candidate[length - 1] &&
             !strstr(path, "/../") && !(path_length >= 3 && !strcmp(path + path_length - 3, "/.."));
  if (safe) {
    int fd = open(path, O_WRONLY | O_CREAT | O_APPEND | O_NOFOLLOW | O_CLOEXEC | O_NONBLOCK, 0600);
    if (fd >= 0) {
      struct stat info;
      if (!fstat(fd, &info) && S_ISREG(info.st_mode) && info.st_uid == getuid() &&
          (info.st_mode & 077) == 0) {
        struct timeval now;
        gettimeofday(&now, NULL);
        dprintf(fd, "{\"stage\":\"%s\",\"pid\":%d,\"parentPID\":%d,\"epochMs\":%.3f,"
                    "\"argumentCount\":%d,\"explicitProfile\":%s,\"restart\":%s,\"errno\":%d}\n",
                stage, getpid(), getppid(), now.tv_sec * 1000.0 + now.tv_usec / 1000.0,
                argc, explicit_profile ? "true" : "false",
                getenv("MOZ_APP_RESTART") ? "true" : "false", error);
      }
      close(fd);
    }
  }
  errno = saved_errno;
}

static void fail(const char *message) {
  perror(message);
  exit(1);
}

static void mkdirs(char *path) {
  for (char *p = path + 1; ; p++) {
    if (*p == '/' || *p == '\0') {
      char saved = *p;
      *p = '\0';
      if (mkdir(path, 0700) && errno != EEXIST) { fail("Forge profile directory"); }
      *p = saved;
      if (!saved) { return; }
    }
  }
}

int main(int argc, char **argv) {
  char executable[PATH_MAX], profile[PATH_MAX];
  uint32_t size = sizeof(executable);
  if (_NSGetExecutablePath(executable, &size)) { fail("Forge executable path"); }
  char *slash = strrchr(executable, '/');
  if (!slash || (size_t)(slash - executable) + sizeof("/firefox") > sizeof(executable)) {
    fail("Forge executable directory");
  }
  strcpy(slash + 1, "firefox");
  const char *home = getenv("HOME");
  if (!home || home[0] != '/' || snprintf(profile, sizeof(profile), "%s/Library/Application Support/Forge Development/profile", home) >= (int)sizeof(profile)) {
    fail("Forge home directory");
  }
  /* Gecko removes the command-line profile on restart and passes it through
   * XRE_PROFILE_PATH instead. Never replace that with the launcher's default. */
  const char *restart_profile = getenv("XRE_PROFILE_PATH");
  int explicit_profile = restart_profile && restart_profile[0] == '/';
  for (int i = 1; i < argc; i++) {
    if (!strcmp(argv[i], "--profile") || !strcmp(argv[i], "-profile") ||
        !strcmp(argv[i], "-P") || !strncmp(argv[i], "--profile=", 10)) { explicit_profile = 1; }
  }
  if (!explicit_profile) { mkdirs(profile); }
  char **args = calloc((size_t)argc + 6, sizeof(char *));
  if (!args) { fail("Forge launcher arguments"); }
  int next = 0;
  args[next++] = executable;
  args[next++] = "--no-remote";
  args[next++] = "--purgecaches";
  if (!explicit_profile) { args[next++] = "--profile"; args[next++] = profile; }
  for (int i = 1; i < argc; i++) { args[next++] = argv[i]; }
  trace_launch("exec", next, explicit_profile, 0);
  execv(executable, args);
  trace_launch("exec-failed", next, explicit_profile, errno);
  fail("Forge runtime");
}
