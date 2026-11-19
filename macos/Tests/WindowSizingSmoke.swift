import AppKit

@main
struct WindowSizingSmoke {
    static func main() {
        let visible = NSRect(x: 0, y: 0, width: 1600, height: 1200)
        let current = NSRect(x: 150, y: 550, width: 880, height: 600)
        let expanded = WindowSizing.frame(current: current, contentHeight: 900, chromeHeight: 28, visible: visible)
        precondition(expanded.height == 928 && expanded.maxY == current.maxY)
        precondition(expanded.width == current.width && expanded.minX == current.minX)

        let small = NSRect(x: 0, y: 40, width: 1200, height: 700)
        let capped = WindowSizing.frame(current: current, contentHeight: 900, chromeHeight: 28, visible: small)
        precondition(capped.height == small.height && capped.minY == small.minY)

        let low = NSRect(x: 150, y: 20, width: 880, height: 650)
        let shifted = WindowSizing.frame(current: low, contentHeight: 900, chromeHeight: 28, visible: visible)
        precondition(shifted.minY == visible.minY && shifted.height == 928)

        let collapsed = WindowSizing.frame(current: expanded, contentHeight: 620, chromeHeight: 28, visible: visible)
        precondition(collapsed.height == 650 && collapsed.maxY == expanded.maxY)

        let secondScreen = NSRect(x: -1600, y: 100, width: 1600, height: 900)
        let secondWindow = NSRect(x: -1400, y: 200, width: 880, height: 650)
        let second = WindowSizing.frame(current: secondWindow, contentHeight: 1400, chromeHeight: 28, visible: secondScreen)
        precondition(second.minX == secondWindow.minX && second.minY == 100 && second.height == 900)

        let shortScreen = NSRect(x: 0, y: 0, width: 1000, height: 550)
        let short = WindowSizing.frame(current: current, contentHeight: 620, chromeHeight: 28, visible: shortScreen)
        precondition(short.height == 550 && short.minY == 0)
        print("Window growth, screen-height cap, upward repositioning, collapse and multiple-display geometry passed.")
    }
}
