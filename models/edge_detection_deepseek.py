import csv
import math
import os
import numpy as np
import cv2
import matplotlib.pyplot as plt
from tqdm import tqdm

INPUT_DIR = "./data"
OUTPUT_DIR = "./data/output/edge_detection_detector"

CROP_SIZE = 200
BLUR_KERNEL = 7
CANNY_LOW = 50
CANNY_HIGH = 150
OPEN_KERNEL = 3
CLOSE_KERNEL = 5

MIN_ASPECT = 0.6
MAX_ASPECT = 1.6
MIN_AREA_FRAC = 0.005
MAX_AREA_FRAC = 0.5

MIN_ESTABLISHED_SEC = 0.5
MIN_ABSENT_SEC = 0.2
COOLDOWN_SEC = 3.0

FOUND_STREAK_DECAY = 1
FOUND_STREAK_CAP_SEC = 2.0


class BobDetector:
    """Multi-feature detector that combines edge statistics with shape detection."""
    
    def __init__(self, fps, window_size_sec=2.0):
        self.fps = fps
        self.window_size = int(fps * window_size_sec)
        
        # Feature buffers for adaptive thresholding
        self.edge_counts = []
        self.density_history = []
        
        # Adaptive baseline
        self.baseline_edge = None
        self.edge_mad = None
        self.baseline_density = None
        self.density_mad = None
        
        # Detection state
        self.edge_zscore = 0.0
        self.density_zscore = 0.0
        self.confidence = 0.0
        
    def _extract_features(self, edges_frame, roi_size):
        """Extract spatial features from edge frame."""
        features = {}
        edge_count = cv2.countNonZero(edges_frame)
        features['edge_count'] = edge_count
        
        if edge_count > 0:
            edge_points = np.column_stack(np.where(edges_frame > 0))
            
            if len(edge_points) > 1:
                # Spatial spread
                features['edge_std_y'] = np.std(edge_points[:, 0])
                features['edge_std_x'] = np.std(edge_points[:, 1])
                
                # Edge density (concentration)
                if features['edge_std_y'] > 0 and features['edge_std_x'] > 0:
                    features['edge_density'] = edge_count / (features['edge_std_y'] * features['edge_std_x'])
                else:
                    features['edge_density'] = 0
                
                # Horizontal continuity (bob edges tend to be horizontal)
                horizontal_profile = np.sum(edges_frame, axis=1)
                if np.mean(horizontal_profile) > 0:
                    features['horizontal_continuity'] = np.max(horizontal_profile) / np.mean(horizontal_profile)
                else:
                    features['horizontal_continuity'] = 0
            else:
                features['edge_density'] = 0
                features['horizontal_continuity'] = 0
        else:
            features['edge_density'] = 0
            features['horizontal_continuity'] = 0
        
        return features
    
    def update(self, edges_frame):
        """Update detector with new edge frame. Returns confidence score."""
        roi_size = edges_frame.shape[0]
        features = self._extract_features(edges_frame, roi_size)
        
        edge_count = features['edge_count']
        density = features['edge_density']
        
        # Update buffers
        self.edge_counts.append(edge_count)
        self.density_history.append(density)
        
        if len(self.edge_counts) > self.window_size:
            self.edge_counts.pop(0)
            self.density_history.pop(0)
        
        # Need enough history for baseline
        if len(self.edge_counts) < self.window_size:
            return 0.0
        
        # Update adaptive baselines using median and MAD
        recent_edges = np.array(self.edge_counts[-self.window_size:])
        recent_densities = np.array(self.density_history[-self.window_size:])
        
        self.baseline_edge = np.median(recent_edges)
        self.edge_mad = np.median(np.abs(recent_edges - self.baseline_edge)) * 1.4826
        
        self.baseline_density = np.median(recent_densities)
        self.density_mad = np.median(np.abs(recent_densities - self.baseline_density)) * 1.4826
        
        # Calculate z-scores
        if self.edge_mad > 0:
            self.edge_zscore = (edge_count - self.baseline_edge) / self.edge_mad
        else:
            self.edge_zscore = 0
        
        if self.density_mad > 0:
            self.density_zscore = (density - self.baseline_density) / self.density_mad
        else:
            self.density_zscore = 0
        
        # Combine features into confidence score
        confidence = 0.0
        
        # Edge count anomaly (weight: 0.4)
        edge_anomaly = abs(self.edge_zscore)
        if edge_anomaly > 2.0:
            confidence += min((edge_anomaly - 2.0) / 4.0, 1.0) * 0.4
        
        # Density anomaly (weight: 0.3)
        density_anomaly = abs(self.density_zscore)
        if density_anomaly > 1.5:
            confidence += min((density_anomaly - 1.5) / 3.0, 1.0) * 0.3
        
        # Horizontal continuity (weight: 0.3)
        if features['horizontal_continuity'] > 2.0:
            confidence += min((features['horizontal_continuity'] - 2.0) / 4.0, 1.0) * 0.3
        
        self.confidence = min(confidence, 1.0)
        return self.confidence


