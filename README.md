# MyMacroRecorder

A simple, no-frills **macro recorder for macOS**. Record your mouse and
keyboard, then replay it with the original timing — loop it, speed it up, or
slow it down. Built in Python with [`pynput`](https://pynput.readthedocs.io/)
and `tkinter`, packaged as a standalone `.app` so you can just double-click it.

> Cross-platform note: the code also runs on Linux and Windows from source.
> Only the packaged `.app` and the permission notes below are macOS-specific.

---

## Features

- 🖱️ **Record** mouse movement, clicks (left / right / middle), scrolls, drags, and keyboard input
- ✅ **Checkboxes** to choose exactly what gets captured
- ⏱️ **Replay with original timing**
- 🔁 **Repeat**: once, *N* times, or infinite loop
- ⚡ **Adjustable playback speed** (e.g. `0.5` = half speed, `2.0` = double)
- 💤 **Optional delay** between repeats
- 💾 **Save / load** recordings as `.json`
- ⌨️ **Configurable global hotkeys** to start/stop recording and playback (default **F2** / **F3**)
- 🎛️ Clean GUI with **Record**, **Stop**, and **Play** buttons

---

## Screenshots

> _Add a screenshot of the running app here, e.g._ `docs/screenshot.png`:
>
> ```markdown
> ![MyMacroRecorder main window](docs/screenshot.png)
> ```

The window has three sections: transport buttons (Record / Stop / Play), a
**Capture** panel of checkboxes, a **Playback** panel (speed, repeat, delay),
and panels for **Global hotkeys** and **Save/Load**.

---

## Download & install (macOS)

1. Go to the [**Releases**](../../releases) page and download **`MyMacroRecorder.app.zip`**.
2. Unzip it (double-click) → you get `MyMacroRecorder.app`. Move it to **Applications** if you like.

### First launch: "unverified developer" warning

This app is **not notarized by Apple**, so Gatekeeper will block the first
launch with a message like *"MyMacroRecorder cannot be opened because the
developer cannot be verified."* This is expected. To open it:

- **Right-click** (or Control-click) the app → **Open** → in the dialog, click **Open** again.
- *Or:* try to open it once, then go to **System Settings → Privacy & Security**,
  scroll down, and click **"Open Anyway"** next to the MyMacroRecorder message.

You only need to do this once.

### Grant permissions (required)

macOS sandboxes input capture and synthesis. The app **will not record or
replay** until you grant **two** permissions in
**System Settings → Privacy & Security**:

1. **Accessibility** — lets the app *replay* (synthesize) mouse/keyboard events.
2. **Input Monitoring** — lets the app *record* (observe) mouse/keyboard events.

For each: open the section, click **+** (or toggle the switch), and add
**MyMacroRecorder**. **Quit and reopen the app** after granting permissions so
the new access takes effect.

> Tip: if recording or playback silently does nothing, it's almost always a
> missing permission or one that needs an app restart.

---

## Usage

1. Tick the **Capture** checkboxes for what you want to record.
2. Click **● Record** (or press the record hotkey, default **F2**). Do your thing.
3. Click **■ Stop** (or press the record hotkey again) to finish.
4. Set **Speed**, **Repeat** (once / N times / infinite), and an optional **Delay between** repeats.
5. Click **▶ Play** (or press the play hotkey, default **F3**). Press **Stop** / the play hotkey to abort.
6. **Save…** your macro to a `.json` file and **Load…** it later.

### Global hotkeys

Type the key names into the **Global hotkeys** fields and click **Apply**.
Use lowercase names: `f2`, `f3`, `esc`, `space`, `tab`, or a single character
like `a`. Hotkeys work even when the app window is not focused. (The configured
hotkey keys are automatically excluded from keyboard recordings.)

---

## Run from source (fallback for any OS)

If you'd rather not use the packaged app, or you're on Linux/Windows:

```bash
# 1. Clone
git clone https://github.com/chattlanisameer-art/macro.git
cd macro

# 2. Create a virtual environment (recommended)
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate

# 3. Install runtime dependency
pip install pynput                 # tkinter ships with python.org Python

# 4. Run
python3 macro_recorder.py
```

> On macOS you still need to grant **Accessibility** + **Input Monitoring** to
> your **terminal** (or to `Python`) when running from source.

---

## Build the `.app` yourself (macOS only)

PyInstaller cannot cross-compile — you must build the macOS `.app` **on a Mac**.

```bash
# from the repo root, on macOS:
chmod +x build_macos.sh
./build_macos.sh
```

This produces `dist/MyMacroRecorder.app` and `MyMacroRecorder.app.zip`.

<details>
<summary>What the script does (manual steps)</summary>

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
pyinstaller MyMacroRecorder.spec --noconfirm
ditto -c -k --sequesterRsrc --keepParent "dist/MyMacroRecorder.app" "MyMacroRecorder.app.zip"
```
</details>

---

## Recording file format

Recordings are plain JSON — easy to inspect or hand-edit:

```json
{
  "app": "MyMacroRecorder",
  "version": "1.0.0",
  "events": [
    { "type": "move",   "t": 0.10, "x": 400, "y": 300 },
    { "type": "click",  "t": 0.45, "x": 400, "y": 300, "button": "left", "pressed": true },
    { "type": "click",  "t": 0.55, "x": 400, "y": 300, "button": "left", "pressed": false },
    { "type": "scroll", "t": 1.20, "x": 400, "y": 300, "dx": 0, "dy": -2 },
    { "type": "key",    "t": 2.00, "key": { "char": "a" }, "pressed": true },
    { "type": "key",    "t": 2.05, "key": { "char": "a" }, "pressed": false }
  ]
}
```

`t` is seconds since recording started. Drags are recorded naturally as a
button-press, a series of moves, and a button-release.

---

## License

[MIT](LICENSE)
