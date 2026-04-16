import queue
import threading
import time

import customtkinter as ctk

from ..core.app_services import ReceiverService
from ..core.audio_transport import AudioReceiver, list_input_devices
from ..core.crypto_session import key_fingerprint
from ..core.settings import ensure_local_settings, save_receiver_settings

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")


class ReceiverWindow(ctk.CTk):
    def __init__(self):
        super().__init__()
        _, receiver_settings = ensure_local_settings()

        self.settings = receiver_settings
        self.service = ReceiverService(self.settings)
        self.ui_events: queue.Queue[dict] = queue.Queue()
        self.stop_event = threading.Event()
        self.listener_thread: threading.Thread | None = None
        self.pending_cards: dict[str, ctk.CTkFrame] = {}
        self.input_devices = list_input_devices()

        self.title("InfoSec Ultrasonic Receiver")
        self.geometry("1160x700")
        self.minsize(980, 620)

        self.status_var = ctk.StringVar(value="Idle")
        self.command_mode_var = ctk.BooleanVar(value=self.settings.command_execution_enabled)
        self.device_var = ctk.StringVar(value=self._current_device_label())
        self.fingerprint_var = ctk.StringVar(value=f"Receiver Key: {key_fingerprint(self.settings.receiver_public_key)}")

        self._build_layout()
        self._append_log("Loaded receiver settings.")
        self.after(120, self._drain_events)
        self.after(200, self.start_listening)

    def _build_layout(self) -> None:
        self.grid_columnconfigure(0, weight=3)
        self.grid_columnconfigure(1, weight=2)
        self.grid_rowconfigure(1, weight=1)

        header = ctk.CTkFrame(self, corner_radius=16)
        header.grid(row=0, column=0, columnspan=2, sticky="ew", padx=18, pady=(18, 12))
        header.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(header, text="InfoSec Ultrasonic Receiver", font=("Segoe UI", 28, "bold")).grid(
            row=0, column=0, sticky="w", padx=18, pady=(16, 4)
        )
        ctk.CTkLabel(header, textvariable=self.fingerprint_var, text_color="#b7c1d1").grid(
            row=1, column=0, sticky="w", padx=18, pady=(0, 16)
        )
        self.status_badge = ctk.CTkLabel(
            header,
            textvariable=self.status_var,
            fg_color="#495057",
            corner_radius=999,
            padx=18,
            pady=8,
        )
        self.status_badge.grid(row=0, column=1, rowspan=2, padx=18)

        left = ctk.CTkFrame(self, corner_radius=16)
        left.grid(row=1, column=0, sticky="nsew", padx=(18, 9), pady=(0, 18))
        left.grid_rowconfigure(1, weight=1)

        ctk.CTkLabel(left, text="Activity Log", font=("Segoe UI", 18, "bold")).grid(
            row=0, column=0, sticky="w", padx=18, pady=(18, 8)
        )
        self.log_box = ctk.CTkTextbox(left, state="disabled")
        self.log_box.grid(row=1, column=0, sticky="nsew", padx=18, pady=(0, 18))

        right = ctk.CTkFrame(self, corner_radius=16)
        right.grid(row=1, column=1, sticky="nsew", padx=(9, 18), pady=(0, 18))
        right.grid_rowconfigure(3, weight=1)

        ctk.CTkLabel(right, text="Settings", font=("Segoe UI", 18, "bold")).grid(
            row=0, column=0, sticky="w", padx=18, pady=(18, 8)
        )
        settings_frame = ctk.CTkFrame(right, corner_radius=12)
        settings_frame.grid(row=1, column=0, sticky="ew", padx=18)
        settings_frame.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(settings_frame, text="Input Device").grid(row=0, column=0, sticky="w", padx=14, pady=(12, 6))
        device_values = [item["label"] for item in self._device_options()] or ["Default device"]
        self.device_menu = ctk.CTkComboBox(settings_frame, values=device_values, variable=self.device_var)
        self.device_menu.grid(row=1, column=0, sticky="ew", padx=14)

        self.command_switch = ctk.CTkSwitch(
            settings_frame,
            text="Enable local command execution",
            variable=self.command_mode_var,
            onvalue=True,
            offvalue=False,
        )
        self.command_switch.grid(row=2, column=0, sticky="w", padx=14, pady=(14, 0))

        actions = ctk.CTkFrame(settings_frame, fg_color="transparent")
        actions.grid(row=3, column=0, sticky="ew", padx=14, pady=(14, 12))
        actions.grid_columnconfigure((0, 1), weight=1)
        ctk.CTkButton(actions, text="Apply Settings", command=self._apply_settings, height=38).grid(
            row=0, column=0, sticky="ew", padx=(0, 6)
        )
        self.listen_button = ctk.CTkButton(actions, text="Stop Listening", command=self._toggle_listening, height=38)
        self.listen_button.grid(row=0, column=1, sticky="ew", padx=(6, 0))

        ctk.CTkLabel(right, text="Pending Commands", font=("Segoe UI", 18, "bold")).grid(
            row=2, column=0, sticky="w", padx=18, pady=(18, 8)
        )
        self.pending_frame = ctk.CTkScrollableFrame(right, corner_radius=12)
        self.pending_frame.grid(row=3, column=0, sticky="nsew", padx=18, pady=(0, 18))

    def _device_options(self) -> list[dict]:
        options = [{"label": "Default device", "index": None}]
        for item in self.input_devices:
            options.append({"label": f"{item['index']}: {item['name']}", "index": item["index"]})
        return options

    def _current_device_label(self) -> str:
        for item in self._device_options():
            if item["index"] == self.settings.input_device_index:
                return item["label"]
        return "Default device"

    def _selected_device_index(self) -> int | None:
        label = self.device_var.get()
        for item in self._device_options():
            if item["label"] == label:
                return item["index"]
        return None

    def _apply_settings(self) -> None:
        self.settings.input_device_index = self._selected_device_index()
        self.settings.command_execution_enabled = bool(self.command_mode_var.get())
        save_receiver_settings(self.settings)
        self.service.update_command_policy(
            enabled=self.settings.command_execution_enabled,
            allowed_commands=self.settings.allowed_commands,
        )
        self._append_log("Receiver settings updated.")
        self.restart_listening()

    def _toggle_listening(self) -> None:
        if self.listener_thread and self.listener_thread.is_alive():
            self.stop_listening()
        else:
            self.start_listening()

    def start_listening(self) -> None:
        if self.listener_thread and self.listener_thread.is_alive():
            return
        self.stop_event = threading.Event()
        audio_receiver = AudioReceiver(
            protocol_id=self.settings.protocol_id,
            input_device_index=self.settings.input_device_index,
        )
        self.listener_thread = threading.Thread(
            target=audio_receiver.listen,
            args=(self.stop_event, self._handle_packet, self._handle_listener_error),
            daemon=True,
        )
        self.listener_thread.start()
        self.status_var.set("Listening")
        self.listen_button.configure(text="Stop Listening")
        self._style_status_badge()
        self._append_log("Receiver started listening for ultrasonic packets.")

    def stop_listening(self) -> None:
        if self.listener_thread and self.listener_thread.is_alive():
            self.stop_event.set()
            self.listener_thread.join(timeout=1.5)
        self.status_var.set("Idle")
        self.listen_button.configure(text="Start Listening")
        self._style_status_badge()
        self._append_log("Receiver stopped listening.")

    def restart_listening(self) -> None:
        self.stop_listening()
        self.start_listening()

    def _handle_packet(self, packet: bytes) -> None:
        for event in self.service.process_packet(packet):
            self.ui_events.put(event)

    def _handle_listener_error(self, exc: Exception) -> None:
        self.ui_events.put({"type": "error", "code": "audio_device_error", "message": str(exc)})

    def _drain_events(self) -> None:
        while not self.ui_events.empty():
            event = self.ui_events.get()
            if event["type"] == "session_ready":
                self.status_var.set("Session Ready")
                self._append_log(f"{event['message']} [{event['sender_fingerprint']}]")
            elif event["type"] == "message_received":
                self.status_var.set("Session Ready")
                self._append_log(f"Message: {event['body']}")
            elif event["type"] == "command_pending":
                self.status_var.set("Session Ready")
                self._append_log(f"Command pending approval: {event['body']}")
                self._render_pending_command(event)
            elif event["type"] == "command_blocked":
                self.status_var.set("Listening")
                self._append_log(f"Command blocked: {event['body']} ({event['message']})")
            elif event["type"] == "command_executed":
                self._append_log(f"Executed command: {event['body']}")
                self._remove_pending_card(event["command_id"])
            elif event["type"] == "command_rejected":
                self._append_log(f"Rejected command: {event['body']}")
                self._remove_pending_card(event["command_id"])
            elif event["type"] == "error":
                if event.get("code") == "audio_device_error":
                    self.status_var.set("Error")
                    self.listen_button.configure(text="Start Listening")
                self._append_log(f"{event.get('code', 'error')}: {event['message']}")
            self._style_status_badge()
        self.after(120, self._drain_events)

    def _render_pending_command(self, event: dict) -> None:
        card = ctk.CTkFrame(self.pending_frame, corner_radius=12)
        card.pack(fill="x", padx=4, pady=6)
        self.pending_cards[event["command_id"]] = card

        timestamp = time.strftime("%H:%M:%S", time.localtime(event["created_at"]))
        ctk.CTkLabel(card, text=event["body"], font=("Segoe UI", 16, "bold")).pack(anchor="w", padx=12, pady=(10, 2))
        ctk.CTkLabel(card, text=f"Session: {event['session_id']} | Received: {timestamp}", text_color="#b7c1d1").pack(
            anchor="w", padx=12
        )

        buttons = ctk.CTkFrame(card, fg_color="transparent")
        buttons.pack(fill="x", padx=12, pady=(10, 12))
        buttons.grid_columnconfigure((0, 1), weight=1)
        ctk.CTkButton(
            buttons,
            text="Approve",
            fg_color="#1f6f43",
            command=lambda command_id=event["command_id"]: self._approve_command(command_id),
        ).grid(row=0, column=0, sticky="ew", padx=(0, 6))
        ctk.CTkButton(
            buttons,
            text="Reject",
            fg_color="#9f2d2d",
            command=lambda command_id=event["command_id"]: self._reject_command(command_id),
        ).grid(row=0, column=1, sticky="ew", padx=(6, 0))

    def _remove_pending_card(self, command_id: str) -> None:
        card = self.pending_cards.pop(command_id, None)
        if card:
            card.destroy()

    def _approve_command(self, command_id: str) -> None:
        threading.Thread(target=lambda: self.ui_events.put(self.service.approve_command(command_id)), daemon=True).start()

    def _reject_command(self, command_id: str) -> None:
        self.ui_events.put(self.service.reject_command(command_id))

    def _style_status_badge(self) -> None:
        state = self.status_var.get().lower()
        if state == "listening":
            color = "#1f6aa5"
        elif state == "session ready":
            color = "#1f6f43"
        elif state == "error":
            color = "#9f2d2d"
        else:
            color = "#495057"
        self.status_badge.configure(fg_color=color)

    def _append_log(self, message: str) -> None:
        timestamp = time.strftime("%H:%M:%S")
        self.log_box.configure(state="normal")
        self.log_box.insert("end", f"[{timestamp}] {message}\n")
        self.log_box.see("end")
        self.log_box.configure(state="disabled")

    def destroy(self) -> None:
        self.stop_listening()
        super().destroy()


def main() -> None:
    app = ReceiverWindow()
    app.mainloop()


if __name__ == "__main__":
    main()

