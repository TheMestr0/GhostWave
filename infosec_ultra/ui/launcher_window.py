import subprocess
import sys

import customtkinter as ctk

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

_VERSION = "v1.1"


class LauncherWindow(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("GhostWave — Launcher")
        self.geometry("540x420")
        self.minsize(480, 380)
        self.resizable(False, False)

        self._build_layout()

    def _build_layout(self) -> None:
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        # ── Header ──────────────────────────────────────────────────────────
        header = ctk.CTkFrame(self, corner_radius=18)
        header.grid(row=0, column=0, sticky="ew", padx=24, pady=(24, 12))
        header.grid_columnconfigure(0, weight=1)

        title_row = ctk.CTkFrame(header, fg_color="transparent")
        title_row.grid(row=0, column=0, sticky="ew", padx=20, pady=(20, 4))
        title_row.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(title_row, text="GhostWave", font=("Segoe UI", 28, "bold")).grid(
            row=0, column=0, sticky="w"
        )
        ctk.CTkLabel(
            title_row,
            text=_VERSION,
            font=("Segoe UI", 13),
            text_color="#6c757d",
            fg_color="#1e2030",
            corner_radius=6,
            padx=8,
            pady=3,
        ).grid(row=0, column=1, sticky="e")

        ctk.CTkLabel(
            header,
            text="Secure ultrasonic message transfer.",
            text_color="#b7c1d1",
        ).grid(row=1, column=0, sticky="w", padx=20, pady=(0, 20))

        # ── Action cards ────────────────────────────────────────────────────
        cards = ctk.CTkFrame(self, corner_radius=18)
        cards.grid(row=1, column=0, sticky="nsew", padx=24, pady=(0, 16))
        cards.grid_columnconfigure(0, weight=1)

        self._make_app_card(
            parent=cards,
            row=0,
            icon="📤",
            title="Sender",
            description="Choose a message or command, select your audio output\ndevice and transmit securely.",
            button_text="Open Sender",
            command=self._open_sender,
        )

        ctk.CTkFrame(cards, height=1, fg_color="#2b2d42").grid(row=1, column=0, sticky="ew", padx=16)

        self._make_app_card(
            parent=cards,
            row=2,
            icon="📥",
            title="Receiver",
            description="Listen on any microphone, decrypt incoming packets\nand approve or reject remote commands.",
            button_text="Open Receiver",
            command=self._open_receiver,
        )

        # ── Footer ──────────────────────────────────────────────────────────
        ctk.CTkLabel(
            self,
            text="python -m infosec_ultra",
            font=("Consolas", 11),
            text_color="#495057",
        ).grid(row=2, column=0, pady=(0, 14))

    def _make_app_card(
        self,
        parent: ctk.CTkFrame,
        row: int,
        icon: str,
        title: str,
        description: str,
        button_text: str,
        command,
    ) -> None:
        card = ctk.CTkFrame(parent, fg_color="transparent")
        card.grid(row=row, column=0, sticky="ew", padx=12, pady=14)
        card.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(card, text=icon, font=("Segoe UI Emoji", 28)).grid(row=0, column=0, rowspan=2, padx=(4, 12))
        ctk.CTkLabel(card, text=title, font=("Segoe UI", 17, "bold"), anchor="w").grid(
            row=0, column=1, sticky="w"
        )
        ctk.CTkLabel(
            card,
            text=description,
            text_color="#9098a9",
            anchor="w",
            justify="left",
        ).grid(row=1, column=1, sticky="w")
        ctk.CTkButton(card, text=button_text, width=140, height=38, command=command).grid(
            row=0, column=2, rowspan=2, padx=(16, 4)
        )

    def _open_sender(self) -> None:
        subprocess.Popen([sys.executable, "-m", "infosec_ultra.ui.sender_window"])

    def _open_receiver(self) -> None:
        subprocess.Popen([sys.executable, "-m", "infosec_ultra.ui.receiver_window"])


def main() -> None:
    app = LauncherWindow()
    app.mainloop()


if __name__ == "__main__":
    main()
