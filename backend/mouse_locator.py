import pyautogui
import time

print("Move your mouse to the Webull widget search box...")
for i in range(5, 0, -1):
    print(f"{i}...")
    time.sleep(1)

x, y = pyautogui.position()
print(f"\nYour mouse is at: X: {x}, Y: {y}")
print("Use these coordinates in the webull_sync.py script!")
