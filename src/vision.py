import face_recognition
import numpy as np
import os
import cv2
import time


class FaceRecognizer:
    """
    Performance-focused FaceRecognizer that keeps your existing return format:
    returns [(student_id, name, (top,right,bottom,left)), ...]
    """

    def __init__(self, encoding_dir="data/encodings"):
        self.encoding_dir = encoding_dir
        os.makedirs(self.encoding_dir, exist_ok=True)

        self.known_encodings = []
        self.known_ids = []
        self.student_names = {}  # Map ID to Name for UI labels

        # --- Performance knobs (safe defaults) ---
        self.scale_factor = 0.20          # smaller = faster (0.20–0.25 recommended)
        self.threshold = 0.50             # same as your current threshold
        self.detect_model = "hog"         # fastest on CPU; do not use "cnn" on Windows CPU
        self.process_every_n_frames = 3   # run heavy recognition every N frames
        self.max_fps_for_recognition = 12 # cap heavy recognition calls per second

        # --- Cache state ---
        self._frame_count = 0
        self._last_results = []
        self._last_run_time = 0.0

        # Precomputed matrix for fast distance calculation
        self._enc_matrix = None  # shape: (N, 128)

    def load_encodings(self, students):
        """Loads encodings from disk into memory."""
        self.known_encodings = []
        self.known_ids = []
        self.student_names = {}

        for student in students:
            if os.path.exists(student.encoding_path):
                try:
                    enc = np.load(student.encoding_path)
                    # Ensure float64 for stable distance math
                    enc = np.asarray(enc, dtype=np.float64)
                    if enc.shape == (128,):
                        self.known_encodings.append(enc)
                        self.known_ids.append(student.id)
                        self.student_names[student.id] = student.name
                except Exception as e:
                    print(f"Error loading encoding for {student.name}: {e}")

        # Precompute matrix for fast vectorized distance
        if self.known_encodings:
            self._enc_matrix = np.vstack(self.known_encodings)  # (N,128)
        else:
            self._enc_matrix = None

    def register_faces(self, image_paths, name, roll_no):
        encodings = []

        for path in image_paths:
            try:
                # Robust Windows decode (handles Unicode paths + odd JPEG variants)
                data = np.fromfile(path, dtype=np.uint8)
                bgr = cv2.imdecode(data, cv2.IMREAD_COLOR)
                if bgr is None:
                    print(f"Skipping file {path}: OpenCV could not decode image")
                    continue

                rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
                rgb = np.ascontiguousarray(rgb, dtype=np.uint8)

                encs = face_recognition.face_encodings(rgb)
                if encs:
                    encodings.append(encs[0])
                else:
                    print(f"Skipping file {path}: No face found")

            except Exception as e:
                print(f"Skipping file {path}: {e}")

        if not encodings:
            return None

        avg_encoding = np.mean(encodings, axis=0)
        filename = f"{roll_no}_{name.replace(' ', '_')}.npy"
        save_path = os.path.join(self.encoding_dir, filename)
        np.save(save_path, avg_encoding)
        return save_path

    def _should_run_heavy(self):
        """Decide whether to run detection+encoding this call."""
        self._frame_count += 1

        # Run only every N frames
        if self.process_every_n_frames > 1 and (self._frame_count % self.process_every_n_frames) != 0:
            return False

        # Also cap calls per second to avoid CPU spikes / UI lag
        now = time.time()
        min_dt = 1.0 / max(1, int(self.max_fps_for_recognition))
        if (now - self._last_run_time) < min_dt:
            return False

        self._last_run_time = now
        return True

    def detect_and_identify(self, frame_rgb):
        """
        Returns: list of (student_id, name, (top,right,bottom,left))
        frame_rgb must be RGB uint8.
        """
        if frame_rgb is None:
            return []

        # If we skip heavy compute, reuse last results (smooth UI, higher FPS)
        if not self._should_run_heavy():
            return self._last_results

        # 1) Resize for speed
        sf = float(self.scale_factor)
        if sf <= 0 or sf >= 1:
            sf = 0.20

        small = cv2.resize(frame_rgb, (0, 0), fx=sf, fy=sf, interpolation=cv2.INTER_LINEAR)

        # 2) Detect faces (HOG is fastest on CPU)
        face_locations = face_recognition.face_locations(small, model=self.detect_model)

        if not face_locations:
            self._last_results = []
            return self._last_results

        # 3) Encode faces
        face_encs = face_recognition.face_encodings(small, face_locations)

        results = []
        scale_back = int(round(1.0 / sf))

        # 4) Identify each face (vectorized distance, same threshold behavior)
        for i, face_encoding in enumerate(face_encs):
            student_id = None
            name = "Unknown"

            if self._enc_matrix is not None and self._enc_matrix.size:
                fe = np.asarray(face_encoding, dtype=np.float64)
                # Euclidean distance: faster than calling face_recognition.face_distance repeatedly
                diffs = self._enc_matrix - fe
                dists = np.sqrt(np.sum(diffs * diffs, axis=1))
                best_idx = int(np.argmin(dists))
                best_dist = float(dists[best_idx])

                if best_dist < float(self.threshold):
                    student_id = self.known_ids[best_idx]
                    name = self.student_names.get(student_id, "Unknown")

            top, right, bottom, left = face_locations[i]
            loc = (top * scale_back, right * scale_back, bottom * scale_back, left * scale_back)
            results.append((student_id, name, loc))

        self._last_results = results
        return results
