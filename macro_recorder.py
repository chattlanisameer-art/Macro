#!/usr/bin/env python3
"""MyMacroRecorder - a simple macro recorder/player for macOS (and Linux/Windows).

Records mouse + keyboard events with pynput and replays them with original
timing. GUI built with tkinter. Recordings are saved/loaded as JSON.

See README.md for usage and the macOS permissions / unsigned-app notes.
"""

import json
import threading
import time
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from pynput import keyboard, mouse

APP_NAME = "MyMacroRecorder"
APP_VERSION = "1.0.0"

# Event type constants used in the JSON format.
EV_MOVE = "move"
EV_CLICK = "click"
EV_SCROLL = "scroll"
EV_KEY = "key"


# --------------------------------------------------------------------------- #
# Key (de)serialization helpers
# --------------------------------------------------------------------------- #
def serialize_key(key):
    """Turn a pynput key into a JSON-safe dict."""
    if isinstance(key, keyboard.Key):
        return {"special": key.name}
    # KeyCode: either a printable char or a raw virtual key code.
    if key.char is not None:
        return {"char": key.char}
    return {"vk": key.vk}


def deserialize_key(data):
    """Turn a serialized key dict back into a pynput key."""
    if "special" in data:
        return keyboard.Key[data["special"]]
    if "char" in data:
        return keyboard.KeyCode.from_char(data["char"])
    return keyboard.KeyCode.from_vk(data["vk"])


def button_name(button):
    return button.name  # e.g. "left", "right", "middle"


def name_to_button(name):
    return getattr(mouse.Button, name)


# --------------------------------------------------------------------------- #
# Recorder
# --------------------------------------------------------------------------- #
class Recorder:
    """Captures mouse + keyboard events into a list of timestamped events."""

    def __init__(self, options, ignore_keys=None):
        self.options = options  # dict of bool flags
        self.ignore_keys = ignore_keys or set()  # key names not to record (hotkeys)
        self.events = []
        self._start = None
        self._mouse_listener = None
        self._keyboard_listener = None
        self._lock = threading.Lock()

    def _now(self):
        return time.time() - self._start

    def _add(self, ev):
        with self._lock:
            self.events.append(ev)

    # -- mouse callbacks --------------------------------------------------- #
    def _on_move(self, x, y):
        if self.options.get("move"):
            self._add({"type": EV_MOVE, "t": self._now(), "x": x, "y": y})

    def _on_click(self, x, y, button, pressed):
        if self.options.get("click"):
            self._add({
                "type": EV_CLICK, "t": self._now(),
                "x": x, "y": y,
                "button": button_name(button), "pressed": pressed,
            })

    def _on_scroll(self, x, y, dx, dy):
        if self.options.get("scroll"):
            self._add({
                "type": EV_SCROLL, "t": self._now(),
                "x": x, "y": y, "dx": dx, "dy": dy,
            })

    # -- keyboard callbacks ------------------------------------------------ #
    def _on_press(self, key):
        self._record_key(key, True)

    def _on_release(self, key):
        self._record_key(key, False)

    def _record_key(self, key, pressed):
        if not self.options.get("keyboard"):
            return
        skey = serialize_key(key)
        # Don't record the global hotkeys themselves.
        if skey.get("special") in self.ignore_keys:
            return
        self._add({
            "type": EV_KEY, "t": self._now(),
            "key": skey, "pressed": pressed,
        })

    # -- control ----------------------------------------------------------- #
    def start(self):
        self.events = []
        self._start = time.time()
        self._mouse_listener = mouse.Listener(
            on_move=self._on_move,
            on_click=self._on_click,
            on_scroll=self._on_scroll,
        )
        self._keyboard_listener = keyboard.Listener(
            on_press=self._on_press,
            on_release=self._on_release,
        )
        self._mouse_listener.start()
        self._keyboard_listener.start()

    def stop(self):
        if self._mouse_listener:
            self._mouse_listener.stop()
            self._mouse_listener = None
        if self._keyboard_listener:
            self._keyboard_listener.stop()
            self._keyboard_listener = None
        with self._lock:
            return list(self.events)


