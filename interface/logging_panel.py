import tkinter as tk
from tkinter import ttk
from interface.styling import *
import queue
import requests
from PIL import Image, ImageTk, ImageDraw
import io
import os


class LoggingPanel(tk.Frame):
    def __init__(self, parent,close_trade_callback=None, **kwargs) -> None:
        kwargs.setdefault("bg", BG_COLOR)
        super().__init__(parent, **kwargs)

        self.close_trade_callback = close_trade_callback

        self._img_cache = {}
        self.sold_tokens = set()

        

        self.placeholder_img = self._load_placeholder()
        

        # === Filter Bar ===
        filter_frame = tk.Frame(self, bg=BG_COLOR)
        filter_frame.pack(fill="x", pady=2)

        tk.Label(filter_frame, text="🔍 Filter:", bg=BG_COLOR, fg="white").pack(side="left", padx=5)
        self.filter_var = tk.StringVar()
        self.filter_var.trace_add("write", lambda *_: self.apply_filter())
        tk.Entry(filter_frame, textvariable=self.filter_var, width=20).pack(side="left")

        # === Treeview Table ===
        self.columns = ["Logo",  "Token", "Entry Price", "Current Price", "PnL (%)","Action"]
        self.tree = ttk.Treeview(
            self,
            columns=self.columns[1:],
            show="tree headings",
            style="Custom.Treeview"
        )

        # Logo column
        self.tree.heading("#0", text="Logo")
        self.tree.column("#0", width=40, anchor="center")

        #close trade
        self.tree.heading("Action", text="Action")
        self.tree.column("Action", width=80, anchor="center")

        for col in self.columns[1:]:
            self.tree.heading(col, text=col)
            self.tree.column(col, anchor="center", width=120)

        self.tree.pack(fill=tk.BOTH, expand=True)
        
        #make it reponsive
        self.tree.tag_configure("hover", background="#2a2a2a")
        self.tree.tag_configure("hover_action", background="#552222", foreground="red")
        self.tree.bind("<Motion>", self._on_hover)
        self.tree.bind("<Leave>", lambda e: [self.tree.item(iid, tags=()) for iid in self.tree.get_children()])


        
        # Treeview bindings
        self.tree.bind("<Button-3>", self._copy_selected) 
        self.tree.bind("<Control-c>", self._copy_selected) 
        self.tree.bind("<Double-1>", self._on_double_click)
        self.tree.bind("<Escape>", lambda e: self.tree.selection_remove(self.tree.selection()))
        self.tree.bind("<Button-1>", self._on_click_with_deselect, add="+")
        self.tree.bind("<Motion>", self._on_motion, add="+")
        self.tree.bind("<Button-1>", self._on_click, add="+")

        


        style = ttk.Style()
        style.configure("Custom.Treeview",
                        background=BG_COLOR,
                        fieldbackground=BG_COLOR,
                        foreground=FG_COLOR_WHITE,
                        rowheight=28,  # slightly taller for logos
                        font=("Courier New", 10))
        style.configure("Custom.Treeview.Heading",
                        background=BG_COLOR_2,
                        foreground=FG_COLOR_WHITE,
                        font=("Calibri", 11, "bold"))
        style.map("Custom.Treeview",
            background=[("selected", "#444444")],
            foreground=[("selected", "cyan")])


        # Track rows
        self.active_logs = {}
        self.all_logs = {}

        # Queue for thread-safe updates
        self.queue = queue.Queue()
        self.after_id = self.after(100, self._poll_queue)

    def _load_placeholder(self):
        """Load and return the default placeholder image."""
        base_dir = os.path.dirname(os.path.dirname(__file__)) 
        placeholder_path = os.path.join(base_dir, "assets", "token.png")
        try:
            pil_img = Image.open(placeholder_path).resize((24, 24), Image.LANCZOS)
            return ImageTk.PhotoImage(self._make_circle(pil_img))
        except Exception:
            return None

    def _load_token_logo(self, token: str, url: str):
        """Fetch, resize, and cache token logo. Fallback to placeholder."""
        if not url:
            return self.placeholder_img
        if token in self._img_cache:
            return self._img_cache[token]

        try:
            resp = requests.get(url, timeout=5)
            pil_img = Image.open(io.BytesIO(resp.content)).resize((20, 20), Image.LANCZOS)
            img = ImageTk.PhotoImage(self._make_circle(pil_img))
            self._img_cache[token] = img
            return img
        except Exception:
            self._img_cache[token] = self.placeholder_img
            return self.placeholder_img

    def _make_circle(self, img: Image.Image):
        """Mask image into a circle."""
        size = img.size
        mask = Image.new("L", size, 0)
        draw = ImageDraw.Draw(mask)
        draw.ellipse((0, 0, size[0], size[1]), fill=255)
        result = img.copy()
        result.putalpha(mask)
        return result

    def add_log(self, msg):
        if isinstance(msg, dict):
            self._insert_dict_log(msg)
        else:
            self.tree.insert("", "end", values=("", str(msg), "", "", "", ""))

    def queue_put(self, msg):
        self.queue.put(msg)

    def _insert_dict_log(self, log: dict):
        token = log.get("token_mint")
        event = log.get("event")

        img = self._load_token_logo(token, log.get("token_image"))

        if event == "track":
            if token in self.sold_tokens:
                return
            values = [
                log.get("token_name", token),
                f"{log.get('entry_price', 0):.8f}",
                f"{log.get('current_price', 0):.8f}",
                f"{log.get('pnl', 0):.2f}%",
                "❌ Close" 
            ]

            if token in self.active_logs:
                self.tree.item(self.active_logs[token], values=values, image=img, text="")
            else:
                item_id = self.tree.insert("", "end", text="", image=img, values=values)
                self.active_logs[token] = item_id
                self.all_logs[token] = values

        elif event == "sell":
            if token in self.active_logs:
                item_id = self.active_logs.pop(token, None)
                if item_id:
                    self.tree.delete(item_id)
                self.sold_tokens.add(token)
                self.all_logs.pop(token, None)
                self._clear_queue_for_token(token)
        self.tree.update_idletasks()
        self.apply_filter()

    def apply_filter(self):
        filter_text = self.filter_var.get().lower()
        for token, item_id in self.active_logs.items():
            token_name = self.all_logs[token][0].lower() 
            if filter_text in token_name:
                self.tree.reattach(item_id, "", "end")
            else:
                self.tree.detach(item_id)

    def _poll_queue(self):
        while not self.queue.empty():
            msg = self.queue.get()
            self.add_log(msg)
        self.after_id = self.after(100, self._poll_queue)

    def stop_polling(self):
        if self.after_id:
            try:
                self.after_cancel(self.after_id)
            except Exception:
                pass
            self.after_id = None

    def _on_double_click(self, event):
        item_id = self.tree.identify_row(event.y)
        col = self.tree.identify_column(event.x)
        if not item_id or col == "#0":
            return

        col_index = int(col[1:]) - 1
        x, y, width, height = self.tree.bbox(item_id, col)

        old_val = self.tree.item(item_id, "values")[col_index]

        # highlight row while editing
        self.tree.tag_configure("editing", background="#333333")
        self.tree.item(item_id, tags=("editing",))

        entry = tk.Entry(
            self.tree,
            bg=BG_COLOR,
            fg=FG_COLOR_WHITE,
            insertbackground="cyan",
            relief="solid",
            borderwidth=1
        )
        entry.insert(0, old_val)
        entry.place(x=x, y=y, width=width, height=height)
        entry.focus()

        def save_edit(event=None):
            new_val = entry.get()
            values = list(self.tree.item(item_id, "values"))
            values[col_index] = new_val
            self.tree.item(item_id, values=values)
            entry.destroy()
            self.tree.item(item_id, tags=())  # remove editing highlight
            self.tree.focus(item_id)
            self.tree.selection_set(item_id)
            self.tree.update_idletasks()

        entry.bind("<Return>", save_edit)
        entry.bind("<Escape>", lambda e: (entry.destroy(), self.tree.item(item_id, tags=()), self.tree.update_idletasks()))
    
    def _copy_selected(self, event=None):
        try:
            item_id = self.tree.selection()[0]
            col = self.tree.identify_column(event.x) if event and "x" in event.__dict__ else None
            values = self.tree.item(item_id, "values")

            if col:
                col_index = int(col[1:]) - 1
                text = str(values[col_index])
            else:
                text = "\t".join(str(v) for v in values)

            self.clipboard_clear()
            self.clipboard_append(text)
            self.update()

            self.tree.tag_configure("copied", background="#555555")
            self.tree.item(item_id, tags=("copied",))
            self.after(200, lambda: self.tree.item(item_id, tags=()))

        except Exception as e:
            print(f"⚠️ Copy failed: {e}")

    def _on_hover(self, event):
        rowid = self.tree.identify_row(event.y)
        for iid in self.tree.get_children():
            self.tree.item(iid, tags=())
        if rowid:
            self.tree.item(rowid, tags=("hover",))

    def _on_click_with_deselect(self, event):
        """Deselect if clicking empty area or same row again."""
        rowid = self.tree.identify_row(event.y)

        if not rowid:  
            # Clicked outside → clear selection
            self.tree.selection_remove(self.tree.selection())
        else:
            selected = self.tree.selection()
            if rowid in selected:
                # Clicked the same row → toggle off
                self.tree.selection_remove(rowid)

    def _clear_queue_for_token(self, token):
        keep = []
        while not self.queue.empty():
            msg = self.queue.get()
            if not (isinstance(msg, dict) and msg.get("token_mint") == token):
                keep.append(msg)
        for msg in keep:
            self.queue.put(msg)

    def _on_motion(self, event):
        col = self.tree.identify_column(event.x)
        rowid = self.tree.identify_row(event.y)
        action_col = self._get_action_col()

        # Reset all row tags
        for iid in self.tree.get_children():
            self.tree.item(iid, tags=())

        if rowid:
            if col == action_col:
                self.tree.config(cursor="hand2")
                self.tree.item(rowid, tags=("hover_action",))
            else:
                self.tree.config(cursor="")
                self.tree.item(rowid, tags=("hover",))

    def _on_click(self, event):
        item_id = self.tree.identify_row(event.y)
        col = self.tree.identify_column(event.x)
        action_col = self._get_action_col()
        if not item_id:
            return
        if col == action_col:
            token = None
            for t, iid in self.active_logs.items():
                if iid == item_id:
                    token = t
                    break
            if token and self.close_trade_callback:
                self.close_trade_callback(token)

    def _get_action_col(self):
        return f"#{self.columns[1:].index('Action') + 1}"
