#import <AppKit/AppKit.h>
#import <ApplicationServices/ApplicationServices.h>
#include <libproc.h>
#include <sys/proc_info.h>
#include <math.h>

static id attribute(AXUIElementRef element, CFStringRef key) {
    CFTypeRef value = NULL;
    if (AXUIElementCopyAttributeValue(element, key, &value) != kAXErrorSuccess) return nil;
    return CFBridgingRelease(value);
}

int main(int argc, const char **argv) {
    @autoreleasepool {
        // This read-only call never prompts or modifies TCC.
        BOOL trusted = AXIsProcessTrusted();
        NSMutableDictionary *result = [@{@"protocol": @1, @"ax_trusted": @(trusted),
                                        @"permission_prompted": @NO} mutableCopy];
        if (argc != 2) {
            result[@"window_binding"] = @"unverified";
            result[@"reason"] = @"owned ready record required";
        } else {
            NSData *data = [NSData dataWithContentsOfFile:@(argv[1])];
            NSDictionary *ready = data ? [NSJSONSerialization JSONObjectWithData:data options:0 error:nil] : nil;
            if (![ready isKindOfClass:NSDictionary.class]) return 2;
            pid_t pid = [ready[@"pid"] intValue];
            uint32_t number = [ready[@"native_window_id"] unsignedIntValue];
            struct proc_bsdinfo info = {0};
            char path[PROC_PIDPATHINFO_MAXSIZE] = {0};
            BOOL identity = pid > 0 && number > 0 &&
                proc_pidinfo(pid, PROC_PIDTBSDINFO, 0, &info, sizeof(info)) == sizeof(info) &&
                proc_pidpath(pid, path, sizeof(path)) > 0 &&
                [ready[@"process_start_sec"] isEqual:@(info.pbi_start_tvsec)] &&
                [ready[@"process_start_usec"] isEqual:@(info.pbi_start_tvusec)] &&
                [ready[@"executable"] isEqual:@(path)];
            if (!identity) {
                result[@"window_binding"] = @"unverified";
                result[@"reason"] = @"process start or executable identity differs";
            } else {
                // Query only the supplied owned window, never enumerate/capture the desktop.
                NSArray *windows = CFBridgingRelease(CGWindowListCopyWindowInfo(kCGWindowListOptionIncludingWindow, number));
                NSDictionary *window = windows.count == 1 ? windows[0] : nil;
                BOOL owned = [window[(__bridge NSString *)kCGWindowOwnerPID] isEqual:@(pid)] &&
                    [window[(__bridge NSString *)kCGWindowNumber] isEqual:@(number)] &&
                    [window[(__bridge NSString *)kCGWindowIsOnscreen] boolValue];
                result[@"window_binding"] = owned ? @"pass" : @"unverified";
                result[@"pid"] = @(pid); result[@"native_window_id"] = @(number);
                result[@"run_token"] = ready[@"run_token"];
                result[@"process_start_sec"] = @(info.pbi_start_tvsec);
                result[@"process_start_usec"] = @(info.pbi_start_tvusec);
                result[@"executable"] = @(path);
                if (window) result[@"window"] = window;
                result[@"ax_status"] = @"unverified";
                result[@"ax_reason"] = trusted ? @"owned AX window not yet matched" : @"AXIsProcessTrusted returned false for this observer";
                if (owned && trusted) {
                    AXUIElementRef app = AXUIElementCreateApplication(pid);
                    AXUIElementSetMessagingTimeout(app, 1.0);
                    id axWindows = attribute(app, kAXWindowsAttribute);
                    NSUInteger matches = 0;
                    if ([axWindows isKindOfClass:NSArray.class] && [axWindows count] <= 16) {
                        for (id object in axWindows) {
                            if (CFGetTypeID((__bridge CFTypeRef)object) != AXUIElementGetTypeID()) continue;
                            AXUIElementRef axWindow = (__bridge AXUIElementRef)object;
                            pid_t owner = 0;
                            AXUIElementGetPid(axWindow, &owner);
                            id title = attribute(axWindow, kAXTitleAttribute), role = attribute(axWindow, kAXRoleAttribute);
                            if (owner != pid || ![title isEqual:ready[@"title"]] || ![role isEqual:(__bridge NSString *)kAXWindowRole]) continue;
                            id position = attribute(axWindow, kAXPositionAttribute), size = attribute(axWindow, kAXSizeAttribute);
                            CGPoint point = CGPointZero; CGSize dimensions = CGSizeZero; CGRect cgBounds = CGRectZero;
                            BOOL valid = position && size &&
                                CFGetTypeID((__bridge CFTypeRef)position) == AXValueGetTypeID() &&
                                CFGetTypeID((__bridge CFTypeRef)size) == AXValueGetTypeID() &&
                                AXValueGetValue((__bridge AXValueRef)position, kAXValueCGPointType, &point) &&
                                AXValueGetValue((__bridge AXValueRef)size, kAXValueCGSizeType, &dimensions) &&
                                CGRectMakeWithDictionaryRepresentation((__bridge CFDictionaryRef)window[(__bridge NSString *)kCGWindowBounds], &cgBounds);
                            if (valid && fabs(point.x-cgBounds.origin.x)<1 && fabs(point.y-cgBounds.origin.y)<1 &&
                                fabs(dimensions.width-cgBounds.size.width)<1 && fabs(dimensions.height-cgBounds.size.height)<1) matches++;
                        }
                    }
                    CFRelease(app);
                    if (matches == 1) {
                        result[@"ax_status"] = @"pass";
                        result[@"ax_reason"] = @"one owned AX window matches nonce title, PID, role and WindowServer bounds";
                    }
                    result[@"ax_matching_windows"] = @(matches);
                }
            }
        }
        NSData *output = [NSJSONSerialization dataWithJSONObject:result options:NSJSONWritingSortedKeys error:nil];
        if (!output) return 2;
        fwrite(output.bytes, 1, output.length, stdout); fputc('\n', stdout);
    }
    return 0;
}
