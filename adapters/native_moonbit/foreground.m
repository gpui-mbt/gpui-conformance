#import <AppKit/AppKit.h>
#include <libproc.h>
#include <sys/proc_info.h>
#include <time.h>
#include <unistd.h>
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

// Called only after completed GPU readback, in explicit observer mode.
// Show only this process's sole fixture window, behind other windows, then
// wait at most five seconds for the nonce-bound parent's acknowledgment.
int32_t conformance_fixture_checkpoint(void) {
    if (![NSThread isMainThread]) return 0;
    NSDictionary *env = NSProcessInfo.processInfo.environment;
    if (![env[@"GPUI_FIXTURE_MODE"] isEqual:@"visible"]) return 1;
    NSString *token = env[@"GPUI_RUN_TOKEN"], *directory = env[@"GPUI_OBSERVER_DIR"];
    if (![[NSUUID alloc] initWithUUIDString:token] || !directory.isAbsolutePath ||
        conformance_fixture_integer(3) != 1 || conformance_fixture_integer(7) != 1 ||
        conformance_fixture_integer(1) || conformance_fixture_integer(2)) return 0;
    NSWindow *window = nil;
    for (NSWindow *candidate in NSApp.windows) {
        if ((candidate.styleMask & NSWindowStyleMaskTitled) && candidate.windowNumber > 0) window = candidate;
    }
    if (!window || window.isKeyWindow) return 0;
    NSString *title = [@"GPUI conformance observer " stringByAppendingString:token];
    window.title = title;
    if (!window.isVisible) [window orderBack:nil];
    [NSApp updateWindows];
    // Let AppKit's own opening/title notifications settle without activating
    // the window or altering system animation settings.
    double settle = NSProcessInfo.processInfo.systemUptime + 0.25;
    while (NSProcessInfo.processInfo.systemUptime < settle) {
        [NSRunLoop.currentRunLoop runUntilDate:[NSDate dateWithTimeIntervalSinceNow:0.01]];
    }
    struct proc_bsdinfo info = {0};
    char path[PROC_PIDPATHINFO_MAXSIZE] = {0};
    if (proc_pidinfo(getpid(), PROC_PIDTBSDINFO, 0, &info, sizeof(info)) != sizeof(info) ||
        proc_pidpath(getpid(), path, sizeof(path)) <= 0 || !window.isVisible || window.isKeyWindow ||
        NSApp.isActive || conformance_fixture_integer(1)) return 0;
    struct timespec now;
    if (clock_gettime(CLOCK_REALTIME, &now)) return 0;
    NSRect bounds = window.contentView.bounds;
    BOOL diagnostics = [env[@"GPUI_AX_DIAGNOSTICS"] isEqual:@"1"];
    id unignored = diagnostics ? NSAccessibilityUnignoredAncestor(window) : nil;
    NSArray *localWindows = diagnostics ? NSApp.accessibilityWindows : @[];
    NSMutableArray *localWindowRoles = [NSMutableArray array];
    for (id candidate in localWindows) {
        if (localWindowRoles.count >= 16) break;
        [localWindowRoles addObject:@{@"class":NSStringFromClass([candidate class]),
                                     @"same_owned_window":@(candidate == window),
                                     @"role":[candidate accessibilityRole] ?: NSNull.null,
                                     @"title":[candidate accessibilityTitle] ?: NSNull.null}];
    }
    NSDictionary *ready = @{
        @"protocol": @1, @"run_token": token, @"pid": @(getpid()),
        @"process_start_sec": @(info.pbi_start_tvsec), @"process_start_usec": @(info.pbi_start_tvusec),
        @"executable": @(path), @"executable_sha256": env[@"GPUI_EXECUTABLE_SHA256"] ?: @"",
        @"source_revision": env[@"GPUI_SOURCE_REVISION"] ?: @"",
        @"scene_revision": env[@"GPUI_SCENE_SHA256"] ?: @"", @"frame_sequence": @1,
        @"ready_unix_ns": @((uint64_t)now.tv_sec * 1000000000 + now.tv_nsec),
        @"native_window_id": @(window.windowNumber), @"title": title,
        @"content_size": @[@(bounds.size.width), @(bounds.size.height)],
        @"scale": @(window.backingScaleFactor), @"visible": @YES, @"key": @NO,
        @"application_active": @NO, @"activation_policy": @1,
        @"local_ax_read": @(diagnostics),
        @"local_ax": @{@"application_role":diagnostics ? (NSApp.accessibilityRole ?: NSNull.null) : NSNull.null,
                        @"window_is_accessibility_element":diagnostics ? @([window isAccessibilityElement]) : NSNull.null,
                        @"window_parent_is_application":diagnostics ? @(window.accessibilityParent == NSApp) : NSNull.null,
                        @"unignored_is_owned_window":diagnostics ? @(unignored == window) : NSNull.null,
                        @"unignored_is_application":diagnostics ? @(unignored == NSApp) : NSNull.null,
                        @"unignored_role":diagnostics ? ([unignored accessibilityRole] ?: NSNull.null) : NSNull.null,
                        @"window_role":diagnostics ? (window.accessibilityRole ?: NSNull.null) : NSNull.null,
                        @"window_title":diagnostics ? (window.accessibilityTitle ?: NSNull.null) : NSNull.null,
                        @"window_class":NSStringFromClass(window.class),
                        @"bundle_path":diagnostics ? NSBundle.mainBundle.bundlePath : NSNull.null,
                        @"bundle_identifier":diagnostics ? (NSBundle.mainBundle.bundleIdentifier ?: NSNull.null) : NSNull.null,
                        @"running_bundle_identifier":diagnostics ? (NSRunningApplication.currentApplication.bundleIdentifier ?: NSNull.null) : NSNull.null,
                        @"application_windows":localWindowRoles},
    };
    NSData *data = [NSJSONSerialization dataWithJSONObject:ready options:0 error:nil];
    NSString *readyPath = [directory stringByAppendingPathComponent:@"ready.json"];
    if (!data || ![data writeToFile:readyPath options:NSDataWritingWithoutOverwriting error:nil]) return 0;
    double deadline = NSProcessInfo.processInfo.systemUptime + 5.0;
    NSString *ackPath = [directory stringByAppendingPathComponent:@"ack.json"];
    while (NSProcessInfo.processInfo.systemUptime < deadline) {
        NSData *ackData = [NSData dataWithContentsOfFile:ackPath];
        NSDictionary *ack = ackData ? [NSJSONSerialization JSONObjectWithData:ackData options:0 error:nil] : nil;
        if ([ack isKindOfClass:NSDictionary.class] && [ack[@"run_token"] isEqual:token] &&
            [ack[@"pid"] isEqual:@(getpid())] && [ack[@"native_window_id"] isEqual:@(window.windowNumber)] &&
            [ack[@"frame_sequence"] isEqual:@1] && [ack[@"observer_completed"] isEqual:@YES]) return 1;
        if (!window.isVisible || window.isKeyWindow || NSApp.isActive || conformance_fixture_integer(1)) return 0;
        [NSRunLoop.currentRunLoop runUntilDate:[NSDate dateWithTimeIntervalSinceNow:0.01]];
    }
    return 0;
}
