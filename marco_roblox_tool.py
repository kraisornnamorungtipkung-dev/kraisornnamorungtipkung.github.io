import tkinter as tk
from tkinter import ttk, messagebox
import threading
import time
import json
import pyautogui
from pynput import keyboard as kb
from pynput import mouse as ms
import queue

pyautogui.FAILSAFE = True

# ─────────────────────────────────────────────
#  Global State
# ─────────────────────────────────────────────
auto_click_running = False
auto_key_running = False
click_positions = []   # list of (x, y, label)
key_actions = []       # list of (key, interval, repeat)
pick_mode = False
pick_callback = None
hotkey_listener = None
click_thread = None
key_thread = None
click_event = threading.Event()
key_event = threading.Event()

# ─────────────────────────────────────────────
#  Colors & Fonts  (Roblox dark theme)
# ─────────────────────────────────────────────
BG        = "#0d0f14"
PANEL     = "#161b26"
ACCENT    = "#ff4757"
ACCENT2   = "#ffa502"
GREEN     = "#2ed573"
TEXT      = "#e8eaf6"
SUBTEXT   = "#7c8db5"
BORDER    = "#252d3d"
BTN_BG    = "#1e2638"
BTN_HOV   = "#2a3550"

FONT_TITLE = ("Segoe UI", 18, "bold")
FONT_HEAD  = ("Segoe UI", 11, "bold")
FONT_BODY  = ("Segoe UI", 10)
FONT_SMALL = ("Segoe UI", 9)
FONT_CODE  = ("Consolas", 10)

# ─────────────────────────────────────────────
#  Auto Click Worker
# ─────────────────────────────────────────────
def click_worker(positions, interval, repeat, log_fn):
    global auto_click_running
    count = 0
    while auto_click_running:
        if not positions:
            time.sleep(0.5)
            continue
        for pos in positions:
            if not auto_click_running:
                break
            x, y, label = pos
            pyautogui.click(x, y)
            log_fn(f"🖱 คลิก: {label} ({x},{y})")
            time.sleep(interval)
        count += 1
        if repeat != 0 and count >= repeat:
            auto_click_running = False
            log_fn("✅ Auto Click เสร็จสิ้น")
            break

# ─────────────────────────────────────────────
#  Auto Key Worker
# ─────────────────────────────────────────────
def key_worker(actions, log_fn):
    global auto_key_running
    import pyautogui
    while auto_key_running:
        for act in actions:
            if not auto_key_running:
                break
            key_str, interval, repeat = act
            for _ in range(int(repeat)):
                if not auto_key_running:
                    break
                pyautogui.press(key_str)
                log_fn(f"⌨ กด: {key_str}")
                time.sleep(interval)

# ─────────────────────────────────────────────
#  Position Picker Overlay
# ─────────────────────────────────────────────
def open_picker(root, callback):
    """ขยายหน้าต่างโปร่งใสเพื่อให้ผู้ใช้คลิกเลือกตำแหน่ง"""
    overlay = tk.Toplevel(root)
    overlay.attributes("-fullscreen", True)
    overlay.attributes("-alpha", 0.25)
    overlay.attributes("-topmost", True)
    overlay.configure(bg="#00aaff")
    overlay.title("เลือกตำแหน่ง")

    lbl = tk.Label(overlay,
                   text="🎯  คลิกที่ตำแหน่งที่ต้องการ  (กด Esc เพื่อยกเลิก)",
                   font=("Segoe UI", 22, "bold"),
                   bg="#00aaff", fg="white")
    lbl.pack(expand=True)

    def on_click(event):
        x = overlay.winfo_pointerx()
        y = overlay.winfo_pointery()
        overlay.destroy()
        callback(x, y)

    def on_esc(event):
        overlay.destroy()
        callback(None, None)

    overlay.bind("<Button-1>", on_click)
    overlay.bind("<Escape>", on_esc)
    overlay.focus_force()

