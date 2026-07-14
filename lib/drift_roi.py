"""
Directional ROI drift compensation, with automatic drift detection.

Problem: in stream environments, the fishing bob drifts steadily in one
direction (current pulling it downstream) and can leave a static ROI.
Widening the ROI or retuning MOG2 for this case risks breaking the
already-tuned static-water detector, since more surface area = more
ambient water-ripple noise feeding into the foreground count.

Fix: instead of touching the detector, keep the ROI the same *size* but
let its position drift over time to track the current. The direction and
speed of that drift is measured automatically per-cycle using dense
optical flow on the water surface, rather than hardcoded per spot.

Why gradual (not instant) shifting matters:
MOG2 builds its background model from a rolling window of prior frames
(the `history` param). If you jump the ROI 50px in one frame, the model
suddenly sees a strip of "new" scenery it never learned, which reads as a
foreground spike - the exact false positive we're trying to avoid.
Shifting by ~1px at a time keeps each frame's edge disturbance small
enough that it stays under the tuned spike_z_thresh, the same way MOG2
already tolerates normal ripple noise.
"""

import cv2
import numpy as np


class OpticalFlowDriftEstimator:
    """
    Watches consecutive frames and estimates the water's current
    direction/speed using dense optical flow (Farneback).

    - Dense flow over the whole ROI, not just tracking the bob: we want
      the water's motion (the current), which dominates the frame area.
    - Median of the flow field, not mean: robust to the bob/splashes
      moving differently from the surrounding water.
    - EMA smoothing across frames: single-frame flow is noisy (ripples,
      compression, lighting flicker).
    - Minimum sample count before reporting nonzero drift: safe fallback
      is exactly zero drift, i.e. identical to a static ROI.
    - Flow computed on a downscaled grayscale frame to keep cost low at
      high capture frame rates.
    """

    def __init__(
            self,
            downscale=0.5,
            ema_alpha=0.2,
            min_samples=10,
            max_px_per_sec=120.0):
        self.downscale = downscale
        self.ema_alpha = ema_alpha
        self.min_samples = min_samples
        self.max_px_per_sec = max_px_per_sec

        self._prev_gray = None
        self._prev_time = None
        self._sample_count = 0

        self._drift_x = 0.0
        self._drift_y = 0.0

    def reset(self):
        """Call at the start of each fishing cycle to discard the previous estimate."""
        self._prev_gray = None
        self._prev_time = None
        self._sample_count = 0
        self._drift_x = 0.0
        self._drift_y = 0.0

    def update(self, frame_bgr, timestamp):
        """Feed one frame in. Safe to call less than every frame (see frame_stride)."""
        small = cv2.resize(
            frame_bgr,
            None,
            fx=self.downscale,
            fy=self.downscale)
        gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)

        if self._prev_gray is None:
            self._prev_gray = gray
            self._prev_time = timestamp
            return

        dt = timestamp - self._prev_time
        if dt <= 0:
            return

        flow = cv2.calcOpticalFlowFarneback(
            self._prev_gray, gray, None,
            pyr_scale=0.5, levels=2, winsize=15,
            iterations=2, poly_n=5, poly_sigma=1.1, flags=0,
        )

        med_dx = float(np.median(flow[..., 0]))
        med_dy = float(np.median(flow[..., 1]))

        px_per_sec_x = (med_dx / self.downscale) / dt
        px_per_sec_y = (med_dy / self.downscale) / dt

        if self._sample_count == 0:
            self._drift_x, self._drift_y = px_per_sec_x, px_per_sec_y
        else:
            a = self.ema_alpha
            self._drift_x = a * px_per_sec_x + (1 - a) * self._drift_x
            self._drift_y = a * px_per_sec_y + (1 - a) * self._drift_y

        self._sample_count += 1
        self._prev_gray = gray
        self._prev_time = timestamp

    def get_drift_px_per_sec(self):
        """Returns (dx, dy) px/sec. Returns (0.0, 0.0) until min_samples is reached."""
        if self._sample_count < self.min_samples:
            return 0.0, 0.0

        dx = max(-self.max_px_per_sec, min(self.max_px_per_sec, self._drift_x))
        dy = max(-self.max_px_per_sec, min(self.max_px_per_sec, self._drift_y))
        return dx, dy


