#import <AppKit/AppKit.h>
#import <ApplicationServices/ApplicationServices.h>
#include <libproc.h>
#include <sys/proc_info.h>
#include <math.h>

static id attribute(AXUIElementRef element, CFStringRef key, NSMutableDictionary *statuses) {
    CFTypeRef value = NULL;
    AXError error = AXUIElementCopyAttributeValue(element, key, &value);
    statuses[(__bridge NSString *)key] = @(error);
    if (error != kAXErrorSuccess) return nil;
    return CFBridgingRelease(value);
}

static NSDictionary *candidateIdentity(id object, AXUIElementRef app, pid_t pid,
                                       NSMutableDictionary *status, BOOL namesRequested) {
    if (CFGetTypeID((__bridge CFTypeRef)object) != AXUIElementGetTypeID()) return nil;
    AXUIElementRef element = (__bridge AXUIElementRef)object;
    pid_t owner = 0;
    AXError error = AXUIElementGetPid(element, &owner);
    status[@"AXUIElementGetPid"] = @(error);
    // A target's AXWindows array is not authority to read a foreign process.
    if (error != kAXErrorSuccess || owner != pid) return nil;
    id title = attribute(element, kAXTitleAttribute, status);
    id role = attribute(element, kAXRoleAttribute, status);
    NSMutableDictionary *candidate = [@{@"pid":@(owner),
        @"title":[title isKindOfClass:NSString.class] ? title : NSNull.null,
        @"role":[role isKindOfClass:NSString.class] ? role : NSNull.null,
        @"same_application_element":@(CFEqual(element, app)),
        @"attribute_names_queried":@(namesRequested), @"attribute_names_error":NSNull.null} mutableCopy];
    if (namesRequested) {
        CFArrayRef names = NULL;
        candidate[@"attribute_names_error"] = @(AXUIElementCopyAttributeNames(element, &names));
        if (names) candidate[@"attribute_names"] = CFBridgingRelease(names);
    }
    return candidate;
}

static NSDictionary *sessionSnapshot(void) {
    NSDictionary *session = CFBridgingRelease(CGSessionCopyCurrentDictionary());
    NSMutableDictionary *result = [@{@"available":@(session != nil)} mutableCopy];
    // Retain only advisory booleans, never the session's usernames or IDs.
    NSDictionary *keys = @{@"on_console":(__bridge NSString *)kCGSessionOnConsoleKey,
        @"login_done":(__bridge NSString *)kCGSessionLoginDoneKey,
        @"screen_locked_marker":@"CGSSessionScreenIsLocked"};
    for (NSString *key in keys) {
        id value = session[keys[key]];
        result[key] = value && CFGetTypeID((__bridge CFTypeRef)value) == CFBooleanGetTypeID() ? value : NSNull.null;
    }
    return result;
}

static BOOL candidateMatches(NSDictionary *candidate, NSString *title) {
    return candidate && ![candidate[@"same_application_element"] boolValue] &&
        [candidate[@"title"] isEqual:title] &&
        [candidate[@"role"] isEqual:(__bridge NSString *)kAXWindowRole];
}

static NSDictionary *indexedWindows(AXUIElementRef app, pid_t pid, id singleValue) {
    CFIndex count = 0;
    AXError countError = AXUIElementGetAttributeValueCount(app, kAXWindowsAttribute, &count);
    NSMutableDictionary *result = [@{@"count_error":@(countError),
        @"reported_count":countError == kAXErrorSuccess ? @(count) : NSNull.null,
        @"copy_queried":@NO, @"copy_error":NSNull.null} mutableCopy];
    // This second public API is diagnostic only; it cannot qualify a match.
    if (countError != kAXErrorSuccess || count < 0 || count > 16) return result;
    if (count == 0) { result[@"candidates"] = @[]; return result; }
    CFArrayRef values = NULL;
    result[@"copy_queried"] = @YES;
    AXError error = AXUIElementCopyAttributeValues(app, kAXWindowsAttribute, 0, count, &values);
    result[@"copy_error"] = @(error);
    NSArray *objects = CFBridgingRelease(values);
    if (error != kAXErrorSuccess || ![objects isKindOfClass:NSArray.class] || objects.count > 16) return result;
    result[@"returned_count"] = @(objects.count);
    NSMutableArray *candidates = [NSMutableArray array];
    for (NSUInteger index = 0; index < objects.count; index++) {
        NSMutableDictionary *status = [NSMutableDictionary dictionary];
        NSDictionary *identity = candidateIdentity(objects[index], app, pid, status, NO);
        NSMutableDictionary *candidate = [@{@"index":@(index), @"attribute_status":status,
            @"owned":@(identity != nil)} mutableCopy];
        if (identity) {
            [candidate addEntriesFromDictionary:identity];
            candidate[@"same_as_single_value_at_index"] =
                [singleValue isKindOfClass:NSArray.class] && index < [singleValue count] ?
                @(CFEqual((__bridge CFTypeRef)objects[index], (__bridge CFTypeRef)singleValue[index])) : NSNull.null;
        }
        [candidates addObject:candidate];
    }
    result[@"candidates"] = candidates;
    return result;
}

