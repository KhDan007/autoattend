# AutoAttend – Face Recognition Attendance System

AutoAttend is a desktop attendance system that uses real-time face recognition to automatically mark students as present during a session.  
It provides a graphical user interface for managing students, sessions, and attendance records.

The system uses:

- **Python**
- **OpenCV** (camera handling and drawing)
- **face_recognition (dlib-based)** for face detection and encoding
- **NumPy**
- **Tkinter** for the GUI
- A local database (SQLite)

---

## Features

- Real-time face detection and identification
- Automatic attendance marking
- Student registration with face encoding generation
- Admin and user role separation
- Session-based attendance tracking
- FPS-optimized recognition pipeline
- Local storage of face encodings

---

## System Requirements (Windows)

- Windows 10 or Windows 11 (64-bit)
- Python 3.10 or 3.11 (64-bit recommended)
- Webcam
- NVIDIA GPU (optional, not required)

Do NOT use Python 3.12 (dlib compatibility issues)

---

## Step 1 – Install Python

1. Download Python 3.10 or 3.11 from:  
   [https://www.python.org/downloads/](https://www.python.org/downloads/)
2. During installation:
   - Check **"Add Python to PATH"**
   - Choose **Install for all users**
3. Verify installation:

```bash
python --version
````

It should return something like:

```text
Python 3.10.x
```

---

## Step 2 – Clone or Download the Project

**Option A – Git:**

```bash
git clone <your-repository-url>
cd autoattend
```

**Option B – ZIP:**

1. Download ZIP
2. Extract it
3. Open Command Prompt inside the extracted folder

---

## Step 3 – Create Virtual Environment

Inside the project root:

```bash
python -m venv .venv
```

Activate it:

```bash
.venv\Scripts\activate
```

Your terminal should now show:

```text
(.venv)
```

---

## Step 4 – Install Dependencies

Install required packages:

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

If you do not have a `requirements.txt`, install manually:

```bash
pip install numpy==1.26.4
pip install opencv-python
pip install face_recognition
pip install pillow
```

Important Notes:

* If OpenCV requires NumPy ≥ 2.0, install:

```bash
pip install numpy>=2
```

* If installation fails for `face_recognition`, ensure:

  * Python is 64-bit
  * You are using Python 3.10 or 3.11

---

## Step 5 – Run the Application

From the project root:

```bash
python src/app.py
```

The GUI should launch.

---

## First-Time Setup (Inside the App)

1. Log in as admin
2. Add students to the system
3. Register student faces (upload clear frontal images)
4. Start a session
5. Camera will begin detecting faces
6. Attendance is marked automatically

---

## Performance Optimization Tips (Windows)

If camera feels slow:

* Ensure resolution is 640x480
* Close other heavy applications
* Use good lighting
* Keep face within reasonable distance
* Do not use the CNN detection model on CPU

The system is optimized to:

* Downscale frames
* Process recognition every few frames
* Reuse cached detection results

---

## Troubleshooting

### Blue Camera Feed

**Cause:** Incorrect BGR/RGB conversion
**Fix:** Ensure camera frame is converted only once before display

### "Unsupported image type"

**Cause:** Incorrect image format
**Fix:**

* Use JPG or PNG
* Ensure images are 8-bit RGB

### NumPy Version Conflict

If you see:

```
opencv-python requires numpy>=2
```

Run:

```bash
pip uninstall numpy
pip install numpy>=2
```

### face_recognition Installation Fails

Ensure:

* Python 3.10 or 3.11
* 64-bit Python
* Updated pip

---

## How Recognition Works (Technical Overview)

1. Frame captured from webcam
2. Frame resized for speed
3. Faces detected using HOG model
4. Face encodings computed (128-d vector)
5. Euclidean distance used for matching
6. If distance < threshold → match accepted
7. Attendance marked in database

Encodings are stored as `.npy` files and loaded into memory at startup for fast comparison.

---

## Security Notes

* All face encodings stored locally
* No cloud processing
* No external API calls
* Database stored locally

---

## Future Improvements

* GPU acceleration
* Better face tracking between frames
* Multi-camera support
* Attendance export (CSV/Excel)
* Liveness detection

---

## Author

Developed as a face-recognition-based automated attendance system project.

---

## License

This project is intended for educational use.
