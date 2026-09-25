import time
import pyperclip
import pyautogui

# --- CONFIGURE YOUR ABSOLUTE SCREEN COORDINATES HERE ---
# Use the backend/mouse_locator.py script to find the exact X, Y
WEBULL_SEARCH_X = 650
WEBULL_SEARCH_Y = 120

CPRO_SEARCH_X = 160
CPRO_SEARCH_Y = 125

def sync_ticker_at_location(x: int, y: int, wait_before_enter: float = 1.0):
    try:
        # 1. Move mouse to the absolute coordinates
        pyautogui.moveTo(x, y)
        
        # 2. Click to focus the window/widget
        pyautogui.click()
        time.sleep(0.1)
        
        # 3. Click again into the search box
        pyautogui.click()
        time.sleep(0.1)
        
        # 4. Select all text
        pyautogui.hotkey('ctrl', 'a')
        time.sleep(0.1)
        
        # 5. Paste the ticker
        pyautogui.hotkey('ctrl', 'v')
        
        # 6. Wait then enter
        time.sleep(wait_before_enter)
        pyautogui.press('enter')
        time.sleep(0.1)
    except Exception as e:
        print(f"Error syncing at location ({x}, {y}): {e}")

def sync_all_platforms(symbol: str):
    try:
        symbol = symbol.strip().upper()
        pyperclip.copy(symbol)
        time.sleep(0.1)
        
        # Sync Webull
        sync_ticker_at_location(WEBULL_SEARCH_X, WEBULL_SEARCH_Y, wait_before_enter=0.2)
        
        # Sync CPRO
        sync_ticker_at_location(CPRO_SEARCH_X, CPRO_SEARCH_Y)
        
    except Exception as e:
        print(f"Error in sync_all_platforms: {e}")
