"""The command toast: a small dark pill under the menu bar icon that names
the command a binding just fired, then fades (issue #27).

It is a borderless non-activating panel that ignores the mouse, so it
never takes keyboard focus or clicks from the app the user is in (a paste
from superwhisper still lands). show() is safe from any thread. A second
firing while the pill is up swaps the text in place, bumps the pill, and
restarts the hold, so rapid firings never stack.
"""
from __future__ import annotations

from typing import Callable

import objc
from AppKit import (
    NSAnimationContext,
    NSAppearance,
    NSAppearanceNameVibrantDark,
    NSBackingStoreBuffered,
    NSBezierPath,
    NSColor,
    NSEdgeInsets,
    NSFont,
    NSFontWeightMedium,
    NSImage,
    NSImageResizingModeStretch,
    NSPanel,
    NSScreen,
    NSStatusWindowLevel,
    NSTextAlignmentCenter,
    NSTextField,
    NSViewHeightSizable,
    NSViewMaxYMargin,
    NSViewMinYMargin,
    NSViewWidthSizable,
    NSVisualEffectBlendingModeBehindWindow,
    NSVisualEffectMaterialHUDWindow,
    NSVisualEffectStateActive,
    NSVisualEffectView,
    NSWindowCollectionBehaviorCanJoinAllSpaces,
    NSWindowCollectionBehaviorFullScreenAuxiliary,
    NSWindowCollectionBehaviorIgnoresCycle,
    NSWindowCollectionBehaviorStationary,
    NSWindowStyleMaskBorderless,
    NSWindowStyleMaskNonactivatingPanel,
)
from Foundation import NSMakeRect, NSObject, NSRunLoop, NSRunLoopCommonModes, NSTimer

HEIGHT = 28.0
PAD_X = 14.0
GAP = 6.0
"""Space between the menu bar and the pill."""
RISE = 4.0
"""The pill slides down this far from under the menu bar as it appears."""
EDGE = 8.0
"""Closest the pill may come to a screen's side."""
FADE_IN_S = 0.18
HOLD_S = 1.1
FADE_OUT_S = 0.3
BUMP_S = 0.08
BUMP = 4.0
"""How much wider (and half as much taller) a repeat firing makes the pill
for a moment."""


def _pill_mask() -> NSImage:
    r = HEIGHT / 2
    size = (HEIGHT + 1, HEIGHT)

    def draw(rect):
        NSColor.blackColor().set()
        NSBezierPath.bezierPathWithRoundedRect_xRadius_yRadius_(rect, r, r).fill()
        return True

    img = NSImage.imageWithSize_flipped_drawingHandler_(size, False, draw)
    img.setCapInsets_(NSEdgeInsets(r, r, r, r))
    img.setResizingMode_(NSImageResizingModeStretch)
    return img


