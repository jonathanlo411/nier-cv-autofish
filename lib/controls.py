import ctypes
from ctypes import wintypes
import time

# ============================================================
#  DIRECTINPUT - keybd_event for keyboard, SendInput for mouse
# ============================================================

VK_RETURN = 0x0D
SCANCODE_ENTER = 0x1C
KEYEVENTF_KEYUP = 0x0002

INPUT_MOUSE = 0
MOUSEEVENTF_MOVE = 0x0001


class MOUSEINPUT(ctypes.Structure):
    _fields_ = [
        ("dx", wintypes.LONG),
        ("dy", wintypes.LONG),
        ("mouseData", wintypes.DWORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong)),
    ]


class KEYBDINPUT(ctypes.Structure):
    _fields_ = [
        ("wVk", wintypes.WORD),
        ("wScan", wintypes.WORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong)),
    ]


class MOUSE_INPUT_UNION(ctypes.Union):
    _fields_ = [
        ("mi", MOUSEINPUT),
        ("ki", KEYBDINPUT),
    ]


class MOUSE_INPUT(ctypes.Structure):
    _fields_ = [
        ("type", wintypes.DWORD),
        ("u", MOUSE_INPUT_UNION),
    ]


def press_enter():
    """Press and release ENTER using keybd_event."""
    ctypes.windll.user32.keybd_event(VK_RETURN, SCANCODE_ENTER, 0, 0)
    time.sleep(0.15)
    ctypes.windll.user32.keybd_event(
        VK_RETURN, SCANCODE_ENTER, KEYEVENTF_KEYUP, 0)
    time.sleep(0.05)


def send_mouse_move(dx, dy):
    """Send relative mouse movement using SendInput."""
    inp = MOUSE_INPUT()
    inp.type = INPUT_MOUSE
    inp.u.mi.dx = dx
    inp.u.mi.dy = dy
    inp.u.mi.mouseData = 0
    inp.u.mi.dwFlags = MOUSEEVENTF_MOVE
    inp.u.mi.time = 0
    inp.u.mi.dwExtraInfo = ctypes.pointer(ctypes.c_ulong(0))

    ctypes.windll.user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(inp))


def move_camera_vertical(direction, duration, speed, label=""):
    """
    Move camera up or down smoothly.
    direction: 1 for down, -1 for up
    """
    steps = 30
    delay = duration / steps
    move_per_step = int(speed * delay) * direction

    for i in range(steps):
        send_mouse_move(0, move_per_step)
        time.sleep(delay)

    if label:
        print(f"  {label} ({duration}s)")


def look_down_camera(duration, speed, settle_time):
    """Move the camera downward."""
    print("  [CAMERA] Moving camera down...")
    move_camera_vertical(1, duration, speed, "[CAMERA] Camera moved down")
    time.sleep(settle_time)


def reset_camera_up(duration, speed):
    """Reset camera back up to neutral position."""
    print("  [CAMERA] Resetting camera up...")
    move_camera_vertical(-1, duration, speed, "[CAMERA] Camera reset up")


def cast_line(wait_after):
    """Cast the fishing line by pressing ENTER."""
    print("  [INPUT] Casting line (ENTER)...")
    press_enter()
    print("  [INPUT] Line cast! Waiting for lure to land...")
    time.sleep(wait_after)


def reel_in(wait_before_reset, reset_duration, reset_speed, total_duration):
    """
    Reel in the fish by pressing ENTER, then reset camera DURING the animation.

    Logic:
    - Real catch: Game pans camera up to show fish, then resets to neutral.
      Our reset-up during animation might over-correct slightly, but the game's
      neutral reset at animation end brings it back to correct position.
    - False catch: Camera stayed looking down. Our reset-up brings it back to
      neutral position so next cycle starts correctly.
    """
    print("  [INPUT] Reeling in (ENTER)...")
    press_enter()

    # Wait briefly then reset camera DURING the animation
    print(f"  [INPUT] Waiting {wait_before_reset}s before camera reset...")
    time.sleep(wait_before_reset)

    # Reset camera up while the animation is still playing
    reset_camera_up(reset_duration, reset_speed)

    # Wait for the rest of the animation to finish
    remaining = total_duration - wait_before_reset - reset_duration
    if remaining > 0:
        print(f"  [INPUT] Waiting {remaining:.1f}s for animation to finish...")
        time.sleep(remaining)

    print("  [INPUT] Reel sequence complete!")
