import queue
import threading
import time

import customtkinter as ctk

from ..core.app_services import SenderService
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

        self.title("InfoSec Ultrasonic Sender")
        self.geometry("980x640")
        self.minsize(880, 580)

        self.kind_var = ctk.StringVar(value="text")
        self.command_var = ctk.StringVar(value="CALC")
        self.status_var = ctk.StringVar(value="Ready")
        self.key_fp_var = ctk.StringVar(value=self._format_fingerprint(self.settings.receiver_public_key))

        self._build_layout()
        self._append_log("Loaded sender settings.")
        self.after(120, self._drain_events)

    def _build_layout(self) -> None:
        self.grid_columnconfigure(0, weight=3)
        self.grid_columnconfigure(1, weight=2)
        self.grid_rowconfigure(1, weight=1)

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

        side = ctk.CTkFrame(self, corner_radius=16)
        side.grid(row=1, column=1, sticky="nsew", padx=(9, 18), pady=(0, 18))
        side.grid_rowconfigure(1, weight=1)
        ctk.CTkLabel(side, text="Recent Activity", font=("Segoe UI", 18, "bold")).grid(
            row=0, column=0, sticky="w", padx=18, pady=(18, 8)
        )
        self.log_box = ctk.CTkTextbox(side, state="disabled")
        self.log_box.grid(row=1, column=0, sticky="nsew", padx=18, pady=(0, 18))

        self._toggle_payload_inputs()

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

    def _start_send(self) -> None:
        payload_kind = self.kind_var.get()
        payload_body = self.text_box.get("1.0", "end").strip() if payload_kind == "text" else self.command_var.get().strip()
        receiver_key = self._receiver_key()

        self.send_button.configure(state="disabled")
        self.status_var.set("Preparing")
        self._style_status_badge()
        threading.Thread(target=self._send_worker, args=(payload_kind, payload_body, receiver_key), daemon=True).start()

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
                if self.status_var.get() != "Failed":
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


def main() -> None:
    app = SenderWindow()
    app.mainloop()


if __name__ == "__main__":
    main()
