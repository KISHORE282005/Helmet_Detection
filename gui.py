import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import threading
import logging
import sys
from pathlib import Path
from datetime import datetime

import config as cfg
from app import HelmetDetectionSystem

logging.basicConfig(
    level=getattr(logging, cfg.LOG_LEVEL),
    format=cfg.LOG_FORMAT,
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(cfg.LOGS_DIR / "gui.log", mode="a"),
    ],
)
logger = logging.getLogger(__name__)


class HelmetDetectionGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("AI Helmet Detection System")
        self.root.geometry("700x600")
        self.root.resizable(False, False)

        self.video_path = None
        self.system = HelmetDetectionSystem()

        self._build_ui()

    def _build_ui(self):
        header = tk.Label(
            self.root, text="AI-Based Helmet Detection & Safety Violation System",
            font=("Segoe UI", 14, "bold"), pady=15
        )
        header.pack(fill=tk.X)

        main_frame = ttk.Frame(self.root, padding=20)
        main_frame.pack(fill=tk.BOTH, expand=True)

        upload_frame = ttk.LabelFrame(main_frame, text="Video Selection", padding=15)
        upload_frame.pack(fill=tk.X, pady=(0, 15))

        btn_frame = ttk.Frame(upload_frame)
        btn_frame.pack(fill=tk.X)

        self.upload_btn = ttk.Button(
            btn_frame, text="Upload Video",
            command=self._select_video, width=20
        )
        self.upload_btn.pack(side=tk.LEFT)

        self.file_label = tk.Label(
            btn_frame, text="No video selected",
            font=("Segoe UI", 9), padx=10, anchor="w"
        )
        self.file_label.pack(side=tk.LEFT, fill=tk.X, expand=True)

        info_frame = ttk.LabelFrame(main_frame, text="Camera Information (Optional)", padding=15)
        info_frame.pack(fill=tk.X, pady=(0, 15))

        ttk.Label(info_frame, text="Camera Name:").grid(row=0, column=0, sticky="w", pady=2)
        self.cam_name_entry = ttk.Entry(info_frame, width=30)
        self.cam_name_entry.grid(row=0, column=1, sticky="w", pady=2, padx=(10, 0))
        self.cam_name_entry.insert(0, cfg.DEFAULT_CAMERA_NAME)

        ttk.Label(info_frame, text="Camera ID:").grid(row=1, column=0, sticky="w", pady=2)
        self.cam_id_entry = ttk.Entry(info_frame, width=30)
        self.cam_id_entry.grid(row=1, column=1, sticky="w", pady=2, padx=(10, 0))
        self.cam_id_entry.insert(0, cfg.DEFAULT_CAMERA_ID)

        ttk.Label(info_frame, text="Location:").grid(row=2, column=0, sticky="w", pady=2)
        self.location_entry = ttk.Entry(info_frame, width=30)
        self.location_entry.grid(row=2, column=1, sticky="w", pady=2, padx=(10, 0))
        self.location_entry.insert(0, cfg.DEFAULT_LOCATION)

        action_frame = ttk.Frame(main_frame)
        action_frame.pack(fill=tk.X, pady=(0, 15))

        self.process_btn = ttk.Button(
            action_frame, text="Start Processing",
            command=self._start_processing, width=20, state="disabled"
        )
        self.process_btn.pack(side=tk.LEFT)

        self.progress = ttk.Progressbar(
            action_frame, mode="indeterminate", length=400
        )
        self.progress.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(10, 0))

        log_frame = ttk.LabelFrame(main_frame, text="Processing Log", padding=10)
        log_frame.pack(fill=tk.BOTH, expand=True)

        text_frame = ttk.Frame(log_frame)
        text_frame.pack(fill=tk.BOTH, expand=True)

        scrollbar = ttk.Scrollbar(text_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.log_text = tk.Text(
            text_frame, height=12, font=("Consolas", 9),
            yscrollcommand=scrollbar.set, state="disabled",
            wrap=tk.WORD
        )
        self.log_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.config(command=self.log_text.yview)

        status_frame = ttk.Frame(main_frame)
        status_frame.pack(fill=tk.X, pady=(5, 0))

        self.status_label = tk.Label(
            status_frame, text="Ready", anchor="w",
            font=("Segoe UI", 9)
        )
        self.status_label.pack(side=tk.LEFT)

    def _select_video(self):
        path = filedialog.askopenfilename(
            title="Select CCTV Video",
            filetypes=[
                ("Video files", "*.mp4 *.avi *.mov *.mkv *.webm"),
                ("All files", "*.*"),
            ]
        )
        if path:
            self.video_path = path
            name = Path(path).name
            size = Path(path).stat().st_size / (1024 * 1024)
            self.file_label.config(text=f"{name} ({size:.1f} MB)")
            self.process_btn.config(state="normal")
            self._log(f"Selected: {name} ({size:.1f} MB)")

    def _log(self, message):
        self.log_text.config(state="normal")
        self.log_text.insert(tk.END, f"[{datetime.now().strftime('%H:%M:%S')}] {message}\n")
        self.log_text.see(tk.END)
        self.log_text.config(state="disabled")
        self.root.update_idletasks()

    def _set_processing_state(self, processing):
        state = "disabled" if processing else "normal"
        self.upload_btn.config(state=state)
        self.process_btn.config(state=state)
        self.cam_name_entry.config(state=state)
        self.cam_id_entry.config(state=state)
        self.location_entry.config(state=state)
        if processing:
            self.progress.start(10)
            self.status_label.config(text="Processing...")
        else:
            self.progress.stop()
            self.status_label.config(text="Ready")

    def _start_processing(self):
        if not self.video_path:
            messagebox.showwarning("No Video", "Please select a video first.")
            return

        self._set_processing_state(True)

        def run():
            try:
                self._log("=" * 50)
                self._log("Processing started...")

                result = self.system.process_video(
                    self.video_path,
                    camera_name=self.cam_name_entry.get() or None,
                    camera_id=self.cam_id_entry.get() or None,
                    location=self.location_entry.get() or None,
                )

                self._log("=" * 50)
                self._log("PROCESSING COMPLETE")
                self._log(f"  Video:        {result['video_name']}")
                self._log(f"  Total frames: {result['total_frames']}")
                self._log(f"  Processed:    {result['frames_processed']}")
                self._log(f"  Violations:   {result['violations']}")
                self._log(f"  Time:         {result['elapsed_seconds']:.1f}s")
                if result['report_path']:
                    self._log(f"  Report:       {result['report_path']}")
                self._log("=" * 50)

                self._set_processing_state(False)

                if result['violations'] > 0:
                    messagebox.showinfo(
                        "Processing Complete",
                        f"Detected {result['violations']} violations.\n"
                        f"Report saved to:\n{result['report_path']}"
                    )
                else:
                    messagebox.showinfo(
                        "Processing Complete",
                        "No violations detected."
                    )

            except Exception as e:
                logger.exception("Processing failed")
                self._log(f"ERROR: {e}")
                self._set_processing_state(False)
                messagebox.showerror("Error", str(e))

        threading.Thread(target=run, daemon=True).start()


def main():
    root = tk.Tk()
    app = HelmetDetectionGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
