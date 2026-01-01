import tkinter as tk
from tkinter import ttk, filedialog, messagebox, simpledialog
from PIL import Image, ImageTk
import cv2
import csv
from datetime import datetime
import time
from src.hardware import CameraManager
from src.persistence import DatabaseManager
from src.vision import FaceRecognizer

class AutoAttendApp:
    def __init__(self, root):
        self.root = root
        self.root.title("AutoAttend - School Management System")
        self.root.geometry("1200x800")

        self.prev_frame_time = 0
        self.new_frame_time = 0

        self.db = DatabaseManager()
        self.camera = CameraManager()
        self.vision = FaceRecognizer()
        
        self.load_global_data()
        
        self.current_user = None
        self.active_session = None
        self.is_session_active = False
        self.student_tree_map = {}
        
        # Admin Selection States
        self.admin_sel_teacher_id = None
        self.admin_sel_group_id = None
        
        self._setup_styles()
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)
        self.show_login_screen()

    def load_global_data(self):
        try:
            all_students = self.db.get_all_students()
            valid_students = [s for s in all_students if s.encoding_path]
            self.vision.load_encodings(valid_students)
        except Exception as e:
            print(f"Vision Load Warning: {e}")

    def _setup_styles(self):
        style = ttk.Style()
        style.configure("Title.TLabel", font=("Helvetica", 24, "bold"))
        style.configure("Header.TLabel", font=("Helvetica", 14, "bold"))
        style.configure("SubHeader.TLabel", font=("Helvetica", 11, "bold"))

    def _clear_window(self):
        for widget in self.root.winfo_children():
            widget.destroy()

    # --- LOGIN & AUTH ---
    def show_login_screen(self):
        self.stop_camera()
        self._clear_window()
        
        login_frame = ttk.Frame(self.root, padding="30", relief="ridge")
        login_frame.place(relx=0.5, rely=0.5, anchor="center")
        
        ttk.Label(login_frame, text="AutoAttend Login", style="Title.TLabel").pack(pady=20)
        
        ttk.Label(login_frame, text="Username:").pack(anchor="w")
        self.username_var = tk.StringVar()
        user_entry = ttk.Entry(login_frame, textvariable=self.username_var, width=30)
        user_entry.pack(pady=5)
        user_entry.bind("<Return>", lambda event: self.perform_login())
        
        ttk.Label(login_frame, text="Password:").pack(anchor="w")
        self.password_var = tk.StringVar()
        pass_entry = ttk.Entry(login_frame, textvariable=self.password_var, show="*", width=30)
        pass_entry.pack(pady=5)
        pass_entry.bind("<Return>", lambda event: self.perform_login())
        
        btn_frame = ttk.Frame(login_frame)
        btn_frame.pack(pady=20, fill="x")
        
        ttk.Button(btn_frame, text="Login", command=self.perform_login).pack(side="left", fill="x", expand=True, padx=5)
        ttk.Button(btn_frame, text="Register Teacher", command=self.register_teacher_popup).pack(side="right", fill="x", expand=True, padx=5)
        
        user_entry.focus()

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
            messagebox.showerror("Login Failed", "Invalid credentials")

    def register_teacher_popup(self):
        username = simpledialog.askstring("Register", "Username:")
        if not username: return
        password = simpledialog.askstring("Register", "Password:", show="*")
        if not password: return
        fullname = simpledialog.askstring("Register", "Full Name:")
        self.db.register_user(username, password, fullname)

    def logout(self):
        self.stop_camera()
        self.current_user = None
        self.active_session = None
        self.show_login_screen()

    # --- ADMIN DASHBOARD ---
    def build_admin_dashboard(self):
        self._clear_window()
        header = ttk.Frame(self.root, padding="10")
        header.pack(fill="x")
        
        ttk.Label(header, text="ADMIN DASHBOARD", style="Header.TLabel", foreground="red").pack(side="left")
        ttk.Button(header, text="Logout", command=self.logout).pack(side="right")
        
        notebook = ttk.Notebook(self.root)
        notebook.pack(fill="both", expand=True, padx=10, pady=10)
        
        self.tab_people = ttk.Frame(notebook)
        notebook.add(self.tab_people, text="1. Groups & Students")
        self._build_admin_people_tab(self.tab_people)
        
        self.tab_academic = ttk.Frame(notebook)
        notebook.add(self.tab_academic, text="2. Teacher Schedules") 
        self._build_admin_academic_tab(self.tab_academic)

    def _build_admin_people_tab(self, parent):
        paned = ttk.PanedWindow(parent, orient=tk.HORIZONTAL)
        paned.pack(fill="both", expand=True, padx=5, pady=5)
        
        # Left: Groups
        left_frame = ttk.LabelFrame(paned, text="Step 1: Select Group", padding="5")
        paned.add(left_frame, weight=1)
        
        self.tree_groups = ttk.Treeview(left_frame, columns=("id", "name"), show="headings")
        self.tree_groups.heading("id", text="ID")
        self.tree_groups.column("id", width=40)
        self.tree_groups.heading("name", text="Group Name")
        self.tree_groups.pack(fill="both", expand=True)
        self.tree_groups.bind("<<TreeviewSelect>>", self.on_group_sel)
        
        btn_g_frame = ttk.Frame(left_frame)
        btn_g_frame.pack(fill="x", pady=5)
        ttk.Button(btn_g_frame, text="+ New Group", command=self.admin_add_group).pack(side="left", fill="x", expand=True, padx=2)
        ttk.Button(btn_g_frame, text="- Delete Group", command=self.admin_delete_group).pack(side="right", fill="x", expand=True, padx=2)
        
        # Right: Students
        right_frame = ttk.LabelFrame(paned, text="Step 2: Manage Students", padding="5")
        paned.add(right_frame, weight=3)
        
        ctrl_frame = ttk.Frame(right_frame)
        ctrl_frame.pack(side=tk.BOTTOM, fill="x", pady=5)
        
        ttk.Button(ctrl_frame, text="+ New Student", command=self.admin_add_student).pack(side="left", padx=5)
        ttk.Button(ctrl_frame, text="🔗 Add Existing / Transfer", command=self.admin_link_existing_student).pack(side="left", padx=5)
        ttk.Button(ctrl_frame, text="📷 Upload Face", command=self.admin_upload_face).pack(side="left", padx=5)
        ttk.Button(ctrl_frame, text="- Remove", command=self.admin_delete_student).pack(side="right", padx=5)
        
        list_frame = ttk.Frame(right_frame)
        list_frame.pack(side=tk.TOP, fill="both", expand=True)
        
        cols = ("roll", "name", "status")
        self.tree_students = ttk.Treeview(list_frame, columns=cols, show="headings")
        self.tree_students.heading("roll", text="ID")
        self.tree_students.column("roll", width=60)
        self.tree_students.heading("name", text="Student Name")
        self.tree_students.heading("status", text="Face Data")
        
        self.tree_students.tag_configure('registered', foreground='green')
        self.tree_students.tag_configure('unregistered', foreground='red')
        
        sb = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.tree_students.yview)
        self.tree_students.configure(yscrollcommand=sb.set)
        sb.pack(side=tk.RIGHT, fill=tk.Y)
        self.tree_students.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        self.refresh_group_list()

    def refresh_group_list(self):
        for i in self.tree_groups.get_children(): self.tree_groups.delete(i)
        for i in self.tree_students.get_children(): self.tree_students.delete(i)
        self.admin_sel_group_id = None
        for g in self.db.get_all_groups():
            self.tree_groups.insert("", "end", values=(g.id, g.name))

    def on_group_sel(self, event):
        sel = self.tree_groups.selection()
        if not sel: return
        self.admin_sel_group_id = self.tree_groups.item(sel[0])['values'][0]
        self.refresh_student_list_for_group()

    def admin_add_group(self):
        name = simpledialog.askstring("New Group", "Group Name:")
        if name:
            if self.db.add_group(name):
                self.refresh_group_list()
                if hasattr(self, 'combo_all_groups'): self.refresh_all_groups_combo()
            else:
                messagebox.showerror("Error", "Group exists or invalid.")

    def admin_delete_group(self):
        if not self.admin_sel_group_id: return
        if messagebox.askyesno("Confirm", "Delete Group? All students in it will be deleted."):
            self.db.delete_group(self.admin_sel_group_id)
            self.refresh_group_list()
            if hasattr(self, 'combo_all_groups'): self.refresh_all_groups_combo()

    def refresh_student_list_for_group(self):
        for i in self.tree_students.get_children(): self.tree_students.delete(i)
        if not self.admin_sel_group_id: return
        
        students = self.db.get_students_by_group(self.admin_sel_group_id)
        for s in students:
            status = "Registered" if s.encoding_path else "Unregistered"
            tag = "registered" if s.encoding_path else "unregistered"
            self.tree_students.insert("", "end", iid=s.id, values=(s.roll_number, s.name, status), tags=(tag,))

    def admin_add_student(self):
        if not self.admin_sel_group_id:
            messagebox.showwarning("Warning", "Please select a group on the left first.")
            return
        next_roll = self.db.generate_next_roll_number()
        name = simpledialog.askstring("Add Student", f"Auto-ID: {next_roll}\nName:")
        if name:
            if self.db.add_student(name, next_roll, self.admin_sel_group_id):
                self.refresh_student_list_for_group()

    def admin_link_existing_student(self):
        if not self.admin_sel_group_id:
            messagebox.showwarning("Select Group", "Please select a target group first.")
            return
        
        all_students = self.db.get_all_students()
        candidates = [s for s in all_students if s.group_id != self.admin_sel_group_id]
        
        if not candidates:
            messagebox.showinfo("Info", "No students found in other groups.")
            return

        top = tk.Toplevel(self.root)
        top.title("Add Existing Student")
        top.geometry("450x350")
        
        ttk.Label(top, text="Select Student:", font=("Helvetica", 10, "bold")).pack(pady=10)
        
        cols = ("name", "roll", "current_grp")
        tree = ttk.Treeview(top, columns=cols, show="headings")
        tree.heading("name", text="Name")
        tree.heading("roll", text="ID")
        tree.heading("current_grp", text="Current Group")
        tree.column("roll", width=50)
        tree.pack(fill="both", expand=True, padx=10, pady=5)
        
        for s in candidates:
            tree.insert("", "end", iid=s.id, values=(s.name, s.roll_number, s.group_name))
            
        btn_frame = ttk.Frame(top)
        btn_frame.pack(pady=15)
        
        def perform_action(action_type):
            sel = tree.selection()
            if not sel: return
            student_id = int(sel[0])
            success = False
            
            if action_type == "COPY":
                success = self.db.copy_student_to_group(student_id, self.admin_sel_group_id)
            elif action_type == "MOVE":
                success = self.db.move_student_to_group(student_id, self.admin_sel_group_id)
                
            if success:
                self.refresh_student_list_for_group()
                self.load_global_data()
                top.destroy()
            else:
                messagebox.showerror("Error", "Operation failed (Check if ID is unique).")

        btn_copy = tk.Button(btn_frame, text="✚ Copy to Group", bg="#E8F5E9", command=lambda: perform_action("COPY"))
        btn_copy.pack(side="left", padx=10)
        
        btn_move = tk.Button(btn_frame, text="➜ Transfer / Move", bg="#FFF3E0", command=lambda: perform_action("MOVE"))
        btn_move.pack(side="left", padx=10)

    def admin_upload_face(self):
        sel = self.tree_students.selection()
        if not sel: return
        item = self.tree_students.item(sel[0])
        roll, name = item['values'][0], item['values'][1]
        
        all_s = self.db.get_students_by_group(self.admin_sel_group_id)
        student = next((s for s in all_s if str(s.roll_number) == str(roll)), None)
        
        files = filedialog.askopenfilenames(title=f"Photos for {name}", filetypes=[("Images", "*.jpg *.png *.jpeg")])
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
        student_id = sel[0]
        if messagebox.askyesno("Confirm", "Remove this student from the group?"):
            self.db.delete_student(student_id)
            self.refresh_student_list_for_group()
            self.load_global_data()

    # --- ACADEMIC / TIMETABLE TAB ---
    def _build_admin_academic_tab(self, parent):
        self.db.init_teacher_group_link()
        frame = ttk.Frame(parent, padding="10")
        frame.pack(fill="both", expand=True)
        
        # 1. Teachers
        col1 = ttk.LabelFrame(frame, text="1. Select Teacher", padding="5")
        col1.pack(side="left", fill="both", expand=True)
        self.tree_teachers = ttk.Treeview(col1, columns=("id", "name"), show="headings")
        self.tree_teachers.heading("id", text="ID")
        self.tree_teachers.heading("name", text="Name")
        self.tree_teachers.column("id", width=30)
        self.tree_teachers.pack(fill="both", expand=True)
        self.tree_teachers.bind("<<TreeviewSelect>>", self.on_teacher_sel)
        
        # 2. Assigned Groups
        col2 = ttk.LabelFrame(frame, text="2. Assigned Groups", padding="5")
        col2.pack(side="left", fill="both", expand=True, padx=5)
        self.tree_academic_groups = ttk.Treeview(col2, columns=("id", "name"), show="headings")
        self.tree_academic_groups.heading("id", text="ID")
        self.tree_academic_groups.heading("name", text="Name")
        self.tree_academic_groups.column("id", width=30)
        self.tree_academic_groups.pack(side="top", fill="both", expand=True)
        self.tree_academic_groups.bind("<<TreeviewSelect>>", self.on_academic_group_sel)
        
        grp_ctrl = ttk.Frame(col2)
        grp_ctrl.pack(side="bottom", fill="x", pady=5)
        ttk.Label(grp_ctrl, text="Assign New Group:").pack(fill="x")
        self.combo_all_groups = ttk.Combobox(grp_ctrl, state="readonly")
        self.combo_all_groups.pack(fill="x", pady=2)
        
        btn_frame = ttk.Frame(grp_ctrl)
        btn_frame.pack(fill="x")
        ttk.Button(btn_frame, text="⬇ Assign", command=self.admin_assign_group).pack(side="left", fill="x", expand=True)
        ttk.Button(btn_frame, text="❌ Remove", command=self.admin_remove_group).pack(side="right", fill="x", expand=True)
        
        # 3. Timetable
        col3 = ttk.LabelFrame(frame, text="3. Timetable", padding="5")
        col3.pack(side="left", fill="both", expand=True)
        self.tree_timetable = ttk.Treeview(col3, columns=("day", "time"), show="headings")
        self.tree_timetable.heading("day", text="Day")
        self.tree_timetable.heading("time", text="Time")
        self.tree_timetable.column("day", width=40)
        self.tree_timetable.pack(fill="both", expand=True)
        
        t_ctrl = ttk.Frame(col3)
        t_ctrl.pack(fill="x", pady=5)
        self.combo_tt_day = ttk.Combobox(t_ctrl, values=["Mon", "Tue", "Wed", "Thu", "Fri"], width=5, state="readonly")
        self.combo_tt_day.current(0)
        self.combo_tt_day.pack(side="left")
        
        self.ent_start = ttk.Entry(t_ctrl, width=5)
        self.ent_start.insert(0, "09:00")
        self.ent_start.pack(side="left", padx=2)
        
        self.ent_end = ttk.Entry(t_ctrl, width=5)
        self.ent_end.insert(0, "10:00")
        self.ent_end.pack(side="left", padx=2)
        
        ttk.Button(t_ctrl, text="+", width=3, command=self.add_slot).pack(side="left", padx=5)
        ttk.Button(t_ctrl, text="-", width=3, command=self.del_slot).pack(side="right")
        
        self.refresh_teacher_list()
        self.refresh_all_groups_combo()

    def refresh_teacher_list(self):
        for i in self.tree_teachers.get_children(): self.tree_teachers.delete(i)
        for t in self.db.get_all_teachers():
            self.tree_teachers.insert("", "end", values=(t['id'], t['full_name']))

    def refresh_all_groups_combo(self):
        groups = self.db.get_all_groups()
        self.combo_all_groups['values'] = [f"{g.id}: {g.name}" for g in groups]
        if groups: self.combo_all_groups.current(0)

    def on_teacher_sel(self, e):
        sel = self.tree_teachers.selection()
        if not sel: return
        self.admin_sel_teacher_id = self.tree_teachers.item(sel[0])['values'][0]
        self.refresh_assigned_groups()
        self.clear_timetable_view()

    def refresh_assigned_groups(self):
        for i in self.tree_academic_groups.get_children(): self.tree_academic_groups.delete(i)
        if not hasattr(self, 'admin_sel_teacher_id'): return
        
        assigned_groups = self.db.get_groups_for_teacher(self.admin_sel_teacher_id)
        for g in assigned_groups:
            self.tree_academic_groups.insert("", "end", values=(g['id'], g['name']))

    def admin_assign_group(self):
        if not hasattr(self, 'admin_sel_teacher_id'):
            messagebox.showwarning("Warning", "Select a teacher first.")
            return
        sel_str = self.combo_all_groups.get()
        if not sel_str: return
        group_id = int(sel_str.split(":")[0])
        
        if self.db.assign_teacher_to_group(self.admin_sel_teacher_id, group_id):
            self.refresh_assigned_groups()
        else:
            messagebox.showerror("Error", "Could not assign group.")

    def admin_remove_group(self):
        if not hasattr(self, 'admin_sel_teacher_id'): return
        sel = self.tree_academic_groups.selection()
        if not sel:
            messagebox.showwarning("Warning", "Select an assigned group to remove.")
            return
        group_id = self.tree_academic_groups.item(sel[0])['values'][0]
        self.db.remove_teacher_from_group(self.admin_sel_teacher_id, group_id)
        self.refresh_assigned_groups()
        self.clear_timetable_view()

    def on_academic_group_sel(self, e):
        sel = self.tree_academic_groups.selection()
        if not sel: return
        self.admin_sel_group_id_academic = self.tree_academic_groups.item(sel[0])['values'][0]
        self.refresh_timetable()

    def refresh_timetable(self):
        self.clear_timetable_view()
        if not hasattr(self, 'admin_sel_group_id_academic') or not self.admin_sel_group_id_academic:
            return
        
        slots = self.db.get_timetable_for_teacher_and_group(self.admin_sel_teacher_id, self.admin_sel_group_id_academic)
        
        days = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
        for s in slots:
            s_id = s['id']
            day_idx = s['day_of_week']
            time_str = f"{s['start_time']} - {s['end_time']}"
            self.tree_timetable.insert("", "end", iid=s_id, values=(days[day_idx], time_str))

    def clear_timetable_view(self):
        for i in self.tree_timetable.get_children(): self.tree_timetable.delete(i)

    def add_slot(self):
        if not hasattr(self, 'admin_sel_group_id_academic') or not self.admin_sel_group_id_academic:
            messagebox.showwarning("Select", "Please select a group (Step 2) first.")
            return
        if not hasattr(self, 'admin_sel_teacher_id') or not self.admin_sel_teacher_id:
            messagebox.showwarning("Select", "Please select a teacher (Step 1) first.")
            return
            
        day = self.combo_tt_day.current()
        start, end = self.ent_start.get(), self.ent_end.get()
        
        if self.db.add_timetable_slot_direct(self.admin_sel_teacher_id, self.admin_sel_group_id_academic, day, start, end):
            self.refresh_timetable()
            messagebox.showinfo("Success", "Slot added successfully.")
        else:
            messagebox.showerror("Error", "Could not add slot.")

    def del_slot(self):
        sel = self.tree_timetable.selection()
        if sel:
            self.db.delete_timetable_slot(sel[0])
            self.refresh_timetable()

    # --- TEACHER DASHBOARD ---
    def build_teacher_dashboard(self):
        self._clear_window()
        h_frame = ttk.Frame(self.root, padding="10")
        h_frame.pack(side="top", fill="x")
        ttk.Label(h_frame, text=f"Teacher: {self.current_user['full_name']}", style="Header.TLabel").pack(side="left")
        ttk.Button(h_frame, text="Logout", command=self.logout).pack(side="right")
        
        notebook = ttk.Notebook(self.root)
        notebook.pack(fill="both", expand=True, padx=10, pady=5)
        
        self.tab_live = ttk.Frame(notebook)
        notebook.add(self.tab_live, text="Live Class")
        self._build_live_tab(self.tab_live)
        
        self.tab_manual = ttk.Frame(notebook)
        notebook.add(self.tab_manual, text="Manual / Past Records")
        self._build_manual_tab(self.tab_manual)

    def _build_live_tab(self, parent):
        paned = ttk.PanedWindow(parent, orient=tk.HORIZONTAL)
        paned.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        left = ttk.Frame(paned, padding=5)
        right = ttk.Frame(paned, padding=5, relief=tk.RIDGE)
        paned.add(left, weight=2)
        paned.add(right, weight=1)
        
        vid_frame = ttk.LabelFrame(left, text="Live Camera", padding=5)
        vid_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        
        self.video_label = ttk.Label(vid_frame)
        self.video_label.pack(fill=tk.BOTH, expand=True)
        self.video_label.image = ImageTk.PhotoImage(Image.new("RGB", (640, 480), "gray"))
        self.video_label.configure(image=self.video_label.image)
        
        btn_box = ttk.Frame(left)
        btn_box.pack(fill=tk.X)
        self.btn_start = ttk.Button(btn_box, text="▶ Start Session", command=self.start_session_camera)
        self.btn_start.pack(side=tk.LEFT, padx=5)
        self.btn_stop = ttk.Button(btn_box, text="■ Stop", command=self.stop_camera, state="disabled")
        self.btn_stop.pack(side=tk.LEFT, padx=5)
        
        info_frame = ttk.LabelFrame(right, text="Current Session", padding=10)
        info_frame.pack(fill=tk.X, pady=(0, 10))
        
        self.lbl_group = ttk.Label(info_frame, text="Group: --")
        self.lbl_group.pack(anchor="w")
        self.lbl_status = ttk.Label(info_frame, text="Status: Inactive", foreground="red")
        self.lbl_status.pack(anchor="w")
        
        ttk.Button(info_frame, text="⟳ Refresh Schedule", command=self.check_schedule).pack(pady=5, fill="x")
        
        list_frame = ttk.LabelFrame(right, text="Attendance (Double-Click to Toggle)", padding=(5, 5, 5, 0))
        list_frame.pack(fill=tk.BOTH, expand=True)
        
        self.tree_att = ttk.Treeview(list_frame, columns=("name", "status"), show="headings")
        self.tree_att.heading("name", text="Student")
        self.tree_att.heading("status", text="Status")
        self.tree_att.column("status", width=80, anchor="center")
        self.tree_att.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        self.tree_att.tag_configure('PRESENT', foreground='green', background='#E8F5E9')
        self.tree_att.tag_configure('ABSENT', foreground='red', background='#FFEBEE')
        self.tree_att.bind("<Double-1>", self.on_live_list_double_click)
        
        self.check_schedule()
        self.update_video_loop()

    def on_live_list_double_click(self, event):
        if not self.active_session: return
        item_id = self.tree_att.identify_row(event.y)
        if not item_id: return
        
        student_id = None
        for (sid, iid) in self.student_tree_map.items():
            if iid == item_id:
                student_id = sid
                break
        
        if student_id:
            group_id = self.active_session['group_id']
            new_status = self.db.toggle_attendance_status(student_id, group_id)
            self.tree_att.set(item_id, "status", new_status)
            self.tree_att.item(item_id, tags=(new_status,))

    def _build_manual_tab(self, parent):
        ctrl_frame = ttk.Frame(parent, padding=10)
        ctrl_frame.pack(fill="x")
        
        ttk.Label(ctrl_frame, text="Date (YYYY-MM-DD):").pack(side="left")
        self.ent_manual_date = ttk.Entry(ctrl_frame, width=12)
        today_str = datetime.now().strftime("%Y-%m-%d")
        self.ent_manual_date.insert(0, today_str)
        self.ent_manual_date.pack(side="left", padx=5)
        
        ttk.Label(ctrl_frame, text="Group:").pack(side="left", padx=(10, 0))
        self.cb_manual_group = ttk.Combobox(ctrl_frame, state="readonly", width=15)
        groups = self.db.get_all_groups()
        group_names = [g.name for g in groups]
        self.cb_manual_group['values'] = group_names
        self.group_name_map = {g.name: g.id for g in groups}
        
        if group_names: self.cb_manual_group.current(0)
        self.cb_manual_group.pack(side="left", padx=5)
        
        ttk.Button(ctrl_frame, text="🔄 Load List", command=self.load_manual_list).pack(side="left", padx=10)
        ttk.Button(ctrl_frame, text="Export CSV", command=self.export_csv).pack(padx=10, side="left")
        ttk.Button(ctrl_frame, text="💾 Save Changes", command=self.save_manual_list).pack(side="right")
        
        list_frame = ttk.Frame(parent)
        list_frame.pack(fill="both", expand=True, padx=10, pady=10)
        
        self.tree_manual = ttk.Treeview(list_frame, columns=("roll", "name", "status", "time"), show="headings")
        self.tree_manual.heading("roll", text="Roll No")
        self.tree_manual.column("roll", width=60, anchor="center")
        self.tree_manual.heading("name", text="Name")
        self.tree_manual.column("name", width=180)
        self.tree_manual.heading("status", text="Status (Dbl-Click)")
        self.tree_manual.column("status", width=100, anchor="center")
        self.tree_manual.heading("time", text="Time Detected")
        self.tree_manual.column("time", width=100, anchor="center")
        
        sb = ttk.Scrollbar(list_frame, orient="vertical", command=self.tree_manual.yview)
        self.tree_manual.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        self.tree_manual.pack(side="left", fill="both", expand=True)
        
        self.tree_manual.tag_configure('PRESENT', foreground='green')
        self.tree_manual.tag_configure('ABSENT', foreground='red')
        self.tree_manual.bind("<Double-1>", self.on_manual_double_click)

    def load_manual_list(self):
        date_str = self.ent_manual_date.get()
        group_name = self.cb_manual_group.get()
        if not group_name:
            messagebox.showwarning("Warning", "Please select a group first.")
            return
            
        for i in self.tree_manual.get_children(): self.tree_manual.delete(i)
        
        try:
            group_id = self.group_name_map[group_name]
            att_data = self.db.get_session_attendance(group_id, date_str)
            
            if not att_data:
                confirm = messagebox.askyesno("No Records Found", f"No attendance found for {group_name} on {date_str}.\n\nDo you want to create a NEW attendance sheet for this date?")
                if not confirm: return
                
            students = self.db.get_students_by_group(group_id)
            for s in students:
                record = att_data.get(s.id, {'status': 'ABSENT', 'time': '-'})
                status = record['status']
                time_val = record['time'] if record['time'] else '-'
                self.tree_manual.insert("", "end", iid=s.id, values=(s.roll_number, s.name, status, time_val), tags=(status,))
                
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load: {e}")

    def on_manual_double_click(self, event):
        row_id = self.tree_manual.identify_row(event.y)
        if not row_id: return
        values = self.tree_manual.item(row_id, "values")
        current_status = values[2]
        current_time = values[3]
        
        new_status = "ABSENT" if current_status == "PRESENT" else "PRESENT"
        new_time = current_time
        if new_status == "PRESENT" and (new_time == '-' or not new_time):
            new_time = datetime.now().strftime("%H:%M:%S")
            
        self.tree_manual.item(row_id, values=(values[0], values[1], new_status, new_time))
        self.tree_manual.item(row_id, tags=(new_status,))

    def save_manual_list(self):
        date_str = self.ent_manual_date.get()
        group_name = self.cb_manual_group.get()
        if not group_name: return
        
        group_id = self.group_name_map[group_name]
        att_map = {}
        for item_id in self.tree_manual.get_children():
            vals = self.tree_manual.item(item_id)['values']
            status = vals[2]
            time_val = vals[3]
            if time_val == '-': time_val = None
            att_map[int(item_id)] = {'status': status, 'time': time_val}
            
        if self.db.save_manual_attendance(group_id, date_str, att_map):
            messagebox.showinfo("Success", "Attendance saved.")
        else:
            messagebox.showerror("Error", "Failed to save.")

    def check_schedule(self):
        session = self.db.get_active_session_info(self.current_user['id'])
        if session:
            self.active_session = session
            self.lbl_group.config(text=f"Active Group: {session['group_name']}", font=("Helvetica", 12, "bold"))
            self.lbl_status.config(text="Status: Ready", foreground="orange")
            self.refresh_att_list()
        else:
            self.active_session = None
            self.lbl_group.config(text="No active class")
            self.lbl_status.config(text="Status: Off Duty", foreground="gray")
            for i in self.tree_att.get_children(): self.tree_att.delete(i)

    def start_session_camera(self):
        if not self.active_session:
            messagebox.showwarning("No Class", "No class is scheduled for right now.")
            return
        try:
            self.camera.start()
            self.btn_start['state'] = 'disabled'
            self.btn_stop['state'] = 'normal'
            self.is_session_active = True
            self.lbl_status.config(text="Status: Active Session", foreground="green")
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def refresh_att_list(self):
        for i in self.tree_att.get_children(): self.tree_att.delete(i)
        self.student_tree_map.clear()
        
        if not self.active_session: return
        
        gid = self.active_session['group_id']
        students = self.db.get_students_by_group(gid)
        
        att_data = self.db.get_todays_attendance(gid)
        
        for s in students:
            status = att_data.get(s.id, "ABSENT")
            iid = self.tree_att.insert("", "end", values=(s.name, status), tags=(status,))
            self.student_tree_map[s.id] = iid

    def stop_camera(self):
        if hasattr(self, 'camera'):
            self.camera.stop()
        self.is_session_active = False
        try:
            if hasattr(self, 'btn_start') and self.btn_start.winfo_exists():
                self.btn_start['state'] = 'normal'
            if hasattr(self, 'btn_stop') and self.btn_stop.winfo_exists():
                self.btn_stop['state'] = 'disabled'
            if hasattr(self, 'lbl_status') and self.lbl_status.winfo_exists():
                self.lbl_status.config(text="Status: Paused", foreground="orange")
            if hasattr(self, 'video_label') and self.video_label.winfo_exists():
                self.video_label.configure(image=self.video_label.image)
        except Exception:
            pass

    def update_video_loop(self):
        if not self.current_user or self.current_user.get('is_admin') == 1:
            return

        frame = self.camera.get_frame()
        if frame is not None:
            # FPS Calculation
            self.new_frame_time = time.time()
            fps = 0
            if self.prev_frame_time > 0:
                fps = 1 / (self.new_frame_time - self.prev_frame_time)
            self.prev_frame_time = self.new_frame_time
            fps_text = f"FPS: {int(fps)}"

            dets = self.vision.detect_and_identify(frame)
            draw = frame.copy()

            for (sid, name, (t, r, b, l)) in dets:
                color = (0, 255, 0) if sid else (255, 0, 0)
                cv2.rectangle(draw, (l, t), (r, b), color, 2)
                cv2.putText(draw, name, (l, b + 20), cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)

                if self.is_session_active and self.active_session and sid:
                    if sid in self.student_tree_map:
                        gid = self.active_session.get('group_id', 0)
                        
                        if self.db.mark_attendance(sid, gid):
                            iid = self.student_tree_map[sid]
                            self.tree_att.set(iid, "status", "PRESENT")
                            self.tree_att.item(iid, tags=('present',))

            cv2.putText(draw, fps_text, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 255), 2)
            img = ImageTk.PhotoImage(Image.fromarray(draw))
            self.video_label.configure(image=img)
            self.video_label.imgtk = img
        
        self.root.after(30, self.update_video_loop)

    def export_csv(self):
        group_name = self.cb_manual_group.get()
        date_str = self.ent_manual_date.get()
        
        if not self.tree_manual.get_children():
            messagebox.showwarning("Warning", "No data to export. Please load a list first.")
            return

        safe_group = group_name.replace(" ", "_")
        default_filename = f"{date_str}_{safe_group}.csv"
        
        try:
            path = filedialog.asksaveasfilename(defaultextension=".csv", initialfile=default_filename, filetypes=[("CSV files", "*.csv")])
            if path:
                with open(path, "w", newline='', encoding='utf-8') as f:
                    w = csv.writer(f)
                    w.writerow(["Date", "Group", "Roll_No", "Name", "Status", "Time"])
                    for iid in self.tree_manual.get_children():
                        vals = self.tree_manual.item(iid)['values']
                        row_data = [date_str, group_name, vals[0], vals[1], vals[2], vals[3]]
                        w.writerow(row_data)
                messagebox.showinfo("Success", "Exported successfully.")
        except Exception as e:
            messagebox.showerror("Error", f"Export failed: {str(e)}")

    def on_close(self):
        self.stop_camera()
        self.root.destroy()