class Toast(NSObject):
    def init(self):
        self = objc.super(Toast, self).init()
        if self is None:
            return None
        self.anchor: Callable[[], object | None] = lambda: None
        """Returns the menu bar icon's window, or None when it is not on
        screen; the pill then sits at the top right of the main screen."""
        self._panel = None
        self._label = None
        self._shown = False
        self._timer = None
        self._gen = 0
        """Bumped on every show, so a fade-out that finishes after a newer
        show does not hide it."""
        return self

    @objc.python_method
    def show(self, label: str) -> None:
        self.performSelectorOnMainThread_withObject_waitUntilDone_("present:", label, False)

    def present_(self, label: str) -> None:
        if self._panel is None:
            self._build()
        self._gen += 1
        self._label.setStringValue_(label)
        frame = self._frame_for(self._label.cell().cellSize().width + 2 * PAD_X)
        if not self._shown:
            self._shown = True
            x, y, w, h = frame
            self._panel.setFrame_display_(NSMakeRect(x, y + RISE, w, h), True)
            self._panel.orderFrontRegardless()

            def enter(ctx):
                ctx.setDuration_(FADE_IN_S)
                self._panel.animator().setAlphaValue_(1.0)
                self._panel.animator().setFrame_display_(NSMakeRect(*frame), True)

            NSAnimationContext.runAnimationGroup_completionHandler_(enter, None)
        else:
            x, y, w, h = frame
            grown = NSMakeRect(x - BUMP / 2, y - BUMP / 4, w + BUMP, h + BUMP / 2)

            def grow(ctx):
                ctx.setDuration_(BUMP_S)
                self._panel.animator().setAlphaValue_(1.0)
                self._panel.animator().setFrame_display_(grown, True)

            def settle():
                def back(ctx):
                    ctx.setDuration_(BUMP_S * 1.5)
                    self._panel.animator().setFrame_display_(NSMakeRect(*frame), True)

                NSAnimationContext.runAnimationGroup_completionHandler_(back, None)

            NSAnimationContext.runAnimationGroup_completionHandler_(grow, settle)
        if self._timer is not None:
            self._timer.invalidate()
        self._timer = NSTimer.timerWithTimeInterval_target_selector_userInfo_repeats_(
            HOLD_S, self, "fade:", None, False
        )
        # Common modes, so the pill still leaves while a menu is open.
        NSRunLoop.mainRunLoop().addTimer_forMode_(self._timer, NSRunLoopCommonModes)

    def fade_(self, _timer) -> None:
        self._timer = None
        self._shown = False
        gen = self._gen

        def out(ctx):
            ctx.setDuration_(FADE_OUT_S)
            self._panel.animator().setAlphaValue_(0.0)

        def done():
            if gen == self._gen:
                self._panel.orderOut_(None)

        NSAnimationContext.runAnimationGroup_completionHandler_(out, done)

    @objc.python_method
    def _frame_for(self, width: float) -> tuple[float, float, float, float]:
        icon = self.anchor()
        if icon is not None and icon.screen() is not None:
            f, screen = icon.frame(), icon.screen().frame()
            cx, top = f.origin.x + f.size.width / 2, f.origin.y
        else:
            screen = NSScreen.mainScreen().visibleFrame()
            cx = screen.origin.x + screen.size.width - EDGE - width / 2
            top = screen.origin.y + screen.size.height
        x = cx - width / 2
        x = max(screen.origin.x + EDGE, min(x, screen.origin.x + screen.size.width - EDGE - width))
        return (x, top - GAP - HEIGHT, width, HEIGHT)

    @objc.python_method
    def _build(self) -> None:
        panel = NSPanel.alloc().initWithContentRect_styleMask_backing_defer_(
            NSMakeRect(0, 0, 100, HEIGHT),
            NSWindowStyleMaskBorderless | NSWindowStyleMaskNonactivatingPanel,
            NSBackingStoreBuffered,
            False,
        )
        panel.setLevel_(NSStatusWindowLevel)
        panel.setIgnoresMouseEvents_(True)
        # An NSPanel hides whenever its app is inactive by default, and a
        # menu bar app is inactive nearly always.
        panel.setHidesOnDeactivate_(False)
        panel.setOpaque_(False)
        panel.setBackgroundColor_(NSColor.clearColor())
        panel.setHasShadow_(True)
        panel.setAlphaValue_(0.0)
        panel.setAppearance_(NSAppearance.appearanceNamed_(NSAppearanceNameVibrantDark))
        panel.setCollectionBehavior_(
            NSWindowCollectionBehaviorCanJoinAllSpaces
            | NSWindowCollectionBehaviorStationary
            | NSWindowCollectionBehaviorFullScreenAuxiliary
            | NSWindowCollectionBehaviorIgnoresCycle
        )
        pill = NSVisualEffectView.alloc().initWithFrame_(NSMakeRect(0, 0, 100, HEIGHT))
        pill.setMaterial_(NSVisualEffectMaterialHUDWindow)
        pill.setBlendingMode_(NSVisualEffectBlendingModeBehindWindow)
        pill.setState_(NSVisualEffectStateActive)
        pill.setMaskImage_(_pill_mask())
        pill.setAutoresizingMask_(NSViewWidthSizable | NSViewHeightSizable)
        label = NSTextField.labelWithString_("")
        label.setFont_(NSFont.systemFontOfSize_weight_(13, NSFontWeightMedium))
        label.setTextColor_(NSColor.labelColor())
        label.setAlignment_(NSTextAlignmentCenter)
        label.sizeToFit()
        h = label.frame().size.height
        label.setFrame_(NSMakeRect(0, (HEIGHT - h) / 2, 100, h))
        label.setAutoresizingMask_(NSViewWidthSizable | NSViewMinYMargin | NSViewMaxYMargin)
        pill.addSubview_(label)
        panel.setContentView_(pill)
        self._panel, self._label = panel, label
