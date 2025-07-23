import tkinter as tk
from tkinter import ttk, messagebox
from config.settings import save_settings, get_bot_settings
import ast
from interface.styling import *

FIELD_DESCRIPTIONS = {
    "MIN_TOKEN_LIQUIDITY": "Minimum USD liquidity required to consider a token.",
    "MAX_TOKEN_AGE_SECONDS": "Max age (in seconds) of a token since mint.",
    "TRADE_AMOUNT": "Amount (USD) used per trade.",
    "MAXIMUM_TRADES": "Max number of trades allowed before stopping.",
    "SIM_MODE": "Simulate trades without real execution (True/False).",
    "TP": "Take-profit multiplier (e.g. 4.0 = 300% gain).",
    "SL": "Emergency stop-loss threshold (e.g. 0.25 = -25%).",
    "TRAILING_STOP": "Trailing stop-loss percentage from peak (e.g. 0.2 = 20%).",
    "MIN_TSL_TRIGGER_MULTIPLIER": "Pump multiplier required to enable TSL (e.g. 1.5 = +50%).",
    "RATE_LIMITS.helius.min_interval": "Minimum delay between Helius API calls (sec).",
    "RATE_LIMITS.helius.jitter_range": "Random jitter range for Helius API calls.",
    "RATE_LIMITS.jupiter.min_interval": "Minimum delay between Jupiter API calls (sec).",
    "RATE_LIMITS.jupiter.jitter_range": "Random jitter range for Jupiter API calls.",
    "RATE_LIMITS.jupiter.max_requests_per_minute": "Jupiter API rate limit."
}


class SettingsConfigUI(tk.Tk):
    def __init__(self):
        super().__init__()
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self.title("Sniper Bot Settings")
        self.geometry("650x700")
        self.configure(bg=BG_COLOR)

        self.settings = get_bot_settings()
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
        style.configure("TLabel", background=BG_COLOR, foreground=FG_COLOR_WHITE, font=GLOBAL_FONT)
        style.configure("TEntry", font=GLOBAL_FONT)
        style.configure("TButton", background=BTN_COLOR, foreground=FG_COLOR_WHITE, font=GLOBAL_FONT)
        style.configure("Description.TLabel", background=BG_COLOR, foreground="#AAAAAA", font=("Segoe UI", 8))
        style.configure("Custom.TFrame", background=BG_COLOR)

    def _build_form(self):
        row = 0
        for key, value in self.settings.items():
            if key == "UI_MODE":
                continue
            if isinstance(value, dict):
                for subkey, subval in value.items():
                    if isinstance(subval, dict):
                        for nested_key, nested_val in subval.items():
                            full_key = f"{key}.{subkey}.{nested_key}"
                            self._create_entry(full_key, nested_val, row)
                            row += 2
                    else:
                        full_key = f"{key}.{subkey}"
                        self._create_entry(full_key, subval, row)
                        row += 2
            else:
                self._create_entry(key, value, row)
                row += 2

    def _create_entry(self, key, value, row):
        label = ttk.Label(self.scrollable_frame, text=key)
        label.grid(row=row, column=0, sticky="w", padx=20, pady=(10, 2))

        entry = ttk.Entry(self.scrollable_frame, width=40)
        entry.insert(0, str(value))
        entry.grid(row=row, column=1, padx=10, pady=(10, 2), sticky="w")
        self.entries[key] = entry

        desc_text = FIELD_DESCRIPTIONS.get(key, "")
        if desc_text:
            desc = ttk.Label(self.scrollable_frame, text=desc_text, style="Description.TLabel")
            desc.grid(row=row + 1, column=0, columnspan=2, sticky="w", padx=20, pady=(0, 8))

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


    def _save_and_continue(self):
        for key, entry in self.entries.items():
            parts = key.split(".")
            val = entry.get().strip()
            try:
                val_cast = ast.literal_eval(val)
            except (ValueError, SyntaxError):
                val_cast = val  # fallback to string

            current = self.settings
            for part in parts[:-1]:
                current = current[part]
            current[parts[-1]] = val_cast

        save_settings(self.settings)
        messagebox.showinfo("Settings Saved", "✅ Your settings have been saved successfully.")
        self.destroy()
    def _on_close(self):
        if messagebox.askyesno("Exit without saving?", "⚠️ Your changes will be lost. Continue?"):
            messagebox.showinfo("Defaults Loaded", "The bot will start with **default settings**.")          
            self.destroy()