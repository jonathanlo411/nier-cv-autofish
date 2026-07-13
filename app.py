import time
import mss
import numpy as np
import cv2
from pynput.keyboard import Key
from lib.bite_detector import BiteDetector
from lib.controls import look_down_camera, cast_line, reel_in, reset_camera_up
from lib.logging import FishingLogger

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
CATCH_TIMEOUT = 45.0

DETECTOR_PARAMS = {
    "crop_size": CROP_SIZE,
    "history": 300,
    "var_threshold": 16,
    "baseline_window_sec": 2.0,
    "spike_z_thresh": 3.5,
    "min_spike_sec": 0.1,
    "cooldown_sec": 3.0,
}

# Build config dict for logger
CONFIG = {
    "monitor_width": MONITOR["width"],
    "monitor_height": MONITOR["height"],
    "monitor_left": MONITOR["left"],
    "monitor_top": MONITOR["top"],
    "fps_target": FPS_TARGET,
    "crop_size": CROP_SIZE,
    "spike_z_thresh": DETECTOR_PARAMS["spike_z_thresh"],
    "min_spike_sec": DETECTOR_PARAMS["min_spike_sec"],
    "baseline_window_sec": DETECTOR_PARAMS["baseline_window_sec"],
    "cooldown_sec": DETECTOR_PARAMS["cooldown_sec"],
    "history": DETECTOR_PARAMS["history"],
    "var_threshold": DETECTOR_PARAMS["var_threshold"],
    "catch_timeout": CATCH_TIMEOUT,
    "look_down_duration": LOOK_DOWN_DURATION,
    "look_down_speed": LOOK_DOWN_SPEED,
    "reset_up_duration": RESET_UP_DURATION,
    "reset_up_speed": RESET_UP_SPEED,
}

# ============================================================
#  DETECTOR
# ============================================================

def start_detector():
    """Step 3: Initialize the bite detector."""
    print("  [DETECTOR] Starting detector...")
    detector = BiteDetector(**DETECTOR_PARAMS)
    warmup_time = DETECTOR_PARAMS["history"] / FPS_TARGET
    print(f"  [DETECTOR] Warming up (~{warmup_time:.1f}s)...")
    return detector


def wait_for_bite(detector, sct, running_flag, logger):
    """Step 4: Monitor for a bite with timeout."""
    print("  [DETECTOR] Waiting for bite...")
    
    bite_detected = False
    last_capture_time = time.time()
    banner_until = 0.0
    frame_interval = 1.0 / FPS_TARGET
    frame_count = 0
    detection_start = time.time()
    
    while not bite_detected:
        if not running_flag[0]:
            return False, None
        
        # Check for timeout
        elapsed_total = time.time() - detection_start
        if elapsed_total > CATCH_TIMEOUT:
            print(f"  [DETECTOR] TIMEOUT after {CATCH_TIMEOUT}s - no bite detected")
            cycle_data = logger.log_timeout()
            return True, cycle_data
        
        # Capture screen
        img = np.array(sct.grab(MONITOR))
        frame = img[:, :, :3]
        
        now = time.time()
        bite_detected = detector.process_frame(frame, timestamp=now)
        frame_count += 1
        
        # Log frame metrics
        logger.log_frame(detector.last_fg_count, detector.last_z)
        
        # Print status periodically
        if frame_count % 60 == 0:
            state = detector.last_state
            z = detector.last_z
            z_str = f"{z:.1f}" if z is not None else "n/a"
            remaining = CATCH_TIMEOUT - elapsed_total
            print(f"    [WAITING] frame={frame_count} fg={detector.last_fg_count} z={z_str} state={state} timeout={remaining:.0f}s")
        
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
            
            overlay = vis.copy()
            cv2.rectangle(overlay, (5, 5), (400, 150), (0, 0, 0), -1)
            cv2.addWeighted(overlay, 0.6, vis, 0.4, 0, vis)
            cv2.rectangle(vis, (5, 5), (400, 150), (100, 100, 100), 1)
            
            cv2.putText(vis, f"fg={fg} z={z_text} state={state}",
                        (15, 35), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)
            cv2.putText(vis, f"FPS: {FPS_TARGET} | Crop: {CROP_SIZE}px | Frame: {frame_count}",
                        (15, 65), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (200, 200, 200), 1)
            cv2.putText(vis, f"Catches: {logger.total_catches} | Timeout: {CATCH_TIMEOUT - elapsed_total:.0f}s",
                        (15, 90), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (200, 200, 200), 1)
            
            if bite_detected:
                banner_until = now + 3.0
            if now < banner_until:
                cv2.rectangle(vis, (5, 100), (400, 150), (0, 0, 200), -1)
                cv2.putText(vis, "!!! BITE DETECTED !!!", (20, 135),
                            cv2.FONT_HERSHEY_SIMPLEX, 1.0, (255, 255, 255), 2)
            elif elapsed_total > CATCH_TIMEOUT - 5:
                cv2.rectangle(vis, (5, 100), (400, 150), (0, 100, 200), -1)
                cv2.putText(vis, f"TIMEOUT SOON: {CATCH_TIMEOUT - elapsed_total:.0f}s", (20, 135),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)
            
            cv2.imshow("Nier Fishing Bot", vis)
            key = cv2.waitKey(1) & 0xFF
            if key == ord('q'):
                return False, None
            if cv2.getWindowProperty("Nier Fishing Bot", cv2.WND_PROP_VISIBLE) < 1:
                return False, None
        
        # Maintain target frame rate
        elapsed = time.time() - last_capture_time
        sleep_time = frame_interval - elapsed
        if sleep_time > 0:
            time.sleep(sleep_time)
        last_capture_time = time.time()
    
    trigger_z = detector.last_z if detector.last_z is not None else 0
    cycle_data = logger.log_bite(trigger_z)
    
    print(f"  [DETECTOR] BITE DETECTED! (time={cycle_data['catch_time']:.1f}s, z={trigger_z:.1f})")
    return True, cycle_data


