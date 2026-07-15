import csv
import os

import cv2
import matplotlib.pyplot as plt
from tqdm import tqdm

INPUT_DIR = "./data"
OUTPUT_DIR = "./data/output/edge_detection"

CROP_SIZE = 200
CANNY_LOW = 50
CANNY_HIGH = 150


def process_video(path):
    name = os.path.splitext(os.path.basename(path))[0]
    outdir = os.path.join(OUTPUT_DIR, name)
    os.makedirs(outdir, exist_ok=True)

    cap = cv2.VideoCapture(path)
    fps = cap.get(cv2.CAP_PROP_FPS)
    frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

    roi = None
    writer = None
    t, edge_counts = [], []

    csv_path = os.path.join(outdir, "metrics.csv")
    csv_file = open(csv_path, "w", newline="")
    csv_writer = csv.writer(csv_file)
    csv_writer.writerow(["frame", "time", "edge_pixels"])

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
        blur = cv2.GaussianBlur(gray, (5, 5), 0)

        edges = cv2.Canny(blur, CANNY_LOW, CANNY_HIGH)
        edge_count = cv2.countNonZero(edges)
        time_s = frame_idx / fps

        csv_writer.writerow([frame_idx, time_s, edge_count])
        t.append(time_s)
        edge_counts.append(edge_count)

        vis = frame.copy()
        cv2.rectangle(vis, (x, y), (x + w, y + h), (255, 0, 0), 1)
        cv2.putText(vis, f"edge_pixels={edge_count}", (10, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)

        edges_bgr = cv2.cvtColor(edges, cv2.COLOR_GRAY2BGR)
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

    plt.figure(figsize=(12, 4))
    plt.plot(t, edge_counts)
    plt.xlabel("Time (s)")
    plt.ylabel("Edge pixels")
    plt.tight_layout()
    plt.savefig(os.path.join(outdir, "edge_pixels.png"))
    plt.close()


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    videos = sorted([os.path.join(INPUT_DIR, f) for f in os.listdir(INPUT_DIR)
                     if f.lower().endswith(".mp4")])
    for v in videos:
        process_video(v)


if __name__ == "__main__":
    main()
