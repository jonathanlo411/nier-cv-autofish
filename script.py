import cv2

def main():
    
    for frame in load_mp4("./data/input.mp4"):
        cv2.imshow("Frame", frame)
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break


def load_mp4(filepath: str):
    """
    Generator that yields one frame at a time from an mp4 file.
    Frame is a numpy array of shape (height, width, 3) in BGR order.
    """
    cap = cv2.VideoCapture(filepath)

    if not cap.isOpened():
        raise IOError(f"Could not open video file: {filepath}")

    while True:
        ret, frame = cap.read()
        if not ret:
            break
        yield frame

    cap.release()


if __name__ == "__main__":
    main()