import sys
import threading
import time
import types
import pathlib


def stub_module(name, obj=None):
    if obj is None:
        obj = types.SimpleNamespace()
    sys.modules[name] = obj
    return obj


# Minimal stubs for external deps used at import-time
stub_module('pyautogui')

pylsl = stub_module('pylsl', types.SimpleNamespace(local_clock=lambda: time.time()))

tk = types.SimpleNamespace()
tk.Tk = type('Tk', (), {'__init__': lambda self: None, 'after': lambda self, delay, fn: fn(), 'withdraw': lambda self: None, 'deiconify': lambda self: None, 'lift': lambda self: None, 'focus_force': lambda self: None, 'destroy': lambda self: None})
tk.W = tk.E = tk.N = tk.S = None
tk.END = None
stub_module('tkinter', tk)
stub_module('tkinter.ttk')
stub_module('tkinter.scrolledtext')
stub_module('tkinter.messagebox', types.SimpleNamespace(showerror=lambda *a, **k: None, showwarning=lambda *a, **k: None, showinfo=lambda *a, **k: None))
stub_module('tkinter.filedialog', types.SimpleNamespace(asksaveasfilename=lambda *a, **k: None))

stub_module('pyxdf')
stub_module('mne')
stub_module('pystray')

PIL = types.SimpleNamespace(Image=types.SimpleNamespace(), ImageDraw=types.SimpleNamespace())
stub_module('PIL', PIL)
stub_module('PIL.Image', PIL.Image)
stub_module('PIL.ImageDraw', PIL.ImageDraw)


# Fake RealtimeSTT with a text() that calls callback then sleeps briefly
class FakeRecorder:
    def __init__(self, *args, **kwargs):
        self._count = 0

    def text(self, cb):
        self._count += 1
        cb(f"hello_{self._count}")
        time.sleep(0.01)

    def shutdown(self):
        pass


stub_module('RealtimeSTT', types.SimpleNamespace(AudioToTextRecorder=FakeRecorder))


# Ensure project root is importable
PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Now import the app (after stubs and path fix)
from pho_launch_live_transcription import LiveWhisperLoggerApp


class DummyRoot:
    def after(self, delay_ms, fn):
        fn()
    def destroy(self):
        pass


def run_smoke():
    root = DummyRoot()
    app = LiveWhisperLoggerApp(root)
    messages = []

    def capture(msg):
        messages.append(msg)

    # Monkeypatch perform_log_message to capture output instead of LSL/prints
    app.perform_log_message = capture

    app.live_recognition_loop()

    # Let the background thread run a bit
    time.sleep(0.1)
    app.on_closing()

    # Expect a few messages captured
    print(f"captured={len(messages)}")
    print("sample=", messages[:3])


if __name__ == '__main__':
    run_smoke()


