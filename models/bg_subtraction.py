import csv
import os

import cv2
import matplotlib.pyplot as plt
from tqdm import tqdm

INPUT_DIR = "./data"
OUTPUT_DIR = "./data/output/bg_subtraction"

CROP_SIZE = 200
HISTORY = 300          # frames used to build the background model
VAR_THRESHOLD = 16     # lower = more sensitive to small deviations


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

    roi = None
    writer = None
    t, fg_counts = [], []

    csv_path = os.path.join(outdir, "metrics.csv")
    csv_file = open(csv_path, "w", newline="")
    csv_writer = csv.writer(csv_file)
    csv_writer.writerow(["frame", "time", "foreground_pixels"])

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
        # Clean up salt-and-pepper noise the same way we did for Otsu masks
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
        fg_mask = cv2.morphologyEx(fg_mask, cv2.MORPH_OPEN, kernel)

        fg_count = cv2.countNonZero(fg_mask)
        time_s = frame_idx / fps

        csv_writer.writerow([frame_idx, time_s, fg_count])
        t.append(time_s)
        fg_counts.append(fg_count)

        vis = frame.copy()
        cv2.rectangle(vis, (x, y), (x + w, y + h), (255, 0, 0), 1)
        cv2.putText(vis, f"fg_pixels={fg_count}", (10, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)

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

    plt.figure(figsize=(12, 4))
    plt.plot(t, fg_counts)
    plt.axvline(
        x=HISTORY / fps,
        color="gray",
        linestyle="--",
        label="warm-up ends")
    plt.xlabel("Time (s)")
    plt.ylabel("Foreground pixels")
    plt.legend()
    plt.tight_layout()
    plt.savefig(os.path.join(outdir, "fg_pixels.png"))
    plt.close()


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    videos = sorted([os.path.join(INPUT_DIR, f) for f in os.listdir(INPUT_DIR)
                     if f.lower().endswith(".mp4")])
    for v in videos:
        process_video(v)


if __name__ == "__main__":
    main()
