import tkinter as tk
from tkinter import ttk, messagebox
import ast
from interface.styling import *



class SettingsConfigUI(tk.Toplevel):
    def __init__(self, parent, on_save=None):
        super().__init__(parent)
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self.title("Sniper Bot Settings")
        self.geometry("700x750")
        self.configure(bg=BG_COLOR)

        self.parent = parent
        self.ctx = parent.ctx 
        self.on_save = on_save
        self.settings = self.ctx.settings
        self.entries = {}

        # Apply custom style
        self._configure_styles()

        # Scrollable frame
        container = ttk.Frame(self)
        canvas = tk.Canvas(container, bg=BG_COLOR, highlightthickness=0)
        scrollbar = ttk.Scrollbar(container, orient="vertical", command=canvas.yview)
        self.scrollable_frame = ttk.Frame(canvas, style="Custom.TFrame")

        self.scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        container.pack(fill="both", expand=True)
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        self._build_form()
        self._add_buttons(container)

    def _configure_styles(self):
        style = ttk.Style()
        style.theme_use("default")

        # Labels
        style.configure("TLabel", background=BG_COLOR, foreground=FG_COLOR_WHITE, font=GLOBAL_FONT)
        style.configure("FormLabel.TLabel", background=BG_COLOR, foreground="white", font=("Segoe UI", 10, "bold"))
        style.configure("Description.TLabel", background=BG_COLOR, foreground="#AAAAAA", font=("Segoe UI", 8))

        # Checkboxes (remove hover effect)
        style.configure("Dark.TCheckbutton",
                        background=BG_COLOR,
                        foreground="white",
                        font=("Segoe UI", 10)),
        

        # Disable hover effect (state map override)
        style.map("Dark.TCheckbutton",
                background=[("active", BG_COLOR), ("selected", BG_COLOR)],
                foreground=[("active", "white"), ("selected", "white")])

        # Frames
        style.configure("Custom.TFrame", background=BG_COLOR)
        style.configure("Section.TLabelframe", background=BG_COLOR)
        style.configure("Section.TLabelframe.Label", background=BG_COLOR, foreground="white", font=("Segoe UI", 12, "bold"))

        # Buttons
        style.configure("TButton", background=BTN_COLOR, foreground=FG_COLOR_WHITE, font=GLOBAL_FONT)

    def _build_form(self):
        row = 0

            # --- General Section ---
        general_frame = ttk.LabelFrame(self.scrollable_frame, text="🛠 General Settings", style="Section.TLabelframe")
        general_frame.grid(row=row, column=0, columnspan=2, sticky="ew", padx=20, pady=10)
        row += 1

        # NETWORK dropdown
        ttk.Label(general_frame, text="NETWORK", style="FormLabel.TLabel").grid(sticky="w", padx=10, pady=(6, 2))
        self.network_var = tk.StringVar(value=self.settings.get("NETWORK", "mainnet"))
        self.network_dropdown = ttk.Combobox(
            general_frame,
            textvariable=self.network_var,
            values=["mainnet", "devnet"],
            state="readonly",
            width=15
        )
        self.network_dropdown.grid(row=0, column=1, sticky="w", padx=10, pady=(6, 2))

        desc_label = ttk.Label(general_frame, text="Blockchain network to use", style="Description.TLabel")
        desc_label.grid(row=1, column=0, columnspan=2, sticky="w", padx=10)

        # UI Mode toggle
        # UI Mode "locked" checkbox
        self.ui_mode_var = tk.BooleanVar(value=self.settings.get("UI_MODE", False))

        chk = ttk.Checkbutton(
            general_frame,
            text="UI_MODE",
            variable=self.ui_mode_var,
            style="Dark.TCheckbutton"
        )
        chk.state(["selected", "disabled"])  # force it enabled + non-editable
        chk.grid(row=2, column=0, columnspan=2, sticky="w", padx=10, pady=4)

        desc_label = ttk.Label(
            general_frame,
            text="Graphical interface mode is enabled (cannot be changed here).",
            style="Description.TLabel"
        )
        desc_label.grid(row=3, column=0, columnspan=2, sticky="w", padx=10, pady=(0, 4))


        # --- Trading Section ---
        trading_frame = ttk.LabelFrame(self.scrollable_frame, text="⚙️ Trading Settings", style="Section.TLabelframe")
        trading_frame.grid(row=row, column=0, columnspan=2, sticky="ew", padx=20, pady=10)
        row += 1

        self._add_entry(trading_frame, "MIN_TOKEN_LIQUIDITY", self.settings["MIN_TOKEN_LIQUIDITY"], "Minimum USD liquidity required.")
        self._add_entry(trading_frame, "MAX_TOKEN_AGE_SECONDS", self.settings["MAX_TOKEN_AGE_SECONDS"], "Max age in seconds.")
        self._add_entry(trading_frame, "TRADE_AMOUNT", self.settings["TRADE_AMOUNT"], "USD per trade.")
        self._add_entry(trading_frame, "MAXIMUM_TRADES", self.settings["MAXIMUM_TRADES"], "Max trades before stopping.")
        self._add_checkbox(trading_frame, "SIM_MODE", self.settings["SIM_MODE"],"Simulate trades instead of real execution.")


        # --- Risk Management ---
        risk_frame = ttk.LabelFrame(self.scrollable_frame, text="🛡️ Risk Management", style="Section.TLabelframe")
        risk_frame.grid(row=row, column=0, columnspan=2, sticky="ew", padx=20, pady=10)
        row += 1

        self._add_entry(risk_frame, "SLPG", self.settings["SLPG"], "Maximum slippage tolerance (as a fraction).")
        self._add_entry(risk_frame, "TP", self.settings["TP"], "Take-profit multiplier.")
        self._add_entry(risk_frame, "SL", self.settings["SL"], "Emergency stop-loss threshold.")
        self._add_entry(risk_frame, "TRAILING_STOP", self.settings["TRAILING_STOP"], "Trailing stop-loss % from peak.")
        self._add_entry(risk_frame, "MIN_TSL_TRIGGER_MULTIPLIER", self.settings["MIN_TSL_TRIGGER_MULTIPLIER"], "Pump multiplier to enable TSL.")
        self._add_entry(risk_frame, "TIMEOUT_SECONDS", self.settings["TIMEOUT_SECONDS"], "Max hold time (seconds) before timeout check.")



        # --- Exit Rules ---
        exit_frame = ttk.LabelFrame(self.scrollable_frame, text="📤 Exit Rules", style="Section.TLabelframe")
        exit_frame.grid(row=row, column=0, columnspan=2, sticky="ew", padx=20, pady=10)
        row += 1
        self.exit_flags = {}
        for flag, val in self.settings["EXIT_RULES"].items():
            var = tk.BooleanVar(value=val)
            chk = ttk.Checkbutton(exit_frame, text=flag, variable=var, style="Dark.TCheckbutton")
            chk.pack(anchor="w", padx=10, pady=2)
            self.exit_flags[flag] = var
        # --- API Rate Limits ---
        rate_frame = ttk.LabelFrame(self.scrollable_frame, text="🌐 API Rate Limits", style="Section.TLabelframe")
        rate_frame.grid(row=row, column=0, columnspan=2, sticky="ew", padx=20, pady=10)
        row += 1

        self.rate_limit_entries = {}
        for api, cfg in self.settings["RATE_LIMITS"].items():
            api_frame = ttk.LabelFrame(rate_frame, text=cfg["name"], style="Section.TLabelframe")
            api_frame.pack(fill="x", padx=10, pady=5)

            # min_interval
            self._add_entry(api_frame, f"{api}_min_interval", cfg["min_interval"], "Minimum seconds between requests")

            # jitter_range (aligned like other fields)
            jitter_label = ttk.Label(api_frame, text="jitter_range", style="FormLabel.TLabel")
            jitter_label.grid(sticky="w", padx=10, pady=(6, 2))

            jitter_container = ttk.Frame(api_frame, style="Custom.TFrame")
            jitter_container.grid(row=jitter_label.grid_info()["row"], column=1, sticky="w", padx=10, pady=(6, 2))

            j_min = tk.Entry(jitter_container, width=8, bg="#2c3e50", fg="white",
                            insertbackground="white", relief="flat")
            j_min.insert(0, str(cfg["jitter_range"][0]))
            j_min.pack(side="left", padx=(0, 5))

            j_max = tk.Entry(jitter_container, width=8, bg="#2c3e50", fg="white",
                            insertbackground="white", relief="flat")
            j_max.insert(0, str(cfg["jitter_range"][1]))
            j_max.pack(side="left")

            self.rate_limit_entries[f"{api}_jitter_range"] = (j_min, j_max)

            # description
            desc_label = ttk.Label(api_frame, text="Random jitter range for API calls.", style="Description.TLabel")
            desc_label.grid(row=jitter_label.grid_info()["row"] + 1, column=0, columnspan=2, sticky="w", padx=10)


            # max_requests_per_minute
            self._add_entry(api_frame, f"{api}_max_rpm", cfg["max_requests_per_minute"] or "", "Max requests per minute (blank = unlimited)")

        # --- Notifications ---
        notify_frame = ttk.LabelFrame(self.scrollable_frame, text="🔔 Notifications", style="Section.TLabelframe")
        notify_frame.grid(row=row, column=0, columnspan=2, sticky="ew", padx=20, pady=10)
        row += 1
        self.notify_flags = {}
        for flag, val in self.settings["NOTIFY"].items():
            if isinstance(val, bool):
                var = tk.BooleanVar(value=val)
                chk = ttk.Checkbutton(notify_frame, text=flag, variable=var, style="Dark.TCheckbutton")
                chk.pack(anchor="w", padx=10, pady=2)
                self.notify_flags[flag] = var

    def _add_buttons(self, container):
        button_frame = ttk.Frame(self, style="Custom.TFrame")
        button_frame.pack(fill="x", pady=10)

        btn = tk.Button(button_frame,
                        text="💾 Save and Continue",
                        command=self._save_and_continue,
                        bg=BTN_COLOR,
                        fg=FG_COLOR_WHITE,
                        font=GLOBAL_FONT)
        btn.pack(pady=10)

    def _add_entry(self, parent, key, value, desc=""):
        label = ttk.Label(parent, text=key, style="FormLabel.TLabel")
        label.grid(sticky="w", padx=10, pady=(6, 2))

        # Use tk.Entry instead of ttk.Entry for full control
        entry = tk.Entry(
            parent,
            width=30,
            bg="#2c3e50",
            fg="white",
            insertbackground="white",  # makes cursor white
            relief="flat",
            font=("Segoe UI", 10)
        )
        entry.insert(0, str(value))
        entry.grid(row=label.grid_info()["row"], column=1, sticky="ew", padx=10, pady=(6, 2))
        self.entries[key] = entry

        if desc:
            desc_label = ttk.Label(parent, text=desc, style="Description.TLabel")
            desc_label.grid(row=label.grid_info()["row"] + 1, column=0, columnspan=2, sticky="w", padx=10)

    def _add_checkbox(self, parent, key, value, desc="", row=None):
        var = tk.BooleanVar(value=value)
        chk = ttk.Checkbutton(parent, text=key, variable=var, style="Dark.TCheckbutton")
        if row is None:
            chk.grid(sticky="w", padx=10, pady=4)
        else:
            chk.grid(row=row, column=0, columnspan=2, sticky="w", padx=10, pady=4)
        self.entries[key] = var

        if desc:
            desc_label = ttk.Label(parent, text=desc, style="Description.TLabel")
            desc_label.grid(row=chk.grid_info()["row"] + 1,
                            column=0, columnspan=2, sticky="w", padx=10, pady=(0, 4))

    def _save_and_continue(self):
        # Save exit rules
        if hasattr(self, "exit_flags"):
            for flag, var in self.exit_flags.items():
                self.settings["EXIT_RULES"][flag] = var.get()

        # Save notifications
        if hasattr(self, "notify_flags"):
            for flag, widget in self.notify_flags.items():
                if isinstance(widget, tk.BooleanVar):
                    self.settings["NOTIFY"][flag] = widget.get()
                else:
                    self.settings["NOTIFY"][flag] = widget.get().strip()

        # Save normal entries
        for key, widget in self.entries.items():
            if isinstance(widget, tk.BooleanVar):
                val_cast = widget.get()
            else:
                val = widget.get().strip()
                try:
                    val_cast = ast.literal_eval(val)
                except (ValueError, SyntaxError):
                    val_cast = val
            self.settings[key] = val_cast
        # Save rate limits
        if hasattr(self, "rate_limit_entries"):
            for api, cfg in self.settings["RATE_LIMITS"].items():
                # min_interval
                min_key = f"{api}_min_interval"
                if min_key in self.entries:
                    val = self.entries[min_key].get().strip()
                    try:
                        cfg["min_interval"] = float(val)
                    except ValueError:
                        cfg["min_interval"] = val

                # max_requests_per_minute
                rpm_key = f"{api}_max_rpm"
                if rpm_key in self.entries:
                    val = self.entries[rpm_key].get().strip()
                    try:
                        cfg["max_requests_per_minute"] = int(val) if val else None
                    except ValueError:
                        cfg["max_requests_per_minute"] = None
                # jitter_range
                jr_key = f"{api}_jitter_range"
                if jr_key in self.rate_limit_entries:
                    j_min, j_max = self.rate_limit_entries[jr_key]
                    try:
                        j_min_val = float(j_min.get().strip())
                        j_max_val = float(j_max.get().strip())
                        cfg["jitter_range"] = [j_min_val, j_max_val]
                    except ValueError:
                        pass  # keep old values if parsing fails
        # ✅ Save selected network
        if hasattr(self, "network_var"):
            self.settings["NETWORK"] = self.network_var.get()
            self.parent.ctx.settings_manager.save_settings(self.settings)
        if self.on_save: 
            self.on_save()                   
        messagebox.showinfo("Settings Saved", "✅ Your settings have been saved successfully.")
        self.destroy()

    def _on_close(self):
        if messagebox.askyesno("Exit without saving?", "⚠️ Your changes will be lost. Continue?"):
            messagebox.showinfo("Defaults Loaded", "The bot will start with **default settings**.")          
            self.destroy()
