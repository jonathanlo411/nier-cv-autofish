import os
import cv2
import numpy as np

DATA_DIR = "./data"
CROP_SIZE = 200

videos = sorted([f for f in os.listdir(DATA_DIR) if f.lower().endswith(".mp4")])
if not videos:
    raise RuntimeError("No MP4 files found in ./data")

video_path = os.path.join(DATA_DIR, videos[1])
cap = cv2.VideoCapture(video_path)

frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
frame_idx = 0
paused = False

cv2.namedWindow("Controls", cv2.WINDOW_NORMAL)

seeking=False

def nothing(x):
    pass

cv2.createTrackbar("Frame","Controls",0,max(frame_count-1,0),nothing)

for name, val, maxv in [
    ("H Min",0,179),("H Max",179,179),
    ("S Min",0,255),("S Max",255,255),
    ("V Min",0,255),("V Max",255,255),
]:
    cv2.createTrackbar(name,"Controls",val,maxv,nothing)

while True:
    slider=cv2.getTrackbarPos("Frame","Controls")
    if slider!=frame_idx:
        frame_idx=slider
        cap.set(cv2.CAP_PROP_POS_FRAMES,frame_idx)
    if not paused:
        ret, frame = cap.read()
        if not ret:
            break
        frame_idx += 1
        cv2.setTrackbarPos("Frame","Controls",min(frame_idx,frame_count-1))

    h, w = frame.shape[:2]
    x = (w - CROP_SIZE)//2
    y = (h - CROP_SIZE)//2
    crop = frame[y:y+CROP_SIZE, x:x+CROP_SIZE]

    hsv = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)

    hmin = cv2.getTrackbarPos("H Min","Controls")
    hmax = cv2.getTrackbarPos("H Max","Controls")
    smin = cv2.getTrackbarPos("S Min","Controls")
    smax = cv2.getTrackbarPos("S Max","Controls")
    vmin = cv2.getTrackbarPos("V Min","Controls")
    vmax = cv2.getTrackbarPos("V Max","Controls")

    lower = np.array([hmin,smin,vmin])
    upper = np.array([hmax,smax,vmax])

    mask = cv2.inRange(hsv, lower, upper)

    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE,(3,3))
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)

    contours,_ = cv2.findContours(mask,cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_SIMPLE)
    overlay = crop.copy()

    if contours:
        c = max(contours,key=cv2.contourArea)
        area = cv2.contourArea(c)
        cv2.drawContours(overlay,[c],-1,(0,255,0),2)
        M = cv2.moments(c)
        if M["m00"]:
            cx = int(M["m10"]/M["m00"])
            cy = int(M["m01"]/M["m00"])
            cv2.circle(overlay,(cx,cy),3,(0,0,255),-1)
        cv2.putText(overlay,f"Area: {area:.0f}",(5,20),
                    cv2.FONT_HERSHEY_SIMPLEX,0.6,(0,255,0),2)

    display = cv2.hconcat([
        cv2.resize(crop,(400,400)),
        cv2.cvtColor(cv2.resize(mask,(400,400)),cv2.COLOR_GRAY2BGR),
        cv2.resize(overlay,(400,400))
    ])

    cv2.imshow("HSV Tuner", display)

    key = cv2.waitKey(30) & 0xFF

    if key == ord('q'):
        break
    elif key == ord(' '):
        paused = not paused
    elif key == ord('s'):
        print(f"H:[{hmin},{hmax}] S:[{smin},{smax}] V:[{vmin},{vmax}]")
    elif key == ord('d'):
        paused = True
        frame_idx = min(frame_idx+1, frame_count-1)
        cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
    elif key == ord('a'):
        paused = True
        frame_idx = max(frame_idx-1, 0)
        cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)

cap.release()
cv2.destroyAllWindows()