# ─────────────────────────────────────────────
#  Main Application
# ─────────────────────────────────────────────
class MarcoTool(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("🎮 Marco Roblox Tool")
        self.geometry("820x680")
        self.configure(bg=BG)
        self.resizable(True, True)
        self._build_ui()
        self.protocol("WM_DELETE_WINDOW", self.on_close)

    # ── UI Builder ──────────────────────────────
    def _build_ui(self):
        # ── Header
        hdr = tk.Frame(self, bg=ACCENT, height=56)
        hdr.pack(fill="x")
        tk.Label(hdr, text="⚡ MARCO ROBLOX TOOL",
                 font=("Segoe UI Black", 16, "bold"),
                 bg=ACCENT, fg="white").pack(side="left", padx=20, pady=14)
        tk.Label(hdr, text="Auto Click & Auto Key",
                 font=FONT_SMALL, bg=ACCENT, fg="#ffd0d0").pack(side="left")

        # ── Notebook (tabs)
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure("TNotebook", background=BG, borderwidth=0)
        style.configure("TNotebook.Tab",
                        background=PANEL, foreground=SUBTEXT,
                        font=FONT_HEAD, padding=[16, 8])
        style.map("TNotebook.Tab",
                  background=[("selected", BTN_HOV)],
                  foreground=[("selected", TEXT)])

        nb = ttk.Notebook(self)
        nb.pack(fill="both", expand=True, padx=10, pady=10)

        self.tab_click = tk.Frame(nb, bg=BG)
        self.tab_key   = tk.Frame(nb, bg=BG)
        self.tab_log   = tk.Frame(nb, bg=BG)

        nb.add(self.tab_click, text="🖱  Auto Click")
        nb.add(self.tab_key,   text="⌨  Auto Key")
        nb.add(self.tab_log,   text="📋  Log")

        self._build_click_tab()
        self._build_key_tab()
        self._build_log_tab()

    # ── AUTO CLICK TAB ───────────────────────────
    def _build_click_tab(self):
        p = self.tab_click
        # Settings row
        sf = tk.Frame(p, bg=PANEL, pady=10, padx=12)
        sf.pack(fill="x", padx=8, pady=(8, 4))

        tk.Label(sf, text="เวลาระหว่างคลิก (วิ):", font=FONT_BODY, bg=PANEL, fg=TEXT).grid(row=0, column=0, padx=(0,6), sticky="w")
        self.click_interval = tk.DoubleVar(value=0.5)
        tk.Spinbox(sf, from_=0.05, to=60, increment=0.05,
                   textvariable=self.click_interval, width=7,
                   font=FONT_CODE, bg=BTN_BG, fg=ACCENT2,
                   buttonbackground=BTN_HOV, relief="flat").grid(row=0, column=1, padx=(0,18))

        tk.Label(sf, text="ทำซ้ำกี่รอบ (0=ไม่หยุด):", font=FONT_BODY, bg=PANEL, fg=TEXT).grid(row=0, column=2, padx=(0,6), sticky="w")
        self.click_repeat = tk.IntVar(value=0)
        tk.Spinbox(sf, from_=0, to=9999, textvariable=self.click_repeat, width=7,
                   font=FONT_CODE, bg=BTN_BG, fg=ACCENT2,
                   buttonbackground=BTN_HOV, relief="flat").grid(row=0, column=3)

        # Position list
        lf = tk.LabelFrame(p, text=" ตำแหน่งที่บันทึก ", font=FONT_HEAD,
                           bg=BG, fg=ACCENT2, bd=1, relief="solid")
        lf.pack(fill="both", expand=True, padx=8, pady=4)

        cols = ("id","label","x","y")
        self.pos_tree = ttk.Treeview(lf, columns=cols, show="headings", height=8)
        style = ttk.Style()
        style.configure("Treeview",
                        background=PANEL, foreground=TEXT,
                        fieldbackground=PANEL, rowheight=28,
                        font=FONT_BODY)
        style.configure("Treeview.Heading", background=BTN_HOV, foreground=ACCENT2, font=FONT_HEAD)
        style.map("Treeview", background=[("selected", ACCENT)])

        for c, w, h in [("id",40,"#"), ("label",160,"ชื่อ"), ("x",80,"X"), ("y",80,"Y")]:
            self.pos_tree.heading(c, text=h)
            self.pos_tree.column(c, width=w, anchor="center")

        sb = ttk.Scrollbar(lf, orient="vertical", command=self.pos_tree.yview)
        self.pos_tree.configure(yscrollcommand=sb.set)
        self.pos_tree.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")

        # Buttons
        bf = tk.Frame(p, bg=BG)
        bf.pack(fill="x", padx=8, pady=6)

        self._btn(bf, "➕ เพิ่มตำแหน่ง", ACCENT2, self.add_position).pack(side="left", padx=4)
        self._btn(bf, "🗑 ลบที่เลือก", "#636e72", self.del_position).pack(side="left", padx=4)
        self._btn(bf, "🔼 ขึ้น", BTN_HOV, self.move_up).pack(side="left", padx=4)
        self._btn(bf, "🔽 ลง", BTN_HOV, self.move_down).pack(side="left", padx=4)

        self.click_btn = self._btn(bf, "▶ เริ่ม Auto Click", GREEN, self.toggle_click)
        self.click_btn.pack(side="right", padx=4)

    # ── AUTO KEY TAB ─────────────────────────────
    def _build_key_tab(self):
        p = self.tab_key

        # Key action input
        inf = tk.Frame(p, bg=PANEL, pady=10, padx=12)
        inf.pack(fill="x", padx=8, pady=(8, 4))

        tk.Label(inf, text="ปุ่ม:", font=FONT_BODY, bg=PANEL, fg=TEXT).grid(row=0, column=0, padx=(0,4))
        self.key_entry = tk.Entry(inf, width=10, font=FONT_CODE, bg=BTN_BG, fg=ACCENT2, insertbackground=ACCENT2, relief="flat")
        self.key_entry.insert(0, "e")
        self.key_entry.grid(row=0, column=1, padx=(0,14))

        tk.Label(inf, text="หน่วงเวลา (วิ):", font=FONT_BODY, bg=PANEL, fg=TEXT).grid(row=0, column=2, padx=(0,4))
        self.key_interval = tk.DoubleVar(value=0.5)
        tk.Spinbox(inf, from_=0.05, to=60, increment=0.05, textvariable=self.key_interval,
                   width=7, font=FONT_CODE, bg=BTN_BG, fg=ACCENT2, buttonbackground=BTN_HOV, relief="flat").grid(row=0, column=3, padx=(0,14))

        tk.Label(inf, text="ทำซ้ำ (0=∞):", font=FONT_BODY, bg=PANEL, fg=TEXT).grid(row=0, column=4, padx=(0,4))
        self.key_repeat = tk.IntVar(value=0)
        tk.Spinbox(inf, from_=0, to=9999, textvariable=self.key_repeat,
                   width=6, font=FONT_CODE, bg=BTN_BG, fg=ACCENT2, buttonbackground=BTN_HOV, relief="flat").grid(row=0, column=5)

        self._btn(inf, "➕ เพิ่ม", ACCENT2, self.add_key_action).grid(row=0, column=6, padx=(12,0))

        # Quick key shortcuts
        qf = tk.Frame(p, bg=BG)
        qf.pack(fill="x", padx=8, pady=2)
        tk.Label(qf, text="ปุ่มลัดยอดนิยม Marco:", font=FONT_SMALL, bg=BG, fg=SUBTEXT).pack(side="left", padx=(4,8))
        for k in ["e","f","space","w","a","s","d","1","2","3","r","q","shift"]:
            self._btn(qf, k, BTN_HOV, lambda key=k: self._quick_key(key), pad_x=3, pad_y=3).pack(side="left", padx=2)

        # Key list
        lf = tk.LabelFrame(p, text=" ลำดับปุ่มที่กด ", font=FONT_HEAD,
                           bg=BG, fg=ACCENT2, bd=1, relief="solid")
        lf.pack(fill="both", expand=True, padx=8, pady=4)

        cols = ("id","key","interval","repeat")
        self.key_tree = ttk.Treeview(lf, columns=cols, show="headings", height=8)
        for c, w, h in [("id",40,"#"), ("key",120,"ปุ่ม"), ("interval",120,"หน่วงเวลา (วิ)"), ("repeat",100,"ซ้ำ (0=∞)")]:
            self.key_tree.heading(c, text=h)
            self.key_tree.column(c, width=w, anchor="center")
        self.key_tree.pack(fill="both", expand=True)

        bf = tk.Frame(p, bg=BG)
        bf.pack(fill="x", padx=8, pady=6)
        self._btn(bf, "🗑 ลบที่เลือก", "#636e72", self.del_key_action).pack(side="left", padx=4)
        self._btn(bf, "🔼 ขึ้น", BTN_HOV, self.key_move_up).pack(side="left", padx=4)
        self._btn(bf, "🔽 ลง", BTN_HOV, self.key_move_down).pack(side="left", padx=4)

        self.key_btn = self._btn(bf, "▶ เริ่ม Auto Key", GREEN, self.toggle_key)
        self.key_btn.pack(side="right", padx=4)

    # ── LOG TAB ──────────────────────────────────
    def _build_log_tab(self):
        p = self.tab_log
        self.log_text = tk.Text(p, bg=PANEL, fg=TEXT, font=FONT_CODE,
                                state="disabled", relief="flat",
                                insertbackground=TEXT, selectbackground=ACCENT)
        sb = ttk.Scrollbar(p, orient="vertical", command=self.log_text.yview)
        self.log_text.configure(yscrollcommand=sb.set)
        self.log_text.pack(side="left", fill="both", expand=True, padx=(8,0), pady=8)
        sb.pack(side="right", fill="y", pady=8, padx=(0,8))
        self._btn(p, "🗑 ล้าง Log", "#636e72", self.clear_log).pack(anchor="e", padx=8, pady=(0,8))

    # ── Helper Widgets ───────────────────────────
    def _btn(self, parent, text, color, cmd, pad_x=12, pad_y=6):
        b = tk.Button(parent, text=text, bg=color, fg="white",
                      font=FONT_BODY, relief="flat", cursor="hand2",
                      padx=pad_x, pady=pad_y, command=cmd,
                      activebackground=color, activeforeground="white")
        def on_enter(e): b.configure(bg=self._lighten(color))
        def on_leave(e): b.configure(bg=color)
        b.bind("<Enter>", on_enter)
        b.bind("<Leave>", on_leave)
        return b

    def _lighten(self, hex_color):
        try:
            r = int(hex_color[1:3], 16)
            g = int(hex_color[3:5], 16)
            b = int(hex_color[5:7], 16)
            r = min(255, r + 30)
            g = min(255, g + 30)
            b = min(255, b + 30)
            return f"#{r:02x}{g:02x}{b:02x}"
        except:
            return hex_color

    # ── Logging ──────────────────────────────────
    def log(self, msg):
        def _do():
            self.log_text.configure(state="normal")
            ts = time.strftime("%H:%M:%S")
            self.log_text.insert("end", f"[{ts}] {msg}\n")
            self.log_text.see("end")
            self.log_text.configure(state="disabled")
        self.after(0, _do)

    def clear_log(self):
        self.log_text.configure(state="normal")
        self.log_text.delete("1.0", "end")
        self.log_text.configure(state="disabled")

    # ── Position CRUD ────────────────────────────
    def add_position(self):
        def got_pos(x, y):
            if x is None:
                return
            label = f"จุด {len(click_positions)+1}"
            click_positions.append((x, y, label))
            idx = len(click_positions)
            self.pos_tree.insert("", "end", values=(idx, label, x, y))
            self.log(f"➕ บันทึกตำแหน่ง: {label} ({x},{y})")
        self.after(200, lambda: open_picker(self, got_pos))

    def del_position(self):
        sel = self.pos_tree.selection()
        if not sel:
            return
        for item in sel:
            idx = int(self.pos_tree.item(item, "values")[0]) - 1
            if 0 <= idx < len(click_positions):
                click_positions.pop(idx)
            self.pos_tree.delete(item)
        self._refresh_pos_tree()

    def move_up(self):
        sel = self.pos_tree.selection()
        if not sel:
            return
        item = sel[0]
        prev = self.pos_tree.prev(item)
        if prev:
            self.pos_tree.move(item, "", self.pos_tree.index(prev))
        self._sync_positions()

    def move_down(self):
        sel = self.pos_tree.selection()
        if not sel:
            return
        item = sel[0]
        nxt = self.pos_tree.next(item)
        if nxt:
            self.pos_tree.move(item, "", self.pos_tree.index(nxt) + 1)
        self._sync_positions()

    def _refresh_pos_tree(self):
        for row in self.pos_tree.get_children():
            self.pos_tree.delete(row)
        for i, (x, y, label) in enumerate(click_positions):
            self.pos_tree.insert("", "end", values=(i+1, label, x, y))

    def _sync_positions(self):
        global click_positions
        click_positions = []
        for row in self.pos_tree.get_children():
            vals = self.pos_tree.item(row, "values")
            click_positions.append((int(vals[2]), int(vals[3]), vals[1]))

    # ── Auto Click Control ───────────────────────
    def toggle_click(self):
        global auto_click_running, click_thread
        if auto_click_running:
            auto_click_running = False
            self.click_btn.configure(text="▶ เริ่ม Auto Click", bg=GREEN)
            self.log("⏹ หยุด Auto Click")
        else:
            if not click_positions:
                messagebox.showwarning("⚠️ Marco Tool", "กรุณาเพิ่มตำแหน่งก่อน!")
                return
            auto_click_running = True
            self.click_btn.configure(text="⏹ หยุด Auto Click", bg=ACCENT)
            self.log("▶ เริ่ม Auto Click")
            interval = self.click_interval.get()
            repeat   = self.click_repeat.get()
            click_thread = threading.Thread(
                target=click_worker,
                args=(list(click_positions), interval, repeat, self.log),
                daemon=True)
            click_thread.start()
            self.after(500, self._check_click_done)

    def _check_click_done(self):
        global auto_click_running
        if not auto_click_running:
            self.click_btn.configure(text="▶ เริ่ม Auto Click", bg=GREEN)
        else:
            self.after(500, self._check_click_done)

    # ── Key CRUD ─────────────────────────────────
    def add_key_action(self):
        key  = self.key_entry.get().strip()
        if not key:
            return
        iv   = self.key_interval.get()
        rep  = self.key_repeat.get()
        key_actions.append((key, iv, rep))
        idx  = len(key_actions)
        self.key_tree.insert("", "end", values=(idx, key, f"{iv:.2f}", rep))
        self.log(f"➕ เพิ่มปุ่ม: {key} | ทุก {iv:.2f}วิ | ซ้ำ {rep}ครั้ง")

    def _quick_key(self, key):
        self.key_entry.delete(0, "end")
        self.key_entry.insert(0, key)

    def del_key_action(self):
        sel = self.key_tree.selection()
        if not sel:
            return
        for item in sel:
            idx = int(self.key_tree.item(item, "values")[0]) - 1
            if 0 <= idx < len(key_actions):
                key_actions.pop(idx)
            self.key_tree.delete(item)
        self._refresh_key_tree()

    def key_move_up(self):
        sel = self.key_tree.selection()
        if not sel:
            return
        item = sel[0]
        prev = self.key_tree.prev(item)
        if prev:
            self.key_tree.move(item, "", self.key_tree.index(prev))

    def key_move_down(self):
        sel = self.key_tree.selection()
        if not sel:
            return
        item = sel[0]
        nxt = self.key_tree.next(item)
        if nxt:
            self.key_tree.move(item, "", self.key_tree.index(nxt) + 1)

    def _refresh_key_tree(self):
        for row in self.key_tree.get_children():
            self.key_tree.delete(row)
        for i, (k, iv, rep) in enumerate(key_actions):
            self.key_tree.insert("", "end", values=(i+1, k, f"{iv:.2f}", rep))

    # ── Auto Key Control ─────────────────────────
    def toggle_key(self):
        global auto_key_running, key_thread
        if auto_key_running:
            auto_key_running = False
            self.key_btn.configure(text="▶ เริ่ม Auto Key", bg=GREEN)
            self.log("⏹ หยุด Auto Key")
        else:
            if not key_actions:
                messagebox.showwarning("⚠️ Marco Tool", "กรุณาเพิ่มปุ่มก่อน!")
                return
            auto_key_running = True
            self.key_btn.configure(text="⏹ หยุด Auto Key", bg=ACCENT)
            self.log("▶ เริ่ม Auto Key")
            key_thread = threading.Thread(
                target=key_worker,
                args=(list(key_actions), self.log),
                daemon=True)
            key_thread.start()

    # ── Close ────────────────────────────────────
    def on_close(self):
        global auto_click_running, auto_key_running
        auto_click_running = False
        auto_key_running   = False
        self.destroy()

# ─────────────────────────────────────────────
if __name__ == "__main__":
    app = MarcoTool()
    app.mainloop()
