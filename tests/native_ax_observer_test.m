#import <AppKit/AppKit.h>
#import <ApplicationServices/ApplicationServices.h>
#include <assert.h>

static pid_t owner;
static AXError pidError, attributeError, countError, copyError;
static NSUInteger attributeReads, nameReads, indexedReads;
static CFIndex reportedCount;
static NSArray *indexedValues;

static AXError testGetPid(AXUIElementRef element, pid_t *pid) {
    (void)element;
    *pid = owner;
    return pidError;
}

static AXError testAttribute(AXUIElementRef element, CFStringRef key, CFTypeRef *value) {
    (void)element;
    attributeReads++;
    *value = NULL;
    if (attributeError != kAXErrorSuccess) return attributeError;
    if (CFEqual(key, kAXTitleAttribute)) *value = CFRetain(CFSTR("nonce title"));
    if (CFEqual(key, kAXRoleAttribute)) *value = CFRetain(kAXWindowRole);
    return kAXErrorSuccess;
}

static AXError testNames(AXUIElementRef element, CFArrayRef *names) {
    (void)element;
    nameReads++;
    *names = (__bridge_retained CFArrayRef)@[@"AXTitle", @"AXRole"];
    return kAXErrorSuccess;
}

static AXError testCount(AXUIElementRef element, CFStringRef key, CFIndex *count) {
    (void)element; (void)key;
    *count = reportedCount;
    return countError;
}

static AXError testValues(AXUIElementRef element, CFStringRef key, CFIndex index,
                          CFIndex maximum, CFArrayRef *values) {
    (void)element; (void)key;
    assert(index == 0 && maximum > 0 && maximum <= 16);
    indexedReads++;
    *values = copyError == kAXErrorSuccess ? (__bridge_retained CFArrayRef)indexedValues : NULL;
    return copyError;
}

// Intercept all candidate reads so these tests cannot message any application.
#define AXUIElementGetTypeID CFDictionaryGetTypeID
#define AXUIElementGetPid testGetPid
#define AXUIElementCopyAttributeValue testAttribute
#define AXUIElementCopyAttributeNames testNames
#define AXUIElementGetAttributeValueCount testCount
#define AXUIElementCopyAttributeValues testValues
#define main observer_program_main
#include "../adapters/native_observer.m"
#undef main

int main(void) {
    @autoreleasepool {
        // CF dictionaries avoid creating even local AX references to other PIDs.
        AXUIElementRef app = (AXUIElementRef)CFBridgingRetain(@{@"identity":@"app"});
        AXUIElementRef element = (AXUIElementRef)CFBridgingRetain(@{@"identity":@"window"});
        owner = 123;
        NSMutableDictionary *status = [NSMutableDictionary dictionary];
        NSDictionary *candidate = candidateIdentity((__bridge id)element, app, 123, status, YES);
        assert(candidateMatches(candidate, @"nonce title"));
        assert(attributeReads == 2 && nameReads == 1);
        assert(!candidateMatches(candidate, @"different nonce"));

        owner = 456; attributeReads = nameReads = 0;
        assert(!candidateIdentity((__bridge id)element, app, 123, status, YES));
        assert(attributeReads == 0 && nameReads == 0);

        owner = 123; pidError = kAXErrorCannotComplete;
        assert(!candidateIdentity((__bridge id)element, app, 123, status, YES));
        assert(attributeReads == 0 && nameReads == 0);
        assert([status[@"AXUIElementGetPid"] intValue] == kAXErrorCannotComplete);

        pidError = kAXErrorSuccess;
        assert(!candidateIdentity(@"not an AX element", app, 123, status, YES));
        assert(attributeReads == 0 && nameReads == 0);

        candidate = candidateIdentity((__bridge id)app, app, 123, status, NO);
        assert([candidate[@"same_application_element"] boolValue]);
        assert(!candidateMatches(candidate, @"nonce title"));
        assert(candidate[@"attribute_names_error"] == NSNull.null && nameReads == 0);

        attributeError = kAXErrorCannotComplete;
        candidate = candidateIdentity((__bridge id)element, app, 123, status, NO);
        assert(!candidateMatches(candidate, @"nonce title"));
        assert([status[@"AXTitle"] intValue] == kAXErrorCannotComplete);
        attributeError = kAXErrorSuccess;

        indexedValues = @[(__bridge id)app]; reportedCount = 1;
        NSDictionary *indexed = indexedWindows(app, 123, indexedValues);
        assert(indexedReads == 1);
        assert([indexed[@"candidates"][0][@"same_application_element"] boolValue]);
        assert([indexed[@"candidates"][0][@"same_as_single_value_at_index"] boolValue]);

        indexedReads = attributeReads = nameReads = 0; owner = 456;
        indexed = indexedWindows(app, 123, indexedValues);
        assert(![indexed[@"candidates"][0][@"owned"] boolValue]);
        assert(attributeReads == 0 && nameReads == 0);

        for (NSNumber *count in @[@(-1), @0, @17]) {
            indexedReads = 0; reportedCount = count.longLongValue;
            indexed = indexedWindows(app, 123, indexedValues);
            assert(indexedReads == 0 && ![indexed[@"copy_queried"] boolValue]);
            assert(indexed[@"copy_error"] == NSNull.null);
        }
        reportedCount = 1; countError = kAXErrorAttributeUnsupported;
        indexedReads = 0;
        indexed = indexedWindows(app, 123, indexedValues);
        assert(indexed[@"reported_count"] == NSNull.null && indexedReads == 0);

        countError = kAXErrorSuccess; copyError = kAXErrorCannotComplete;
        indexed = indexedWindows(app, 123, indexedValues);
        assert([indexed[@"copy_queried"] boolValue] && !indexed[@"candidates"]);
        assert([indexed[@"copy_error"] intValue] == kAXErrorCannotComplete);
        CFRelease(element); CFRelease(app);
        puts("PASS: owned AX candidate and indexed-query guards (mock reads; no GUI)");
    }
    return 0;
}
