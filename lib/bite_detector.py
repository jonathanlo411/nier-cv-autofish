import time
from collections import deque
import statistics
import cv2

class BiteDetector:
    """
    Real‑time bite detector using MOG2 background subtraction and
    rolling z‑score thresholding. Matches the original offline logic exactly.
    """
    def __init__(self, crop_size=200, history=300, var_threshold=16,
                 baseline_window_sec=2.0, spike_z_thresh=3.5,
                 min_spike_sec=0.2, cooldown_sec=3.0, border_margin=0):
        self.crop_size = crop_size
        self.history = history
        self.var_threshold = var_threshold
        self.baseline_window_sec = baseline_window_sec
        self.spike_z_thresh = spike_z_thresh
        self.min_spike_sec = min_spike_sec
        self.cooldown_sec = cooldown_sec
        # Pixels within this distance of the analysis crop's edge are
        # excluded from fg_count/z, AFTER MOG2 runs on the full crop.
        # This is deliberately applied to the foreground mask, not the
        # input frame: MOG2 still learns real variance everywhere (no
        # artificial always-black zone that would make it hypersensitive),
        # and only the final tally used for spike detection ignores
        # activity right at the boundary - which is exactly where a
        # drifting bob getting clipped by the crop edge would otherwise
        # register as a false spike.
        self.border_margin = border_margin

        self.subtractor = cv2.createBackgroundSubtractorMOG2(
            history=history, varThreshold=var_threshold, detectShadows=False
        )
        self.baseline = deque()          # stores (timestamp, fg_count)
        self.state = "warmup"            # warmup → idle → triggered → cooldown
        self.spike_start = None          # timestamp when current spike began
        self.last_trigger_time = 0       # timestamp of last confirmed bite
        self.roi = None                  # (x, y, w, h) – set on first frame

        # Exposed metrics for display/logging
        self.last_fg_count = 0
        self.last_z = None
        self.last_state = "warmup"

    def _crop(self, frame):
        if self.roi is None:
            fh, fw = frame.shape[:2]
            x = (fw - self.crop_size) // 2
            y = (fh - self.crop_size) // 2
            self.roi = (x, y, self.crop_size, self.crop_size)
        x, y, w, h = self.roi
        return frame[y:y+h, x:x+w]

    def process_frame(self, frame_bgr, timestamp=None):
        """
        Returns True if a bite is confirmed on this frame.
        Matches original logic:
        - MOG2 subtraction on centre crop
        - Morphological open with 3x3 ellipse kernel
        - Border margin excluded from the foreground mask (post-MOG2)
        - Rolling z-score baseline (BASELINE_WINDOW_SEC)
        - Spike must exceed SPIKE_Z_THRESH for MIN_SPIKE_SEC duration
        - COOLDOWN_SEC after each trigger
        - Baseline cleared after trigger
        """
        if timestamp is None:
            timestamp = time.time()

        crop = self._crop(frame_bgr)

        # Background subtraction (matches original) - runs on the FULL
        # crop, so MOG2's own background model stays realistic everywhere.
        fg_mask = self.subtractor.apply(crop)
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
        fg_mask = cv2.morphologyEx(fg_mask, cv2.MORPH_OPEN, kernel)

        # Exclude a border band from the COUNT only, after MOG2 has
        # already done its normal thing on the full crop.
        if self.border_margin > 0:
            m = self.border_margin
            fg_mask[:m, :] = 0
            fg_mask[-m:, :] = 0
            fg_mask[:, :m] = 0
            fg_mask[:, -m:] = 0

        fg_count = cv2.countNonZero(fg_mask)

        # --- WARMUP: accumulate history (matches original: frame_idx > HISTORY) ---
        if self.state == "warmup":
            self.baseline.append((timestamp, fg_count))
            # Original: past_warmup = frame_idx > HISTORY
            # We need enough frames for both the subtractor AND baseline statistics
            if len(self.baseline) >= self.history:
                self.state = "idle"
            self.last_fg_count = fg_count
            self.last_z = None
            self.last_state = self.state
            return False

        # --- COOLDOWN: wait then return to idle (matches original) ---
        if self.state == "cooldown":
            if timestamp - self.last_trigger_time >= self.cooldown_sec:
                self.state = "idle"
                self.spike_start = None
            self.last_fg_count = fg_count
            self.last_z = None
            self.last_state = self.state
            return False

        # --- IDLE / SPIKE MONITORING ---
        # Maintain rolling baseline window (matches original baseline_window_frames)
        self.baseline.append((timestamp, fg_count))
        cutoff = timestamp - self.baseline_window_sec
        while self.baseline and self.baseline[0][0] < cutoff:
            self.baseline.popleft()

        # Need enough data (original: len(baseline) >= max(5, baseline_window_frames // 3))
        min_samples = max(5, int(self.baseline_window_sec * 30) // 3)  # ~30fps estimate
        if len(self.baseline) < min_samples:
            self.last_fg_count = fg_count
            self.last_z = None
            self.last_state = self.state
            return False

        # Compute z-score (matches original: statistics.mean, statistics.pstdev)
        fg_values = [v for _, v in self.baseline]
        mean = statistics.mean(fg_values)
        std = statistics.pstdev(fg_values) or 1.0
        z = (fg_count - mean) / std

        self.last_fg_count = fg_count
        self.last_z = z
        self.last_state = self.state

        # Spike detection (matches original logic exactly)
        if z > self.spike_z_thresh:
            if self.spike_start is None:
                self.spike_start = timestamp
            elif (timestamp - self.spike_start) >= self.min_spike_sec:
                # BITE CONFIRMED
                self.state = "cooldown"
                self.last_trigger_time = timestamp
                self.spike_start = None
                self.baseline.clear()  # matches original: baseline.clear() after trigger
                self.last_state = self.state
                return True
        else:
            self.spike_start = None

        return False