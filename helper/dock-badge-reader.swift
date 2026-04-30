import Cocoa
import ApplicationServices
import Darwin

// Private but stable since macOS 10.14 — sets the spawned child to be its
// own responsible process for TCC purposes, instead of inheriting from the
// parent. Without this, when this helper is spawned by Python under launchd,
// TCC checks Python's Accessibility grant (the parent) rather than the
// helper's own grant — and denies. See messages-icon issue #13.
@_silgen_name("responsibility_spawnattrs_setdisclaim")
func responsibility_spawnattrs_setdisclaim(_ attrs: UnsafeMutablePointer<posix_spawnattr_t?>, _ disclaim: Int32) -> Int32

let DISCLAIMED_FLAG = "--disclaimed"

func fail(_ message: String, code: Int32) -> Never {
    FileHandle.standardError.write(Data((message + "\n").utf8))
    exit(code)
}

func readBadgeAndExit() -> Never {
    guard AXIsProcessTrusted() else {
        fail("Accessibility permission not granted to this helper. Add the helper binary in System Settings → Privacy & Security → Accessibility.", code: 3)
    }

    guard let dock = NSWorkspace.shared.runningApplications.first(where: { $0.bundleIdentifier == "com.apple.dock" }) else {
        fail("Dock process not running", code: 2)
    }

    let dockApp = AXUIElementCreateApplication(dock.processIdentifier)

    var childrenRef: CFTypeRef?
    guard AXUIElementCopyAttributeValue(dockApp, kAXChildrenAttribute as CFString, &childrenRef) == .success,
          let children = childrenRef as? [AXUIElement] else {
        fail("Could not read Dock children (AX call failed — Accessibility permission may have been revoked)", code: 4)
    }

    var dockList: AXUIElement?
    for child in children {
        var roleRef: CFTypeRef?
        AXUIElementCopyAttributeValue(child, kAXRoleAttribute as CFString, &roleRef)
        if let role = roleRef as? String, role == (kAXListRole as String) {
            dockList = child
            break
        }
    }

    guard let list = dockList else {
        fail("No AXList child found under Dock", code: 5)
    }

    var tilesRef: CFTypeRef?
    guard AXUIElementCopyAttributeValue(list, kAXChildrenAttribute as CFString, &tilesRef) == .success,
          let tiles = tilesRef as? [AXUIElement] else {
        fail("Could not read Dock list children", code: 6)
    }

    for tile in tiles {
        var titleRef: CFTypeRef?
        AXUIElementCopyAttributeValue(tile, kAXTitleAttribute as CFString, &titleRef)
        guard let title = titleRef as? String, title == "Messages" else { continue }

        var labelRef: CFTypeRef?
        if AXUIElementCopyAttributeValue(tile, "AXStatusLabel" as CFString, &labelRef) == .success,
           let label = labelRef as? String, let count = Int(label) {
            print(count)
        } else {
            print(0)
        }
        exit(0)
    }

    fail("Messages tile not found in Dock", code: 7)
}

// If we're already the disclaimed child, do the work and exit.
if CommandLine.arguments.contains(DISCLAIMED_FLAG) {
    readBadgeAndExit()
}

// Otherwise, re-exec ourselves with disclaim set so the child is its own
// responsible process for TCC. The parent here just waits and propagates exit.
var attr: posix_spawnattr_t? = nil
guard posix_spawnattr_init(&attr) == 0 else {
    fail("posix_spawnattr_init failed", code: 90)
}
defer { posix_spawnattr_destroy(&attr) }

guard responsibility_spawnattrs_setdisclaim(&attr, 1) == 0 else {
    fail("responsibility_spawnattrs_setdisclaim failed", code: 91)
}

let selfPath = CommandLine.arguments[0]
let argv: [String] = [selfPath, DISCLAIMED_FLAG]
var cArgv: [UnsafeMutablePointer<CChar>?] = argv.map { strdup($0) } + [nil]
defer { for p in cArgv { if let p = p { free(p) } } }

var pid: pid_t = 0
let spawnResult = selfPath.withCString { pathPtr -> Int32 in
    return posix_spawn(&pid, pathPtr, nil, &attr, cArgv, environ)
}

guard spawnResult == 0 else {
    fail("posix_spawn failed: \(spawnResult)", code: 92)
}

var status: Int32 = 0
waitpid(pid, &status, 0)
if (status & 0x7f) == 0 {
    exit((status >> 8) & 0xff)
} else {
    fail("disclaimed child terminated by signal \(status & 0x7f)", code: 93)
}
