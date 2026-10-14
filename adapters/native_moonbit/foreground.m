#import <AppKit/AppKit.h>
#include <unistd.h>
static NSRunningApplication *previous_application;
int conformance_frontmost_pid(void) {
    return NSWorkspace.sharedWorkspace.frontmostApplication.processIdentifier;
}
void conformance_restore_owned(int owned_pid, int previous_pid) {
    if (conformance_frontmost_pid() == owned_pid && previous_pid != owned_pid) {
        NSRunningApplication *previous = [NSRunningApplication runningApplicationWithProcessIdentifier:previous_pid];
        [previous activateWithOptions:0];
    }
}
void conformance_preserve_foreground(void) {
    previous_application = NSWorkspace.sharedWorkspace.frontmostApplication;
}
void conformance_restore_foreground(void) {
    // Respect a user focus change during this short fixture. Never activate,
    // terminate or otherwise alter an app that was not already frontmost.
    if (NSWorkspace.sharedWorkspace.frontmostApplication.processIdentifier == getpid()) {
        [previous_application activateWithOptions:0];
    }
}
