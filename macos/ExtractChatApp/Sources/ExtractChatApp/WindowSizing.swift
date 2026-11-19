import AppKit

enum WindowSizing {
    /// Keep the top edge when possible, but move up before resorting to scrolling.
    static func frame(current: NSRect, contentHeight: CGFloat, chromeHeight: CGFloat, visible: NSRect, minimumHeight: CGFloat = 650) -> NSRect {
        let height = min(visible.height, max(minimumHeight, ceil(contentHeight + chromeHeight)))
        let bottom = max(visible.minY, min(current.maxY - height, visible.maxY - height))
        return NSRect(x: current.minX, y: bottom, width: current.width, height: height)
    }
}
