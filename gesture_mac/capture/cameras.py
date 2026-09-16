"""Enumerate cameras by name through AVFoundation, and map a chosen name to
the index OpenCV's AVFoundation backend uses.

The index mapping is an assumption: OpenCV enumerates devices in the same
order AVCaptureDevice lists them. It holds on the machines tried so far and
is the reason the menu shows names, not indexes. If a wrong camera opens,
this is the first place to look.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class CameraInfo:
    index: int
    name: str
    unique_id: str
    builtin: bool


def list_cameras() -> list[CameraInfo]:
    import AVFoundation as AV

    types = [AV.AVCaptureDeviceTypeBuiltInWideAngleCamera]
    for name in ("AVCaptureDeviceTypeExternal", "AVCaptureDeviceTypeExternalUnknown", "AVCaptureDeviceTypeContinuityCamera"):
        if hasattr(AV, name):
            types.append(getattr(AV, name))
    session = AV.AVCaptureDeviceDiscoverySession.discoverySessionWithDeviceTypes_mediaType_position_(
        types, AV.AVMediaTypeVideo, AV.AVCaptureDevicePositionUnspecified
    )
    out = []
    for i, dev in enumerate(session.devices()):
        out.append(
            CameraInfo(
                index=i,
                name=str(dev.localizedName()),
                unique_id=str(dev.uniqueID()),
                builtin=dev.deviceType() == AV.AVCaptureDeviceTypeBuiltInWideAngleCamera,
            )
        )
    return out


def resolve_camera(name: str | None, cameras: list[CameraInfo]) -> CameraInfo | None:
    """The camera matching a saved name, else the built-in one, else the first."""
    if name:
        for c in cameras:
            if c.name == name:
                return c
    for c in cameras:
        if c.builtin:
            return c
    return cameras[0] if cameras else None


def camera_status_authorized() -> bool:
    """The current grant, no prompt. Safe from any thread; the capture loop
    polls it while denied so a grant made in System Settings takes effect
    without a relaunch."""
    import AVFoundation as AV

    return AV.AVCaptureDevice.authorizationStatusForMediaType_(AV.AVMediaTypeVideo) == AV.AVAuthorizationStatusAuthorized


def camera_authorized(timeout_s: float = 60.0) -> bool:
    """Ask macOS for camera access if not yet decided. Must run on the main
    thread (the prompt spins the main run loop). OpenCV's own request cannot
    run from a worker thread, so the runtime sets
    OPENCV_AVFOUNDATION_SKIP_AUTH=1 and relies on this instead."""
    import threading

    import AVFoundation as AV

    status = AV.AVCaptureDevice.authorizationStatusForMediaType_(AV.AVMediaTypeVideo)
    if status == AV.AVAuthorizationStatusAuthorized:
        return True
    if status != AV.AVAuthorizationStatusNotDetermined:
        return False
    done = threading.Event()
    result = {"ok": False}

    def handler(granted: bool) -> None:
        result["ok"] = bool(granted)
        done.set()

    AV.AVCaptureDevice.requestAccessForMediaType_completionHandler_(AV.AVMediaTypeVideo, handler)
    done.wait(timeout_s)
    return result["ok"]
