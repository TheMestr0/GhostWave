import sys, ggwave, pyaudio, numpy as np, base64, threading, time
import customtkinter as ctk
from cryptography.hazmat.primitives.asymmetric import x25519
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.fernet import Fernet
from reedsolo import RSCodec

# حل مشكلة الترميز في ويندوز
if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

class TransmitterApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Acoustic Transmitter Pro")
        self.geometry("500x400")
        self.rs = RSCodec(8)

        # الواجهة
        self.label = ctk.CTkLabel(self, text="📡 ULTRASONIC TRANSMITTER", font=("Arial", 20, "bold"))
        self.label.pack(pady=20)

        self.entry = ctk.CTkEntry(self, width=350, height=50, placeholder_text="Enter Command or Message...")
        self.entry.pack(pady=10)
        self.entry.bind("<Return>", lambda e: self.send_thread())

        self.btn = ctk.CTkButton(self, text="SEND ENCRYPTED", command=self.send_thread, height=40)
        self.btn.pack(pady=20)

        self.log_box = ctk.CTkTextbox(self, width=450, height=150, fg_color="#111", text_color="cyan")
        self.log_box.pack(pady=10)

    def log(self, text):
        self.log_box.insert("end", f"[{time.strftime('%H:%M:%S')}] {text}\n")
        self.log_box.see("end")

    def send_thread(self):
        msg = self.entry.get()
        if msg:
            threading.Thread(target=self.transmit, args=(msg,), daemon=True).start()
            self.entry.delete(0, "end")

    def transmit(self, text):
        try:
            self.log("Generating Handshake Keys...")
            priv = x25519.X25519PrivateKey.generate()
            pub_bytes = priv.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
            
            # بث المفتاح
            self.log("Broadcasting Public Key (Silent)...")
            self.play_sound(pub_bytes)
            
            # تجهيز التشفير
            derived = HKDF(algorithm=hashes.SHA256(), length=32, salt=None, info=b'ultra-secure').derive(pub_bytes)
            cipher = Fernet(base64.urlsafe_b64encode(derived))
            
            # إضافة حماية FEC وتشفير
            fec_data = bytes(self.rs.encode(text.encode()))
            encrypted = cipher.encrypt(fec_data)
            
            time.sleep(1.0) # فاصل زمني للمستقبل
            self.log(f"Sending Encrypted Data: {text}")
            self.play_sound(encrypted)
            self.log("✅ Transmission Finished.")
        except Exception as e:
            self.log(f"Error: {e}")

    def play_sound(self, data):
        inst = ggwave.init()
        wave = ggwave.encode(data, protocolId=4, volume=100, instance=inst)
        p = pyaudio.PyAudio()
        stream = p.open(format=pyaudio.paFloat32, channels=1, rate=48000, output=True)
        stream.write(np.zeros(24000, dtype=np.float32).tobytes()) # صمت تمهيدي
        stream.write(wave)
        stream.stop_stream(); p.terminate()

if __name__ == "__main__":
    app = TransmitterApp()
    app.mainloop()