import queue
import threading
import time

import customtkinter as ctk

from ..core.app_services import SenderService
from ..core.audio_transport import list_output_devices
from ..core.crypto_session import key_fingerprint
from ..core.errors import InfoSecError
from ..core.settings import ensure_local_settings, save_sender_settings

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")


class SenderWindow(ctk.CTk):
    def __init__(self):
        super().__init__()
        sender_settings, receiver_settings = ensure_local_settings()
        if not sender_settings.receiver_public_key:
            sender_settings.receiver_public_key = receiver_settings.receiver_public_key
            save_sender_settings(sender_settings)

        self.settings = sender_settings
        self.service = SenderService(self.settings)
        self.ui_events: queue.Queue[dict] = queue.Queue()

        # Enumerate output devices (guarded against failure)
        try:
            self.output_devices = list_output_devices()
        except Exception:
            self.output_devices = []

        self.title("InfoSec Ultrasonic Sender")
        self.geometry("1020x720")
        self.minsize(900, 620)

        self.kind_var = ctk.StringVar(value="text")
        self.command_var = ctk.StringVar(value="CALC")
        self.status_var = ctk.StringVar(value="Ready")
        self.key_fp_var = ctk.StringVar(value=self._format_fingerprint(self.settings.receiver_public_key))
        self.volume_var = ctk.IntVar(value=self.settings.output_volume)
        self.device_var = ctk.StringVar(value=self._current_output_device_label())

        self._build_layout()
        self._append_log("Loaded sender settings.")
        self.after(120, self._drain_events)

    # ─── Device helpers ───────────────────────────────────────────────────────

    def _output_device_options(self) -> list[dict]:
        options = [{"label": "Default device", "index": None}]
        for item in self.output_devices:
            options.append({"label": f"{item['index']}: {item['name']}", "index": item["index"]})
        return options

    def _current_output_device_label(self) -> str:
        for item in self._output_device_options():
            if item["index"] == self.settings.output_device_index:
                return item["label"]
        return "Default device"

    def _selected_output_device_index(self) -> int | None:
        label = self.device_var.get()
        for item in self._output_device_options():
            if item["label"] == label:
                return item["index"]
        return None

    # ─── Layout ───────────────────────────────────────────────────────────────

    def _build_layout(self) -> None:
        self.grid_columnconfigure(0, weight=3)
        self.grid_columnconfigure(1, weight=2)
        self.grid_rowconfigure(1, weight=1)

        # Header
        header = ctk.CTkFrame(self, corner_radius=16)
        header.grid(row=0, column=0, columnspan=2, sticky="ew", padx=18, pady=(18, 12))
        header.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(header, text="InfoSec Ultrasonic Sender", font=("Segoe UI", 28, "bold")).grid(
            row=0, column=0, sticky="w", padx=18, pady=(16, 4)
        )
        ctk.CTkLabel(
            header,
            text="Send encrypted text or allowlisted commands over ultrasonic audio.",
            text_color="#b7c1d1",
        ).grid(row=1, column=0, sticky="w", padx=18, pady=(0, 16))
        self.status_badge = ctk.CTkLabel(
            header,
            textvariable=self.status_var,
            fg_color="#1f6aa5",
            corner_radius=999,
            padx=18,
            pady=8,
        )
        self.status_badge.grid(row=0, column=1, rowspan=2, padx=18)

        # ── Main left panel ──
        main = ctk.CTkFrame(self, corner_radius=16)
        main.grid(row=1, column=0, sticky="nsew", padx=(18, 9), pady=(0, 18))
        main.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(main, text="Payload Type", font=("Segoe UI", 18, "bold")).grid(
            row=0, column=0, sticky="w", padx=18, pady=(18, 8)
        )
        kind_control = ctk.CTkSegmentedButton(
            main,
            values=["text", "command"],
            variable=self.kind_var,
            command=lambda _: self._toggle_payload_inputs(),
        )
        kind_control.grid(row=1, column=0, sticky="ew", padx=18)

        self.text_box = ctk.CTkTextbox(main, height=170)
        self.text_box.grid(row=2, column=0, sticky="nsew", padx=18, pady=(14, 0))
        self.text_box.insert("1.0", "Type a secure message here...")
        self.text_box.bind("<FocusIn>", self._clear_default_text)

        self.command_box = ctk.CTkComboBox(main, values=["CALC", "LOCK", "NOTEPAD"], variable=self.command_var)
        self.command_box.grid(row=3, column=0, sticky="ew", padx=18, pady=(14, 0))

        key_frame = ctk.CTkFrame(main, corner_radius=12)
        key_frame.grid(row=4, column=0, sticky="ew", padx=18, pady=(18, 0))
        key_frame.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(key_frame, text="Receiver Public Key", font=("Segoe UI", 16, "bold")).grid(
            row=0, column=0, sticky="w", padx=14, pady=(12, 6)
        )
        self.key_entry = ctk.CTkTextbox(key_frame, height=110)
        self.key_entry.grid(row=1, column=0, sticky="ew", padx=14)
        self.key_entry.insert("1.0", self.settings.receiver_public_key)
        self.key_entry.bind("<KeyRelease>", lambda _: self._update_fingerprint())
        ctk.CTkLabel(key_frame, textvariable=self.key_fp_var, text_color="#9fc5ff").grid(
            row=2, column=0, sticky="w", padx=14, pady=(8, 12)
        )

        actions = ctk.CTkFrame(main, fg_color="transparent")
        actions.grid(row=5, column=0, sticky="ew", padx=18, pady=(18, 18))
        actions.grid_columnconfigure((0, 1), weight=1)
        self.send_button = ctk.CTkButton(actions, text="Send", command=self._start_send, height=40)
        self.send_button.grid(row=0, column=0, sticky="ew", padx=(0, 6))
        ctk.CTkButton(actions, text="Save Key", command=self._save_receiver_key, height=40).grid(
            row=0, column=1, sticky="ew", padx=(6, 0)
        )

        # ── Right sidebar ──
        side = ctk.CTkFrame(self, corner_radius=16)
        side.grid(row=1, column=1, sticky="nsew", padx=(9, 18), pady=(0, 18))
        side.grid_rowconfigure(3, weight=1)
        side.grid_columnconfigure(0, weight=1)

        # Audio settings section
        ctk.CTkLabel(side, text="Audio Settings", font=("Segoe UI", 18, "bold")).grid(
            row=0, column=0, sticky="w", padx=18, pady=(18, 8)
        )
        audio_frame = ctk.CTkFrame(side, corner_radius=12)
        audio_frame.grid(row=1, column=0, sticky="ew", padx=18)
        audio_frame.grid_columnconfigure(0, weight=1)

        # Output device picker
        ctk.CTkLabel(audio_frame, text="Output Device").grid(row=0, column=0, sticky="w", padx=14, pady=(12, 6))
        device_values = [item["label"] for item in self._output_device_options()] or ["Default device"]
        self.device_menu = ctk.CTkComboBox(audio_frame, values=device_values, variable=self.device_var)
        self.device_menu.grid(row=1, column=0, sticky="ew", padx=14)

        # Volume slider
        vol_header = ctk.CTkFrame(audio_frame, fg_color="transparent")
        vol_header.grid(row=2, column=0, sticky="ew", padx=14, pady=(14, 0))
        vol_header.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(vol_header, text="Volume").grid(row=0, column=0, sticky="w")
        self.vol_label = ctk.CTkLabel(vol_header, text=f"{self.volume_var.get()}%", text_color="#9fc5ff")
        self.vol_label.grid(row=0, column=1, sticky="e")

        self.volume_slider = ctk.CTkSlider(
            audio_frame,
            from_=10,
            to=100,
            variable=self.volume_var,
            command=self._on_volume_change,
        )
        self.volume_slider.grid(row=3, column=0, sticky="ew", padx=14, pady=(6, 0))

        ctk.CTkButton(
            audio_frame,
            text="Apply Audio Settings",
            command=self._apply_audio_settings,
            height=36,
        ).grid(row=4, column=0, sticky="ew", padx=14, pady=(12, 12))

        # Activity log section
        log_header_frame = ctk.CTkFrame(side, fg_color="transparent")
        log_header_frame.grid(row=2, column=0, sticky="ew", padx=18, pady=(18, 8))
        log_header_frame.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(log_header_frame, text="Recent Activity", font=("Segoe UI", 18, "bold")).grid(
            row=0, column=0, sticky="w"
        )
        ctk.CTkButton(
            log_header_frame,
            text="Clear",
            width=70,
            height=28,
            fg_color="#2b2d42",
            hover_color="#3a3c54",
            command=self._clear_log,
        ).grid(row=0, column=1, sticky="e")

        self.log_box = ctk.CTkTextbox(side, state="disabled")
        self.log_box.grid(row=3, column=0, sticky="nsew", padx=18, pady=(0, 18))

        self._toggle_payload_inputs()

    # ─── Audio settings ───────────────────────────────────────────────────────

    def _on_volume_change(self, value: float) -> None:
        self.vol_label.configure(text=f"{int(value)}%")

    def _apply_audio_settings(self) -> None:
        self.settings.output_device_index = self._selected_output_device_index()
        self.settings.output_volume = int(self.volume_var.get())
        save_sender_settings(self.settings)
        self._append_log(
            f"Audio settings saved — device: {self.device_var.get()}, volume: {self.settings.output_volume}%"
        )

    # ─── Payload helpers ──────────────────────────────────────────────────────

    def _clear_default_text(self, _event) -> None:
        if self.text_box.get("1.0", "end").strip() == "Type a secure message here...":
            self.text_box.delete("1.0", "end")

    def _toggle_payload_inputs(self) -> None:
        if self.kind_var.get() == "text":
            self.command_box.grid_remove()
            self.text_box.grid()
        else:
            self.text_box.grid_remove()
            self.command_box.grid()

    # ─── Key helpers ──────────────────────────────────────────────────────────

    def _update_fingerprint(self) -> None:
        self.key_fp_var.set(self._format_fingerprint(self._receiver_key()))

    def _format_fingerprint(self, public_key: str) -> str:
        try:
            return f"Fingerprint: {key_fingerprint(public_key)}" if public_key.strip() else "Fingerprint: n/a"
        except InfoSecError:
            return "Fingerprint: invalid key"

    def _receiver_key(self) -> str:
        return self.key_entry.get("1.0", "end").strip()

    def _save_receiver_key(self) -> None:
        self.settings.receiver_public_key = self._receiver_key()
        save_sender_settings(self.settings)
        self._update_fingerprint()
        self._append_log("Saved receiver public key to config/sender.json.")

    # ─── Send logic ───────────────────────────────────────────────────────────

    def _start_send(self) -> None:
        # Snapshot current audio settings before sending
        self.settings.output_device_index = self._selected_output_device_index()
        self.settings.output_volume = int(self.volume_var.get())

        payload_kind = self.kind_var.get()
        payload_body = (
            self.text_box.get("1.0", "end").strip() if payload_kind == "text" else self.command_var.get().strip()
        )
        receiver_key = self._receiver_key()

        self.send_button.configure(state="disabled")
        self.status_var.set("Preparing")
        self._style_status_badge()
        threading.Thread(
            target=self._send_worker, args=(payload_kind, payload_body, receiver_key), daemon=True
        ).start()

    def _send_worker(self, payload_kind: str, payload_body: str, receiver_key: str) -> None:
        try:
            self.settings.receiver_public_key = receiver_key
            save_sender_settings(self.settings)
            self.service.send(
                payload_kind,
                payload_body,
                receiver_key,
                progress=lambda code, message: self.ui_events.put({"type": "progress", "code": code, "message": message}),
            )
        except (InfoSecError, ValueError) as exc:
            self.ui_events.put({"type": "error", "message": str(exc)})
        except Exception as exc:
            self.ui_events.put({"type": "error", "message": f"Unexpected sender error: {exc}"})
        finally:
            self.ui_events.put({"type": "send_complete"})

    # ─── Event loop ───────────────────────────────────────────────────────────

    def _drain_events(self) -> None:
        while not self.ui_events.empty():
            event = self.ui_events.get()
            if event["type"] == "progress":
                self.status_var.set(event["code"].replace("_", " ").title())
                self._append_log(event["message"])
            elif event["type"] == "error":
                self.status_var.set("Failed")
                self._append_log(event["message"])
            elif event["type"] == "send_complete":
                self.send_button.configure(state="normal")
                if self.status_var.get() not in {"Failed"}:
                    self.status_var.set("Ready")
            self._style_status_badge()
        self.after(120, self._drain_events)

    def _style_status_badge(self) -> None:
        state = self.status_var.get().lower()
        if state in {"done", "ready"}:
            color = "#1f6f43"
        elif state == "failed":
            color = "#9f2d2d"
        elif state in {"preparing", "encoding", "encrypting", "transmitting"}:
            color = "#1f6aa5"
        else:
            color = "#495057"
        self.status_badge.configure(fg_color=color)

    def _append_log(self, message: str) -> None:
        timestamp = time.strftime("%H:%M:%S")
        self.log_box.configure(state="normal")
        self.log_box.insert("end", f"[{timestamp}] {message}\n")
        self.log_box.see("end")
        self.log_box.configure(state="disabled")

    def _clear_log(self) -> None:
        self.log_box.configure(state="normal")
        self.log_box.delete("1.0", "end")
        self.log_box.configure(state="disabled")


def main() -> None:
    app = SenderWindow()
    app.mainloop()


if __name__ == "__main__":
    main()
