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
        right_frame = ttk.LabelFrame(paned, text="Step 2: Manage Students", padding="5")
        paned.add(right_frame, weight=3)

        # UI FIX: Pack Control Frame FIRST at BOTTOM so it sticks there
        ctrl_frame = ttk.Frame(right_frame)
        ctrl_frame.pack(side=tk.BOTTOM, fill="x", pady=5)

        # Controls
        ttk.Button(
            ctrl_frame, text="+ New Student", command=self.admin_add_student
        ).pack(side="left", padx=5)
        ttk.Button(
            ctrl_frame,
            text="🔗 Add Existing / Transfer",
            command=self.admin_link_existing_student,
        ).pack(side="left", padx=5)
        ttk.Button(
            ctrl_frame, text="📷 Upload Face", command=self.admin_upload_face
        ).pack(side="left", padx=5)
        ttk.Button(ctrl_frame, text="- Remove", command=self.admin_delete_student).pack(
            side="right", padx=5
        )

        # Student List (Takes all remaining space)
        list_frame = ttk.Frame(right_frame)
        list_frame.pack(side=tk.TOP, fill="both", expand=True)

        cols = ("roll", "name", "status")
        self.tree_students = ttk.Treeview(list_frame, columns=cols, show="headings")
        self.tree_students.heading("roll", text="ID")
        self.tree_students.column("roll", width=60)
        self.tree_students.heading("name", text="Student Name")
        self.tree_students.heading("status", text="Face Data")
        self.tree_students.tag_configure("registered", foreground="green")
        self.tree_students.tag_configure("unregistered", foreground="red")

        sb = ttk.Scrollbar(
            list_frame, orient=tk.VERTICAL, command=self.tree_students.yview
        )
        self.tree_students.configure(yscrollcommand=sb.set)
        sb.pack(side=tk.RIGHT, fill=tk.Y)
        self.tree_students.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.refresh_group_list()

    # --- LOGIC: GROUPS ---
    def refresh_group_list(self):
        for i in self.tree_groups.get_children():
            self.tree_groups.delete(i)
        for i in self.tree_students.get_children():
            self.tree_students.delete(i)
        self.admin_sel_group_id = None
        for g in self.db.get_all_groups():
            self.tree_groups.insert("", "end", values=(g.id, g.name))

    def on_group_sel(self, event):
        sel = self.tree_groups.selection()
        if not sel:
            return
        self.admin_sel_group_id = self.tree_groups.item(sel[0])["values"][0]
        self.refresh_student_list_for_group()

    def admin_add_group(self):
        name = simpledialog.askstring("New Group", "Group Name:")
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

        students = self.db.get_students_by_group(self.admin_sel_group_id)

        for s in students:
            status = "Registered" if s.encoding_path else "Unregistered"
            tag = "registered" if s.encoding_path else "unregistered"

            # FIX: We now explicitly set 'iid=s.id'.
            # This stores the Database ID as the row's hidden identifier.
            self.tree_students.insert(
                "", "end", iid=s.id, values=(s.roll_number, s.name, status), tags=(tag,)
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

    def admin_link_existing_student(self):
        """Allows Transferring (Move) or Copying (Add) a student to the current group."""
        if not self.admin_sel_group_id:
            messagebox.showwarning(
                "Select Group", "Please select a target group first."
            )
            return

        # 1. Get candidates (Students not in current group)
        all_students = self.db.get_all_students()
        candidates = [s for s in all_students if s.group_id != self.admin_sel_group_id]

        if not candidates:
            messagebox.showinfo("Info", "No students found in other groups.")
            return

        # 2. Build Popup
        top = tk.Toplevel(self.root)
        top.title("Add Existing Student")
        top.geometry("450x350")

        ttk.Label(top, text="Select Student:", font=("Helvetica", 10, "bold")).pack(
            pady=10
        )

        cols = ("name", "roll", "current_grp")
        tree = ttk.Treeview(top, columns=cols, show="headings")
        tree.heading("name", text="Name")
        tree.heading("roll", text="ID")
        tree.heading("current_grp", text="Current Group")
        tree.column("roll", width=50)
        tree.pack(fill="both", expand=True, padx=10, pady=5)

        for s in candidates:
            tree.insert(
                "", "end", iid=s.id, values=(s.name, s.roll_number, s.group_name)
            )

        # 3. Action Buttons
        btn_frame = ttk.Frame(top)
        btn_frame.pack(pady=15)

        def perform_action(action_type):
            sel = tree.selection()
            if not sel:
                return
            student_id = int(sel[0])

            success = False
            if action_type == "COPY":
                # Create a copy in this group
                success = self.db.copy_student_to_group(
                    student_id, self.admin_sel_group_id
                )
            elif action_type == "MOVE":
                # Remove from old group, move to this one
                success = self.db.move_student_to_group(
                    student_id, self.admin_sel_group_id
                )

            if success:
                self.refresh_student_list_for_group()
                # Reload global data to ensure FaceRecognizer knows about the new ID
                self.load_global_data()
                top.destroy()
            else:
                messagebox.showerror(
                    "Error", "Operation failed (Check if ID is unique)."
                )

        # COPY BUTTON (Green) - Keeps student in old group AND adds to new one
        btn_copy = tk.Button(
            btn_frame,
            text="✚ Copy to Group",
            bg="#E8F5E9",
            command=lambda: perform_action("COPY"),
        )
        btn_copy.pack(side="left", padx=10)

        # TRANSFER BUTTON (Orange) - Removes from old group
        btn_move = tk.Button(
            btn_frame,
            text="➜ Transfer / Move",
            bg="#FFF3E0",
            command=lambda: perform_action("MOVE"),
        )
        btn_move.pack(side="left", padx=10)

    def admin_upload_face(self):
        sel = self.tree_students.selection()
        if not sel:
            return
        item = self.tree_students.item(sel[0])
        roll, name = item["values"][0], item["values"][1]

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

    def admin_delete_student(self):
        sel = self.tree_students.selection()
        if not sel:
            messagebox.showwarning("Selection", "Please select a student to remove.")
            return

        # FIX: The selection 'sel[0]' is now the actual Database ID (because we set iid=s.id above)
        student_id = sel[0]

        if messagebox.askyesno("Confirm", "Remove this student from the group?"):
            self.db.delete_student(student_id)
            self.refresh_student_list_for_group()
            # Reload global data so face recognition stops looking for this deleted student
            self.load_global_data()

    # --- TAB 3: ACADEMIC (Timetable links Groups now) ---

    def _build_admin_academic_tab(self, parent):
        frame = ttk.Frame(parent, padding="10")
        frame.pack(fill="both", expand=True)

        # COL 1: Select Teacher (Context)
        # Note: Even if the direct link is weak in the DB, selecting a teacher
        # helps us visualize who we are scheduling for (conceptually).
        col1 = ttk.LabelFrame(frame, text="1. Select Teacher", padding="5")
        col1.pack(side="left", fill="both", expand=True)
        self.tree_teachers = ttk.Treeview(
            col1, columns=("id", "name"), show="headings", height=10
        )
        self.tree_teachers.heading("id", text="ID")
        self.tree_teachers.heading("name", text="Name")
        self.tree_teachers.column("id", width=30)
        self.tree_teachers.pack(fill="both", expand=True)
        self.tree_teachers.bind("<<TreeviewSelect>>", self.on_teacher_sel)

        # COL 2: Select Group (REPLACED "Select Course")
        col2 = ttk.LabelFrame(frame, text="2. Select Group", padding="5")
        col2.pack(side="left", fill="both", expand=True)
        self.tree_academic_groups = ttk.Treeview(
            col2, columns=("id", "name"), show="headings", height=10
        )
        self.tree_academic_groups.heading("id", text="ID")
        self.tree_academic_groups.heading("name", text="Group Name")
        self.tree_academic_groups.column("id", width=30)
        self.tree_academic_groups.pack(fill="both", expand=True, pady=(0, 5))
        self.tree_academic_groups.bind("<<TreeviewSelect>>", self.on_academic_group_sel)
        # No "Add Course" button anymore

        # COL 3: Timetable (For Selected Group)
        col3 = ttk.LabelFrame(frame, text="3. Timetable", padding="5")
        col3.pack(side="left", fill="both", expand=True)
        self.tree_timetable = ttk.Treeview(
            col3, columns=("day", "time"), show="headings", height=10
        )
        self.tree_timetable.heading("day", text="Day")
        self.tree_timetable.heading("time", text="Time")
        self.tree_timetable.column("day", width=50)
        self.tree_timetable.pack(fill="both", expand=True, pady=(0, 5))

        # Timetable Controls (Simplified: No Group Dropdown)
        t_ctrl = ttk.Frame(col3)
        t_ctrl.pack(fill="x")

        self.combo_tt_day = ttk.Combobox(
            t_ctrl,
            values=["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"],
            state="readonly",
            width=10,
        )
        self.combo_tt_day.current(0)
        self.combo_tt_day.pack(side="left", padx=2)

        self.ent_start = ttk.Entry(t_ctrl, width=6)
        self.ent_start.insert(0, "09:00")
        self.ent_start.pack(side="left", padx=2)
        ttk.Label(t_ctrl, text="-").pack(side="left")
        self.ent_end = ttk.Entry(t_ctrl, width=6)
        self.ent_end.insert(0, "10:00")
        self.ent_end.pack(side="left", padx=2)

        ttk.Button(t_ctrl, text="+ Add Slot", command=self.add_slot).pack(
            side="left", padx=5
        )
        ttk.Button(t_ctrl, text="- Del", command=self.del_slot).pack(side="right")

        self.refresh_teacher_list()

    def refresh_teacher_list(self):
        for i in self.tree_teachers.get_children():
            self.tree_teachers.delete(i)
        for t in self.db.get_all_teachers():
            self.tree_teachers.insert("", "end", values=(t["id"], t["full_name"]))

    def on_teacher_sel(self, e):
        # When teacher is selected, show ALL groups (or filtered groups if you add that logic later)
        self.refresh_academic_groups()
        self.clear_timetable_view()

    def refresh_academic_groups(self):
        for i in self.tree_academic_groups.get_children():
            self.tree_academic_groups.delete(i)
        # Display all groups so the teacher can pick which one they are scheduling
        for g in self.db.get_all_groups():
            self.tree_academic_groups.insert("", "end", values=(g.id, g.name))

    def on_academic_group_sel(self, e):
        sel = self.tree_academic_groups.selection()
        if not sel:
            return
        # Store selected Group ID instead of Course ID
        self.admin_sel_group_id_academic = self.tree_academic_groups.item(sel[0])[
            "values"
        ][0]
        self.refresh_timetable()

    def refresh_timetable(self):
        self.clear_timetable_view()
        if (
            not hasattr(self, "admin_sel_group_id_academic")
            or not self.admin_sel_group_id_academic
        ):
            return

        # We pass 0 as teacher_id for now, just fetching by group
        slots = self.db.get_timetable_for_teacher_and_group(
            0, self.admin_sel_group_id_academic
        )
        days = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]

        # Handle the fact that row factory returns dict-like objects
        for s in slots:
            # Check if using object or dict based on your persistence setup
            # Assuming dict access from row factory
            s_id = s["id"]
            day_idx = s["day_of_week"]
            time_str = f"{s['start_time']}-{s['end_time']}"
            self.tree_timetable.insert(
                "", "end", iid=s_id, values=(days[day_idx], time_str)
            )

    def clear_timetable_view(self):
        for i in self.tree_timetable.get_children():
            self.tree_timetable.delete(i)

    def add_slot(self):
        if (
            not hasattr(self, "admin_sel_group_id_academic")
            or not self.admin_sel_group_id_academic
        ):
            messagebox.showwarning("Select", "Please select a group first.")
            return

        day = self.combo_tt_day.current()
        start, end = self.ent_start.get(), self.ent_end.get()

        if self.db.add_timetable_slot_direct(
            self.admin_sel_group_id_academic, day, start, end
        ):
            self.refresh_timetable()
        else:
            messagebox.showerror("Error", "Could not add slot.")

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

        # --- Header ---
        h_frame = ttk.Frame(self.root, padding="10")
        h_frame.pack(side="top", fill="x")
        ttk.Label(
            h_frame,
            text=f"Teacher: {self.current_user['full_name']}",
            style="Header.TLabel",
        ).pack(side="left")
        ttk.Button(h_frame, text="Logout", command=self.logout).pack(side="right")

        # --- Notebook (Tabs) ---
        notebook = ttk.Notebook(self.root)
        notebook.pack(fill="both", expand=True, padx=10, pady=5)

        # Tab 1: Live Class
        self.tab_live = ttk.Frame(notebook)
        notebook.add(self.tab_live, text="Live Class")
        self._build_live_tab(self.tab_live)

        # Tab 2: Manual Edit (Past Classes)
        self.tab_manual = ttk.Frame(notebook)
        notebook.add(self.tab_manual, text="Manual / Past Records")
        self._build_manual_tab(self.tab_manual)

    # ------------------------------------------
    # TAB 1: LIVE CLASS (Logic Moved Here)
    # ------------------------------------------
    def _build_live_tab(self, parent):
        paned = ttk.PanedWindow(parent, orient=tk.HORIZONTAL)
        paned.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        left = ttk.Frame(paned, padding=5)
        right = ttk.Frame(paned, padding=5, relief=tk.RIDGE)
        paned.add(left, weight=2)
        paned.add(right, weight=1)

        # Camera Section
        vid_frame = ttk.LabelFrame(left, text="Live Camera", padding=5)
        vid_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        self.video_label = ttk.Label(vid_frame)
        self.video_label.pack(fill=tk.BOTH, expand=True)
        # Placeholder image
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

        # Session Info Section
        info_frame = ttk.LabelFrame(right, text="Current Session", padding=10)
        info_frame.pack(fill=tk.X, pady=(0, 10))

        self.lbl_group = ttk.Label(info_frame, text="Group: --")
        self.lbl_group.pack(anchor="w")
        self.lbl_status = ttk.Label(
            info_frame, text="Status: Inactive", foreground="red"
        )
        self.lbl_status.pack(anchor="w")

        ttk.Button(
            info_frame, text="⟳ Refresh Schedule", command=self.check_schedule
        ).pack(pady=5, fill="x")

        # Attendance List (With Double-Click Override)
        list_frame = ttk.LabelFrame(
            right, text="Attendance (Double-Click to Toggle)", padding=(5, 5, 5, 0)
        )
        list_frame.pack(fill=tk.BOTH, expand=True)

        self.tree_att = ttk.Treeview(
            list_frame, columns=("name", "status"), show="headings"
        )
        self.tree_att.heading("name", text="Student")
        self.tree_att.heading("status", text="Status")
        self.tree_att.column("status", width=80, anchor="center")
        self.tree_att.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # Tags for colors
        self.tree_att.tag_configure("PRESENT", foreground="green", background="#E8F5E9")
        self.tree_att.tag_configure("ABSENT", foreground="red", background="#FFEBEE")

        # BIND DOUBLE CLICK
        self.tree_att.bind("<Double-1>", self.on_live_list_double_click)

        # Export
        ttk.Button(right, text="Export CSV", command=self.export_csv).pack(
            fill="x", pady=10
        )

        # Init
        self.check_schedule()
        self.update_video_loop()

    def on_live_list_double_click(self, event):
        """Toggle status between PRESENT and ABSENT on double click."""
        if not self.active_session:
            return

        item_id = self.tree_att.identify_row(event.y)
        if not item_id:
            return

        # Get student ID from our map (reverse lookup needed or store it in iid)
        # Note: In refresh_att_list, we stored map[student_id] = iid.
        # Let's reverse find the student_id
        student_id = None
        for sid, iid in self.student_tree_map.items():
            if iid == item_id:
                student_id = sid
                break

        if student_id:
            group_id = self.active_session["group_id"]
            # Toggle in DB
            new_status = self.db.toggle_attendance_status(student_id, group_id)
            # Update UI
            self.tree_att.set(item_id, "status", new_status)
            self.tree_att.item(item_id, tags=(new_status,))

    # ------------------------------------------
    # TAB 2: MANUAL EDIT (New Feature)
    # ------------------------------------------
    def _build_manual_tab(self, parent):
        # Control Bar
        ctrl_frame = ttk.Frame(parent, padding=10)
        ctrl_frame.pack(fill="x")

        ttk.Label(ctrl_frame, text="Date (YYYY-MM-DD):").pack(side="left")
        self.ent_manual_date = ttk.Entry(ctrl_frame, width=12)
        self.ent_manual_date.insert(0, datetime.now().strftime("%Y-%m-%d"))
        self.ent_manual_date.pack(side="left", padx=5)

        # Group Selector (Simple Combobox for Teacher's Groups)
        ttk.Label(ctrl_frame, text="Group:").pack(side="left", padx=(10, 0))
        self.cb_manual_group = ttk.Combobox(ctrl_frame, state="readonly", width=15)

        # Populate Groups (Just all groups for now for simplicity, or filter by teacher)
        groups = self.db.get_all_groups()
        group_names = [g.name for g in groups]
        self.cb_manual_group["values"] = group_names
        if group_names:
            self.cb_manual_group.current(0)
        self.cb_manual_group.pack(side="left", padx=5)

        # Map names to IDs
        self.group_name_map = {g.name: g.id for g in groups}

        ttk.Button(ctrl_frame, text="Load List", command=self.load_manual_list).pack(
            side="left", padx=10
        )
        ttk.Button(
            ctrl_frame, text="💾 Save Changes", command=self.save_manual_list
        ).pack(side="right")

        # Table
        self.tree_manual = ttk.Treeview(
            parent, columns=("id", "name", "status"), show="headings"
        )
        self.tree_manual.heading("id", text="Roll No")
        self.tree_manual.heading("name", text="Name")
        self.tree_manual.heading("status", text="Status (Click to Toggle)")

        self.tree_manual.column("id", width=80)
        self.tree_manual.column("status", width=100)

        self.tree_manual.pack(fill="both", expand=True, padx=10, pady=10)

        self.tree_manual.tag_configure("PRESENT", foreground="green")
        self.tree_manual.tag_configure("ABSENT", foreground="red")

        # Bind Click to toggle
        self.tree_manual.bind("<ButtonRelease-1>", self.on_manual_click)

    def load_manual_list(self):
        date_str = self.ent_manual_date.get()
        group_name = self.cb_manual_group.get()
        if not group_name:
            return

        group_id = self.group_name_map[group_name]

        # 1. Get all students in group
        students = self.db.get_students_by_group(group_id)

        # 2. Get existing attendance for this date
        existing_att = self.db.get_session_attendance(group_id, date_str)

        # 3. Clear Tree
        for i in self.tree_manual.get_children():
            self.tree_manual.delete(i)

        # 4. Populate
        for s in students:
            # Default to ABSENT if no record, or use existing status
            status = existing_att.get(s.id, "ABSENT")
            self.tree_manual.insert(
                "",
                "end",
                iid=s.id,
                values=(s.roll_number, s.name, status),
                tags=(status,),
            )

    def on_manual_click(self, event):
        region = self.tree_manual.identify("region", event.x, event.y)
        if region == "cell":
            # Check if clicked on Status column (index 2) or generally the row
            # Treeview column detection is tricky, so we'll just toggle row selection
            item_id = self.tree_manual.focus()
            if not item_id:
                return

            # Toggle Status
            curr_vals = self.tree_manual.item(item_id)["values"]
            # values comes back as a list. Name is index 1, Status index 2
            curr_status = curr_vals[2]

            new_status = "ABSENT" if curr_status == "PRESENT" else "PRESENT"

            # Update UI
            self.tree_manual.set(item_id, "status", new_status)
            self.tree_manual.item(item_id, tags=(new_status,))

    def save_manual_list(self):
        date_str = self.ent_manual_date.get()
        group_name = self.cb_manual_group.get()
        group_id = self.group_name_map[group_name]

        # Build map {student_id: status}
        att_map = {}
        for item_id in self.tree_manual.get_children():
            # item_id is the student_id (we set iid=s.id)
            val = self.tree_manual.item(item_id)["values"][2]  # Status column
            att_map[int(item_id)] = val

        if self.db.save_manual_attendance(group_id, date_str, att_map):
            messagebox.showinfo("Success", "Attendance saved successfully.")
        else:
            messagebox.showerror("Error", "Failed to save attendance.")

    def check_schedule(self):
        # Auto-detect what the teacher should be teaching right now
        session = self.db.get_active_session_info(self.current_user["id"])

        if session:
            self.active_session = session

            # REMOVED: self.lbl_course.config(...) references

            self.lbl_group.config(
                text=f"Active Group: {session['group_name']}",
                font=("Helvetica", 12, "bold"),
            )
            self.lbl_status.config(text="Status: Ready", foreground="orange")
            self.refresh_att_list()
        else:
            self.active_session = None

            # REMOVED: self.lbl_course.config(...) references

            self.lbl_group.config(text="No active class")
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
        # Assuming course_id is not strictly needed for fetch, or pass 0
        students = self.db.get_students_by_group(gid)
        att_data = self.db.get_todays_attendance(0, gid)  # 0 = course_id ignored

        for s in students:
            # Default to ABSENT if not found
            status = att_data.get(s.id, "ABSENT")

            # INSERT with Correct Tag
            iid = self.tree_att.insert(
                "", "end", values=(s.name, status), tags=(status,)
            )
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
        # 1. Always stop the hardware camera logic first
        if hasattr(self, "camera"):
            self.camera.stop()
        
        self.is_session_active = False

        # 2. Only update UI buttons if they exist AND are valid widgets
        try:
            # Check if button exists in memory AND is a valid visible widget
            if hasattr(self, "btn_start") and self.btn_start.winfo_exists():
                self.btn_start["state"] = "normal"
            
            if hasattr(self, "btn_stop") and self.btn_stop.winfo_exists():
                self.btn_stop["state"] = "disabled"
                
            if hasattr(self, "lbl_status") and self.lbl_status.winfo_exists():
                self.lbl_status.config(text="Status: Paused", foreground="orange")
                
            if hasattr(self, "video_label") and self.video_label.winfo_exists():
                # Reset placeholder image
                self.video_label.configure(image=self.video_label.image)

        except Exception:
            # If widgets are already destroyed or invalid, we just ignore it
            pass

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
                    w.writerow(
                        ["Student", "Status", "Date", "Group"]
                    )  # Removed Course Column
                    for iid in self.tree_att.get_children():
                        vals = self.tree_att.item(iid)["values"]
                        w.writerow(
                            [
                                vals[0],
                                vals[1],
                                datetime.now().date(),
                                self.active_session["group_name"],
                            ]
                        )
                messagebox.showinfo("Success", "Exported")
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def on_close(self):
        self.stop_camera()
        self.root.destroy()
