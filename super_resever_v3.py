import sys, ggwave, pyaudio, numpy as np, base64, os, threading, time
import customtkinter as ctk
from scipy.signal import butter, lfilter
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.fernet import Fernet
from reedsolo import RSCodec

if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

ctk.set_appearance_mode("dark")

class ReceiverApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Acoustic Receiver Pro")
        self.geometry("500x500")
        self.session_key = None
        self.rs = RSCodec(8)

        # الواجهة
        self.label = ctk.CTkLabel(self, text="🕵️ ULTRASONIC RECEIVER", font=("Arial", 20, "bold"))
        self.label.pack(pady=20)

        self.led_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.led_frame.pack(pady=10)
        self.led_canvas = ctk.CTkCanvas(self.led_frame, width=30, height=30, bg="#1a1a1a", highlightthickness=0)
        self.led_circle = self.led_canvas.create_oval(5, 5, 25, 25, fill="gray")
        self.led_canvas.pack(side="left", padx=10)
        self.status_txt = ctk.CTkLabel(self.led_frame, text="LISTENING...", text_color="white")
        self.status_txt.pack(side="left")

        self.terminal = ctk.CTkTextbox(self, width=450, height=250, fg_color="black", text_color="#0F0", font=("Consolas", 13))
        self.terminal.pack(pady=20)

        self.btn_exit = ctk.CTkButton(self, text="STOP SYSTEM", fg_color="red", command=self.quit)
        self.btn_exit.pack(pady=10)

        threading.Thread(target=self.listen_loop, daemon=True).start()

    def log(self, text):
        self.terminal.insert("end", f"> {text}\n")
        self.terminal.see("end")

    def set_led(self, color, status):
        self.led_canvas.itemconfig(self.led_circle, fill=color)
        self.status_txt.configure(text=status)

    def listen_loop(self):
        inst = ggwave.init()
        p = pyaudio.PyAudio()
        stream = p.open(format=pyaudio.paFloat32, channels=1, rate=48000, input=True, frames_per_buffer=4096)
        
        while True:
            try:
                data = stream.read(4096, exception_on_overflow=False)
                # فلتر Ultrasound (فوق 16kHz)
                nyq = 0.5 * 48000
                b, a = butter(5, 16000/nyq, btype='high')
                filtered = lfilter(b, a, np.frombuffer(data, dtype=np.float32)).astype(np.float32)
                
                res = ggwave.decode(inst, filtered.tobytes())
                if res:
                    if len(res) == 32: # مفتاح عام
                        self.log("🔑 New Handshake Received.")
                        derived = HKDF(algorithm=hashes.SHA256(), length=32, salt=None, info=b'ultra-secure').derive(res)
                        self.session_key = Fernet(base64.urlsafe_b64encode(derived))
                        self.set_led("lime", "SECURE LINK ACTIVE")
                    
                    elif self.session_key: # رسالة مشفرة
                        try:
                            dec = self.session_key.decrypt(res)
                            fixed = self.rs.decode(dec)[0].decode().upper()
                            self.log(f"📥 RECEIVED: {fixed}")
                            # تنفيذ الأوامر
                            if fixed == "CALC": os.system("calc")
                            elif fixed == "LOCK": os.system("rundll32.exe user32.dll,LockWorkStation")
                            elif fixed == "NOTEPAD": os.system("notepad")
                        except:
                            self.log("⚠️ Noise Error - Correction Failed.")
            except: pass

if __name__ == "__main__":
    app = ReceiverApp()
    app.mainloop()