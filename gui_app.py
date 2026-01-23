import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import threading
import queue
import time
import csv
import os
import math  # [NEW] Import math để tính toán chia lưới màn hình

# --- IMPORT MODULES ---
from config_utils import get_driver
from step1_login import InstagramLoginStep
from step2_exceptions import InstagramExceptionStep
from step3_post_login import InstagramPostLoginStep
from step4_2fa import Instagram2FAStep
# ----------------------

class AutomationGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Instagram Automation Tool Pro")
        self.root.geometry("1280x720")
        
        # Variables
        self.file_path_var = tk.StringVar()
        self.thread_count_var = tk.IntVar(value=10)   # Mặc định 10 luồng để test chia màn hình
        self.headless_var = tk.BooleanVar(value=False) # Mặc định False để hiện trình duyệt
        self.status_var = tk.StringVar(value="Ready")
        
        # Stats
        self.total_count = 0
        self.processed_count = 0
        self.success_count = 0
        self.fail_count = 0
        
        # Control Flags
        self.is_running = False
        self.stop_event = threading.Event()
        self.msg_queue = queue.Queue()
        
        # [NEW] Queue quản lý vị trí cửa sổ (Slot ID)
        self.window_slots = queue.Queue()

        # --- CẤU HÌNH CỘT (INDEX 0 -> 12) ---
        self.columns = (
            "uid",          # 0
            "mail_lk",      # 1
            "user",         # 2
            "pass",         # 3
            "2fa",          # 4
            "origin_mail",  # 5
            "pass_mail",    # 6
            "recovery",     # 7
            "post",         # 8
            "followers",    # 9
            "following",    # 10
            "cookie",       # 11
            "note"          # 12
        )
        
        self.setup_ui()
        self.process_queue()

    def setup_ui(self):
        style = ttk.Style()
        style.theme_use('clam')
        style.configure("Treeview", rowheight=25)
        style.map('Treeview', background=[('selected', '#3498db')])

        # TOP FRAME
        top_frame = ttk.LabelFrame(self.root, text="Configuration & Input", padding=10)
        top_frame.pack(fill="x", padx=10, pady=5)

        ttk.Label(top_frame, text="Input File (.txt):").grid(row=0, column=0, sticky="w")
        ttk.Entry(top_frame, textvariable=self.file_path_var, width=50).grid(row=0, column=1, padx=5)
        ttk.Button(top_frame, text="Browse", command=self.browse_file).grid(row=0, column=2, padx=5)
        ttk.Button(top_frame, text="Reload Data", command=self.reload_data).grid(row=0, column=3, padx=5)
        ttk.Button(top_frame, text="Manual Input", command=self.open_manual_input).grid(row=0, column=4, padx=5)

        ttk.Label(top_frame, text="Threads:").grid(row=1, column=0, sticky="w", pady=10)
        tk.Spinbox(top_frame, from_=1, to=50, textvariable=self.thread_count_var, width=5).grid(row=1, column=1, sticky="w", padx=5)
        ttk.Checkbutton(top_frame, text="Run Headless (Hidden)", variable=self.headless_var).grid(row=1, column=1, sticky="e", padx=5)

        self.btn_start = ttk.Button(top_frame, text="START", command=self.start_automation, width=15)
        self.btn_start.grid(row=1, column=3, padx=5)
        self.btn_stop = ttk.Button(top_frame, text="STOP", command=self.stop_automation, state="disabled", width=15)
        self.btn_stop.grid(row=1, column=4, padx=5)

        # STATS FRAME
        stats_frame = ttk.Frame(self.root)
        stats_frame.pack(fill="x", padx=10)
        self.lbl_progress = ttk.Label(stats_frame, text="Progress: 0/0", font=("Arial", 10, "bold"))
        self.lbl_progress.pack(side="left", padx=10)
        self.lbl_success = ttk.Label(stats_frame, text="Success: 0", foreground="green", font=("Arial", 10, "bold"))
        self.lbl_success.pack(side="left", padx=10)
        self.lbl_status = ttk.Label(stats_frame, textvariable=self.status_var, foreground="blue")
        self.lbl_status.pack(side="right", padx=10)

        # TABLE FRAME
        table_frame = ttk.Frame(self.root)
        table_frame.pack(fill="both", expand=True, padx=10, pady=5)
        
        y_scroll = ttk.Scrollbar(table_frame, orient="vertical")
        x_scroll = ttk.Scrollbar(table_frame, orient="horizontal")
        
        self.tree = ttk.Treeview(table_frame, columns=self.columns, show="headings", 
                                 yscrollcommand=y_scroll.set, xscrollcommand=x_scroll.set, selectmode="extended")
        
        y_scroll.config(command=self.tree.yview); y_scroll.pack(side="right", fill="y")
        x_scroll.config(command=self.tree.xview); x_scroll.pack(side="bottom", fill="x")
        self.tree.pack(fill="both", expand=True)

        # Headers & Widths
        headers = {
            "uid": "UID", "mail_lk": "MAIL LK", "user": "USER", "pass": "PASS",
            "2fa": "2FA (RESULT)", "origin_mail": "GMX MAIL", "pass_mail": "GMX PASS",
            "recovery": "RECOVERY", "post": "POST", "followers": "FLWR", "following": "FLWG",
            "cookie": "COOKIE", "note": "NOTE"
        }
        col_width = {
            "uid": 80, "mail_lk": 150, "user": 100, "pass": 80, 
            "2fa": 150, "origin_mail": 150, "pass_mail": 80, 
            "post": 50, "followers": 60, "following": 60, "cookie": 100, "note": 100
        }
        for col in self.columns:
            self.tree.heading(col, text=headers.get(col, col))
            self.tree.column(col, width=col_width.get(col, 100), minwidth=50)

        self.tree.tag_configure("success", background="#d4edda")
        self.tree.tag_configure("error", background="#f8d7da")
        self.tree.tag_configure("running", background="#fff3cd")

        # Context Menu
        self.context_menu = tk.Menu(self.root, tearoff=0)
        self.context_menu.add_command(label="Copy Cell Value", command=self.copy_cell_value)
        self.context_menu.add_separator()
        self.context_menu.add_command(label="Delete Selected Rows", command=self.delete_selected_rows)
        self.tree.bind("<Button-3>", self.show_context_menu)

        # BOTTOM FRAME
        bottom_frame = ttk.LabelFrame(self.root, text="Data Operations", padding=10)
        bottom_frame.pack(fill="x", padx=10, pady=5)
        ttk.Button(bottom_frame, text="Delete Selected", command=self.delete_selected_rows).pack(side="left", padx=5)
        ttk.Button(bottom_frame, text="Clear All", command=self.clear_all_data).pack(side="left", padx=5)
        ttk.Separator(bottom_frame, orient="vertical").pack(side="left", fill="y", padx=10)
        ttk.Button(bottom_frame, text="Export Success", command=lambda: self.export_data("success")).pack(side="left", padx=5)
        ttk.Button(bottom_frame, text="Export Failed", command=lambda: self.export_data("failed")).pack(side="left", padx=5)
        ttk.Button(bottom_frame, text="Export No Success", command=lambda: self.export_data("no_success")).pack(side="left", padx=5)
        ttk.Button(bottom_frame, text="Export All", command=lambda: self.export_data("all")).pack(side="left", padx=5)

    # --- [NEW] HÀM TÍNH TOÁN VỊ TRÍ CỬA SỔ (GRID LAYOUT) ---
    def calculate_window_rect(self, slot_id, total_slots):
        """
        Tính toán x, y, width, height dựa trên Slot ID và kích thước màn hình.
        Chia màn hình thành lưới (Grid) để xếp các cửa sổ Chrome.
        """
        try:
            screen_width = self.root.winfo_screenwidth()
            screen_height = self.root.winfo_screenheight() - 50 # Trừ thanh Taskbar
            
            # Tính số cột và dòng tối ưu
            # Ví dụ: 10 threads -> 5 cột x 2 dòng
            cols = math.ceil(math.sqrt(total_slots))
            if total_slots > 4: 
                cols = 5 # Fix cứng tối đa 5 cột ngang cho dễ nhìn nếu chạy nhiều
            rows = math.ceil(total_slots / cols)
            
            win_w = int(screen_width / cols)
            win_h = int(screen_height / rows)
            
            # Tính tọa độ
            # slot_id 0 -> row 0, col 0
            # slot_id 1 -> row 0, col 1 ...
            curr_row = slot_id // cols
            curr_col = slot_id % cols
            
            x = curr_col * win_w
            y = curr_row * win_h
            
            return (x, y, win_w, win_h)
        except:
            return None

    # --- PROCESS LOGIC (ĐÃ CẬP NHẬT WINDOW RECT) ---
    def process_single_account(self, item_id, window_rect=None):
        values = list(self.tree.item(item_id)['values'])
        acc = {
            "uid": values[0], "linked_mail": values[1], "username": values[2],
            "password": values[3], "gmx_user": values[5], "gmx_pass": values[6]
        }
        
        self.msg_queue.put(("UPDATE_STATUS", (item_id, "Running...", "running")))
        driver = None
        
        try:
            # [UPDATE] Truyền tham số window_rect vào hàm lấy driver
            driver = get_driver(headless=self.headless_var.get(), window_rect=window_rect)
            
            # Step 1: Login
            step1 = InstagramLoginStep(driver)
            step1.load_base_cookies("Wed New Instgram  2026 .json") 
            status = step1.perform_login(acc['username'], acc['password'])
            
            if "FAIL" in status:
                self.msg_queue.put(("FAIL_CRITICAL", (item_id, status)))
                return

            # Step 2: Handle Exception
            step2 = InstagramExceptionStep(driver)
            step2.handle_status(status, acc['username'], acc['gmx_user'], acc['gmx_pass'], acc['linked_mail'])

            # Step 3: Crawl
            step3 = InstagramPostLoginStep(driver)
            data = step3.process_post_login(acc['username'])
            
            # Gửi Cookie và Data về GUI
            self.msg_queue.put(("UPDATE_CRAWL", (item_id, {
                "post": data.get('posts', '0'),
                "followers": data.get('followers', '0'),
                "following": data.get('following', '0'),
                "cookie": data.get('cookie', '')
            })))

            # Step 4: 2FA
            step4 = Instagram2FAStep(driver)
            key = step4.setup_2fa(acc['gmx_user'], acc['gmx_pass'], acc['username'], acc['linked_mail'])
            
            if key == "2FA_ALREADY_ON":
                self.msg_queue.put(("SUCCESS", (item_id, "EXISTING_2FA")))
            else:
                self.msg_queue.put(("SUCCESS", (item_id, key)))

        except Exception as e:
            msg = str(e).replace("STOP_FLOW_", "")
            self.msg_queue.put(("FAIL_CRITICAL", (item_id, msg)))
        finally:
            if driver: 
                try: driver.quit()
                except: pass

    # --- THREAD MANAGER (ĐÃ CẬP NHẬT SLOT MANAGEMENT) ---
    def thread_manager(self, items, n_threads):
        task_queue = queue.Queue()
        for i in items: task_queue.put(i)
        
        # [NEW] Khởi tạo các slot hiển thị (0, 1, 2, ... n-1)
        self.window_slots = queue.Queue()
        for i in range(n_threads):
            self.window_slots.put(i)

        def worker():
            while not self.stop_event.is_set():
                try:
                    # 1. Lấy Account cần chạy
                    item_id = task_queue.get(timeout=1)
                    
                    # 2. Lấy Slot hiển thị (để tính tọa độ cửa sổ)
                    # Nếu hết slot (đang full luồng), nó sẽ chờ ở đây
                    slot_id = self.window_slots.get() 
                    
                    # 3. Tính toán Rect (x, y, w, h)
                    rect = self.calculate_window_rect(slot_id, n_threads)
                    
                    # 4. Chạy
                    self.process_single_account(item_id, window_rect=rect)
                    
                    # 5. Xong việc -> Trả lại Slot ID cho luồng khác dùng
                    self.window_slots.put(slot_id)
                    task_queue.task_done()
                    
                except queue.Empty:
                    break
                except Exception as e:
                    print(f"Worker Error: {e}")
                    # Đảm bảo không bị mất slot nếu lỗi xảy ra ở bước lấy slot
                    pass
                
                if not self.is_running: break
        
        # Khởi tạo Threads
        threads = []
        for _ in range(n_threads):
            t = threading.Thread(target=worker, daemon=True)
            t.start()
            threads.append(t)

        for t in threads: t.join()
        self.msg_queue.put(("ALL_DONE", None))

    # --- CÁC HÀM KHÁC (GIỮ NGUYÊN) ---
    def start_automation(self):
        items = self.tree.get_children()
        pending_items = [i for i in items if self.tree.item(i)['values'][-1] == "Pending"]
        
        if not pending_items:
            messagebox.showinfo("Info", "No 'Pending' items to process.")
            return

        self.is_running = True
        self.stop_event.clear()
        
        self.btn_start.config(state="disabled")
        self.btn_stop.config(state="normal", text="STOP")
        self.status_var.set("Running...")
        
        self.processed_count = 0
        self.success_count = 0
        self.fail_count = 0
        self.lbl_success.config(text="Success: 0")
        
        num_threads = self.thread_count_var.get()
        threading.Thread(target=self.thread_manager, args=(pending_items, num_threads), daemon=True).start()

    def stop_automation(self):
        if messagebox.askyesno("Confirm", "Stop automation process?"):
            self.is_running = False
            self.stop_event.set()
            self.btn_stop.config(text="Stopping...", state="disabled")
            self.status_var.set("Stopping...")

    def process_queue(self):
        try:
            while True:
                msg_type, data = self.msg_queue.get_nowait()
                
                if msg_type == "UPDATE_STATUS":
                    item_id, note, tag = data
                    self.update_tree_item(item_id, {12: note}, tag)
                
                elif msg_type == "UPDATE_CRAWL":
                    item_id, info = data
                    # Cập nhật Post(8), Follow(9), Following(10), Cookie(11)
                    self.update_tree_item(item_id, {
                        8: info['post'], 
                        9: info['followers'], 
                        10: info['following'],
                        11: info['cookie']
                    })
                
                elif msg_type == "SUCCESS":
                    item_id, key = data
                    self.success_count += 1
                    self.processed_count += 1
                    # Cập nhật Key 2FA(4), Note(12)
                    self.update_tree_item(item_id, {4: key, 12: "Success"}, "success")
                    self.update_stats_label()
                    self.write_result_to_output(item_id, success=True)
                
                elif msg_type == "FAIL_CRITICAL":
                    item_id, err = data
                    self.fail_count += 1
                    self.processed_count += 1
                    self.update_tree_item(item_id, {8: err[:60], 12: "Failed"}, "error") 
                    self.update_stats_label()
                    self.write_result_to_output(item_id, success=False)
                
                elif msg_type == "ALL_DONE":
                    self.is_running = False
                    self.btn_start.config(state="normal")
                    self.btn_stop.config(state="disabled", text="STOP")
                    self.status_var.set("Finished")
                    messagebox.showinfo("Done", "Completed!")

        except queue.Empty: pass
        self.root.after(100, self.process_queue)

    def write_result_to_output(self, item_id, success=True):
        try:
            values = self.tree.item(item_id)['values']
            with open("output.txt", "a", encoding="utf-8") as f:
                row = [str(v) for v in values]
                f.write("\t".join(row) + "\n")
        except: pass

    def update_tree_item(self, id, col_map, tag=None):
        try:
            vals = list(self.tree.item(id, "values"))
            for idx, v in col_map.items(): vals[idx] = v
            kw = {"values": vals}
            if tag: kw["tags"] = (tag,)
            self.tree.item(id, **kw)
        except: pass

    def update_stats_label(self):
        self.lbl_progress.config(text=f"Progress: {self.processed_count}/{self.total_count}")
        self.lbl_success.config(text=f"Success: {self.success_count}")

    # --- UI HELPERS (Manual Input, File Browse...) ---
    def open_manual_input(self):
        dialog = tk.Toplevel(self.root)
        dialog.title("Manual Input (Tab Separated)")
        dialog.geometry("800x600")
        dialog.minsize(600, 400)
        
        btn_frame = ttk.Frame(dialog)
        btn_frame.pack(side="bottom", fill="x", padx=10, pady=10)
        
        txt_frame = ttk.Frame(dialog)
        txt_frame.pack(side="top", fill="both", expand=True, padx=10, pady=(10, 0))
        
        scroll_y = ttk.Scrollbar(txt_frame)
        scroll_y.pack(side="right", fill="y")
        
        txt_input = tk.Text(txt_frame, wrap="none", yscrollcommand=scroll_y.set)
        txt_input.pack(side="left", fill="both", expand=True)
        scroll_y.config(command=txt_input.yview)
        
        def submit():
            raw_data = txt_input.get("1.0", "end").strip()
            if raw_data:
                lines = raw_data.split("\n")
                added_count = 0
                for line in lines:
                    if line.strip():
                        parts = line.strip().split("\t")
                        while len(parts) < len(self.columns): parts.append("")
                        parts[-1] = "Pending"
                        self.tree.insert("", "end", values=parts)
                        added_count += 1
                self.update_stats()
                messagebox.showinfo("Success", f"Added {added_count} accounts.")
                dialog.destroy()

        ttk.Button(btn_frame, text="Submit Data", command=submit).pack(side="right", padx=5)
        ttk.Button(btn_frame, text="Clear", command=lambda: txt_input.delete("1.0", "end")).pack(side="right", padx=5)
        ttk.Button(btn_frame, text="Close", command=dialog.destroy).pack(side="right", padx=5)
        ttk.Label(btn_frame, text="Paste data from Excel/Text (Tab separated)", font=("Arial", 9, "italic")).pack(side="left")

    def browse_file(self):
        filename = filedialog.askopenfilename(filetypes=[("Text Files", "*.txt")])
        if filename:
            self.file_path_var.set(filename)
            self.load_data_from_file(filename)

    def reload_data(self):
        path = self.file_path_var.get()
        if path and os.path.exists(path):
            self.load_data_from_file(path)
        else:
            messagebox.showwarning("Warning", "File path is invalid or empty.")

    def load_data_from_file(self, filepath):
        self.clear_all_data(confirm=False)
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                for line in f:
                    if line.strip():
                        parts = line.strip().split("\t")
                        while len(parts) < len(self.columns): parts.append("")
                        parts[-1] = "Pending"
                        self.tree.insert("", "end", values=parts)
            self.update_stats()
        except Exception as e:
            messagebox.showerror("Error", f"Could not load file: {e}")

    def show_context_menu(self, event):
        item = self.tree.identify_row(event.y)
        col = self.tree.identify_column(event.x)
        if item:
            self.tree.selection_set(item)
            self.selected_cell_col = col 
            self.context_menu.post(event.x_root, event.y_root)

    def copy_cell_value(self):
        try:
            selected_item = self.tree.selection()[0]
            col_idx = int(self.selected_cell_col.replace("#", "")) - 1
            value = self.tree.item(selected_item)['values'][col_idx]
            self.root.clipboard_clear()
            self.root.clipboard_append(str(value))
        except: pass

    def delete_selected_rows(self):
        selected = self.tree.selection()
        if not selected: return
        if messagebox.askyesno("Confirm", f"Delete {len(selected)} rows?"):
            for item in selected: self.tree.delete(item)
            self.update_stats()

    def clear_all_data(self, confirm=True):
        if confirm and not messagebox.askyesno("Confirm", "Clear ALL data?"): return
        for item in self.tree.get_children(): self.tree.delete(item)
        self.update_stats()

    def update_stats(self):
        items = self.tree.get_children()
        self.total_count = len(items)
        self.lbl_progress.config(text=f"Progress: {self.processed_count}/{self.total_count}")

    def export_data(self, mode):
        filename = filedialog.asksaveasfilename(defaultextension=".txt", filetypes=[("Text File", "*.txt")])
        if not filename: return
        count = 0
        with open(filename, "w", encoding="utf-8", newline='') as f:
            writer = csv.writer(f, delimiter='\t')
            for item in self.tree.get_children():
                vals = self.tree.item(item)['values']
                note = vals[-1].lower()
                should_export = False
                if mode == "all": should_export = True
                elif mode == "success" and "success" in note: should_export = True
                elif mode == "failed" and ("fail" in note or "error" in note): should_export = True
                elif mode == "no_success" and "success" not in note: should_export = True
                
                if should_export:
                    writer.writerow(vals[:-1])
                    count += 1
        messagebox.showinfo("Export", f"Exported {count} items.")

if __name__ == "__main__":
    root = tk.Tk()
    app = AutomationGUI(root)
    root.mainloop()