def find_bob_candidate(edges_closed, roi_size):
    contours, _ = cv2.findContours(edges_closed, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
    roi_area = roi_size * roi_size
    center = roi_size / 2

    best = None
    best_dist = None

    for c in contours:
        area = cv2.contourArea(c)
        if area < MIN_AREA_FRAC * roi_area or area > MAX_AREA_FRAC * roi_area:
            continue

        peri = cv2.arcLength(c, True)
        approx = cv2.approxPolyDP(c, 0.03 * peri, True)
        if not (4 <= len(approx) <= 6):
            continue

        x, y, w, h = cv2.boundingRect(c)
        if h == 0:
            continue
        aspect = w / h
        if not (MIN_ASPECT <= aspect <= MAX_ASPECT):
            continue

        cx, cy = x + w / 2, y + h / 2
        dist = math.hypot(cx - center, cy - center)

        if best_dist is None or dist < best_dist:
            best_dist = dist
            best = (x, y, w, h)

    return best


def process_video(path):
    name = os.path.splitext(os.path.basename(path))[0]
    outdir = os.path.join(OUTPUT_DIR, name)
    os.makedirs(outdir, exist_ok=True)

    cap = cv2.VideoCapture(path)
    fps = cap.get(cv2.CAP_PROP_FPS)
    frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

    # Initialize multi-feature detector
    detector = BobDetector(fps, window_size_sec=2.0)

    min_established_frames = int(fps * MIN_ESTABLISHED_SEC)
    min_absent_frames = int(fps * MIN_ABSENT_SEC)
    cooldown_frames = int(fps * COOLDOWN_SEC)
    found_streak_cap = int(fps * FOUND_STREAK_CAP_SEC)

    open_kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (OPEN_KERNEL, OPEN_KERNEL))
    close_kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (CLOSE_KERNEL, CLOSE_KERNEL))

    found_streak = 0
    absent_streak = 0
    established = False
    state = "idle"
    cooldown_counter = 0
    banner_until_frame = -1

    roi = None
    writer = None

    t_all, found_all = [], []
    triggers = []

    csv_path = os.path.join(outdir, "metrics.csv")
    csv_file = open(csv_path, "w", newline="")
    csv_writer = csv.writer(csv_file)
    csv_writer.writerow(["frame", "time", "found", "found_streak", "absent_streak",
                          "established", "state", "edge_zscore", "density_zscore", "confidence"])

    pbar = tqdm(total=frames, desc=name)
    frame_idx = 0

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        if roi is None:
            fh, fw = frame.shape[:2]
            x = (fw - CROP_SIZE) // 2
            y = (fh - CROP_SIZE) // 2
            roi = (x, y, CROP_SIZE, CROP_SIZE)

        x, y, w, h = roi
        crop = frame[y:y + h, x:x + w]
        gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
        blur = cv2.GaussianBlur(gray, (BLUR_KERNEL, BLUR_KERNEL), 0)

        edges = cv2.Canny(blur, CANNY_LOW, CANNY_HIGH)
        edges = cv2.morphologyEx(edges, cv2.MORPH_OPEN, open_kernel)
        edges_closed = cv2.morphologyEx(edges, cv2.MORPH_CLOSE, close_kernel)

        # Update multi-feature detector
        ml_confidence = detector.update(edges_closed)
        
        # Find shape candidate
        candidate = find_bob_candidate(edges_closed, CROP_SIZE)
        found = candidate is not None
        time_s = frame_idx / fps

        if found:
            found_streak = min(found_streak + 1, found_streak_cap)
            absent_streak = 0
        else:
            found_streak = max(found_streak - FOUND_STREAK_DECAY, 0)
            absent_streak += 1

        if not established and found_streak >= min_established_frames:
            established = True

        # Modified trigger logic: use both shape detection AND ML confidence
        if state == "idle":
            # Trigger if bob is absent AND ML confidence is high
            if established and absent_streak >= min_absent_frames and ml_confidence > 0.3:
                state = "triggered"
                cooldown_counter = 0
                established = False
                found_streak = 0
                banner_until_frame = frame_idx + int(fps)
                triggers.append((time_s, absent_streak, ml_confidence))
                print(f"[ml_edge_detection] BITE at t={time_s:.2f}s "
                      f"(absent={absent_streak}frames, confidence={ml_confidence:.2f})")
        else:
            cooldown_counter += 1
            if cooldown_counter >= cooldown_frames:
                state = "idle"
                found_streak = 0
                absent_streak = 0

        csv_writer.writerow([frame_idx, time_s, found, found_streak, absent_streak,
                              established, state, detector.edge_zscore, 
                              detector.density_zscore, ml_confidence])
        t_all.append(time_s)
        found_all.append(1 if found else 0)

        # Visualization (same as original)
        vis = frame.copy()
        cv2.rectangle(vis, (x, y), (x + w, y + h), (255, 0, 0), 1)
        if candidate:
            cx, cy, cw, ch = candidate
            cv2.rectangle(vis, (x + cx, y + cy), (x + cx + cw, y + cy + ch), (0, 255, 0), 3)
        
        # Display info
        cv2.putText(vis, f"found={found} estab={established} state={state}", (10, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)
        cv2.putText(vis, f"edge_z={detector.edge_zscore:.1f} dense_z={detector.density_zscore:.1f}", 
                    (10, 55), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 0), 1)
        cv2.putText(vis, f"ml_conf={ml_confidence:.2f}", 
                    (10, 75), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 0), 1)
        
        if frame_idx < banner_until_frame:
            cv2.putText(vis, "BITE DETECTED!", (10, 120),
                        cv2.FONT_HERSHEY_SIMPLEX, 1.2, (0, 0, 255), 3)
            cv2.imwrite(os.path.join(outdir, f"trigger_{time_s:.2f}s.png"), vis)

        edges_bgr = cv2.cvtColor(edges_closed, cv2.COLOR_GRAY2BGR)
        edges_bgr = cv2.resize(edges_bgr, (fw, fh))
        combo = cv2.hconcat([vis, edges_bgr])

        if writer is None:
            writer = cv2.VideoWriter(
                os.path.join(outdir, "detection.mp4"),
                cv2.VideoWriter_fourcc(*"mp4v"), fps, (fw * 2, fh)
            )
        writer.write(combo)

        frame_idx += 1
        pbar.update(1)

    pbar.close()
    cap.release()
    csv_file.close()
    if writer:
        writer.release()

    # Generate charts
    fig, axes = plt.subplots(3, 1, figsize=(14, 10))
    
    # Chart 1: Bob presence (same as original)
    ax = axes[0]
    ax.plot(t_all, found_all, label="bob found (1=yes)", linewidth=0.8)
    for ts, absent, conf in triggers:
        ax.axvline(x=ts, color="red", linestyle="--", alpha=0.7)
        ax.annotate(f"BITE\nconf={conf:.2f}", (ts, 1.05), color="red", fontsize=8, ha="center")
    ax.set_ylim(-0.1, 1.2)
    ax.set_xlabel("Time (s)")
    ax.set_ylabel("Bob detected")
    ax.set_title(f"ml_edge_detection - {name}")
    ax.legend()
    ax.grid(True, alpha=0.3)
    
    # Chart 2: ML confidence over time
    ax = axes[1]
    confidences = []
    with open(csv_path, 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            confidences.append(float(row['confidence']))
    
    ax.plot(t_all, confidences, 'g-', alpha=0.7, label='ML confidence')
    ax.axhline(y=0.3, color='orange', linestyle='--', alpha=0.5, label='trigger threshold')
    ax.fill_between(t_all, 0, confidences, alpha=0.2, color='green')
    ax.set_ylabel("Confidence")
    ax.set_xlabel("Time (s)")
    ax.set_title("Multi-feature Confidence Score")
    ax.legend()
    ax.grid(True, alpha=0.3)
    
    # Chart 3: Feature z-scores
    ax = axes[2]
    edge_zscores = []
    density_zscores = []
    with open(csv_path, 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            edge_zscores.append(float(row['edge_zscore']))
            density_zscores.append(float(row['density_zscore']))
    
    ax.plot(t_all, edge_zscores, 'b-', alpha=0.6, label='Edge count z-score')
    ax.plot(t_all, density_zscores, 'r-', alpha=0.6, label='Edge density z-score')
    ax.axhline(y=2, color='b', linestyle=':', alpha=0.3)
    ax.axhline(y=-2, color='b', linestyle=':', alpha=0.3)
    ax.axhline(y=1.5, color='r', linestyle=':', alpha=0.3)
    ax.axhline(y=-1.5, color='r', linestyle=':', alpha=0.3)
    ax.set_ylabel("Z-score")
    ax.set_xlabel("Time (s)")
    ax.set_title("Feature Z-scores")
    ax.legend()
    ax.grid(True, alpha=0.3)
    
    plt.tight_layout()
    plt.savefig(os.path.join(outdir, "chart.png"))
    plt.close()

    # log.txt (same format as original)
    with open(os.path.join(outdir, "log.txt"), "w") as f:
        f.write(f"ml_edge_detection detections for {name}\n")
        f.write(f"params: MIN_ESTABLISHED_SEC={MIN_ESTABLISHED_SEC} "
                f"MIN_ABSENT_SEC={MIN_ABSENT_SEC} COOLDOWN_SEC={COOLDOWN_SEC} "
                f"BLUR_KERNEL={BLUR_KERNEL}\n")
        f.write(f"ml_params: window_size=2.0s, edge_weight=0.4, density_weight=0.3, continuity_weight=0.3\n\n")
        if not triggers:
            f.write("No bites detected.\n")
        for ts, absent, conf in triggers:
            f.write(f"t={ts:.2f}s  absent_frames={absent}  ml_confidence={conf:.2f}\n")

    return triggers


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    videos = sorted([os.path.join(INPUT_DIR, f) for f in os.listdir(INPUT_DIR)
                      if f.lower().endswith(".mp4")])
    for v in videos:
        process_video(v)


if __name__ == "__main__":
    main()