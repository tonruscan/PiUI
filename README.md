# 🎛 PiUI — Modular Raspberry Pi Synth Control System

**PiUI** is a modular touchscreen control interface for analog synths, filters, and effects.  
It runs on Raspberry Pi 3/4 and Pi Zero 2 W, using Python + Pygame to provide real-time CV and MIDI control.

---

## ✨ Features

- Dynamic module system (`/modules/`) for effects like **Vibrato**, **ADSR**, and **Mixer**
- Touchscreen-friendly UI running up to 100 FPS
- Integrated **CV Server** on a Pi Zero 2 W for 5 V / 10 V analog output
- Preset system with **remote keyboard** and **device patch sync**
- Per-device themes (e.g. “Tequila Sunrise” for BMLPF filter)
- Full logging, event bus, and registry management

---

## 🧰 Installation

\`\`\`bash
git clone https://github.com/tonruscan/PiUI.git
cd PiUI
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python ui.py
\`\`\`

---

## 📁 Structure

| Folder | Purpose |
|:-------|:---------|
| `modules/` | Modular effect units (e.g. `vibrato_mod.py`) |
| `widgets/` | UI elements such as ADSR Widget |
| `system/`  | Core services: registry, state manager, event bus |
| `pages/`   | UI pages (dials, presets, mixer, etc.) |
| `device/`  | Device definitions (e.g. `bmlpf.py`) |
| `config/`  | Presets and patch data |

---

## 🧠 Credits

Developed by **tonruscan**  
Designed for real-time modular control of analog gear.
