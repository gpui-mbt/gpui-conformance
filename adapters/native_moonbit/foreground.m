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
// Read only this fixture process's AppKit objects. No external app/window lookup.
int64_t conformance_fixture_integer(int32_t field) {
    if (![NSThread isMainThread]) return -1;
    NSWindow *first = nil;
    int64_t count = 0;
    for (NSWindow *window in NSApp.windows) {
        if ((window.styleMask & NSWindowStyleMaskTitled) && window.windowNumber > 0) {
            if (!first) first = window;
            count++;
        }
    }
    switch (field) {
        case 0: return getpid();
        case 1: return NSWorkspace.sharedWorkspace.frontmostApplication.processIdentifier == getpid();
        case 2: return NSApp.isActive;
        case 3: return count;
        case 4: return first ? first.windowNumber : 0;
        case 5: return first.isVisible;
        case 6: return first.isKeyWindow;
        case 7: return NSApp.activationPolicy;
        default: return -1;
    }
}
