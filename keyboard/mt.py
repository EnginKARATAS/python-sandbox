import time
import pyautogui

print("5 saniye içinde başlayacak. Durdurmak için Ctrl+C tuşlarına bas.")
time.sleep(5)

try:
    while True:
        pyautogui.keyDown('shift')
        pyautogui.press('2')   # Türkçe Q klavyede Shift+2 = "
        pyautogui.keyUp('shift')
        time.sleep(1)
except KeyboardInterrupt:
    print("\nDurduruldu.")
