"""Clipboard and auto-paste module for Typeness.

Copies text to the system clipboard and simulates Ctrl+V to paste
into the currently focused window.
"""

import time

import pyperclip
from pynput.keyboard import Controller, Key


_keyboard = Controller()


def paste_text(text: str) -> None:
    """Copy text to clipboard and simulate Ctrl+V to paste it.

    A short delay between clipboard write and key simulation ensures
    the clipboard content is ready before pasting.
    """
    pyperclip.copy(text)
    time.sleep(0.02)

    _keyboard.press(Key.ctrl)
    _keyboard.press("v")
    _keyboard.release("v")
    _keyboard.release(Key.ctrl)
