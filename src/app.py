from src.utils.report_generator import ReportGenerator
import tkinter as tk
from tkinter import filedialog, messagebox
from PIL import Image, ImageTk
from src.hardware import CameraManager
from src.persistence import DatabaseManager
from src.vision import FaceRecognizer


class AutoAttendApp:
    def __init__(self, root):
        self.root = root
        self.root.title("AutoAttend System")
        self.root.geometry("800x600")

        # Initialize Subsystems
        self.db = DatabaseManager()
        self.camera = CameraManager()
        self.vision = FaceRecognizer()
        self.reporter = ReportGenerator(self.db)

        # Load initial data
        students = self.db.get_all_students()
        self.vision.load_encodings(students)

        # UI Setup
        self.setup_ui()

        # Start Camera
        self.camera.start()
        # Start UI Update Loop
        self.update_loop()

    def setup_ui(self):
        # Video Display
        self.video_label = tk.Label(self.root)
        self.video_label.pack(pady=10)

        # Controls
        self.btn_frame = tk.Frame(self.root)
        self.btn_frame.pack(fill=tk.X)

        self.btn_register = tk.Button(
            self.btn_frame,
            text="Register New Student",
            command=self.open_register_window,
        )
        self.btn_register.pack(side=tk.LEFT, padx=10, pady=10)

        self.btn_report = tk.Button(self.btn_frame, text="Export CSV", command=self.generate_report)
        self.btn_report.pack(side=tk.LEFT, padx=10, pady=10)

        self.btn_quit = tk.Button(self.btn_frame, text="Quit", command=self.on_close)
        self.btn_quit.pack(side=tk.RIGHT, padx=10, pady=10)

        self.status_label = tk.Label(self.root, text="System Ready", font=("Arial", 14))
        self.status_label.pack(side=tk.BOTTOM, pady=10)

    def update_loop(self):
        """Polls camera and updates UI + runs recognition"""
        frame = self.camera.get_frame()

        if frame is not None:
            # 1. Update UI Image
            img = Image.fromarray(frame)
            imgtk = ImageTk.PhotoImage(image=img)
            self.video_label.imgtk = imgtk
            self.video_label.configure(image=imgtk)

            # 2. Run Recognition
            student_id = self.vision.identify_face(frame)
            if student_id:
                self.db.mark_attendance(student_id)
                self.status_label.config(
                    text=f"Marked: Student ID {student_id}", fg="green"
                )
            else:
                self.status_label.config(text="Scanning...", fg="black")

        # Schedule next update (20ms = ~50 FPS attempt)
        self.root.after(20, self.update_loop)

    def open_register_window(self):
        top = tk.Toplevel(self.root)
        top.title("Register Student")
        top.geometry("300x250")

        tk.Label(top, text="Name:").pack(pady=5)
        name_entry = tk.Entry(top)
        name_entry.pack(pady=5)

        tk.Label(top, text="Roll Number:").pack(pady=5)
        roll_entry = tk.Entry(top)
        roll_entry.pack(pady=5)

        def select_images():
            files = filedialog.askopenfilenames(
                parent=top,
                title="Select 3-5 Photos",
                filetypes=[("Images", "*.jpg *.png *.jpeg")],
            )
            if not files:
                return

            name = name_entry.get()
            roll = roll_entry.get()

            if not name or not roll:
                messagebox.showerror("Error", "Fill all fields")
                return

            # Process Registration
            path = self.vision.register_faces(files, name, roll)
            if path:
                success = self.db.add_student(name, roll, path)
                if success:
                    messagebox.showinfo("Success", "Student Added")
                    # Reload encodings
                    self.vision.load_encodings(self.db.get_all_students())
                    top.destroy()
                else:
                    messagebox.showerror("Error", "Roll number already exists")
            else:
                messagebox.showerror("Error", "No faces found in images")

        tk.Button(top, text="Select Images & Save", command=select_images).pack(pady=20)

    def on_close(self):
        self.camera.stop()
        self.root.destroy()

    def generate_report(self):
        path, msg = self.reporter.export_daily_report()
        if path:
            messagebox.showinfo("Report Generated", msg)
        else:
            messagebox.showwarning("Report Failed", msg)
