import csv
import math
import os

import cv2
import matplotlib.pyplot as plt
from tqdm import tqdm

INPUT_DIR = "./data"
OUTPUT_DIR = "./data/output/edge_detection_detector"

CROP_SIZE = 200
BLUR_KERNEL = 7             # raised from 5 - suppresses noise when bob is
# close/large and edges get cluttered
CANNY_LOW = 50
CANNY_HIGH = 150
OPEN_KERNEL = 3              # NEW - strips small noise specks before closing
CLOSE_KERNEL = 5             # bridges gaps where ripples break the outline

MIN_ASPECT = 0.6
MAX_ASPECT = 1.6
MIN_AREA_FRAC = 0.005
MAX_AREA_FRAC = 0.5

MIN_ESTABLISHED_SEC = 0.5
MIN_ABSENT_SEC = 0.2
COOLDOWN_SEC = 3.0

# Leaky-bucket tuning for the "established" tracker - decays gradually
# instead of resetting to zero on a single missed/noisy frame
FOUND_STREAK_DECAY = 1        # how much found_streak drops per miss
FOUND_STREAK_CAP_SEC = 2.0    # cap so it doesn't take forever to decay


def find_bob_candidate(edges_closed, roi_size):
    contours, _ = cv2.findContours(
        edges_closed, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
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

    min_established_frames = int(fps * MIN_ESTABLISHED_SEC)
    min_absent_frames = int(fps * MIN_ABSENT_SEC)
    cooldown_frames = int(fps * COOLDOWN_SEC)
    found_streak_cap = int(fps * FOUND_STREAK_CAP_SEC)

    open_kernel = cv2.getStructuringElement(
        cv2.MORPH_ELLIPSE, (OPEN_KERNEL, OPEN_KERNEL))
    close_kernel = cv2.getStructuringElement(
        cv2.MORPH_ELLIPSE, (CLOSE_KERNEL, CLOSE_KERNEL))

    found_streak = 0     # leaky - grows on found, decays (not resets) on miss
    absent_streak = 0    # hard reset - must be a clean run of misses
    established = False
    state = "idle"
    cooldown_counter = 0
    banner_until_frame = -1

    roi = None
    writer = None

    t_all, found_all = [], []
    triggers = []  # (time_s, absent_streak)

    csv_path = os.path.join(outdir, "metrics.csv")
    csv_file = open(csv_path, "w", newline="")
    csv_writer = csv.writer(csv_file)
    csv_writer.writerow(["frame",
                         "time",
                         "found",
                         "found_streak",
                         "absent_streak",
                         "established",
                         "state"])

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
        # Opening first strips small noise specks, THEN closing bridges the
        # real gaps in the bob's outline - doing both jobs in one pass (just
        # closing) was letting noise survive alongside the real shape
        edges = cv2.morphologyEx(edges, cv2.MORPH_OPEN, open_kernel)
        edges_closed = cv2.morphologyEx(edges, cv2.MORPH_CLOSE, close_kernel)

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

        if state == "idle":
            if established and absent_streak >= min_absent_frames:
                state = "triggered"
                cooldown_counter = 0
                established = False
                found_streak = 0
                banner_until_frame = frame_idx + int(fps)
                triggers.append((time_s, absent_streak))
                print(
                    f"[edge_detection] BITE at t={time_s:.2f}s (absent {absent_streak} frames)")
        else:
            cooldown_counter += 1
            if cooldown_counter >= cooldown_frames:
                state = "idle"
                found_streak = 0
                absent_streak = 0

        csv_writer.writerow([frame_idx, time_s, found, found_streak, absent_streak,
                             established, state])
        t_all.append(time_s)
        found_all.append(1 if found else 0)

        vis = frame.copy()
        cv2.rectangle(vis, (x, y), (x + w, y + h), (255, 0, 0), 1)
        if candidate:
            cx, cy, cw, ch = candidate
            # Bright, thick highlight so it's easy to spot while scrubbing
            cv2.rectangle(vis, (x + cx, y + cy),
                          (x + cx + cw, y + cy + ch), (0, 255, 0), 3)
        cv2.putText(
            vis,
            f"found={found} estab={established} state={state}",
            (10,
             30),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.6,
            (0,
             0,
             255),
            2)
        if frame_idx < banner_until_frame:
            cv2.putText(vis, "BITE DETECTED!", (10, 80),
                        cv2.FONT_HERSHEY_SIMPLEX, 1.2, (0, 0, 255), 3)
            cv2.imwrite(
                os.path.join(
                    outdir,
                    f"trigger_{time_s:.2f}s.png"),
                vis)

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

    # Chart: presence (0/1) over time, with trigger points marked
    plt.figure(figsize=(14, 4))
    plt.plot(t_all, found_all, label="bob found (1=yes)", linewidth=0.8)
    for ts, absent in triggers:
        plt.axvline(x=ts, color="red", linestyle="--", alpha=0.7)
        plt.annotate("BITE", (ts, 1.05), color="red", fontsize=8, ha="center")
    plt.ylim(-0.1, 1.2)
    plt.xlabel("Time (s)")
    plt.ylabel("Bob detected")
    plt.title(f"edge_detection - {name}")
    plt.legend()
    plt.tight_layout()
    plt.savefig(os.path.join(outdir, "chart.png"))
    plt.close()

    # log.txt
    with open(os.path.join(outdir, "log.txt"), "w") as f:
        f.write(f"edge_detection detections for {name}\n")
        f.write(f"params: MIN_ESTABLISHED_SEC={MIN_ESTABLISHED_SEC} "
                f"MIN_ABSENT_SEC={MIN_ABSENT_SEC} COOLDOWN_SEC={COOLDOWN_SEC} "
                f"BLUR_KERNEL={BLUR_KERNEL}\n\n")
        if not triggers:
            f.write("No bites detected.\n")
        for ts, absent in triggers:
            f.write(f"t={ts:.2f}s  absent_frames={absent}\n")

    return triggers


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    videos = sorted([os.path.join(INPUT_DIR, f) for f in os.listdir(INPUT_DIR)
                     if f.lower().endswith(".mp4")])
    for v in videos:
        process_video(v)


if __name__ == "__main__":
    main()
