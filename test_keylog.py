"""Debug script to see what keys pynput actually receives.

Run with: uv run python test_keylog.py

Press any keys and see what pynput reports.
Press Ctrl+C to exit.
"""

from pynput.keyboard import Key, KeyCode, Listener


def on_press(key, injected):
    print(f"PRESS   key={key!r}  type={type(key).__name__}  injected={injected}")


def on_release(key, injected):
    print(f"RELEASE key={key!r}  type={type(key).__name__}  injected={injected}")


def main():
    print("=== Key Logger Debug ===")
    print("Press any keys to see what pynput receives.")
    print("Try: Ctrl+Win+A, Win+Shift+D, Right Alt, etc.")
    print("Press Ctrl+C to exit.\n")

    listener = Listener(on_press=on_press, on_release=on_release)
    listener.daemon = True
    listener.start()

    try:
        while True:
            listener.join(timeout=0.5)
    except KeyboardInterrupt:
        print("\nExiting...")
    finally:
        listener.stop()


if __name__ == "__main__":
    main()
