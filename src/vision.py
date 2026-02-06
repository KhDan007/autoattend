import face_recognition
import numpy as np
import os
import cv2

class FaceRecognizer:
    # Configure recognition settings and load existing encodings.
    # threshold controls how strict matching is (lower threshold = fewer false positives).
    # scale_factor reduces the frame size before recognition to improve speed and maintain FPS.
    # Encodings are loaded into memory once so matching each frame is fast.
    def __init__(self, encoding_dir="data/encodings"):
        self.encoding_dir = encoding_dir
        os.makedirs(self.encoding_dir, exist_ok=True)
        self.known_encodings = []
        self.known_ids = []
        self.student_names = {}  # Map ID to Name for UI labels

    # Load all stored student encodings from disk into memory.
    # Each encoding file is a NumPy array named with the student's id (e.g., 12.npy).
    # Keeping encodings in memory avoids re-reading files every frame, improving performance.
    def load_encodings(self, students):
        """Loads encodings from disk into memory."""
        self.known_encodings = []
        self.known_ids = []
        self.student_names = {}
        for student in students:
            if os.path.exists(student.encoding_path):
                try:
                    enc = np.load(student.encoding_path)
                    self.known_encodings.append(enc)
                    self.known_ids.append(student.id)
                    self.student_names[student.id] = student.name
                except Exception as e:
                    print(f"Error loading encoding for {student.name}: {e}")

    # Build a student's face template from one or more images.
    # For each image:
    # - detect a face
    # - compute a face encoding
    # If multiple encodings are found, average them to make recognition more stable across conditions.
    # Save the final encoding to disk and reload encodings so the student becomes recognizable immediately.
    def register_faces(self, image_paths, name, roll_no):
        encodings = []
        for path in image_paths:
            try:
                img = face_recognition.load_image_file(path)
                encs = face_recognition.face_encodings(img)
                if encs:
                    encodings.append(encs[0])
            except Exception as e:
                print(f"Skipping file {path}: {e}")

        if not encodings:
            return None
        avg_encoding = np.mean(encodings, axis=0)
        filename = f"{roll_no}_{name.replace(' ', '_')}.npy"
        save_path = os.path.join(self.encoding_dir, filename)
        np.save(save_path, avg_encoding)
        return save_path

    # Detect and identify faces in a live frame.
    # Steps:
    # 1) Resize frame for speed (scale_factor).
    # 2) Find face locations and compute encodings.
    # 3) Compare each encoding to known encodings using distance.
    # 4) Choose the closest match and accept it only if it is below the threshold.
    # 5) Scale face box coordinates back to the original frame size for accurate drawing.
    # Returns a list of (box coords, student_id, label) for UI overlay + attendance marking.
    def detect_and_identify(self, frame_rgb):
        """
        Returns a list of tuples: (student_id, name, location_rect)
        location_rect is (top, right, bottom, left)
        """
        # 1. Resize for speed
        scale_factor = 0.25
        small_frame = cv2.resize(frame_rgb, (0, 0), fx=scale_factor, fy=scale_factor)

        # 2. Detect Faces
        face_locations = face_recognition.face_locations(small_frame)
        face_encodings = face_recognition.face_encodings(small_frame, face_locations)

        results = []
        for i, face_encoding in enumerate(face_encodings):
            student_id = None
            name = "Unknown"

            # 3. Identify Faces
            if self.known_encodings:
                matches = face_recognition.compare_faces(
                    self.known_encodings, face_encoding
                )
                face_distances = face_recognition.face_distance(
                    self.known_encodings, face_encoding
                )

                if len(face_distances) > 0:
                    best_match_index = np.argmin(face_distances)
                    if (
                        matches[best_match_index]
                        and face_distances[best_match_index] < 0.5
                    ):  # Threshold
                        student_id = self.known_ids[best_match_index]
                        name = self.student_names.get(student_id, "Unknown")

            # 4. Scale locations back up
            top, right, bottom, left = face_locations[i]
            scale = int(1 / scale_factor)
            loc = (top * scale, right * scale, bottom * scale, left * scale)

            results.append((student_id, name, loc))

        return results
