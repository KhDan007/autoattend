import tkinter as tk
from tkinter import ttk, filedialog, messagebox, simpledialog
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
        self.root.title("AutoAttend - Intelligent Attendance System")
        self.root.geometry("1200x800")

        # --- Initialize Subsystems ---
        self.db = DatabaseManager()
        self.camera = CameraManager()
        self.vision = FaceRecognizer()

        # Load initial face data
        self.load_global_data()

        # --- Application State ---
        self.current_user = None
        self.current_course = None
        self.is_session_active = False
        self.student_tree_map = {}
        
        # Admin State
        self.admin_selected_teacher_id = None
        self.admin_selected_course_id = None

        # --- Styles ---
        self._setup_styles()
        
        # Handle Window Close Event
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

        # --- Start at Login Screen ---
        self.show_login_screen()

    def _setup_styles(self):
        style = ttk.Style()
        style.configure("Title.TLabel", font=("Helvetica", 24, "bold"))
        style.configure("Header.TLabel", font=("Helvetica", 14, "bold"))
        style.configure("SubHeader.TLabel", font=("Helvetica", 12, "bold"))

    def load_global_data(self):
        try:
            all_students = self.db.get_all_students()
            self.vision.load_encodings(all_students)
        except Exception as e:
            print(f"Vision Load Warning: {e}")
    
    def _clear_window(self):
        for widget in self.root.winfo_children():
            widget.destroy()

    # ==========================================
    # 1. LOGIN SYSTEM
    # ==========================================
    def show_login_screen(self):
        self.stop_camera() 
        self._clear_window()
        
        login_frame = ttk.Frame(self.root, padding="30", relief="ridge")
        login_frame.place(relx=0.5, rely=0.5, anchor="center")

        ttk.Label(login_frame, text="AutoAttend Login", style="Title.TLabel").pack(pady=20)

        # Username
        ttk.Label(login_frame, text="Username:").pack(anchor="w")
        self.username_var = tk.StringVar()
        ttk.Entry(login_frame, textvariable=self.username_var, width=30).pack(pady=5)

        # Password
        ttk.Label(login_frame, text="Password:").pack(anchor="w")
        self.password_var = tk.StringVar()
        ttk.Entry(login_frame, textvariable=self.password_var, show="*", width=30).pack(pady=5)

        # Buttons
        btn_frame = ttk.Frame(login_frame)
        btn_frame.pack(pady=20, fill="x")
        
        ttk.Button(btn_frame, text="Login", command=self.perform_login).pack(side="left", fill="x", expand=True, padx=5)
        ttk.Button(btn_frame, text="Register New Teacher", command=self.register_teacher_popup).pack(side="right", fill="x", expand=True, padx=5)

    def perform_login(self):
        user = self.username_var.get()
        pwd = self.password_var.get()
        
        success, data = self.db.login_user(user, pwd)
        if success:
            self.current_user = data
            if data['is_admin'] == 1:
                self.build_admin_dashboard()
            else:
                self.build_teacher_dashboard()
        else:
            messagebox.showerror("Login Failed", "Invalid username or password")

    def register_teacher_popup(self):
        username = simpledialog.askstring("Register", "Choose a Username:")
        if not username: return
        password = simpledialog.askstring("Register", "Choose a Password:", show="*")
        if not password: return
        fullname = simpledialog.askstring("Register", "Enter Full Name:")
        
        success, msg = self.db.register_user(username, password, fullname)
        if success:
            messagebox.showinfo("Registration", msg)
        else:
            messagebox.showerror("Registration Failed", msg)

    def logout(self):
        self.stop_camera()
        self.current_user = None
        self.current_course = None
        if hasattr(self, 'lbl_session_status'): del self.lbl_session_status
        self.show_login_screen()

    # ==========================================
    # 2. ADMIN DASHBOARD
    # ==========================================
    def build_admin_dashboard(self):
        self._clear_window()
        
        # Header
        header = ttk.Frame(self.root, padding="10")
        header.pack(fill="x")
        ttk.Label(header, text="ADMIN DASHBOARD", style="Header.TLabel", foreground="red").pack(side="left")
        ttk.Button(header, text="Logout", command=self.logout).pack(side="right")

        # Main Layout: 3 Columns (Teachers | Courses | Timetable)
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.pack(fill="both", expand=True)

        # --- Col 1: Teachers ---
        col1 = ttk.LabelFrame(main_frame, text="1. Select Teacher", padding="5")
        col1.pack(side="left", fill="both", expand=True, padx=5)

        self.tree_teachers = ttk.Treeview(col1, columns=("id", "name"), show="headings", height=15)
        self.tree_teachers.heading("id", text="ID")
        self.tree_teachers.heading("name", text="Name")
        self.tree_teachers.column("id", width=30)
        self.tree_teachers.pack(fill="both", expand=True)
        self.tree_teachers.bind("<<TreeviewSelect>>", self.admin_on_teacher_select)
        
        self.refresh_teacher_list()

        # --- Col 2: Courses ---
        col2 = ttk.LabelFrame(main_frame, text="2. Manage Courses", padding="5")
        col2.pack(side="left", fill="both", expand=True, padx=5)

        self.tree_courses = ttk.Treeview(col2, columns=("id", "code", "name"), show="headings", height=10)
        self.tree_courses.heading("id", text="ID")
        self.tree_courses.heading("code", text="Code")
        self.tree_courses.heading("name", text="Name")
        self.tree_courses.column("id", width=30)
        self.tree_courses.column("code", width=60)
        self.tree_courses.pack(fill="both", expand=True, pady=(0, 5))
        self.tree_courses.bind("<<TreeviewSelect>>", self.admin_on_course_select)

        # Add Course Controls
        ctrl_c = ttk.Frame(col2)
        ctrl_c.pack(fill="x")
        ttk.Button(ctrl_c, text="+ Add Course", command=self.admin_add_course).pack(side="left", fill="x", expand=True)
        ttk.Button(ctrl_c, text="- Delete Course", command=self.admin_delete_course).pack(side="right", fill="x", expand=True)

        # --- Col 3: Timetable ---
        col3 = ttk.LabelFrame(main_frame, text="3. Manage Timetable", padding="5")
        col3.pack(side="left", fill="both", expand=True, padx=5)

        self.tree_timetable = ttk.Treeview(col3, columns=("day", "time"), show="headings", height=10)
        self.tree_timetable.heading("day", text="Day")
        self.tree_timetable.heading("time", text="Time")
        self.tree_timetable.pack(fill="both", expand=True, pady=(0, 5))

        # Add Time Slot Controls
        ctrl_t = ttk.Frame(col3)
        ctrl_t.pack(fill="x")
        
        # Day Dropdown
        self.var_day = tk.StringVar()
        days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
        self.combo_day = ttk.Combobox(ctrl_t, textvariable=self.var_day, values=days, state="readonly", width=10)
        self.combo_day.set("Monday")
        self.combo_day.grid(row=0, column=0, padx=2)

        # Start/End Entry
        self.var_start = tk.StringVar(value="09:00")
        ttk.Entry(ctrl_t, textvariable=self.var_start, width=6).grid(row=0, column=1, padx=2)
        
        self.var_end = tk.StringVar(value="10:00")
        ttk.Entry(ctrl_t, textvariable=self.var_end, width=6).grid(row=0, column=2, padx=2)

        ttk.Button(ctrl_t, text="Add Slot", command=self.admin_add_slot).grid(row=1, column=0, columnspan=3, sticky="ew", pady=5)
        ttk.Button(ctrl_t, text="Delete Slot", command=self.admin_delete_slot).grid(row=2, column=0, columnspan=3, sticky="ew")

    # --- Admin Logic ---
    def refresh_teacher_list(self):
        for item in self.tree_teachers.get_children():
            self.tree_teachers.delete(item)
        teachers = self.db.get_all_teachers()
        for t in teachers:
            self.tree_teachers.insert("", "end", values=(t['id'], t['full_name']))

    def admin_on_teacher_select(self, event):
        selected = self.tree_teachers.selection()
        if not selected: return
        item = self.tree_teachers.item(selected[0])
        self.admin_selected_teacher_id = item['values'][0]
        self.admin_refresh_courses()
        # Clear timetable
        for i in self.tree_timetable.get_children(): self.tree_timetable.delete(i)
        self.admin_selected_course_id = None

    def admin_refresh_courses(self):
        for item in self.tree_courses.get_children():
            self.tree_courses.delete(item)
        if not self.admin_selected_teacher_id: return
        
        courses = self.db.get_courses_for_teacher(self.admin_selected_teacher_id)
        for c in courses:
            self.tree_courses.insert("", "end", values=(c.id, c.code, c.name))

    def admin_on_course_select(self, event):
        selected = self.tree_courses.selection()
        if not selected: return
        item = self.tree_courses.item(selected[0])
        self.admin_selected_course_id = item['values'][0]
        self.admin_refresh_timetable()

    def admin_refresh_timetable(self):
        for item in self.tree_timetable.get_children():
            self.tree_timetable.delete(item)
        if not self.admin_selected_course_id: return

        slots = self.db.get_timetable_for_course(self.admin_selected_course_id)
        days = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
        for s in slots:
            day_str = days[s['day']]
            time_str = f"{s['start']} - {s['end']}"
            self.tree_timetable.insert("", "end", iid=s['id'], values=(day_str, time_str))

    def admin_add_course(self):
        if not self.admin_selected_teacher_id:
            messagebox.showwarning("Warning", "Select a teacher first.")
            return
        
        code = simpledialog.askstring("New Course", "Course Code (e.g. CS101):")
        if not code: return
        name = simpledialog.askstring("New Course", "Course Name (e.g. Intro to AI):")
        if not name: return

        self.db.add_course(code, name, self.admin_selected_teacher_id)
        self.admin_refresh_courses()

    def admin_delete_course(self):
        if not self.admin_selected_course_id: return
        if messagebox.askyesno("Confirm", "Delete this course and its timetable?"):
            self.db.delete_course(self.admin_selected_course_id)
            self.admin_refresh_courses()
            self.admin_selected_course_id = None
            for i in self.tree_timetable.get_children(): self.tree_timetable.delete(i)

    def admin_add_slot(self):
        if not self.admin_selected_course_id:
            messagebox.showwarning("Warning", "Select a course first.")
            return
        
        day_idx = self.combo_day.current()
        start = self.var_start.get()
        end = self.var_end.get()

        try:
            # Simple validation of time format
            datetime.strptime(start, "%H:%M")
            datetime.strptime(end, "%H:%M")
        except ValueError:
            messagebox.showerror("Error", "Use HH:MM format (24hr).")
            return

        self.db.add_timetable_slot(self.admin_selected_course_id, day_idx, start, end)
        self.admin_refresh_timetable()

    def admin_delete_slot(self):
        selected = self.tree_timetable.selection()
        if not selected: return
        slot_id = selected[0] # The iid was set to slot_id
        self.db.delete_timetable_slot(slot_id)
        self.admin_refresh_timetable()

    # ==========================================
    # 3. TEACHER DASHBOARD (Original Dashboard)
    # ==========================================
    def build_teacher_dashboard(self):
        self._clear_window()
        
        # --- Top Header ---
        header_frame = ttk.Frame(self.root, padding="10")
        header_frame.pack(side="top", fill="x")
        
        user_text = f"Teacher: {self.current_user['full_name']}"
        ttk.Label(header_frame, text=user_text, style="Header.TLabel").pack(side="left")
        ttk.Button(header_frame, text="Logout", command=self.logout).pack(side="right")

        # --- Paned Window Layout ---
        self.paned_window = ttk.PanedWindow(self.root, orient=tk.HORIZONTAL)
        self.paned_window.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        self.left_panel = ttk.Frame(self.paned_window, padding=5)
        self.right_panel = ttk.Frame(self.paned_window, padding=5, relief=tk.RIDGE)

        self.paned_window.add(self.left_panel, weight=2)
        self.paned_window.add(self.right_panel, weight=1)

        self.setup_left_panel()
        self.setup_right_panel()
        self.setup_status_bar()

        self.update_video_loop()

    # ... (Rest of the Teacher Logic: setup_left_panel, setup_right_panel, callbacks) ...
    # This code remains mostly the same as your previous version, 
    # just indented under the class.

    def setup_left_panel(self):
        video_frame = ttk.LabelFrame(self.left_panel, text="Live Camera Feed", padding=5)
        video_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

        self.video_label = ttk.Label(video_frame)
        self.video_label.pack(fill=tk.BOTH, expand=True)
        placeholder = ImageTk.PhotoImage(Image.new("RGB", (640, 480), color="gray"))
        self.video_label.configure(image=placeholder)
        self.video_label.image = placeholder

        controls_frame = ttk.Frame(self.left_panel)
        controls_frame.pack(fill=tk.X, pady=5)
        self.btn_start = ttk.Button(controls_frame, text="▶ Start Camera", command=self.start_camera)
        self.btn_start.pack(side=tk.LEFT, padx=5)
        self.btn_stop = ttk.Button(controls_frame, text="■ Stop Camera", command=self.stop_camera, state="disabled")
        self.btn_stop.pack(side=tk.LEFT, padx=5)

    def setup_right_panel(self):
        # Course Selection
        course_frame = ttk.LabelFrame(self.right_panel, text="Course Selection", padding=10)
        course_frame.pack(fill=tk.X, pady=(0, 15))

        teacher_id = self.current_user['id']
        self.courses = self.db.get_courses_for_teacher(teacher_id)
        
        course_options = [f"{c.code} - {c.name}" for c in self.courses]
        self.course_var = tk.StringVar()
        self.course_combo = ttk.Combobox(course_frame, textvariable=self.course_var, values=course_options, state="readonly")
        self.course_combo.pack(fill=tk.X)
        self.course_combo.bind("<<ComboboxSelected>>", self.on_course_selected)

        # Session Info
        self.session_info_frame = ttk.LabelFrame(self.right_panel, text="Session Info", padding=10)
        self.session_info_frame.pack(fill=tk.X, pady=(0, 15))

        self.lbl_session_course = ttk.Label(self.session_info_frame, text="Course: None")
        self.lbl_session_course.pack(anchor=tk.W)

        today_str = datetime.now().strftime("%B %d, %Y")
        ttk.Label(self.session_info_frame, text=f"Date: {today_str}").pack(anchor=tk.W)

        self.lbl_session_status = ttk.Label(self.session_info_frame, text="Status: Inactive", foreground="red")
        self.lbl_session_status.pack(anchor=tk.W)

        # Attendance List
        list_frame = ttk.LabelFrame(self.right_panel, text="Attendance List", padding=(5, 5, 5, 0))
        list_frame.pack(fill=tk.BOTH, expand=True)

        columns = ("name", "status")
        self.tree = ttk.Treeview(list_frame, columns=columns, show="headings", selectmode="browse")
        self.tree.heading("name", text="Student Name")
        self.tree.heading("status", text="Status")
        self.tree.column("name", width=200)
        self.tree.column("status", width=100, anchor=tk.CENTER)
        
        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        self.tree.tag_configure("present", foreground="green", background="#E8F5E9")
        self.tree.tag_configure("absent", foreground="red", background="#FFEBEE")

        # Action Buttons
        action_frame = ttk.Frame(self.right_panel, padding=(0, 15, 0, 0))
        action_frame.pack(fill=tk.X, side=tk.BOTTOM)
        ttk.Button(action_frame, text="Register Student", command=self.open_register_window).pack(side=tk.LEFT, expand=True, fill=tk.X, padx=2)
        ttk.Button(action_frame, text="Export CSV", command=self.export_current_session).pack(side=tk.RIGHT, expand=True, fill=tk.X, padx=2)

        # Auto-Select Logic
        active_course = self.db.get_active_course_for_teacher(teacher_id)
        if active_course:
            combo_value = f"{active_course.code} - {active_course.name}"
            if any(c.id == active_course.id for c in self.courses):
                self.course_combo.set(combo_value)
                self.current_course = active_course
                self.lbl_session_course.config(text=f"Course: {active_course.code} (Auto-Selected)")
                self.refresh_attendance_list()
        else:
            if not self.courses:
                self.course_combo.set("No courses assigned")

    def setup_status_bar(self):
        self.status_bar = ttk.Frame(self.root, relief=tk.SUNKEN, padding=2)
        self.status_bar.pack(side=tk.BOTTOM, fill=tk.X)
        self.status_lbl = ttk.Label(self.status_bar, text="System Ready")
        self.status_lbl.pack(side=tk.LEFT)

    def start_camera(self):
        try:
            self.camera.start()
            self.btn_start["state"] = "disabled"
            self.btn_stop["state"] = "normal"
            self.is_session_active = True
            if hasattr(self, 'lbl_session_status'):
                self.lbl_session_status.config(text="Status: Active Session", foreground="green")
            if hasattr(self, 'status_lbl'):
                self.status_lbl.config(text="Camera Started")
        except Exception as e:
            messagebox.showerror("Camera Error", f"Failed to start camera.\nError: {e}")

    def stop_camera(self):
        self.camera.stop()
        self.is_session_active = False
        try:
            if hasattr(self, 'btn_start'): self.btn_start["state"] = "normal"
            if hasattr(self, 'btn_stop'): self.btn_stop["state"] = "disabled"
            if hasattr(self, 'lbl_session_status'):
                self.lbl_session_status.config(text="Status: Inactive", foreground="red")
            if hasattr(self, 'status_lbl'):
                self.status_lbl.config(text="Camera Stopped")
            if hasattr(self, 'video_label'):
                placeholder = ImageTk.PhotoImage(Image.new("RGB", (640, 480), color="gray"))
                self.video_label.configure(image=placeholder)
                self.video_label.image = placeholder
        except:
            pass 

    def on_course_selected(self, event):
        selection = self.course_var.get()
        if not selection: return
        course_code = selection.split(" - ")[0]
        self.current_course = next((c for c in self.courses if c.code == course_code), None)
        if self.current_course:
            self.lbl_session_course.config(text=f"Course: {self.current_course.code}")
            self.refresh_attendance_list()

    def refresh_attendance_list(self):
        for item in self.tree.get_children(): self.tree.delete(item)
        self.student_tree_map.clear()
        if not self.current_course: return
        students = self.db.get_students_for_course(self.current_course.id)
        attendance_today = self.db.get_todays_attendance(self.current_course.id)
        for student in students:
            status = attendance_today.get(student.id, "ABSENT")
            tag = "present" if status == "PRESENT" else "absent"
            tree_id = self.tree.insert("", tk.END, values=(student.name, status), tags=(tag,))
            self.student_tree_map[student.id] = tree_id

    def update_video_loop(self):
        if not self.current_user or self.current_user.get('is_admin') == 1:
            return # Don't run video loop for admin
        
        frame_rgb = self.camera.get_frame()
        if frame_rgb is not None:
            detections = self.vision.detect_and_identify(frame_rgb)
            frame_draw = frame_rgb.copy()
            for student_id, name, (top, right, bottom, left) in detections:
                color = (0, 255, 0) if student_id else (255, 0, 0)
                cv2.rectangle(frame_draw, (left, top), (right, bottom), color, 2)
                cv2.rectangle(frame_draw, (left, bottom - 30), (right, bottom), color, cv2.FILLED)
                cv2.putText(frame_draw, name, (left + 6, bottom - 6), cv2.FONT_HERSHEY_DUPLEX, 0.6, (255, 255, 255), 1)
                
                if self.is_session_active and self.current_course and student_id:
                    if self.db.mark_attendance(student_id, self.current_course.id):
                        if student_id in self.student_tree_map:
                            tree_id = self.student_tree_map[student_id]
                            self.tree.set(tree_id, "status", "PRESENT")
                            self.tree.item(tree_id, tags=("present",))
                            self.status_lbl.config(text=f"Marked: {name}")
            try:
                img = Image.fromarray(frame_draw)
                imgtk = ImageTk.PhotoImage(image=img)
                if hasattr(self, 'video_label'):
                    self.video_label.imgtk = imgtk
                    self.video_label.configure(image=imgtk)
            except: pass
        self.root.after(30, self.update_video_loop)

    def export_current_session(self):
        if not self.current_course: return
        today_str = datetime.now().strftime("%Y-%m-%d")
        default_name = f"Attendance_{self.current_course.code}_{today_str}.csv"
        filepath = filedialog.asksaveasfilename(defaultextension=".csv", initialfile=default_name, filetypes=[("CSV Files", "*.csv")])
        if not filepath: return
        try:
            with open(filepath, "w", newline="") as f:
                writer = csv.writer(f)
                writer.writerow(["Student Name", "Status", "Date", "Course"])
                for item_id in self.tree.get_children():
                    vals = self.tree.item(item_id)["values"]
                    writer.writerow([vals[0], vals[1], today_str, self.current_course.code])
            messagebox.showinfo("Success", f"Data exported to {filepath}")
        except Exception as e: messagebox.showerror("Export Error", str(e))

    def open_register_window(self):
        """Opens popup to register new students with Auto-ID."""
        top = tk.Toplevel(self.root)
        top.title("Register Student")
        top.geometry("350x300")

        # 1. Auto-Generate Next ID
        next_roll = self.db.generate_next_roll_number()

        # 2. UI Layout
        ttk.Label(top, text="Auto-Assigned ID:").pack(pady=(15, 5))
        
        # Entry is 'disabled' so user cannot change it, but we can read it programmatically
        roll_var = tk.StringVar(value=next_roll)
        roll_entry = ttk.Entry(top, textvariable=roll_var, state="disabled") 
        roll_entry.pack(pady=5)

        ttk.Label(top, text="Full Name:").pack(pady=5)
        name_entry = ttk.Entry(top)
        name_entry.pack(pady=5)
        name_entry.focus() # Put cursor here automatically

        def run_registration():
            files = filedialog.askopenfilenames(
                parent=top,
                title="Select 3-5 Photos of Student",
                filetypes=[("Images", "*.jpg *.png *.jpeg")],
            )
            if not files:
                return

            name = name_entry.get().strip()
            # We use the variable we generated, not user input
            roll = roll_var.get() 

            if not name:
                messagebox.showerror("Error", "Please enter a name.")
                return

            # Register Face
            path = self.vision.register_faces(files, name, roll)

            if path:
                # Save to DB
                success = self.db.add_student(name, roll, path)
                if success:
                    messagebox.showinfo("Success", f"Student '{name}' registered with ID: {roll}")
                    self.load_global_data()
                    
                    # Refresh list if a course is active
                    if self.current_course:
                        self.refresh_attendance_list()
                    
                    top.destroy()
                else:
                    messagebox.showerror("Database Error", "ID error. Please try again.")
            else:
                messagebox.showerror("Vision Error", "No faces detected in the selected images.")

        ttk.Button(top, text="Select Photos & Save", command=run_registration).pack(pady=20)

    def on_close(self):
        self.stop_camera()
        self.root.destroy()