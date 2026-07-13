import time
import ctypes
from ctypes import wintypes
import mss
import numpy as np
import cv2
from pynput.keyboard import Key, Controller as KeyboardController
from pynput.mouse import Button, Controller as MouseController
from bite_detector import BiteDetector

# ============================================================
#  DIRECTINPUT – keybd_event (verified working in test)
# ============================================================

VK_RETURN = 0x0D
SCANCODE_ENTER = 0x1C
KEYEVENTF_KEYUP = 0x0002

# Mouse movement constants
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
    """
    Press and release ENTER using keybd_event.
    EXACT same code that worked in your test.
    """
    # Press
    ctypes.windll.user32.keybd_event(VK_RETURN, SCANCODE_ENTER, 0, 0)
    time.sleep(0.15)
    # Release
    ctypes.windll.user32.keybd_event(VK_RETURN, SCANCODE_ENTER, KEYEVENTF_KEYUP, 0)
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

# ============================================================
#  CONFIGURATION
# ============================================================
MONITOR = {
    "top": 520, "left": 1080, "width": 400, "height": 400
}
LOOK_DOWN_DURATION = 0.5
LOOK_DOWN_SPEED = 250
WAIT_AFTER_CAMERA = 0.5
WAIT_AFTER_CAST = 1.5
REEL_DURATION = 10.0
CROP_SIZE = 200
FPS_TARGET = 120
DISPLAY_WINDOW = True

DETECTOR_PARAMS = {
    "crop_size": CROP_SIZE,
    "history": 300,
    "var_threshold": 16,
    "baseline_window_sec": 2.0,
    "spike_z_thresh": 3.5,
    "min_spike_sec": 0.1,
    "cooldown_sec": 3.0,
}
# ============================================================

def look_down_camera():
    """Step 1: Move the camera downward."""
    print("  [1/5] Moving camera down...")
    steps = 30
    delay = LOOK_DOWN_DURATION / steps
    move_per_step = int(LOOK_DOWN_SPEED * delay)
    
    for i in range(steps):
        send_mouse_move(0, move_per_step)
        time.sleep(delay)
    
    print(f"  [1/5] Camera moved down ({LOOK_DOWN_DURATION}s)")
    time.sleep(WAIT_AFTER_CAMERA)

def cast_line():
    """Step 2: Cast the fishing line by pressing ENTER."""
    print("  [2/5] Casting line (ENTER)...")
    press_enter()
    print("  [2/5] Line cast! Waiting for lure to land...")
    time.sleep(WAIT_AFTER_CAST)

def start_detector():
    """Step 3: Initialize the bite detector."""
    print("  [3/5] Starting detector...")
    detector = BiteDetector(**DETECTOR_PARAMS)
    warmup_time = DETECTOR_PARAMS["history"] / FPS_TARGET
    print(f"  [3/5] Detector warming up (~{warmup_time:.1f}s)...")
    return detector

def wait_for_bite(detector, sct, running_flag):
    """Step 4: Monitor for a bite."""
    print("  [4/5] Waiting for bite...")
    
    bite_detected = False
    last_capture_time = time.time()
    banner_until = 0.0
    frame_interval = 1.0 / FPS_TARGET
    frame_count = 0
    
    while not bite_detected:
        if not running_flag[0]:
            return False
        
        # Capture screen
        img = np.array(sct.grab(MONITOR))
        frame = img[:, :, :3]
        
        now = time.time()
        bite_detected = detector.process_frame(frame, timestamp=now)
        frame_count += 1
        
        # Print status periodically
        if frame_count % 60 == 0:
            state = detector.last_state
            z = detector.last_z
            z_str = f"{z:.1f}" if z is not None else "n/a"
            print(f"    [WAITING] frame={frame_count} fg={detector.last_fg_count} z={z_str} state={state}")
        
        # Visual overlay
        if DISPLAY_WINDOW:
            vis = frame.copy()
            
            if detector.roi is not None:
                x, y, w, h = detector.roi
                cv2.rectangle(vis, (x, y), (x + w, y + h), (255, 0, 0), 2)
            
            fg = detector.last_fg_count
            z = detector.last_z
            state = detector.last_state
            z_text = f"{z:.1f}" if z is not None else "n/a"
            
            # Semi-transparent background for text
            overlay = vis.copy()
            cv2.rectangle(overlay, (5, 5), (400, 130), (0, 0, 0), -1)
            cv2.addWeighted(overlay, 0.6, vis, 0.4, 0, vis)
            cv2.rectangle(vis, (5, 5), (400, 130), (100, 100, 100), 1)
            
            cv2.putText(vis, f"fg={fg} z={z_text} state={state}",
                        (15, 35), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)
            cv2.putText(vis, f"FPS: {FPS_TARGET} | Crop: {CROP_SIZE}px | Frame: {frame_count}",
                        (15, 65), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (200, 200, 200), 1)
            cv2.putText(vis, f"Key: ENTER | Speed: {LOOK_DOWN_SPEED}",
                        (15, 90), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (200, 200, 200), 1)
            
            if bite_detected:
                banner_until = now + 3.0
            if now < banner_until:
                cv2.rectangle(vis, (5, 95), (400, 140), (0, 0, 200), -1)
                cv2.putText(vis, "!!! BITE DETECTED !!!", (20, 125),
                            cv2.FONT_HERSHEY_SIMPLEX, 1.0, (255, 255, 255), 2)
            
            cv2.imshow("Nier Fishing Bot", vis)
            key = cv2.waitKey(1) & 0xFF
            if key == ord('q'):
                return False
            if cv2.getWindowProperty("Nier Fishing Bot", cv2.WND_PROP_VISIBLE) < 1:
                return False
        
        # Maintain target frame rate
        elapsed = time.time() - last_capture_time
        sleep_time = frame_interval - elapsed
        if sleep_time > 0:
            time.sleep(sleep_time)
        last_capture_time = time.time()
    
    print("  [4/5] BITE DETECTED!")
    return True

