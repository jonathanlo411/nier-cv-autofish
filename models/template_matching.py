import csv
import os

import cv2
import matplotlib.pyplot as plt
from tqdm import tqdm

INPUT_DIR = "./data"
OUTPUT_DIR = "./data/output/template_matching"

CROP_SIZE = 200
TEMPLATE_SIZE = 50          # size of the bob template patch, in pixels
IDLE_TIMESTAMP_SEC = 1.0    # assumed idle moment to grab the template from
# ADJUST if the bob isn't idle/visible at this
# time in a given clip


def process_video(path):
    name = os.path.splitext(os.path.basename(path))[0]
    outdir = os.path.join(OUTPUT_DIR, name)
    os.makedirs(outdir, exist_ok=True)

    cap = cv2.VideoCapture(path)
    fps = cap.get(cv2.CAP_PROP_FPS)
    frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

    roi = None
    writer = None
    template = None
    template_idx = int(IDLE_TIMESTAMP_SEC * fps)
    t, scores = [], []

    csv_path = os.path.join(outdir, "metrics.csv")
    csv_file = open(csv_path, "w", newline="")
    csv_writer = csv.writer(csv_file)
    csv_writer.writerow(["frame", "time", "match_score", "match_x", "match_y"])

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

        if frame_idx == template_idx:
            # Grab a small patch centered in the ROI as our reference bob image
            c = CROP_SIZE // 2
            r = TEMPLATE_SIZE // 2
            template = gray[c - r:c + r, c - r:c + r].copy()
            cv2.imwrite(os.path.join(outdir, "template.png"), template)

        vis = frame.copy()
        cv2.rectangle(vis, (x, y), (x + w, y + h), (255, 0, 0), 1)

        if template is not None:
            result = cv2.matchTemplate(gray, template, cv2.TM_CCOEFF_NORMED)
            _, max_val, _, max_loc = cv2.minMaxLoc(result)
            time_s = frame_idx / fps

            csv_writer.writerow(
                [frame_idx, time_s, max_val, max_loc[0], max_loc[1]])
            t.append(time_s)
            scores.append(max_val)

            match_x, match_y = max_loc[0] + x, max_loc[1] + y
            cv2.rectangle(vis, (match_x, match_y),
                          (match_x + TEMPLATE_SIZE, match_y + TEMPLATE_SIZE),
                          (0, 255, 0), 2)
            cv2.putText(vis, f"match_score={max_val:.2f}", (10, 30),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)

        if writer is None:
            writer = cv2.VideoWriter(
                os.path.join(outdir, "detection.mp4"),
                cv2.VideoWriter_fourcc(*"mp4v"), fps, (fw, fh)
            )
        writer.write(vis)

        frame_idx += 1
        pbar.update(1)

    pbar.close()
    cap.release()
    csv_file.close()
    if writer:
        writer.release()

    if scores:
        plt.figure(figsize=(12, 4))
        plt.plot(t, scores)
        plt.axvline(
            x=IDLE_TIMESTAMP_SEC,
            color="gray",
            linestyle="--",
            label="template source")
        plt.xlabel("Time (s)")
        plt.ylabel("Match score (normalized correlation)")
        plt.legend()
        plt.tight_layout()
        plt.savefig(os.path.join(outdir, "match_score.png"))
        plt.close()


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    videos = sorted([os.path.join(INPUT_DIR, f) for f in os.listdir(INPUT_DIR)
                     if f.lower().endswith(".mp4")])
    for v in videos:
        process_video(v)


if __name__ == "__main__":
    main()
