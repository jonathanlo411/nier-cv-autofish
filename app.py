import time
import mss
import numpy as np
import cv2
from pynput.keyboard import Key, Controller as KeyboardController
from bite_detector import BiteDetector
from controls import look_down_camera, cast_line, reel_in

# ============================================================
#  CONFIGURATION
# ============================================================
MONITOR = {
    "top": 520, "left": 1080, "width": 400, "height": 400
}
LOOK_DOWN_DURATION = 0.5
LOOK_DOWN_SPEED = 250
WAIT_AFTER_CAMERA = 0.3
WAIT_AFTER_CAST = 1.5
RESET_UP_DURATION = 0.5
RESET_UP_SPEED = 250
RESET_DELAY_AFTER_REEL = 0.5
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

def start_detector():
    """Step 3: Initialize the bite detector."""
    print("  [DETECTOR] Starting detector...")
    detector = BiteDetector(**DETECTOR_PARAMS)
    warmup_time = DETECTOR_PARAMS["history"] / FPS_TARGET
    print(f"  [DETECTOR] Warming up (~{warmup_time:.1f}s)...")
    return detector


def wait_for_bite(detector, sct, running_flag):
    """Step 4: Monitor for a bite."""
    print("  [DETECTOR] Waiting for bite...")
    
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
    
    print("  [DETECTOR] BITE DETECTED!")
    return True


def main():
    print("=" * 60)
    print("  Nier: Automata Fishing Bot")
    print("=" * 60)
    print(f"  Monitor capture: {MONITOR['width']}x{MONITOR['height']} at ({MONITOR['left']},{MONITOR['top']})")
    print(f"  Capture target: {FPS_TARGET} FPS")
    print(f"  Cast/Reel key: ENTER (keybd_event)")
    print(f"  Look-down: speed={LOOK_DOWN_SPEED}, duration={LOOK_DOWN_DURATION}s")
    print(f"  Reset-up: speed={RESET_UP_SPEED}, duration={RESET_UP_DURATION}s")
    print(f"  Reset delay after reel: {RESET_DELAY_AFTER_REEL}s")
    print(f"  Reel duration: {REEL_DURATION}s")
    print(f"  Crop size: {CROP_SIZE}px")
    print("=" * 60)
    print("  CYCLE FLOW:")
    print("  Look Down -> Cast -> Detect Bite -> Reel In ->")
    print("  Wait 0.5s -> Reset Up (during animation) ->")
    print("  Animation ends -> Game resets to neutral -> Repeat")
    print("=" * 60)

    sct = mss.mss()
    running = [False]

    # Hotkey listener (F1 toggles)
    def on_press(key):
        try:
            if key == Key.f1:
                running[0] = not running[0]
                state_str = "STARTED" if running[0] else "STOPPED"
                print(f"\n>>> Bot {state_str}")
        except AttributeError:
            pass

    from pynput import keyboard as kb
    listener = kb.Listener(on_press=on_press)
    listener.start()

    # Overlay window
    if DISPLAY_WINDOW:
        cv2.namedWindow("Nier Fishing Bot", cv2.WINDOW_NORMAL)
        cv2.resizeWindow("Nier Fishing Bot", 400, 400)
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
            
            # Step 1: Look down
            look_down_camera(LOOK_DOWN_DURATION, LOOK_DOWN_SPEED, WAIT_AFTER_CAMERA)
            
            # Step 2: Cast
            cast_line(WAIT_AFTER_CAST)
            
            # Step 3: Start detector
            detector = start_detector()
            
            # Step 4: Wait for bite
            bite_found = wait_for_bite(detector, sct, running)
            
            if not bite_found:
                print("  [QUIT] Detection stopped.")
                break
            
            # Step 5: Reel in and reset camera during animation
            reel_in(RESET_DELAY_AFTER_REEL, RESET_UP_DURATION, RESET_UP_SPEED, REEL_DURATION)
            
            print(f"  [DONE] Cycle #{cycle_count} complete!")

    except KeyboardInterrupt:
        print("\n\nBot interrupted by user.")
    finally:
        listener.stop()
        if DISPLAY_WINDOW:
            cv2.destroyAllWindows()
        print("\nBot terminated.")


if __name__ == "__main__":
    main()