def reel_in():
    """Step 4b: Reel in the fish."""
    print("  [REEL] Reeling in (ENTER)...")
    press_enter()
    print(f"  [REEL] Waiting {REEL_DURATION}s for animation...")
    time.sleep(REEL_DURATION)
    print("  [REEL] Done!")

def main():
    print("=" * 60)
    print("  Nier: Automata Fishing Bot")
    print("=" * 60)
    print(f"  Resolution: {MONITOR['width']}x{MONITOR['height']}")
    print(f"  Capture: {FPS_TARGET} FPS")
    print(f"  Cast/Reel key: ENTER (keybd_event)")
    print(f"  Look-down speed: {LOOK_DOWN_SPEED}")
    print(f"  Crop size: {CROP_SIZE}px")
    print("=" * 60)
    print("  INSTRUCTIONS:")
    print("  1. Go to a fishing spot")
    print("  2. Enter fishing mode and face the water")
    print("  3. Make sure game window is FOCUSED")
    print("  4. Press F1 to START the bot")
    print("  5. Press F1 again to STOP")
    print("  6. Press 'q' on overlay window to quit")
    print("=" * 60)

    sct = mss.mss()
    running = [False]

    # ---------- Hotkey listener (F1 toggles) ----------
    def on_press(key):
        try:
            if key == Key.f1:
                running[0] = not running[0]
                if running[0]:
                    print("\n" + "=" * 60)
                    print(">>> Bot STARTED")
                    print("=" * 60)
                else:
                    print("\n" + "=" * 60)
                    print(">>> Bot STOPPED")
                    print("=" * 60)
        except AttributeError:
            pass

    from pynput import keyboard as kb
    listener = kb.Listener(on_press=on_press)
    listener.start()

    # ---------- OpenCV overlay window ----------
    if DISPLAY_WINDOW:
        cv2.namedWindow("Nier Fishing Bot", cv2.WINDOW_NORMAL)
        cv2.resizeWindow("Nier Fishing Bot", 1280, 720)
        print("  Overlay window created.")

    try:
        cycle_count = 0
        
        while True:
            if not running[0]:
                time.sleep(0.1)
                if DISPLAY_WINDOW:
                    if cv2.getWindowProperty("Nier Fishing Bot", cv2.WND_PROP_VISIBLE) < 1:
                        break
                continue

            cycle_count += 1
            print(f"\n{'='*60}")
            print(f"  FISHING CYCLE #{cycle_count}")
            print(f"{'='*60}")
            
            # Step 1: Move camera down
            look_down_camera()
            
            # Step 2: Cast the line
            cast_line()
            
            # Step 3: Start the bite detector
            detector = start_detector()
            
            # Step 4: Wait for bite
            bite_found = wait_for_bite(detector, sct, running)
            
            if not bite_found:
                if not running[0]:
                    print("  [QUIT] Bot stopped by user.")
                else:
                    print("  [QUIT] Detection stopped.")
                break
            
            # Step 4b: Reel in
            reel_in()
            
            print(f"  [DONE] Cycle #{cycle_count} complete!")
            print(f"  [NEXT] Preparing for next cast...")

    except KeyboardInterrupt:
        print("\n\nBot interrupted by user.")
    finally:
        listener.stop()
        if DISPLAY_WINDOW:
            cv2.destroyAllWindows()
        print("\nBot terminated.")

if __name__ == "__main__":
    main()