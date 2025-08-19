import os
import time
import tempfile
from typing import Optional


def _find_dolphin_window_bbox() -> Optional[tuple]:
    """Try to find the Dolphin window bounding box (left, top, width, height).

    Attempts via pygetwindow; falls back to None if unavailable.
    """
    try:
        import pygetwindow as gw  # type: ignore
    except Exception:
        return None

    try:
        candidates = []
        for w in gw.getAllWindows():
            title = getattr(w, "title", "") or ""
            if not title:
                continue
            t = title.lower()
            if "dolphin" in t or "animal crossing" in t or "gafe01" in t:
                if getattr(w, "isMinimized", False):
                    continue
                try:
                    left, top, right, bottom = w.left, w.top, w.right, w.bottom
                    width = max(0, right - left)
                    height = max(0, bottom - top)
                    if width > 200 and height > 200:
                        candidates.append((left, top, width, height))
                except Exception:
                    continue
        if candidates:
            # Prefer the largest area
            candidates.sort(key=lambda r: r[2] * r[3], reverse=True)
            return candidates[0]
    except Exception:
        return None
    return None


def capture_dolphin_screenshot(out_dir: Optional[str] = None) -> Optional[str]:
    """Capture a screenshot of the Dolphin game window if possible.

    - Tries to locate the Dolphin window and capture only that region.
    - Falls back to a full-screen screenshot if the window cannot be found.
    - Returns the saved image path on success, or None on failure.
    """
    try:
        import pyautogui  # type: ignore
    except Exception:
        return None

    # Prepare output path
    base_dir = out_dir or os.path.join(tempfile.gettempdir(), "dolphin_listener_shots")
    os.makedirs(base_dir, exist_ok=True)
    ts = time.strftime("%Y%m%d-%H%M%S")
    out_path = os.path.join(base_dir, f"dolphin-shot-{ts}.png")

    region = _find_dolphin_window_bbox()
    try:
        if region is not None:
            img = pyautogui.screenshot(region=region)  # type: ignore[arg-type]
        else:
            img = pyautogui.screenshot()
        img.save(out_path)
        return out_path
    except Exception:
        return None


