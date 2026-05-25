import pyautogui

def click(x, y):
    pyautogui.click(x, y)

def type_text(text):
    pyautogui.write(text)

def screenshot():
    return pyautogui.screenshot()
