import csv
import os
import statistics
from collections import deque

import cv2
import matplotlib.pyplot as plt
from tqdm import tqdm

INPUT_DIR = "./data"
OUTPUT_DIR = "./data/output/bg_subtraction_detector"

CROP_SIZE = 200
HISTORY = 300               # MOG2 warm-up frames
VAR_THRESHOLD = 16

BASELINE_WINDOW_SEC = 2.0
SPIKE_Z_THRESH = 3.5        # raised from 3.0 - fewer marginal triggers
MIN_SPIKE_SEC = 0.2         # raised from 0.08 - real bites sustain much
                             # longer than a partial bob; this is the main
                             # fix for "too sensitive to slight bobs"
COOLDOWN_SEC = 3.0


def process_video(path):
    name = os.path.splitext(os.path.basename(path))[0]
    outdir = os.path.join(OUTPUT_DIR, name)
    os.makedirs(outdir, exist_ok=True)

    cap = cv2.VideoCapture(path)
    fps = cap.get(cv2.CAP_PROP_FPS)
    frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

    subtractor = cv2.createBackgroundSubtractorMOG2(
        history=HISTORY, varThreshold=VAR_THRESHOLD, detectShadows=False
    )

    baseline_window_frames = int(fps * BASELINE_WINDOW_SEC)
    min_spike_frames = max(1, int(fps * MIN_SPIKE_SEC))
    cooldown_frames = int(fps * COOLDOWN_SEC)

    baseline = deque(maxlen=baseline_window_frames)
    state = "idle"
    spike_counter = 0
    cooldown_counter = 0
    banner_until_frame = -1

    roi = None
    writer = None

    t_all, fg_all, z_all = [], [], []
    triggers = []  # (time_s, z)

    csv_path = os.path.join(outdir, "metrics.csv")
    csv_file = open(csv_path, "w", newline="")
    csv_writer = csv.writer(csv_file)
    csv_writer.writerow(["frame", "time", "fg_pixels", "z", "state"])

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

        fg_mask = subtractor.apply(crop)
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
        fg_mask = cv2.morphologyEx(fg_mask, cv2.MORPH_OPEN, kernel)
        fg_count = cv2.countNonZero(fg_mask)

        time_s = frame_idx / fps
        z = None
        past_warmup = frame_idx > HISTORY

        if past_warmup:
            if state == "idle":
                if len(baseline) >= max(5, baseline_window_frames // 3):
                    mean = statistics.mean(baseline)
                    std = statistics.pstdev(baseline) or 1.0
                    z = (fg_count - mean) / std

                    if z > SPIKE_Z_THRESH:
                        spike_counter += 1
                    else:
                        spike_counter = 0

                    if spike_counter >= min_spike_frames:
                        state = "triggered"
                        cooldown_counter = 0
                        spike_counter = 0
                        banner_until_frame = frame_idx + int(fps)
                        triggers.append((time_s, z))
                        print(f"[bg_subtraction] BITE at t={time_s:.2f}s (z={z:.1f})")

                baseline.append(fg_count)
            else:
                cooldown_counter += 1
                if cooldown_counter >= cooldown_frames:
                    state = "idle"
                    spike_counter = 0
                    baseline.clear()

        csv_writer.writerow([frame_idx, time_s, fg_count, "" if z is None else z, state])
        t_all.append(time_s)
        fg_all.append(fg_count)
        z_all.append(z if z is not None else 0)

        vis = frame.copy()
        cv2.rectangle(vis, (x, y), (x + w, y + h), (255, 0, 0), 1)
        z_text = f"{z:.1f}" if z is not None else "n/a"
        cv2.putText(vis, f"fg={fg_count} z={z_text} state={state}", (10, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
        if frame_idx < banner_until_frame:
            cv2.putText(vis, "BITE DETECTED!", (10, 80),
                        cv2.FONT_HERSHEY_SIMPLEX, 1.2, (0, 0, 255), 3)
            cv2.imwrite(os.path.join(outdir, f"trigger_{time_s:.2f}s.png"), vis)

        mask_bgr = cv2.cvtColor(fg_mask, cv2.COLOR_GRAY2BGR)
        mask_bgr = cv2.resize(mask_bgr, (fw, fh))
        combo = cv2.hconcat([vis, mask_bgr])

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

    # Chart: fg_pixels over time, with trigger points marked
    plt.figure(figsize=(14, 5))
    plt.plot(t_all, fg_all, label="fg_pixels", linewidth=0.8)
    for ts, z in triggers:
        plt.axvline(x=ts, color="red", linestyle="--", alpha=0.7)
        plt.annotate(f"BITE\nz={z:.1f}", (ts, max(fg_all) * 0.9),
                     color="red", fontsize=8, ha="center")
    plt.xlabel("Time (s)")
    plt.ylabel("Foreground pixels")
    plt.title(f"bg_subtraction - {name}")
    plt.legend()
    plt.tight_layout()
    plt.savefig(os.path.join(outdir, "chart.png"))
    plt.close()

    # log.txt
    with open(os.path.join(outdir, "log.txt"), "w") as f:
        f.write(f"bg_subtraction detections for {name}\n")
        f.write(f"params: SPIKE_Z_THRESH={SPIKE_Z_THRESH} MIN_SPIKE_SEC={MIN_SPIKE_SEC} "
                f"BASELINE_WINDOW_SEC={BASELINE_WINDOW_SEC} COOLDOWN_SEC={COOLDOWN_SEC}\n\n")
        if not triggers:
            f.write("No bites detected.\n")
        for ts, z in triggers:
            f.write(f"t={ts:.2f}s  z={z:.2f}\n")

    return triggers


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    videos = sorted([os.path.join(INPUT_DIR, f) for f in os.listdir(INPUT_DIR)
                      if f.lower().endswith(".mp4")])
    for v in videos:
        process_video(v)


if __name__ == "__main__":
    main()