class DriftingROI:
    """
    Wraps a static monitor region and gradually shifts it to compensate
    for the currently estimated drift velocity.

    The offset only ever moves ~1px per call (accumulated from fractional
    px/sec via a sub-pixel accumulator), which is what keeps MOG2's
    background model from seeing a shift as a foreground spike.
    """

    def __init__(
        self, base_monitor, drift_px_per_sec=(
            0.0, 0.0), max_shift_px=(
            0, 0), max_step_px=1):
        self.base_monitor = dict(base_monitor)
        self.drift_x, self.drift_y = drift_px_per_sec
        self.max_shift_x, self.max_shift_y = max_shift_px
        # Hard cap on how many pixels the ROI may move in a SINGLE frame,
        # independent of the estimated velocity. This is what actually
        # protects MOG2: a high velocity estimate still only ever exposes
        # max_step_px of new content per frame - it sustains that rate
        # for longer instead of jumping further in one frame. Effective
        # max sustained speed becomes max_step_px * frames_per_sec.
        self.max_step_px = max_step_px

        self._last_update = None
        self._accum_x = 0.0
        self._accum_y = 0.0
        self._offset_x = 0
        self._offset_y = 0

    def set_velocity(self, drift_px_per_sec):
        """Update the drift rate in-flight. Doesn't jump the current offset."""
        self.drift_x, self.drift_y = drift_px_per_sec

    def reset(self):
        """Call at the start of each fishing cycle, right after cast."""
        import time
        now = time.time()
        self._last_update = now
        self._accum_x = 0.0
        self._accum_y = 0.0
        self._offset_x = 0
        self._offset_y = 0

    def get_region(self):
        """Returns an mss-compatible monitor dict for the current frame."""
        import time
        if self._last_update is None:
            self.reset()

        now = time.time()
        dt = now - self._last_update
        self._last_update = now

        self._accum_x += self.drift_x * dt
        self._accum_y += self.drift_y * dt

        # Raw desired step from accumulated sub-pixel drift.
        raw_step_x = int(self._accum_x)
        raw_step_y = int(self._accum_y)

        # Hard-clamp the ACTUAL step applied this frame, regardless of how
        # large the accumulated/desired step is. A sustained fast current
        # keeps producing a large raw_step every frame, but we only ever
        # apply max_step_px of it - the rest is intentionally discarded
        # (not carried forward) rather than accumulated as backlog, which
        # would otherwise let a burst catch up in one disruptive jump
        # later (anti-windup).
        step_x = max(-self.max_step_px, min(self.max_step_px, raw_step_x))
        step_y = max(-self.max_step_px, min(self.max_step_px, raw_step_y))

        if step_x:
            self._offset_x = max(-self.max_shift_x,
                                 min(self.max_shift_x, self._offset_x + step_x))
        if step_y:
            self._offset_y = max(-self.max_shift_y,
                                 min(self.max_shift_y, self._offset_y + step_y))

        # Drain the accumulator by the RAW step (not the clamped one) so
        # slow drift still accumulates fractional progress normally, but
        # cap the leftover so a sustained fast current can't build up an
        # ever-growing backlog that eventually forces a big jump.
        self._accum_x = max(-self.max_step_px,
                            min(self.max_step_px, self._accum_x - raw_step_x))
        self._accum_y = max(-self.max_step_px,
                            min(self.max_step_px, self._accum_y - raw_step_y))

        region = dict(self.base_monitor)
        region["left"] += self._offset_x
        region["top"] += self._offset_y
        return region

    def get_offset(self):
        """Returns the current (offset_x, offset_y) from the base monitor, in px."""
        return self._offset_x, self._offset_y
