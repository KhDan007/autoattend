import cv2
import threading
import time


class CameraManager:
    def __init__(self, camera_index=0):
        self.camera_index = camera_index
        self.cap = cv2.VideoCapture(self.camera_index)
        self.current_frame = None
        self.running = False
        self.lock = threading.Lock()
        self.thread = None

    def start(self):
        if self.running:
            return
        
        # --- FIX: Re-initialize camera if it was released ---
        if not self.cap.isOpened():
            self.cap = cv2.VideoCapture(self.camera_index)
        # ----------------------------------------------------

        self.running = True
        self.thread = threading.Thread(target=self._capture_loop, daemon=True)
        self.thread.start()

    def stop(self):
        self.running = False
        if self.thread:
            self.thread.join()
        if self.cap.isOpened():
            self.cap.release()

    def _capture_loop(self):
        while self.running:
            ret, frame = self.cap.read()
            if ret:
                # Convert BGR (OpenCV) to RGB (Tkinter/Pillow) here
                frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                with self.lock:
                    self.current_frame = frame_rgb
            time.sleep(0.01)  # Sleep 10ms to save CPU

    def get_frame(self):
        with self.lock:
            return self.current_frame
