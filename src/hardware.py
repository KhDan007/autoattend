import cv2
import threading
import time


class CameraManager:
    def __init__(self, camera_index=0):
        self.camera_index = camera_index
        self.cap = cv2.VideoCapture(self.camera_index, cv2.CAP_DSHOW)

        # Reduce capture load
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        self.cap.set(cv2.CAP_PROP_FPS, 30)

        # If supported, reduce buffering (prevents “lag behind real time”)
        self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

        self.current_frame = None
        self.running = False
        self.lock = threading.Lock()
        self.thread = None

    def start(self):
        """Starts the camera thread. Raises RuntimeError if camera is unavailable."""
        if self.running:
            return

        # 1. Attempt to open the camera
        if not self.cap.isOpened():
            self.cap = cv2.VideoCapture(self.camera_index)

        # 2. Did the driver acknowledge the device?
        if not self.cap.isOpened():
            raise RuntimeError(
                f"Could not open camera {self.camera_index}. Is it plugged in?"
            )

        # 3. Try to read a frame
        # This catches the case where another app has locked the camera stream
        ret, frame = self.cap.read()
        if not ret:
            # If we can't read, the camera is likely busy or broken
            self.cap.release()
            raise RuntimeError(
                f"Camera {self.camera_index} is busy or not responding. Is another app using it?"
            )

        # 4. If successful, start the thread
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
        """
        Continuous loop running on a separate thread.
        Decouples hardware latency (camera reads) from the UI rendering loop.
        """
        while self.running:
            ret, frame = self.cap.read()
            if ret:
                # Convert BGR (OpenCV standard) to RGB (UI standard)
                frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

                # Acquire lock before writing to shared memory
                with self.lock:
                    self.current_frame = frame_rgb

            # Sleep 10ms to prevent CPU core saturation
            time.sleep(0.01)

    def get_frame(self):
        """Thread-safe accessor for the latest frame."""
        with self.lock:
            return self.current_frame
