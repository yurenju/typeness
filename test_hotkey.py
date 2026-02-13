"""Manual test script for hotkey module.

Run with: uv run python test_hotkey.py

Press Shift+Win+A once -> should print "recording start"
Press Shift+Win+A again -> should print "recording stop"
Press Ctrl+C to exit.
"""

import queue

from hotkey import EVENT_START_RECORDING, EVENT_STOP_RECORDING, HotkeyListener


def main():
    q = queue.Queue()
    listener = HotkeyListener(q)

    print("=== Hotkey Test ===")
    print("Press Shift+Win+A to toggle recording.")
    print("Press Ctrl+C to exit.\n")

    listener.start()

    try:
        while True:
            try:
                event = q.get(timeout=0.5)
            except queue.Empty:
                continue

            if event == EVENT_START_RECORDING:
                print("recording start")
            elif event == EVENT_STOP_RECORDING:
                print("recording stop")
    except KeyboardInterrupt:
        print("\nExiting...")
    finally:
        listener.stop()
        print("Listener stopped.")


if __name__ == "__main__":
    main()
