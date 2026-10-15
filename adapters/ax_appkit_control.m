#import <AppKit/AppKit.h>
#include <libproc.h>
#include <sys/proc_info.h>
#include <time.h>
#include <unistd.h>

static BOOL safe(NSWindow *window, pid_t foreground) {
    return NSApp.activationPolicy == NSApplicationActivationPolicyAccessory &&
        !NSApp.isActive && !window.isKeyWindow && !window.isMainWindow &&
        NSWorkspace.sharedWorkspace.frontmostApplication.processIdentifier == foreground;
}

static void tick(BOOL events) {
    NSDate *until = [NSDate dateWithTimeIntervalSinceNow:0.01];
    if (events) {
        // No keyboard/pointer dispatch: this experiment only services AppKit's queue.
        NSEvent *event = [NSApp nextEventMatchingMask:NSEventMaskApplicationDefined
            untilDate:until inMode:NSDefaultRunLoopMode dequeue:YES];
        if (event) [NSApp sendEvent:event];
        [NSApp updateWindows];
    } else {
        [NSRunLoop.currentRunLoop runUntilDate:until];
    }
}

int main(void) {
    @autoreleasepool {
        NSDictionary *env = NSProcessInfo.processInfo.environment;
        NSString *token = env[@"GPUI_RUN_TOKEN"], *directory = env[@"GPUI_OBSERVER_DIR"];
        NSString *pump = env[@"GPUI_AX_CONTROL_PUMP"];
        if (![[NSUUID alloc] initWithUUIDString:token] || !directory.isAbsolutePath ||
            (!([pump isEqual:@"runloop"] || [pump isEqual:@"appkit"]))) return 2;
        pid_t foreground = NSWorkspace.sharedWorkspace.frontmostApplication.processIdentifier;
        [NSApplication sharedApplication];
        if (NSApp.activationPolicy != NSApplicationActivationPolicyAccessory &&
            ![NSApp setActivationPolicy:NSApplicationActivationPolicyAccessory]) return 3;
        [NSApp finishLaunching];
        NSWindow *window = [[NSWindow alloc] initWithContentRect:NSMakeRect(0, 0, 256, 192)
            styleMask:NSWindowStyleMaskTitled backing:NSBackingStoreBuffered defer:NO];
        window.releasedWhenClosed = NO;
        window.animationBehavior = NSWindowAnimationBehaviorNone;
        window.ignoresMouseEvents = YES;
        window.title = [@"GPUI conformance observer " stringByAppendingString:token];
        NSButton *button = [[NSButton alloc] initWithFrame:NSMakeRect(24, 20, 180, 48)];
        button.title = @"Stock AppKit control";
        [window.contentView addSubview:button];
        if (!safe(window, foreground)) { [window close]; return 4; }
        [window orderBack:nil];
        [NSApp updateWindows];
        double start = NSProcessInfo.processInfo.systemUptime;
        double deadline = start + 5.0;
        BOOL events = [pump isEqual:@"appkit"];
        while (NSProcessInfo.processInfo.systemUptime < start + 0.25) {
            if (!safe(window, foreground)) { [window close]; return 4; }
            tick(events);
        }
        struct proc_bsdinfo info = {0};
        char path[PROC_PIDPATHINFO_MAXSIZE] = {0};
        struct timespec now;
        if (!safe(window, foreground) || !window.isVisible ||
            proc_pidinfo(getpid(), PROC_PIDTBSDINFO, 0, &info, sizeof(info)) != sizeof(info) ||
            proc_pidpath(getpid(), path, sizeof(path)) <= 0 || clock_gettime(CLOCK_REALTIME, &now)) {
            [window close]; return 5;
        }
        NSMutableArray *local = [NSMutableArray array];
        for (id candidate in NSApp.accessibilityWindows) {
            if (local.count >= 16) break;
            [local addObject:@{@"class":NSStringFromClass([candidate class]),
                @"same_owned_window":@(candidate == window),
                @"role":[candidate accessibilityRole] ?: NSNull.null,
                @"title":[candidate accessibilityTitle] ?: NSNull.null}];
        }
        NSDictionary *ready = @{
            @"protocol":@1, @"control_kind":@"stock-appkit-no-gpu", @"pump":pump,
            @"run_token":token, @"pid":@(getpid()), @"native_window_id":@(window.windowNumber),
            @"process_start_sec":@(info.pbi_start_tvsec), @"process_start_usec":@(info.pbi_start_tvusec),
            @"executable":@(path), @"executable_sha256":env[@"GPUI_EXECUTABLE_SHA256"] ?: @"",
            @"source_revision":env[@"GPUI_SOURCE_REVISION"] ?: @"",
            @"scene_revision":env[@"GPUI_SCENE_SHA256"] ?: @"", @"frame_sequence":@1,
            @"ready_unix_ns":@((uint64_t)now.tv_sec * 1000000000 + now.tv_nsec),
            @"content_size":@[@256, @192], @"scale":@(window.backingScaleFactor),
            @"title":window.title, @"visible":@YES, @"key":@NO,
            @"application_active":@NO, @"activation_policy":@1, @"local_ax_read":@YES,
            @"local_ax":@{@"application_windows":local,
                @"window_role":window.accessibilityRole ?: NSNull.null,
                @"window_title":window.accessibilityTitle ?: NSNull.null,
                @"button_role":button.accessibilityRole ?: NSNull.null,
                @"bundle_path":NSBundle.mainBundle.bundlePath,
                @"bundle_identifier":NSBundle.mainBundle.bundleIdentifier ?: NSNull.null,
                @"running_bundle_identifier":NSRunningApplication.currentApplication.bundleIdentifier ?: NSNull.null},
        };
        NSData *data = [NSJSONSerialization dataWithJSONObject:ready options:0 error:nil];
        if (!data || ![data writeToFile:[directory stringByAppendingPathComponent:@"ready.json"]
            options:NSDataWritingWithoutOverwriting error:nil]) { [window close]; return 6; }
        BOOL acknowledged = NO;
        while (NSProcessInfo.processInfo.systemUptime < deadline) {
            if (!safe(window, foreground) || !window.isVisible) break;
            NSData *ackData = [NSData dataWithContentsOfFile:[directory stringByAppendingPathComponent:@"ack.json"]];
            NSDictionary *ack = ackData ? [NSJSONSerialization JSONObjectWithData:ackData options:0 error:nil] : nil;
            if ([ack isKindOfClass:NSDictionary.class] && [ack[@"run_token"] isEqual:token] &&
                [ack[@"pid"] isEqual:@(getpid())] && [ack[@"native_window_id"] isEqual:@(window.windowNumber)] &&
                [ack[@"frame_sequence"] isEqual:@1] && [ack[@"observer_completed"] isEqual:@YES]) {
                acknowledged = YES; break;
            }
            tick(events);
        }
        BOOL finalSafe = safe(window, foreground);
        [window close];
        return acknowledged && finalSafe ? 0 : 7;
    }
}
