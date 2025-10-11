# otomatik_x_pyautogui.py
import time
import pyautogui

print("5 saniye içinde başlayacak. İptal etmek için Ctrl+C yapın ve imleci güvenli bir yere alın.")
time.sleep(5)

try:
    while True:
        pyautogui.press('x')
        time.sleep(1)  # 1 saniye bekle
except KeyboardInterrupt:
    print("\nDurduruldu.")
