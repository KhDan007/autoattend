import face_recognition
import numpy as np
import os
import cv2


class FaceRecognizer:
    def __init__(self, encoding_dir="data/encodings"):
        self.encoding_dir = encoding_dir
        os.makedirs(self.encoding_dir, exist_ok=True)
        self.known_encodings = []
        self.known_ids = []

    def load_encodings(self, students):
        """Loads encodings from disk into memory."""
        self.known_encodings = []
        self.known_ids = []
        for student in students:
            if os.path.exists(student.encoding_path):
                try:
                    enc = np.load(student.encoding_path)
                    self.known_encodings.append(enc)
                    self.known_ids.append(student.id)
                except Exception as e:
                    print(f"Error loading encoding for {student.name}: {e}")

    def register_faces(self, image_paths, name, roll_no):
        """Encodes bulk images, averages them, and saves to .npy file."""
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

        # Average the encodings
        avg_encoding = np.mean(encodings, axis=0)

        # Save to file
        filename = f"{roll_no}_{name.replace(' ', '_')}.npy"
        save_path = os.path.join(self.encoding_dir, filename)
        np.save(save_path, avg_encoding)
        return save_path

    def identify_face(self, frame_rgb):
        """Returns student_id if found, else None."""
        if not self.known_encodings:
            return None

        # Resize frame to 1/4 size for faster processing
        small_frame = cv2.resize(frame_rgb, (0, 0), fx=0.25, fy=0.25)

        face_locations = face_recognition.face_locations(small_frame)
        face_encodings = face_recognition.face_encodings(small_frame, face_locations)

        for face_encoding in face_encodings:
            # Compare faces
            matches = face_recognition.compare_faces(
                self.known_encodings, face_encoding
            )
            face_distances = face_recognition.face_distance(
                self.known_encodings, face_encoding
            )

            if len(face_distances) > 0:
                best_match_index = np.argmin(face_distances)
                if matches[best_match_index]:
                    return self.known_ids[best_match_index]

        return None
