"""Render the app icon: the same SF Symbols hand the menu bar shows, in
white on a blue rounded square, at every size an .icns wants. Output is
scripts/icon.iconset/ plus the .icns iconutil builds from it. Run by
make-app.sh; needs the project's venv (PyObjC)."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from AppKit import (
    NSBezierPath,
    NSBitmapImageRep,
    NSColor,
    NSCompositingOperationSourceOver,
    NSGradient,
    NSGraphicsContext,
    NSImage,
    NSImageSymbolConfiguration,
    NSImageSymbolScaleLarge,
    NSMakeRect,
    NSMakeSize,
)

OUT = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).parent / "icon"
SIZES = [16, 32, 128, 256, 512]


def render(px: int) -> NSImage:
    img = NSImage.alloc().initWithSize_(NSMakeSize(px, px))
    img.lockFocus()
    # macOS icon geometry: the rounded square fills ~80% of the canvas.
    inset = px * 0.1
    side = px - 2 * inset
    rect = NSMakeRect(inset, inset, side, side)
    path = NSBezierPath.bezierPathWithRoundedRect_xRadius_yRadius_(rect, side * 0.225, side * 0.225)
    top = NSColor.colorWithSRGBRed_green_blue_alpha_(0.33, 0.52, 0.96, 1.0)
    bottom = NSColor.colorWithSRGBRed_green_blue_alpha_(0.12, 0.30, 0.78, 1.0)
    NSGradient.alloc().initWithStartingColor_endingColor_(top, bottom).drawInBezierPath_angle_(path, -90)

    symbol = NSImage.imageWithSystemSymbolName_accessibilityDescription_("hand.raised", None)
    cfg = NSImageSymbolConfiguration.configurationWithPointSize_weight_scale_(side * 0.5, 2, NSImageSymbolScaleLarge)
    cfg = cfg.configurationByApplyingConfiguration_(NSImageSymbolConfiguration.configurationWithHierarchicalColor_(NSColor.whiteColor()))
    symbol = symbol.imageWithSymbolConfiguration_(cfg)
    size = symbol.size()
    scale = (side * 0.62) / max(size.width, size.height)
    w, h = size.width * scale, size.height * scale
    dst = NSMakeRect(inset + (side - w) / 2, inset + (side - h) / 2, w, h)
    symbol.drawInRect_fromRect_operation_fraction_(dst, NSMakeRect(0, 0, 0, 0), NSCompositingOperationSourceOver, 1.0)
    img.unlockFocus()
    return img


def save_png(img: NSImage, px: int, path: Path) -> None:
    rep = NSBitmapImageRep.alloc().initWithBitmapDataPlanes_pixelsWide_pixelsHigh_bitsPerSample_samplesPerPixel_hasAlpha_isPlanar_colorSpaceName_bytesPerRow_bitsPerPixel_(
        None, px, px, 8, 4, True, False, "NSCalibratedRGBColorSpace", 0, 0
    )
    rep.setSize_(NSMakeSize(px, px))
    NSGraphicsContext.saveGraphicsState()
    NSGraphicsContext.setCurrentContext_(NSGraphicsContext.graphicsContextWithBitmapImageRep_(rep))
    img.drawInRect_fromRect_operation_fraction_(NSMakeRect(0, 0, px, px), NSMakeRect(0, 0, 0, 0), NSCompositingOperationSourceOver, 1.0)
    NSGraphicsContext.restoreGraphicsState()
    path.write_bytes(bytes(rep.representationUsingType_properties_(4, None)))  # NSBitmapImageFileTypePNG


def main() -> None:
    iconset = OUT.with_suffix(".iconset")
    iconset.mkdir(parents=True, exist_ok=True)
    for base in SIZES:
        for mult in (1, 2):
            px = base * mult
            name = f"icon_{base}x{base}{'@2x' if mult == 2 else ''}.png"
            save_png(render(px), px, iconset / name)
    icns = OUT.with_suffix(".icns")
    subprocess.run(["iconutil", "-c", "icns", str(iconset), "-o", str(icns)], check=True)
    print(icns)


if __name__ == "__main__":
    main()
