# script.py
import csv
import os
import statistics
from collections import deque

import cv2
import matplotlib.pyplot as plt
from tqdm import tqdm

INPUT_DIR = "./data"
OUTPUT_DIR = "./data/output"

CROP_SIZE = 200
BASELINE_WINDOW_SEC = 1.5
SPIKE_Z_THRESH = 2.5
MIN_SPIKE_SEC = 0.05
COOLDOWN_SEC = 3.0
DIFF_THRESHOLD = 20


def get_fps(path):
    cap = cv2.VideoCapture(path)
    if not cap.isOpened():
        raise IOError(path)
    fps = cap.get(cv2.CAP_PROP_FPS)
    cap.release()
    return fps


def process_video(path):
    name = os.path.splitext(os.path.basename(path))[0]
    outdir = os.path.join(OUTPUT_DIR, name)
    os.makedirs(outdir, exist_ok=True)

    cap = cv2.VideoCapture(path)
    fps = cap.get(cv2.CAP_PROP_FPS)
    frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

    baseline = deque(maxlen=int(BASELINE_WINDOW_SEC * fps))
    cooldown_frames = int(COOLDOWN_SEC * fps)
    min_spike = max(1, int(MIN_SPIKE_SEC * fps))

    state = "idle"
    cooldown = 0
    spike = 0
    prev = None
    roi = None
    writer = None

    csv_path = os.path.join(outdir, "metrics.csv")
    csv_file = open(csv_path, "w", newline="")
    csv_writer = csv.writer(csv_file)
    csv_writer.writerow(["frame","time","changed_pixels","motion_sum","motion_mean","z"])

    t = []
    motion = []
    zhist = []

    pbar = tqdm(total=frames, desc=name)

    frame_idx = 0
    while True:
        ret, frame = cap.read()
        if not ret:
            break

        if roi is None:
            fh, fw = frame.shape[:2]
            x = (fw - CROP_SIZE)//2
            y = (fh - CROP_SIZE)//2
            roi = (x,y,CROP_SIZE,CROP_SIZE)

        x,y,w,h = roi
        crop = frame[y:y+h,x:x+w]
        gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
        blur = cv2.GaussianBlur(gray,(5,5),0)

        if prev is None:
            prev = blur
            frame_idx += 1
            pbar.update(1)
            continue

        diff = cv2.absdiff(prev, blur)
        diff = cv2.GaussianBlur(diff,(5,5),0)
        _, mask = cv2.threshold(diff, DIFF_THRESHOLD,255,cv2.THRESH_BINARY)

        changed = cv2.countNonZero(mask)
        motion_sum = int(diff.sum())
        motion_mean = float(diff.mean())
        prev = blur

        z = None
        if state == "idle":
            if len(baseline) > max(5, baseline.maxlen//3):
                mean = statistics.mean(baseline)
                std = statistics.pstdev(baseline) or 1.0
                z = (changed-mean)/std
                if z > SPIKE_Z_THRESH:
                    spike += 1
                else:
                    spike = 0
                if spike >= min_spike:
                    print(f"BITE DETECTED {name}: {frame_idx/fps:.2f}s z={z:.2f}")
                    state="triggered"
                    cooldown=0
                    spike=0
            baseline.append(changed)
        else:
            cooldown += 1
            if cooldown >= cooldown_frames:
                state="idle"
                baseline.clear()

        csv_writer.writerow([frame_idx,frame_idx/fps,changed,motion_sum,motion_mean,"" if z is None else z])
        t.append(frame_idx/fps)
        motion.append(changed)
        zhist.append(0 if z is None else z)

        vis = frame.copy()
        cv2.rectangle(vis,(x,y),(x+w,y+h),(255,0,0),1)
        cv2.putText(vis,f"motion={changed} z={z if z is not None else 'n/a'}",
                    (10,30),cv2.FONT_HERSHEY_SIMPLEX,0.7,(0,0,255),2)

        mask_bgr = cv2.cvtColor(mask,cv2.COLOR_GRAY2BGR)
        mask_bgr = cv2.resize(mask_bgr,(fw,fh))
        combo = cv2.hconcat([vis,mask_bgr])

        if writer is None:
            writer = cv2.VideoWriter(
                os.path.join(outdir,"detection.mp4"),
                cv2.VideoWriter_fourcc(*"mp4v"),
                fps,
                (fw*2,fh)
            )
        writer.write(combo)

        frame_idx += 1
        pbar.update(1)

    pbar.close()
    cap.release()
    csv_file.close()
    if writer:
        writer.release()

    plt.figure(figsize=(10,4))
    plt.plot(t,motion)
    plt.xlabel("Time (s)")
    plt.ylabel("Changed Pixels")
    plt.tight_layout()
    plt.savefig(os.path.join(outdir,"motion.png"))
    plt.close()

    plt.figure(figsize=(10,4))
    plt.plot(t,zhist)
    plt.xlabel("Time (s)")
    plt.ylabel("Z Score")
    plt.tight_layout()
    plt.savefig(os.path.join(outdir,"zscore.png"))
    plt.close()


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    videos = sorted([os.path.join(INPUT_DIR,f) for f in os.listdir(INPUT_DIR)
                     if f.lower().endswith(".mp4")])
    for v in videos:
        process_video(v)


if __name__ == "__main__":
    main()