int main(int argc, const char **argv) {
    @autoreleasepool {
        // This read-only call never prompts or modifies TCC.
        BOOL trusted = AXIsProcessTrusted();
        BOOL diagnostics = [NSProcessInfo.processInfo.environment[@"GPUI_AX_DIAGNOSTICS"] isEqual:@"1"];
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
                if (owned && diagnostics) result[@"ax_session_before"] = sessionSnapshot();
                if (owned && trusted) {
                    AXUIElementRef app = AXUIElementCreateApplication(pid);
                    AXUIElementSetMessagingTimeout(app, 1.0);
                    NSMutableDictionary *appStatus = [NSMutableDictionary dictionary];
                    id axWindows = attribute(app, kAXWindowsAttribute, appStatus);
                    result[@"ax_application_attribute_status"] = appStatus;
                    if (diagnostics) {
                        CFArrayRef appNames = NULL;
                        result[@"ax_application_names_error"] = @(AXUIElementCopyAttributeNames(app, &appNames));
                        if (appNames) result[@"ax_application_attribute_names"] = CFBridgingRelease(appNames);
                    }
                    NSMutableArray *matched = [NSMutableArray array], *windowStatuses = [NSMutableArray array], *candidates = [NSMutableArray array];
                    NSUInteger matches = 0;
                    if ([axWindows isKindOfClass:NSArray.class] && [axWindows count] <= 16) {
                        for (id object in axWindows) {
                            AXUIElementRef axWindow = (__bridge AXUIElementRef)object;
                            NSMutableDictionary *status = [NSMutableDictionary dictionary];
                            NSDictionary *candidate = candidateIdentity(object, app, pid, status, diagnostics);
                            [windowStatuses addObject:status];
                            if (!candidate) continue;
                            [candidates addObject:candidate];
                            id title = candidate[@"title"], role = candidate[@"role"];
                            if (!candidateMatches(candidate, ready[@"title"])) continue;
                            id position = attribute(axWindow, kAXPositionAttribute, status), size = attribute(axWindow, kAXSizeAttribute, status);
                            CGPoint point = CGPointZero; CGSize dimensions = CGSizeZero; CGRect cgBounds = CGRectZero;
                            BOOL valid = position && size &&
                                CFGetTypeID((__bridge CFTypeRef)position) == AXValueGetTypeID() &&
                                CFGetTypeID((__bridge CFTypeRef)size) == AXValueGetTypeID() &&
                                AXValueGetValue((__bridge AXValueRef)position, kAXValueCGPointType, &point) &&
                                AXValueGetValue((__bridge AXValueRef)size, kAXValueCGSizeType, &dimensions) &&
                                CGRectMakeWithDictionaryRepresentation((__bridge CFDictionaryRef)window[(__bridge NSString *)kCGWindowBounds], &cgBounds);
                            if (valid && isfinite(point.x) && isfinite(point.y) && isfinite(dimensions.width) && isfinite(dimensions.height)) {
                                [matched addObject:@{@"pid":@(pid),@"title":title,@"role":role,
                                                     @"same_application_element":@NO,
                                                     @"position":@[@(point.x),@(point.y)],@"size":@[@(dimensions.width),@(dimensions.height)]}];
                                if (fabs(point.x-cgBounds.origin.x)<1 && fabs(point.y-cgBounds.origin.y)<1 &&
                                    fabs(dimensions.width-cgBounds.size.width)<1 && fabs(dimensions.height-cgBounds.size.height)<1) matches++;
                            }
                        }
                    }
                    if (diagnostics) {
                        result[@"ax_indexed_windows"] = indexedWindows(app, pid, axWindows);
                        result[@"ax_session_after"] = sessionSnapshot();
                    }
                    CFRelease(app);
                    if (matches == 1) {
                        result[@"ax_status"] = @"pass";
                        result[@"ax_reason"] = @"one owned AX window matches nonce title, PID, role and WindowServer bounds";
                    }
                    result[@"ax_matching_windows"] = @(matches);
                    result[@"ax_windows"] = matched;
                    result[@"ax_window_attribute_status"] = windowStatuses;
                    result[@"ax_owned_candidates"] = candidates;
                }
            }
        }
        NSData *output = [NSJSONSerialization dataWithJSONObject:result options:NSJSONWritingSortedKeys error:nil];
        if (!output) return 2;
        fwrite(output.bytes, 1, output.length, stdout); fputc('\n', stdout);
    }
    return 0;
}