# --------------------------------------------------------------------------- #
# Player
# --------------------------------------------------------------------------- #
class Player:
    """Replays a list of recorded events with adjustable timing."""

    def __init__(self):
        self.mouse = mouse.Controller()
        self.keyboard = keyboard.Controller()
        self._stop = threading.Event()

    def stop(self):
        self._stop.set()

    def _replay_event(self, ev):
        etype = ev["type"]
        if etype == EV_MOVE:
            self.mouse.position = (ev["x"], ev["y"])
        elif etype == EV_CLICK:
            self.mouse.position = (ev["x"], ev["y"])
            btn = name_to_button(ev["button"])
            if ev["pressed"]:
                self.mouse.press(btn)
            else:
                self.mouse.release(btn)
        elif etype == EV_SCROLL:
            self.mouse.scroll(ev["dx"], ev["dy"])
        elif etype == EV_KEY:
            key = deserialize_key(ev["key"])
            if ev["pressed"]:
                self.keyboard.press(key)
            else:
                self.keyboard.release(key)

    def play(self, events, speed=1.0, repeat=1, infinite=False,
             delay_between=0.0, on_finish=None, on_progress=None):
        """Blocking playback. Run this in a background thread."""
        self._stop.clear()
        speed = max(speed, 0.01)
        iteration = 0
        try:
            while not self._stop.is_set():
                iteration += 1
                if on_progress:
                    on_progress(iteration)
                last_t = 0.0
                for ev in events:
                    if self._stop.is_set():
                        break
                    wait = (ev["t"] - last_t) / speed
                    if wait > 0:
                        # Sleep in small slices so Stop is responsive.
                        end = time.time() + wait
                        while time.time() < end and not self._stop.is_set():
                            time.sleep(min(0.02, end - time.time()))
                    if self._stop.is_set():
                        break
                    self._replay_event(ev)
                    last_t = ev["t"]

                if self._stop.is_set():
                    break
                if not infinite and iteration >= repeat:
                    break
                if delay_between > 0:
                    end = time.time() + delay_between
                    while time.time() < end and not self._stop.is_set():
                        time.sleep(min(0.02, end - time.time()))
        finally:
            if on_finish:
                on_finish()


# --------------------------------------------------------------------------- #
# Hotkey manager
# --------------------------------------------------------------------------- #
class HotkeyManager:
    """Wraps pynput GlobalHotKeys; supports live reconfiguration."""

    def __init__(self):
        self._listener = None

    def start(self, mapping):
        """mapping: {"<f2>": callable, "<f3>": callable}"""
        self.stop()
        try:
            self._listener = keyboard.GlobalHotKeys(mapping)
            self._listener.start()
            return True
        except Exception as exc:  # invalid hotkey spec, etc.
            print(f"Hotkey error: {exc}")
            self._listener = None
            return False

    def stop(self):
        if self._listener:
            self._listener.stop()
            self._listener = None


