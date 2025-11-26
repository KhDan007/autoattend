import tkinter as tk
from src.app import AutoAttendApp

if __name__ == "__main__":
    root = tk.Tk()
    app = AutoAttendApp(root)
    # Ensure camera thread is killed on exit
    root.protocol("WM_DELETE_WINDOW", app.on_close)
    root.mainloop()