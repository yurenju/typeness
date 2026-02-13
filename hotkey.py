"""Global hotkey listener module for Typeness.

Listens for Shift+Win+A to toggle recording state.
Dispatches events to the main thread via a queue.Queue.
"""

import queue

from pynput.keyboard import Key, KeyCode, Listener


# Event types sent to the main thread
EVENT_START_RECORDING = "start_recording"
EVENT_STOP_RECORDING = "stop_recording"

# Hotkey combination: Shift+Win+A
_HOTKEY = {Key.shift, Key.cmd, KeyCode.from_char("a")}


class HotkeyListener:
    """Listens for Shift+Win+A to toggle recording on/off.

    State machine: idle -> recording -> idle
    - First hotkey press: idle -> recording (sends EVENT_START_RECORDING)
    - Second hotkey press: recording -> idle (sends EVENT_STOP_RECORDING)

    Defenses:
    - Ignores injected (synthetic) key events to avoid capturing our own Ctrl+V
    - busy flag prevents starting new recording during processing
    """

    def __init__(self, event_queue: queue.Queue) -> None:
        self._queue = event_queue
        self._recording = False
        self._busy = False
        self._pressed_keys: set = set()
        self._hotkey_handled = False
        self._listener: Listener | None = None

    @property
    def busy(self) -> bool:
        return self._busy

    @busy.setter
    def busy(self, value: bool) -> None:
        self._busy = value

    def _on_press(self, key: Key | KeyCode, injected: bool) -> None:
        # Ignore synthetic (injected) key events
        if injected:
            return

        # Normalize: treat Key.shift_l / Key.shift_r as Key.shift, etc.
        normalized = self._normalize(key)
        self._pressed_keys.add(normalized)

        # Check if hotkey combination is active
        if not _HOTKEY.issubset(self._pressed_keys):
            return

        # Prevent repeated firing while keys are held down
        if self._hotkey_handled:
            return
        self._hotkey_handled = True

        if self._recording:
            self._recording = False
            self._queue.put(EVENT_STOP_RECORDING)
        else:
            if self._busy:
                return
            self._recording = True
            self._queue.put(EVENT_START_RECORDING)

    def _on_release(self, key: Key | KeyCode, injected: bool) -> None:
        if injected:
            return

        normalized = self._normalize(key)
        self._pressed_keys.discard(normalized)

        # Reset handled flag when any hotkey member is released
        if normalized in _HOTKEY:
            self._hotkey_handled = False

    @staticmethod
    def _normalize(key: Key | KeyCode) -> Key | KeyCode:
        """Normalize left/right modifier variants to a single key."""
        if key in (Key.shift_l, Key.shift_r):
            return Key.shift
        if key in (Key.cmd_l, Key.cmd_r):
            return Key.cmd
        # Normalize character keys to lowercase
        if isinstance(key, KeyCode) and key.char is not None:
            return KeyCode.from_char(key.char.lower())
        return key

    def start(self) -> None:
        """Start the global keyboard listener (runs in a daemon thread)."""
        self._listener = Listener(
            on_press=self._on_press,
            on_release=self._on_release,
        )
        self._listener.daemon = True
        self._listener.start()

    def stop(self) -> None:
        """Stop the global keyboard listener and clean up the hook."""
        if self._listener is not None:
            self._listener.stop()
            self._listener.join(timeout=0.5)
            self._listener = None