# --------------------------------------------------------------------------- #
# GUI Application
# --------------------------------------------------------------------------- #
class App:
    def __init__(self, root):
        self.root = root
        self.root.title(f"{APP_NAME} {APP_VERSION}")
        self.root.resizable(False, False)

        self.recorder = None
        self.player = Player()
        self.hotkeys = HotkeyManager()

        self.events = []          # current recording
        self.is_recording = False
        self.is_playing = False
        self._play_thread = None

        # Recording option flags.
        self.opt_move = tk.BooleanVar(value=True)
        self.opt_click = tk.BooleanVar(value=True)
        self.opt_scroll = tk.BooleanVar(value=True)
        self.opt_keyboard = tk.BooleanVar(value=True)

        # Playback options.
        self.speed_var = tk.StringVar(value="1.0")
        self.repeat_mode = tk.StringVar(value="once")  # once | times | infinite
        self.repeat_n = tk.StringVar(value="2")
        self.delay_var = tk.StringVar(value="0.0")

        # Hotkeys (the F-key names without the angle brackets).
        self.hk_record = tk.StringVar(value="f2")
        self.hk_play = tk.StringVar(value="f3")

        self.status_var = tk.StringVar(value="Ready.")

        self._build_ui()
        self._apply_hotkeys()
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    # -- UI ---------------------------------------------------------------- #
    def _build_ui(self):
        pad = {"padx": 8, "pady": 4}
        main = ttk.Frame(self.root, padding=12)
        main.grid(row=0, column=0, sticky="nsew")

        # Transport buttons
        btns = ttk.Frame(main)
        btns.grid(row=0, column=0, columnspan=2, sticky="w", **pad)
        self.btn_record = ttk.Button(btns, text="● Record", command=self.toggle_record)
        self.btn_stop = ttk.Button(btns, text="■ Stop", command=self.stop_all)
        self.btn_play = ttk.Button(btns, text="▶ Play", command=self.toggle_play)
        self.btn_record.grid(row=0, column=0, padx=4)
        self.btn_stop.grid(row=0, column=1, padx=4)
        self.btn_play.grid(row=0, column=2, padx=4)

        # Capture options
        cap = ttk.LabelFrame(main, text="Capture", padding=8)
        cap.grid(row=1, column=0, sticky="nsew", **pad)
        ttk.Checkbutton(cap, text="Mouse movement", variable=self.opt_move).grid(row=0, column=0, sticky="w")
        ttk.Checkbutton(cap, text="Clicks (L/R/M) & drags", variable=self.opt_click).grid(row=1, column=0, sticky="w")
        ttk.Checkbutton(cap, text="Scrolls", variable=self.opt_scroll).grid(row=2, column=0, sticky="w")
        ttk.Checkbutton(cap, text="Keyboard", variable=self.opt_keyboard).grid(row=3, column=0, sticky="w")

        # Playback options
        pb = ttk.LabelFrame(main, text="Playback", padding=8)
        pb.grid(row=1, column=1, sticky="nsew", **pad)

        ttk.Label(pb, text="Speed ×").grid(row=0, column=0, sticky="w")
        ttk.Entry(pb, textvariable=self.speed_var, width=6).grid(row=0, column=1, sticky="w")

        ttk.Label(pb, text="Delay between (s)").grid(row=1, column=0, sticky="w")
        ttk.Entry(pb, textvariable=self.delay_var, width=6).grid(row=1, column=1, sticky="w")

        ttk.Radiobutton(pb, text="Once", variable=self.repeat_mode, value="once").grid(row=2, column=0, sticky="w")
        rt = ttk.Frame(pb)
        rt.grid(row=3, column=0, columnspan=2, sticky="w")
        ttk.Radiobutton(rt, text="Repeat", variable=self.repeat_mode, value="times").grid(row=0, column=0, sticky="w")
        ttk.Entry(rt, textvariable=self.repeat_n, width=5).grid(row=0, column=1, sticky="w")
        ttk.Label(rt, text="times").grid(row=0, column=2, sticky="w")
        ttk.Radiobutton(pb, text="Infinite loop", variable=self.repeat_mode, value="infinite").grid(row=4, column=0, sticky="w")

        # Hotkeys
        hk = ttk.LabelFrame(main, text="Global hotkeys", padding=8)
        hk.grid(row=2, column=0, sticky="nsew", **pad)
        ttk.Label(hk, text="Record toggle").grid(row=0, column=0, sticky="w")
        ttk.Entry(hk, textvariable=self.hk_record, width=8).grid(row=0, column=1, sticky="w")
        ttk.Label(hk, text="Play toggle").grid(row=1, column=0, sticky="w")
        ttk.Entry(hk, textvariable=self.hk_play, width=8).grid(row=1, column=1, sticky="w")
        ttk.Button(hk, text="Apply", command=self._apply_hotkeys).grid(row=2, column=0, columnspan=2, pady=4)

        # File operations
        filef = ttk.LabelFrame(main, text="Recording", padding=8)
        filef.grid(row=2, column=1, sticky="nsew", **pad)
        ttk.Button(filef, text="Save…", command=self.save_recording).grid(row=0, column=0, padx=2, pady=2)
        ttk.Button(filef, text="Load…", command=self.load_recording).grid(row=0, column=1, padx=2, pady=2)
        self.count_var = tk.StringVar(value="0 events")
        ttk.Label(filef, textvariable=self.count_var).grid(row=1, column=0, columnspan=2, sticky="w")

        # Status bar
        status = ttk.Frame(main)
        status.grid(row=3, column=0, columnspan=2, sticky="ew", **pad)
        ttk.Label(status, textvariable=self.status_var, foreground="#444").grid(row=0, column=0, sticky="w")

    def _set_status(self, text):
        self.status_var.set(text)

    def _update_count(self):
        self.count_var.set(f"{len(self.events)} events")

    # -- Recording --------------------------------------------------------- #
    def toggle_record(self):
        if self.is_recording:
            self.stop_recording()
        else:
            self.start_recording()

    def start_recording(self):
        if self.is_playing:
            self._set_status("Can't record while playing.")
            return
        if self.is_recording:
            return
        options = {
            "move": self.opt_move.get(),
            "click": self.opt_click.get(),
            "scroll": self.opt_scroll.get(),
            "keyboard": self.opt_keyboard.get(),
        }
        ignore = {self.hk_record.get().lower(), self.hk_play.get().lower()}
        self.recorder = Recorder(options, ignore_keys=ignore)
        self.recorder.start()
        self.is_recording = True
        self.btn_record.config(text="● Recording…")
        self._set_status("Recording — press Stop or the record hotkey to finish.")

    def stop_recording(self):
        if not self.is_recording:
            return
        self.events = self.recorder.stop()
        self.recorder = None
        self.is_recording = False
        self.btn_record.config(text="● Record")
        self._update_count()
        self._set_status(f"Recorded {len(self.events)} events.")

    # -- Playback ---------------------------------------------------------- #
    def toggle_play(self):
        if self.is_playing:
            self.stop_playing()
        else:
            self.start_playing()

    def start_playing(self):
        if self.is_recording:
            self._set_status("Can't play while recording.")
            return
        if self.is_playing:
            return
        if not self.events:
            self._set_status("Nothing to play — record or load a macro first.")
            return
        try:
            speed = float(self.speed_var.get())
        except ValueError:
            speed = 1.0
        try:
            delay = float(self.delay_var.get())
        except ValueError:
            delay = 0.0

        mode = self.repeat_mode.get()
        infinite = mode == "infinite"
        repeat = 1
        if mode == "times":
            try:
                repeat = max(1, int(self.repeat_n.get()))
            except ValueError:
                repeat = 1

        self.is_playing = True
        self.btn_play.config(text="▶ Playing…")
        self._set_status("Playing… press Stop or the play hotkey to abort.")

        def progress(i):
            self.root.after(0, lambda: self._set_status(f"Playing… iteration {i}"))

        def finish():
            self.root.after(0, self._on_play_finished)

        self._play_thread = threading.Thread(
            target=self.player.play,
            kwargs=dict(events=self.events, speed=speed, repeat=repeat,
                        infinite=infinite, delay_between=delay,
                        on_finish=finish, on_progress=progress),
            daemon=True,
        )
        self._play_thread.start()

    def stop_playing(self):
        if self.is_playing:
            self.player.stop()

    def _on_play_finished(self):
        self.is_playing = False
        self.btn_play.config(text="▶ Play")
        self._set_status("Playback finished.")

    # -- Stop all ---------------------------------------------------------- #
    def stop_all(self):
        if self.is_recording:
            self.stop_recording()
        if self.is_playing:
            self.stop_playing()

    # -- Save / load ------------------------------------------------------- #
    def save_recording(self):
        if not self.events:
            self._set_status("Nothing to save.")
            return
        path = filedialog.asksaveasfilename(
            defaultextension=".json",
            filetypes=[("Macro JSON", "*.json"), ("All files", "*.*")],
            initialfile="macro.json",
        )
        if not path:
            return
        data = {
            "app": APP_NAME,
            "version": APP_VERSION,
            "events": self.events,
        }
        with open(path, "w") as fh:
            json.dump(data, fh, indent=2)
        self._set_status(f"Saved {len(self.events)} events to {path}")

    def load_recording(self):
        path = filedialog.askopenfilename(
            filetypes=[("Macro JSON", "*.json"), ("All files", "*.*")],
        )
        if not path:
            return
        try:
            with open(path) as fh:
                data = json.load(fh)
            self.events = data["events"]
        except (OSError, ValueError, KeyError) as exc:
            messagebox.showerror(APP_NAME, f"Could not load recording:\n{exc}")
            return
        self._update_count()
        self._set_status(f"Loaded {len(self.events)} events from {path}")

    # -- Hotkeys ----------------------------------------------------------- #
    def _apply_hotkeys(self):
        rec = self.hk_record.get().strip().lower()
        play = self.hk_play.get().strip().lower()

        def spec(name):
            # Single letters/chars stay literal; named keys get angle brackets.
            return f"<{name}>" if len(name) > 1 else name

        mapping = {
            spec(rec): lambda: self.root.after(0, self.toggle_record),
            spec(play): lambda: self.root.after(0, self.toggle_play),
        }
        ok = self.hotkeys.start(mapping)
        if ok:
            self._set_status(f"Hotkeys active — record: {rec}, play: {play}")
        else:
            self._set_status("Invalid hotkey(s). Use names like f2, f3, esc, a.")

    # -- Lifecycle --------------------------------------------------------- #
    def _on_close(self):
        try:
            self.stop_all()
            self.hotkeys.stop()
        finally:
            self.root.destroy()


def main():
    root = tk.Tk()
    App(root)
    root.mainloop()


if __name__ == "__main__":
    main()