# ============================================================
#  MAIN
# ============================================================

def main():
    print("=" * 60)
    print("  Nier: Automata Fishing Bot")
    print("=" * 60)
    print(f"  Monitor: {MONITOR['width']}x{MONITOR['height']} at ({MONITOR['left']},{MONITOR['top']})")
    print(f"  FPS Target: {FPS_TARGET}")
    print(f"  Crop: {CROP_SIZE}px | Timeout: {CATCH_TIMEOUT}s")
    print(f"  Log: logs/autofishing-<datetime>.log")
    print("=" * 60)

    sct = mss.mss()
    running = [False]
    logger = FishingLogger(CONFIG)
    
    print(f"  Logging to: {logger.filepath}")

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

    if DISPLAY_WINDOW:
        cv2.namedWindow("Nier Fishing Bot", cv2.WINDOW_NORMAL)
        cv2.resizeWindow("Nier Fishing Bot", 400, 400)

    try:
        cycle_count = 0
        
        while True:
            if not running[0]:
                time.sleep(0.1)
                if DISPLAY_WINDOW and cv2.getWindowProperty("Nier Fishing Bot", cv2.WND_PROP_VISIBLE) < 1:
                    break
                continue

            cycle_count += 1
            print(f"\n{'='*60}")
            print(f"  FISHING CYCLE #{cycle_count}")
            print(f"{'='*60}")
            
            look_down_camera(LOOK_DOWN_DURATION, LOOK_DOWN_SPEED, WAIT_AFTER_CAMERA)
            cast_line(WAIT_AFTER_CAST)
            
            detector = start_detector()
            logger.start_cycle()
            
            bite_found, cycle_data = wait_for_bite(detector, sct, running, logger)
            
            if not bite_found:
                print("  [QUIT] Detection stopped.")
                break
            
            if cycle_data is not None and cycle_data['status'] == 'complete':
                reel_in(RESET_DELAY_AFTER_REEL, RESET_UP_DURATION, RESET_UP_SPEED, REEL_DURATION)
                print(f"  [DONE] Cycle #{cycle_count} complete! (catch in {cycle_data['catch_time']:.1f}s)")
            else:
                reel_in(0, RESET_UP_DURATION, RESET_UP_SPEED, 1.0)
                print(f"  [DONE] Cycle #{cycle_count} timed out after {CATCH_TIMEOUT}s")

    except KeyboardInterrupt:
        print("\n\nBot interrupted by user.")
    finally:
        logger.print_summary()
        listener.stop()
        if DISPLAY_WINDOW:
            cv2.destroyAllWindows()
        print("\nBot terminated.")


if __name__ == "__main__":
    main()