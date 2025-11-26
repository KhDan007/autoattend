import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from PIL import Image, ImageTk
import cv2
import csv
from datetime import datetime

# Local Imports
from src.hardware import CameraManager
from src.persistence import DatabaseManager
from src.vision import FaceRecognizer


class AutoAttendApp:
    def __init__(self, root):
        self.root = root
        self.root.title("AutoAttend - Face Recognition Attendance System")
        self.root.geometry("1100x750")

        # --- Initialize Subsystems ---
        self.db = DatabaseManager()
        self.camera = CameraManager()
        self.vision = FaceRecognizer()

        # Load initial face data
        self.load_global_data()

        # --- Application State ---
        self.current_course = None
        self.is_session_active = False
        self.student_tree_map = {}  # Maps student_id -> Treeview Item ID

        # --- UI Setup ---
        self.setup_main_layout()
        self.setup_left_panel()
        self.setup_right_panel()
        self.setup_status_bar()

        # --- Start Loops ---
        # Note: We don't start the camera immediately; user must click Start
        self.update_video_loop()

    def load_global_data(self):
        """Loads all student encodings initially."""
        try:
            all_students = self.db.get_all_students()
            self.vision.load_encodings(all_students)
        except Exception as e:
            messagebox.showerror("Initialization Error", f"Failed to load data: {e}")

    # ================= UI Layout =================

    def setup_main_layout(self):
        # Split window into Left (Video) and Right (Controls/List)
        self.paned_window = ttk.PanedWindow(self.root, orient=tk.HORIZONTAL)
        self.paned_window.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        self.left_panel = ttk.Frame(self.paned_window, padding=5)
        self.right_panel = ttk.Frame(self.paned_window, padding=5, relief=tk.RIDGE)

        self.paned_window.add(self.left_panel, weight=2)
        self.paned_window.add(self.right_panel, weight=1)

    def setup_left_panel(self):
        # 1. Video Feed Area
        video_frame = ttk.LabelFrame(
            self.left_panel, text="Live Camera Feed", padding=5
        )
        video_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

        self.video_label = ttk.Label(video_frame)
        self.video_label.pack(fill=tk.BOTH, expand=True)

        # Set a grey placeholder image initially
        placeholder = ImageTk.PhotoImage(Image.new("RGB", (640, 480), color="gray"))
        self.video_label.configure(image=placeholder)
        self.video_label.image = placeholder

        # 2. Camera Controls
        controls_frame = ttk.Frame(self.left_panel)
        controls_frame.pack(fill=tk.X, pady=5)

        self.btn_start = ttk.Button(
            controls_frame, text="▶ Start Camera", command=self.start_camera
        )
        self.btn_start.pack(side=tk.LEFT, padx=5)

        self.btn_stop = ttk.Button(
            controls_frame,
            text="■ Stop Camera",
            command=self.stop_camera,
            state="disabled",
        )
        self.btn_stop.pack(side=tk.LEFT, padx=5)

    def setup_right_panel(self):
        # 3. Course Selection
        course_frame = ttk.LabelFrame(
            self.right_panel, text="Course Selection", padding=10
        )
        course_frame.pack(fill=tk.X, pady=(0, 15))

        # Fetch courses from DB
        courses = self.db.get_all_courses()
        course_options = [f"{c.code} - {c.name}" for c in courses]

        self.course_var = tk.StringVar()
        self.course_combo = ttk.Combobox(
            course_frame,
            textvariable=self.course_var,
            values=course_options,
            state="readonly",
        )
        self.course_combo.pack(fill=tk.X)
        self.course_combo.bind("<<ComboboxSelected>>", self.on_course_selected)

        if not courses:
            self.course_combo.set("No courses found in DB")

        # 4. Session Info
        self.session_info_frame = ttk.LabelFrame(
            self.right_panel, text="Session Info", padding=10
        )
        self.session_info_frame.pack(fill=tk.X, pady=(0, 15))

        self.lbl_session_course = ttk.Label(
            self.session_info_frame, text="Course: None"
        )
        self.lbl_session_course.pack(anchor=tk.W)

        today_str = datetime.now().strftime("%B %d, %Y")
        ttk.Label(self.session_info_frame, text=f"Date: {today_str}").pack(anchor=tk.W)

        self.lbl_session_status = ttk.Label(
            self.session_info_frame, text="Status: Inactive", foreground="red"
        )
        self.lbl_session_status.pack(anchor=tk.W)

        # 5. Real-time Attendance List
        list_frame = ttk.LabelFrame(
            self.right_panel, text="Attendance List", padding=(5, 5, 5, 0)
        )
        list_frame.pack(fill=tk.BOTH, expand=True)

        # Treeview setup
        columns = ("name", "status")
        self.tree = ttk.Treeview(
            list_frame, columns=columns, show="headings", selectmode="browse"
        )
        self.tree.heading("name", text="Student Name")
        self.tree.heading("status", text="Status")
        self.tree.column("name", width=200)
        self.tree.column("status", width=100, anchor=tk.CENTER)

        # Scrollbar
        scrollbar = ttk.Scrollbar(
            list_frame, orient=tk.VERTICAL, command=self.tree.yview
        )
        self.tree.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # Tags for coloring rows
        self.tree.tag_configure("present", foreground="green", background="#E8F5E9")
        self.tree.tag_configure("absent", foreground="red", background="#FFEBEE")

        # 6. Action Buttons
        action_frame = ttk.Frame(self.right_panel, padding=(0, 15, 0, 0))
        action_frame.pack(fill=tk.X, side=tk.BOTTOM)

        btn_register = ttk.Button(
            action_frame, text="Register Student", command=self.open_register_window
        )
        btn_register.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=2)

        btn_export = ttk.Button(
            action_frame, text="Export CSV", command=self.export_current_session
        )
        btn_export.pack(side=tk.RIGHT, expand=True, fill=tk.X, padx=2)

    def setup_status_bar(self):
        self.status_bar = ttk.Frame(self.root, relief=tk.SUNKEN, padding=2)
        self.status_bar.pack(side=tk.BOTTOM, fill=tk.X)

        self.status_lbl = ttk.Label(self.status_bar, text="System Ready")
        self.status_lbl.pack(side=tk.LEFT)

    # ================= Logic & Callbacks =================

    def start_camera(self):
        self.camera.start()
        self.btn_start["state"] = "disabled"
        self.btn_stop["state"] = "normal"
        self.is_session_active = True
        self.lbl_session_status.config(
            text="Status: Active Session", foreground="green"
        )
        self.status_lbl.config(text="Camera Started")

    def stop_camera(self):
        self.camera.stop()
        self.btn_start["state"] = "normal"
        self.btn_stop["state"] = "disabled"
        self.is_session_active = False
        self.lbl_session_status.config(text="Status: Inactive", foreground="red")
        self.status_lbl.config(text="Camera Stopped")

        # Reset Placeholder
        placeholder = ImageTk.PhotoImage(Image.new("RGB", (640, 480), color="gray"))
        self.video_label.configure(image=placeholder)
        self.video_label.image = placeholder

    def on_course_selected(self, event):
        """Handle Combobox selection"""
        selection = self.course_var.get()
        if not selection:
            return

        # Parse "CS101 - Intro" -> "CS101"
        course_code = selection.split(" - ")[0]
        courses = self.db.get_all_courses()
        self.current_course = next((c for c in courses if c.code == course_code), None)

        if self.current_course:
            self.lbl_session_course.config(text=f"Course: {self.current_course.code}")
            self.refresh_attendance_list()

    def refresh_attendance_list(self):
        """Populate Treeview based on selected course"""
        # Clear existing
        for item in self.tree.get_children():
            self.tree.delete(item)
        self.student_tree_map.clear()

        if not self.current_course:
            return

        # Get Data
        students = self.db.get_students_for_course(self.current_course.id)
        attendance_today = self.db.get_todays_attendance(self.current_course.id)

        # Populate
        for student in students:
            status = attendance_today.get(student.id, "ABSENT")
            tag = "present" if status == "PRESENT" else "absent"

            # Insert and save ID
            tree_id = self.tree.insert(
                "", tk.END, values=(student.name, status), tags=(tag,)
            )
            self.student_tree_map[student.id] = tree_id

    def update_video_loop(self):
        """Core loop: Capture -> Detect -> Draw -> Update UI"""
        frame_rgb = self.camera.get_frame()

        if frame_rgb is not None:
            # 1. Detect Faces (Using updated method from previous step)
            # Returns list of (student_id, name, (top, right, bottom, left))
            detections = self.vision.detect_and_identify(frame_rgb)

            # 2. Draw on Frame (Copy frame to avoid modifying original buffer)
            frame_draw = frame_rgb.copy()

            for student_id, name, (top, right, bottom, left) in detections:
                # Color: Green if identified, Red if unknown
                color = (0, 255, 0) if student_id else (255, 0, 0)

                # Draw Box
                cv2.rectangle(frame_draw, (left, top), (right, bottom), color, 2)
                # Draw Name Background
                cv2.rectangle(
                    frame_draw, (left, bottom - 30), (right, bottom), color, cv2.FILLED
                )
                # Draw Name Text
                cv2.putText(
                    frame_draw,
                    name,
                    (left + 6, bottom - 6),
                    cv2.FONT_HERSHEY_DUPLEX,
                    0.6,
                    (255, 255, 255),
                    1,
                )

                # 3. Mark Attendance (Only if session is active and course selected)
                if self.is_session_active and self.current_course and student_id:
                    newly_marked = self.db.mark_attendance(
                        student_id, self.current_course.id
                    )

                    if newly_marked:
                        # Update UI Treeview instantly without full refresh
                        if student_id in self.student_tree_map:
                            tree_id = self.student_tree_map[student_id]
                            self.tree.set(tree_id, "status", "PRESENT")
                            self.tree.item(tree_id, tags=("present",))
                            self.status_lbl.config(text=f"Marked: {name}")

            # 4. Display in Tkinter
            img = Image.fromarray(frame_draw)
            imgtk = ImageTk.PhotoImage(image=img)
            self.video_label.imgtk = imgtk
            self.video_label.configure(image=imgtk)

        # Schedule next update (~30 FPS)
        self.root.after(30, self.update_video_loop)

    def export_current_session(self):
        """Exports the visible Treeview list to CSV"""
        if not self.current_course:
            messagebox.showwarning("Warning", "Please select a course first.")
            return

        today_str = datetime.now().strftime("%Y-%m-%d")
        default_name = f"Attendance_{self.current_course.code}_{today_str}.csv"

        filepath = filedialog.asksaveasfilename(
            defaultextension=".csv",
            initialfile=default_name,
            filetypes=[("CSV Files", "*.csv")],
        )

        if not filepath:
            return

        try:
            with open(filepath, "w", newline="") as f:
                writer = csv.writer(f)
                writer.writerow(["Student Name", "Status", "Date", "Course"])

                # Iterate through treeview items
                for item_id in self.tree.get_children():
                    vals = self.tree.item(item_id)["values"]
                    writer.writerow(
                        [vals[0], vals[1], today_str, self.current_course.code]
                    )

            messagebox.showinfo("Success", f"Data exported to {filepath}")
        except Exception as e:
            messagebox.showerror("Export Error", str(e))

    def open_register_window(self):
        """Opens popup to register new students"""
        top = tk.Toplevel(self.root)
        top.title("Register Student")
        top.geometry("350x300")

        ttk.Label(top, text="Full Name:").pack(pady=5)
        name_entry = ttk.Entry(top)
        name_entry.pack(pady=5)

        ttk.Label(top, text="Roll Number (Unique ID):").pack(pady=5)
        roll_entry = ttk.Entry(top)
        roll_entry.pack(pady=5)

        def run_registration():
            files = filedialog.askopenfilenames(
                parent=top,
                title="Select 3-5 Photos of Student",
                filetypes=[("Images", "*.jpg *.png *.jpeg")],
            )
            if not files:
                return

            name = name_entry.get().strip()
            roll = roll_entry.get().strip()

            if not name or not roll:
                messagebox.showerror("Error", "All fields are required.")
                return

            # Call Vision module to process images
            path = self.vision.register_faces(files, name, roll)

            if path:
                success = self.db.add_student(name, roll, path)
                if success:
                    messagebox.showinfo("Success", f"Student {name} registered!")
                    self.load_global_data()  # Reload encodings

                    # If current course is selected, refresh list so they appear
                    if self.current_course:
                        self.refresh_attendance_list()
                    top.destroy()
                else:
                    messagebox.showerror(
                        "Database Error", "Roll number already exists."
                    )
            else:
                messagebox.showerror(
                    "Vision Error", "No faces detected in the selected images."
                )

        ttk.Button(top, text="Select Photos & Save", command=run_registration).pack(
            pady=20
        )

    def on_close(self):
        self.stop_camera()
        self.root.destroy()
