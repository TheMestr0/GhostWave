import subprocess
import sys

import customtkinter as ctk

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")


class LauncherWindow(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("InfoSec Ultrasonic Launcher")
        self.geometry("520x360")
        self.minsize(460, 320)

        self._build_layout()

    def _build_layout(self) -> None:
        self.grid_columnconfigure(0, weight=1)

        header = ctk.CTkFrame(self, corner_radius=18)
        header.grid(row=0, column=0, sticky="nsew", padx=24, pady=(24, 12))
        header.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(header, text="InfoSec Ultrasonic", font=("Segoe UI", 28, "bold")).grid(
            row=0, column=0, sticky="w", padx=20, pady=(20, 6)
        )
        ctk.CTkLabel(
            header,
            text="Start the Sender or Receiver from one official entrypoint.",
            text_color="#b7c1d1",
        ).grid(row=1, column=0, sticky="w", padx=20, pady=(0, 20))

        actions = ctk.CTkFrame(self, corner_radius=18)
        actions.grid(row=1, column=0, sticky="nsew", padx=24, pady=(0, 24))
        actions.grid_columnconfigure(0, weight=1)
        ctk.CTkButton(actions, text="Open Sender", height=48, command=self._open_sender).grid(
            row=0, column=0, sticky="ew", padx=20, pady=(22, 10)
        )
        ctk.CTkButton(actions, text="Open Receiver", height=48, command=self._open_receiver).grid(
            row=1, column=0, sticky="ew", padx=20, pady=10
        )
        ctk.CTkLabel(
            actions,
            text="Official startup command: python -m infosec_ultra",
            text_color="#9fc5ff",
        ).grid(row=2, column=0, sticky="w", padx=20, pady=(10, 22))

    def _open_sender(self) -> None:
        subprocess.Popen([sys.executable, "-m", "infosec_ultra.ui.sender_window"])

    def _open_receiver(self) -> None:
        subprocess.Popen([sys.executable, "-m", "infosec_ultra.ui.receiver_window"])


def main() -> None:
    app = LauncherWindow()
    app.mainloop()


if __name__ == "__main__":
    main()

