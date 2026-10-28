/* This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. https://mozilla.org/MPL/2.0/ */
/* A normal restart must not recursively mutate the installed app's xattrs.
 * Actual update operations remain in the unchanged upstream updater. */
#import <AppKit/AppKit.h>
#include <mach-o/dyld.h>
#include <errno.h>
#include <limits.h>
#include <signal.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

static int original_updater(int argc, char **argv, const char *self) {
  (void)argc;
  char executable[PATH_MAX];
  if (snprintf(executable, sizeof(executable), "%s.real", self) >= (int)sizeof(executable)) { return 1; }
  argv[0] = executable;
  execv(executable, argv);
  perror("Forge upstream updater");
  return 1;
}

int main(int argc, char **argv) {
  char self[PATH_MAX];
  uint32_t size = sizeof(self);
  if (_NSGetExecutablePath(self, &size)) { return 1; }
  if (argc < 3 || strcmp(argv[1], "--openAppBundle")) { return original_updater(argc, argv, self); }
  @autoreleasepool {
    int appIndex = 2;
    pid_t waitFor = 0;
    if (argc > 4 && !strcmp(argv[2], "--wait-pid")) {
      char *end = NULL;
      errno = 0;
      long value = strtol(argv[3], &end, 10);
      if (errno || !end || *end || value <= 0 || value > INT_MAX) { return original_updater(argc, argv, self); }
      waitFor = (pid_t)value;
      appIndex = 4;
    }
    NSString *target = [NSString stringWithUTF8String:argv[appIndex]];
    NSString *ownApp = [NSString stringWithUTF8String:self];
    for (int index = 0; index < 6; index++) { ownApp = [ownApp stringByDeletingLastPathComponent]; }
    target = [[target stringByStandardizingPath] stringByResolvingSymlinksInPath];
    ownApp = [[ownApp stringByStandardizingPath] stringByResolvingSymlinksInPath];
    // Do not reinterpret arbitrary updater invocations or other app targets.
    if (!target.isAbsolutePath || ![target hasSuffix:@".app"] || ![target isEqualToString:ownApp]) {
      return original_updater(argc, argv, self);
    }
    if (waitFor) {
      int attempts = 0;
      while (true) {
        NSRunningApplication *previous = [NSRunningApplication runningApplicationWithProcessIdentifier:waitFor];
        // kill(pid, 0) also reports a zombie as alive. Marionette may not reap
        // the old PID until the replacement connects, so use macOS app state.
        if (!previous || previous.terminated) { break; }
        if (++attempts >= 200) { fprintf(stderr, "Forge relaunch: previous process did not exit\n"); return 1; }
        usleep(50000);
      }
    }
    NSMutableArray<NSString *> *arguments = [NSMutableArray array];
    for (int index = appIndex + 1; index < argc; index++) {
      NSString *argument = [NSString stringWithUTF8String:argv[index]];
      if (!argument) { return 1; }
      [arguments addObject:argument];
    }
    NSWorkspaceOpenConfiguration *config = [NSWorkspaceOpenConfiguration configuration];
    config.arguments = arguments;
    config.environment = NSProcessInfo.processInfo.environment;
    config.activates = NO;
    config.createsNewApplicationInstance = YES;
    dispatch_semaphore_t finished = dispatch_semaphore_create(0);
    __block NSInteger errorCode = 0;
    __block pid_t childPID = 0;
    [NSWorkspace.sharedWorkspace openApplicationAtURL:[NSURL fileURLWithPath:target]
                                      configuration:config
                                  completionHandler:^(NSRunningApplication *app, NSError *error) {
      errorCode = error ? error.code : 0;
      childPID = app ? app.processIdentifier : 0;
      dispatch_semaphore_signal(finished);
    }];
    if (dispatch_semaphore_wait(finished, dispatch_time(DISPATCH_TIME_NOW, 30 * NSEC_PER_SEC))) {
      fprintf(stderr, "Forge relaunch: macOS launch request timed out\n"); return 1;
    }
    if (errorCode || childPID <= 0) {
      fprintf(stderr, "Forge relaunch: macOS launch failed (%ld)\n", (long)errorCode); return 1;
    }
    return 0;
  }
}
