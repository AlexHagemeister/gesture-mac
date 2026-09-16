"""The window the menu bar opens the HUD page in: an NSWindow holding a
WKWebView. Closing it navigates the view to about:blank first, so the
page's websocket drops and the server stops streaming (a hidden window
keeping a live page would defeat the whole point of the client count).
"""
from __future__ import annotations

import objc
from AppKit import (
    NSApp,
    NSBackingStoreBuffered,
    NSMakeRect,
    NSObject,
    NSWindow,
    NSWindowStyleMaskClosable,
    NSWindowStyleMaskMiniaturizable,
    NSWindowStyleMaskResizable,
    NSWindowStyleMaskTitled,
)
from Foundation import NSURL, NSURLRequest
from WebKit import WKWebView, WKWebViewConfiguration

BLANK = NSURLRequest.requestWithURL_(NSURL.URLWithString_("about:blank"))


class _Delegate(NSObject):
    """NSWindowDelegate: blank the page on close so the socket drops."""

    def initWithView_(self, view):
        self = objc.super(_Delegate, self).init()
        self.view = view
        return self

    def windowWillClose_(self, _note):
        self.view.loadRequest_(BLANK)


class HudWindow:
    def __init__(self, title: str = "gesture-mac HUD") -> None:
        self.title = title
        self._window: NSWindow | None = None
        self._view: WKWebView | None = None
        self._delegate = None

    def show(self, url: str) -> None:
        """Main thread only (menu callbacks are)."""
        if self._window is None:
            self._build()
        assert self._window is not None and self._view is not None
        self._view.loadRequest_(NSURLRequest.requestWithURL_(NSURL.URLWithString_(url)))
        self._window.makeKeyAndOrderFront_(None)
        NSApp.activateIgnoringOtherApps_(True)

    def close(self) -> None:
        if self._window is not None:
            self._window.close()

    def _build(self) -> None:
        style = (
            NSWindowStyleMaskTitled
            | NSWindowStyleMaskClosable
            | NSWindowStyleMaskResizable
            | NSWindowStyleMaskMiniaturizable
        )
        win = NSWindow.alloc().initWithContentRect_styleMask_backing_defer_(
            NSMakeRect(120, 120, 1180, 720), style, NSBackingStoreBuffered, False
        )
        win.setTitle_(self.title)
        win.setReleasedWhenClosed_(False)
        win.setMinSize_((720, 420))
        view = WKWebView.alloc().initWithFrame_configuration_(win.contentView().bounds(), WKWebViewConfiguration.alloc().init())
        view.setAutoresizingMask_(18)  # width + height sizable
        win.contentView().addSubview_(view)
        self._delegate = _Delegate.alloc().initWithView_(view)
        win.setDelegate_(self._delegate)
        self._window, self._view = win, view
