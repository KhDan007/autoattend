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
        self.root.title("AutoAttend - School Management System")
        self.root.geometry("1200x800")

        self.db = DatabaseManager()
        self.camera = CameraManager()
        self.vision = FaceRecognizer()

        self.load_global_data()

        self.current_user = None
        self.active_session = None  # Dict: {course_id, group_id, etc}
        self.is_session_active = False
        self.student_tree_map = {}

        # Admin Selection States
        self.admin_sel_teacher_id = None
        self.admin_sel_course_id = None
        self.admin_sel_group_id = None

        self._setup_styles()
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)
        self.show_login_screen()

    def _setup_styles(self):
        style = ttk.Style()
        style.configure("Title.TLabel", font=("Helvetica", 24, "bold"))
        style.configure("Header.TLabel", font=("Helvetica", 14, "bold"))
        style.configure("SubHeader.TLabel", font=("Helvetica", 11, "bold"))

    def load_global_data(self):
        try:
            all_students = self.db.get_all_students()
            valid_students = [s for s in all_students if s.encoding_path]
            self.vision.load_encodings(valid_students)
        except Exception as e:
            print(f"Vision Load Warning: {e}")

    def _clear_window(self):
        for widget in self.root.winfo_children():
            widget.destroy()

    # ==========================================
    # LOGIN
    # ==========================================
    def show_login_screen(self):
        self.stop_camera()
        self._clear_window()

        login_frame = ttk.Frame(self.root, padding="30", relief="ridge")
        login_frame.place(relx=0.5, rely=0.5, anchor="center")

        ttk.Label(login_frame, text="AutoAttend Login", style="Title.TLabel").pack(
            pady=20
        )

        ttk.Label(login_frame, text="Username:").pack(anchor="w")
        self.username_var = tk.StringVar()
        user_entry = ttk.Entry(login_frame, textvariable=self.username_var, width=30)
        user_entry.pack(pady=5)
        user_entry.bind("<Return>", lambda event: self.perform_login())

        ttk.Label(login_frame, text="Password:").pack(anchor="w")
        self.password_var = tk.StringVar()
        pass_entry = ttk.Entry(
            login_frame, textvariable=self.password_var, show="*", width=30
        )
        pass_entry.pack(pady=5)
        pass_entry.bind("<Return>", lambda event: self.perform_login())

        btn_frame = ttk.Frame(login_frame)
        btn_frame.pack(pady=20, fill="x")
        ttk.Button(btn_frame, text="Login", command=self.perform_login).pack(
            side="left", fill="x", expand=True, padx=5
        )
        ttk.Button(
            btn_frame, text="Register Teacher", command=self.register_teacher_popup
        ).pack(side="right", fill="x", expand=True, padx=5)

        user_entry.focus()

    def perform_login(self):
        user = self.username_var.get()
        pwd = self.password_var.get()
        success, data = self.db.login_user(user, pwd)
        if success:
            self.current_user = data
            if data["is_admin"] == 1:
                self.build_admin_dashboard()
            else:
                self.build_teacher_dashboard()
        else:
            messagebox.showerror("Login Failed", "Invalid credentials")

    def register_teacher_popup(self):
        username = simpledialog.askstring("Register", "Username:")
        if not username:
            return
        password = simpledialog.askstring("Register", "Password:", show="*")
        if not password:
            return
        fullname = simpledialog.askstring("Register", "Full Name:")
        self.db.register_user(username, password, fullname)

    def logout(self):
        self.stop_camera()
        self.current_user = None
        self.active_session = None
        self.show_login_screen()

    # ==========================================
    # ADMIN DASHBOARD
    # ==========================================
    def build_admin_dashboard(self):
        self._clear_window()
        header = ttk.Frame(self.root, padding="10")
        header.pack(fill="x")
        ttk.Label(
            header, text="ADMIN DASHBOARD", style="Header.TLabel", foreground="red"
        ).pack(side="left")
        ttk.Button(header, text="Logout", command=self.logout).pack(side="right")

        notebook = ttk.Notebook(self.root)
        notebook.pack(fill="both", expand=True, padx=10, pady=10)

        # TAB 1: Merged People Management (Groups + Students)
        self.tab_people = ttk.Frame(notebook)
        notebook.add(self.tab_people, text="1. Groups & Students")
        self._build_admin_people_tab(self.tab_people)

        # TAB 2: Academic (Courses & Timetable)
        self.tab_academic = ttk.Frame(notebook)
        notebook.add(self.tab_academic, text="2. Courses & Timetable")
        self._build_admin_academic_tab(self.tab_academic)

    # --- TAB 1: PEOPLE (Master-Detail View) ---
    def _build_admin_people_tab(self, parent):
        paned = ttk.PanedWindow(parent, orient=tk.HORIZONTAL)
        paned.pack(fill="both", expand=True, padx=5, pady=5)

        # === LEFT PANEL: GROUPS ===
        left_frame = ttk.LabelFrame(paned, text="Step 1: Select Group", padding="5")
        paned.add(left_frame, weight=1)

        self.tree_groups = ttk.Treeview(
            left_frame, columns=("id", "name"), show="headings"
        )
        self.tree_groups.heading("id", text="ID")
        self.tree_groups.column("id", width=40)
        self.tree_groups.heading("name", text="Group Name")
        self.tree_groups.pack(fill="both", expand=True)
        self.tree_groups.bind("<<TreeviewSelect>>", self.on_group_sel)

        btn_g_frame = ttk.Frame(left_frame)
        btn_g_frame.pack(fill="x", pady=5)
        ttk.Button(btn_g_frame, text="+ New Group", command=self.admin_add_group).pack(
            side="left", fill="x", expand=True, padx=2
        )
        ttk.Button(
            btn_g_frame, text="- Delete Group", command=self.admin_delete_group
        ).pack(side="right", fill="x", expand=True, padx=2)

        # === RIGHT PANEL: STUDENTS ===
        right_frame = ttk.LabelFrame(
            paned, text="Step 2: Manage Students in Group", padding="5"
        )
        paned.add(right_frame, weight=3)

        # Student List
        cols = ("roll", "name", "status")
        self.tree_students = ttk.Treeview(right_frame, columns=cols, show="headings")
        self.tree_students.heading("roll", text="ID")
        self.tree_students.column("roll", width=60)
        self.tree_students.heading("name", text="Student Name")
        self.tree_students.heading("status", text="Face Data")
        self.tree_students.tag_configure("registered", foreground="green")
        self.tree_students.tag_configure("unregistered", foreground="red")

        sb = ttk.Scrollbar(
            right_frame, orient=tk.VERTICAL, command=self.tree_students.yview
        )
        self.tree_students.configure(yscrollcommand=sb.set)
        sb.pack(side=tk.RIGHT, fill=tk.Y)
        self.tree_students.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # Student Controls (Bottom)
        ctrl_frame = ttk.Frame(right_frame)
        ctrl_frame.pack(side=tk.BOTTOM, fill="x", pady=5)

        ttk.Button(
            ctrl_frame, text="+ Add Student", command=self.admin_add_student
        ).pack(side="left", padx=5)
        ttk.Button(
            ctrl_frame, text="📷 Upload Face", command=self.admin_upload_face
        ).pack(side="left", padx=5)
        ttk.Button(
            ctrl_frame, text="- Delete Student", command=self.admin_delete_student
        ).pack(side="right", padx=5)

        self.refresh_group_list()

    # --- LOGIC: GROUPS ---
    def refresh_group_list(self):
        # Clear Group Tree
        for i in self.tree_groups.get_children():
            self.tree_groups.delete(i)
        # Clear Student Tree (UI Reset)
        for i in self.tree_students.get_children():
            self.tree_students.delete(i)
        self.admin_sel_group_id = None

        for g in self.db.get_all_groups():
            self.tree_groups.insert("", "end", values=(g.id, g.name))

    def on_group_sel(self, event):
        sel = self.tree_groups.selection()
        if not sel:
            return

        # Get Group ID and Refresh Student List
        self.admin_sel_group_id = self.tree_groups.item(sel[0])["values"][0]
        group_name = self.tree_groups.item(sel[0])["values"][1]
        self.refresh_student_list_for_group()

    def admin_add_group(self):
        name = simpledialog.askstring("New Group", "Group Name (e.g., CS-SL-26-1):")
        if name:
            if self.db.add_group(name):
                self.refresh_group_list()
            else:
                messagebox.showerror("Error", "Group exists or invalid.")

    def admin_delete_group(self):
        if not self.admin_sel_group_id:
            return
        if messagebox.askyesno(
            "Confirm", "Delete Group? All students in it will be deleted."
        ):
            self.db.delete_group(self.admin_sel_group_id)
            self.refresh_group_list()

    # --- LOGIC: STUDENTS ---
    def refresh_student_list_for_group(self):
        # Clear current list
        for i in self.tree_students.get_children():
            self.tree_students.delete(i)

        if not self.admin_sel_group_id:
            return

        # Fetch students only for this group
        students = self.db.get_students_by_group(self.admin_sel_group_id)

        for s in students:
            status = "Registered" if s.encoding_path else "Unregistered"
            tag = "registered" if s.encoding_path else "unregistered"
            self.tree_students.insert(
                "", "end", values=(s.roll_number, s.name, status), tags=(tag,)
            )

    def admin_add_student(self):
        if not self.admin_sel_group_id:
            messagebox.showwarning(
                "Warning", "Please select a group on the left first."
            )
            return

        next_roll = self.db.generate_next_roll_number()
        name = simpledialog.askstring("Add Student", f"Auto-ID: {next_roll}\nName:")
        if name:
            if self.db.add_student(name, next_roll, self.admin_sel_group_id):
                self.refresh_student_list_for_group()
            else:
                messagebox.showerror("Error", "DB Error")

    def admin_upload_face(self):
        sel = self.tree_students.selection()
        if not sel:
            messagebox.showwarning("Select", "Select a student first.")
            return

        item = self.tree_students.item(sel[0])
        roll, name = item["values"][0], item["values"][1]

        # Get Student ID via helper or direct lookup
        all_s = self.db.get_students_by_group(self.admin_sel_group_id)
        student = next((s for s in all_s if str(s.roll_number) == str(roll)), None)

        files = filedialog.askopenfilenames(
            title=f"Photos for {name}", filetypes=[("Images", "*.jpg *.png *.jpeg")]
        )
        if files and student:
            path = self.vision.register_faces(files, name, str(roll))
            if path:
                self.db.update_student_face(student.id, path)
                self.load_global_data()
                self.refresh_student_list_for_group()
                messagebox.showinfo("Success", "Face updated.")
            else:
                messagebox.showerror("Error", "No faces found.")

    def admin_delete_student(self):
        sel = self.tree_students.selection()
        if not sel:
            return
        roll = self.tree_students.item(sel[0])["values"][0]

        # Get ID
        all_s = self.db.get_students_by_group(self.admin_sel_group_id)
        student = next((s for s in all_s if str(s.roll_number) == str(roll)), None)

        if student and messagebox.askyesno("Confirm", "Delete student?"):
            self.db.delete_student(student.id)
            self.refresh_student_list_for_group()

    # --- TAB 3: ACADEMIC (Timetable links Groups now) ---
    def _build_admin_academic_tab(self, parent):
        frame = ttk.Frame(parent, padding="10")
        frame.pack(fill="both", expand=True)

        # Teachers
        col1 = ttk.LabelFrame(frame, text="1. Teacher", padding="5")
        col1.pack(side="left", fill="both", expand=True)
        self.tree_teachers = ttk.Treeview(
            col1, columns=("id", "name"), show="headings", height=10
        )
        self.tree_teachers.heading("id", text="ID")
        self.tree_teachers.heading("name", text="Name")
        self.tree_teachers.column("id", width=30)
        self.tree_teachers.pack(fill="both", expand=True)
        self.tree_teachers.bind("<<TreeviewSelect>>", self.on_teacher_sel)

        # Courses
        col2 = ttk.LabelFrame(frame, text="2. Course", padding="5")
        col2.pack(side="left", fill="both", expand=True)
        self.tree_courses = ttk.Treeview(
            col2, columns=("id", "name"), show="headings", height=10
        )
        self.tree_courses.heading("id", text="ID")
        self.tree_courses.heading("name", text="Name")
        self.tree_courses.column("id", width=30)
        self.tree_courses.pack(fill="both", expand=True, pady=(0, 5))
        self.tree_courses.bind("<<TreeviewSelect>>", self.on_course_sel)
        ttk.Button(col2, text="+ Add Course", command=self.add_course_popup).pack(
            fill="x"
        )

        # Timetable
        col3 = ttk.LabelFrame(frame, text="3. Timetable (Assign Group)", padding="5")
        col3.pack(side="left", fill="both", expand=True)
        self.tree_timetable = ttk.Treeview(
            col3, columns=("day", "time", "group"), show="headings", height=10
        )
        self.tree_timetable.heading("day", text="Day")
        self.tree_timetable.heading("time", text="Time")
        self.tree_timetable.heading("group", text="Group")  # New Column
        self.tree_timetable.column("day", width=50)
        self.tree_timetable.column("group", width=80)
        self.tree_timetable.pack(fill="both", expand=True, pady=(0, 5))

        # Timetable Controls
        t_ctrl = ttk.Frame(col3)
        t_ctrl.pack(fill="x")

        ttk.Label(t_ctrl, text="Group:").grid(row=0, column=0, sticky="w")
        self.var_tt_group = tk.StringVar()
        self.combo_tt_group = ttk.Combobox(
            t_ctrl, textvariable=self.var_tt_group, state="readonly", width=12
        )
        self.combo_tt_group.grid(row=0, column=1, padx=2)

        self.combo_tt_day = ttk.Combobox(
            t_ctrl,
            values=["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"],
            state="readonly",
            width=10,
        )
        self.combo_tt_day.current(0)
        self.combo_tt_day.grid(row=1, column=0, padx=2, pady=2)

        self.ent_start = ttk.Entry(t_ctrl, width=6)
        self.ent_start.insert(0, "09:00")
        self.ent_start.grid(row=1, column=1, padx=2)
        self.ent_end = ttk.Entry(t_ctrl, width=6)
        self.ent_end.insert(0, "10:00")
        self.ent_end.grid(row=1, column=2, padx=2)

        ttk.Button(t_ctrl, text="Assign Slot", command=self.add_slot).grid(
            row=2, column=0, columnspan=3, sticky="ew", pady=5
        )
        ttk.Button(t_ctrl, text="Delete Slot", command=self.del_slot).grid(
            row=3, column=0, columnspan=3, sticky="ew"
        )

        self.refresh_teacher_list()

    def refresh_teacher_list(self):
        for i in self.tree_teachers.get_children():
            self.tree_teachers.delete(i)
        for t in self.db.get_all_teachers():
            self.tree_teachers.insert("", "end", values=(t["id"], t["full_name"]))

    def on_teacher_sel(self, e):
        sel = self.tree_teachers.selection()
        if not sel:
            return
        self.admin_sel_teacher_id = self.tree_teachers.item(sel[0])["values"][0]
        self.refresh_courses()
        self.clear_timetable_view()

    def refresh_courses(self):
        for i in self.tree_courses.get_children():
            self.tree_courses.delete(i)
        if not self.admin_sel_teacher_id:
            return
        for c in self.db.get_courses_for_teacher(self.admin_sel_teacher_id):
            self.tree_courses.insert("", "end", values=(c.id, c.name))

    def add_course_popup(self):
        if not self.admin_sel_teacher_id:
            return
        name = simpledialog.askstring("New Course", "Name:")
        if name:
            self.db.add_course(name, self.admin_sel_teacher_id)
            self.refresh_courses()

    def on_course_sel(self, e):
        sel = self.tree_courses.selection()
        if not sel:
            return
        self.admin_sel_course_id = self.tree_courses.item(sel[0])["values"][0]
        self.refresh_timetable()

        # Populate Group Combo for Timetable
        groups = self.db.get_all_groups()
        self.combo_tt_group["values"] = [g.name for g in groups]
        if groups:
            self.combo_tt_group.current(0)

    def refresh_timetable(self):
        self.clear_timetable_view()
        if not self.admin_sel_course_id:
            return
        slots = self.db.get_timetable_for_course(self.admin_sel_course_id)
        days = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
        for s in slots:
            self.tree_timetable.insert(
                "",
                "end",
                iid=s.id,
                values=(
                    days[s.day_of_week],
                    f"{s.start_time}-{s.end_time}",
                    s.group_name,
                ),
            )

    def clear_timetable_view(self):
        for i in self.tree_timetable.get_children():
            self.tree_timetable.delete(i)

    def add_slot(self):
        if not self.admin_sel_course_id:
            return
        g_name = self.var_tt_group.get()
        if not g_name:
            messagebox.showerror("Error", "Select a group.")
            return

        # Get Group ID
        groups = self.db.get_all_groups()
        gid = next((g.id for g in groups if g.name == g_name), None)

        day = self.combo_tt_day.current()
        start, end = self.ent_start.get(), self.ent_end.get()
        self.db.add_timetable_slot(self.admin_sel_course_id, gid, day, start, end)
        self.refresh_timetable()

    def del_slot(self):
        sel = self.tree_timetable.selection()
        if sel:
            self.db.delete_timetable_slot(sel[0])
            self.refresh_timetable()

    # ==========================================
    # TEACHER DASHBOARD (Auto-Detect Group)
    # ==========================================
    def build_teacher_dashboard(self):
        self._clear_window()

        # Header
        h_frame = ttk.Frame(self.root, padding="10")
        h_frame.pack(side="top", fill="x")
        ttk.Label(
            h_frame,
            text=f"Teacher: {self.current_user['full_name']}",
            style="Header.TLabel",
        ).pack(side="left")
        ttk.Button(h_frame, text="Logout", command=self.logout).pack(side="right")

        paned = ttk.PanedWindow(self.root, orient=tk.HORIZONTAL)
        paned.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        left = ttk.Frame(paned, padding=5)
        right = ttk.Frame(paned, padding=5, relief=tk.RIDGE)
        paned.add(left, weight=2)
        paned.add(right, weight=1)

        # Camera
        vid_frame = ttk.LabelFrame(left, text="Live Camera", padding=5)
        vid_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        self.video_label = ttk.Label(vid_frame)
        self.video_label.pack(fill=tk.BOTH, expand=True)
        self.video_label.image = ImageTk.PhotoImage(
            Image.new("RGB", (640, 480), "gray")
        )
        self.video_label.configure(image=self.video_label.image)

        btn_box = ttk.Frame(left)
        btn_box.pack(fill=tk.X)
        self.btn_start = ttk.Button(
            btn_box, text="▶ Start Session", command=self.start_session_camera
        )
        self.btn_start.pack(side=tk.LEFT, padx=5)
        self.btn_stop = ttk.Button(
            btn_box, text="■ Stop", command=self.stop_camera, state="disabled"
        )
        self.btn_stop.pack(side=tk.LEFT, padx=5)

        # Session Info
        info_frame = ttk.LabelFrame(right, text="Current Session", padding=10)
        info_frame.pack(fill=tk.X, pady=(0, 10))

        self.lbl_course = ttk.Label(info_frame, text="Course: --")
        self.lbl_course.pack(anchor="w")
        self.lbl_group = ttk.Label(info_frame, text="Group: --")
        self.lbl_group.pack(anchor="w")
        self.lbl_status = ttk.Label(
            info_frame, text="Status: Inactive", foreground="red"
        )
        self.lbl_status.pack(anchor="w")

        # Check Schedule Button
        ttk.Button(
            info_frame, text="⟳ Refresh Schedule", command=self.check_schedule
        ).pack(pady=5, fill="x")

        # Attendance List
        list_frame = ttk.LabelFrame(right, text="Attendance", padding=(5, 5, 5, 0))
        list_frame.pack(fill=tk.BOTH, expand=True)
        self.tree_att = ttk.Treeview(
            list_frame, columns=("name", "status"), show="headings"
        )
        self.tree_att.heading("name", text="Student")
        self.tree_att.heading("status", text="Status")
        self.tree_att.column("status", width=80, anchor="center")
        self.tree_att.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.tree_att.tag_configure("present", foreground="green", background="#E8F5E9")

        # Action
        ttk.Button(right, text="Export CSV", command=self.export_csv).pack(
            fill="x", pady=10
        )

        # Initial Check
        self.check_schedule()
        self.update_video_loop()

    def check_schedule(self):
        # Auto-detect what the teacher should be teaching right now
        session = self.db.get_active_session_info(self.current_user["id"])

        if session:
            self.active_session = session
            self.lbl_course.config(text=f"Course: {session['course_name']}")
            self.lbl_group.config(text=f"Group: {session['group_name']}")
            self.lbl_status.config(text="Status: Ready", foreground="orange")
            self.refresh_att_list()
        else:
            self.active_session = None
            self.lbl_course.config(text="Course: No class scheduled")
            self.lbl_group.config(text="Group: --")
            self.lbl_status.config(text="Status: Off Duty", foreground="gray")
            for i in self.tree_att.get_children():
                self.tree_att.delete(i)

    def refresh_att_list(self):
        for i in self.tree_att.get_children():
            self.tree_att.delete(i)
        self.student_tree_map.clear()

        if not self.active_session:
            return

        gid = self.active_session["group_id"]
        cid = self.active_session["course_id"]

        students = self.db.get_students_by_group(gid)
        att_data = self.db.get_todays_attendance(cid, gid)

        for s in students:
            status = att_data.get(s.id, "ABSENT")
            tag = "present" if status == "PRESENT" else "absent"
            iid = self.tree_att.insert("", "end", values=(s.name, status), tags=(tag,))
            self.student_tree_map[s.id] = iid

    def start_session_camera(self):
        if not self.active_session:
            messagebox.showwarning("No Class", "No class is scheduled for right now.")
            return

        try:
            self.camera.start()
            self.btn_start["state"] = "disabled"
            self.btn_stop["state"] = "normal"
            self.is_session_active = True
            self.lbl_status.config(text="Status: Active Session", foreground="green")
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def stop_camera(self):
        # Always stop the hardware logic
        self.camera.stop()
        self.is_session_active = False

        # Only try to update the buttons/labels if they actually exist
        # (This prevents the crash during the login screen)
        if hasattr(self, "btn_start"):
            self.btn_start["state"] = "normal"
            self.btn_stop["state"] = "disabled"
            self.lbl_status.config(text="Status: Paused", foreground="orange")
            # Reset placeholder image
            if hasattr(self, "video_label"):
                self.video_label.configure(image=self.video_label.image)

    def update_video_loop(self):
        if not self.current_user or self.current_user.get("is_admin") == 1:
            return

        frame = self.camera.get_frame()
        if frame is not None:
            # Detection
            dets = self.vision.detect_and_identify(frame)
            draw = frame.copy()

            for sid, name, (t, r, b, l) in dets:
                color = (0, 255, 0) if sid else (255, 0, 0)
                cv2.rectangle(draw, (l, t), (r, b), color, 2)
                cv2.putText(
                    draw, name, (l, b + 20), cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2
                )

                # Logic: Mark Attendance if belongs to current group
                if self.is_session_active and self.active_session and sid:
                    # Check if student is in list (belongs to group)
                    if sid in self.student_tree_map:
                        cid = self.active_session["course_id"]
                        gid = self.active_session["group_id"]
                        if self.db.mark_attendance(sid, cid, gid):
                            # Update UI
                            iid = self.student_tree_map[sid]
                            self.tree_att.set(iid, "status", "PRESENT")
                            self.tree_att.item(iid, tags=("present",))

            img = ImageTk.PhotoImage(Image.fromarray(draw))
            self.video_label.configure(image=img)
            self.video_label.imgtk = img

        self.root.after(30, self.update_video_loop)

    def export_csv(self):
        if not self.active_session:
            return
        try:
            path = filedialog.asksaveasfilename(defaultextension=".csv")
            if path:
                with open(path, "w", newline="") as f:
                    w = csv.writer(f)
                    w.writerow(["Student", "Status", "Date", "Course", "Group"])
                    for iid in self.tree_att.get_children():
                        vals = self.tree_att.item(iid)["values"]
                        w.writerow(
                            [
                                vals[0],
                                vals[1],
                                datetime.now().date(),
                                self.active_session["course_name"],
                                self.active_session["group_name"],
                            ]
                        )
                messagebox.showinfo("Success", "Exported")
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def on_close(self):
        self.stop_camera()
        self.root.destroy()
