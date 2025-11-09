# 🥁 Drumbo Drum Machine - Implementation Manual

**Date:** November 4, 2025  
**Version:** 1.0.0  
**Plugin Type:** Standalone Instrument  
**Architecture:** ModuleBase with Custom Widget

---

## 📖 Overview

Drumbo is a multi-sampled drum machine plugin designed for the UI-Midi-Pi ecosystem. It features:

- **16-microphone articulation system** for snare drums
- **8 round-robin samples** for kick drums
- **GM drum note compatibility** for Pro Tools integration
- **Audio hat interface** for recording and playback
- **Real-time parameter control** via 8 dials
- **4x4 pad grid** for triggering samples

---

## 🎯 Design Goals

✅ Record samples from 16 microphone positions for rich articulation variety  
✅ Support GM drum note protocol for DAW integration (Pro Tools, etc.)  
✅ Provide real-time control over velocity, pitch, decay, pan, and filtering  
✅ Enable round-robin playback for natural kick drum variations  
✅ Full preset save/load support for complete kit configurations  
✅ Visual feedback for articulation selection and playback state  

---

## 🏗️ Architecture

### File Structure

```
plugins/drumbo_plugin.py          # Main plugin module (ModuleBase)
widgets/drumbo_widget.py          # Custom 4x4 pad grid widget
config/device_page_layout.json    # Navigation button (ID 8)
config/samples/drumbo/            # Sample library storage
  snare/
    articulation_01.wav
    articulation_02.wav
    ...
    articulation_16.wav
  kick/
    round_robin_01.wav
    round_robin_02.wav
    ...
    round_robin_08.wav
```

### Integration Points

1. **Mode Manager** (`managers/mode_manager.py`)
   - Switch handler: `elif new_mode == "drumbo"`
   - Setup function: `_setup_drumbo()`
   - Navigation history: Added to nav recording list

2. **Renderer** (`rendering/renderer.py`)
   - UI mode check: Added `"drumbo"` to draw_ui() modes
   - Themed pages: Added `"drumbo"` to themed_pages tuple

3. **Performance Config** (`config/performance.py`)
   - FPS mode: High (100 FPS) for responsive triggering
   - Dirty rect: Enabled for efficient rendering

---

## 🎛️ Control Layout

### 8 Dials (Hardware Control)

| Slot | Label        | Variable            | Range      | Description                          |
|------|--------------|---------------------|------------|--------------------------------------|
| 1    | Velocity     | `velocity`          | 0-127      | Sample velocity/volume               |
| 2    | Articulation | `articulation`      | 1-16       | Snare mic position (1-16)            |
| 3    | RR Index     | `round_robin_index` | 1-8        | Kick round-robin selection (1-8)     |
| 4    | Pitch        | `pitch_shift`       | -24 to +24 | Pitch shift in semitones             |
| 5    | Decay        | `decay_time`        | 0-127      | Sample decay/release time            |
| 6    | Pan          | `pan`               | -64 to +63 | Stereo pan position                  |
| 7    | Volume       | `master_volume`     | 0-127      | Master output volume                 |
| 8    | Filter       | `filter_cutoff`     | 0-127      | Low-pass filter cutoff frequency     |

### 10 Buttons

| ID | Label       | Behavior    | States            | Description                          |
|----|-------------|-------------|-------------------|--------------------------------------|
| 1  | SNARE/KICK  | multi       | SNARE, KICK       | Toggle instrument mode               |
| 2  | MUTE        | toggle      | OFF, ON           | Mute all output                      |
| 3  | SOLO        | toggle      | OFF, ON           | Solo this instrument                 |
| 4  | REC         | transient   | -                 | Record sample from 16 mics           |
| 5  | PLAY        | transient   | -                 | Trigger current sample               |
| 6  | (Store)     | nav         | -                 | Store preset                         |
| 7  | P           | nav         | presets           | Load preset                          |
| 8  | (Mute)      | transient   | mute_toggle       | Quick mute toggle                    |
| 9  | S           | nav         | save_preset       | Save preset                          |
| 10 | (Exit)      | nav         | device_select     | Return to device selection           |

---

## 🎨 Custom Widget: DrumboWidget

### Visual Layout

```
┌────────────────────────────────────────┐
│           SNARE/KICK                   │  ← Header (instrument mode)
│                                        │
│   ┌──┐ ┌──┐ ┌──┐ ┌──┐                │
│   │1 │ │2 │ │3 │ │4 │                │  ← Pad grid (4x4)
│   └──┘ └──┘ └──┘ └──┘                │
│   ┌──┐ ┌──┐ ┌──┐ ┌──┐                │
│   │5 │ │6 │ │7 │ │8 │                │
│   └──┘ └──┘ └──┘ └──┘                │
│   ┌──┐ ┌──┐ ┌──┐ ┌──┐                │
│   │9 │ │10│ │11│ │12│                │
│   └──┘ └──┘ └──┘ └──┘                │
│   ┌──┐ ┌──┐ ┌──┐ ┌──┐                │
│   │13│ │14│ │15│ │16│                │
│   └──┘ └──┘ └──┘ └──┘                │
│                                        │
│     Articulation: 8/16                 │  ← Indicator
│                                        │
│     Velocity: 100                      │  ← Velocity bar
│     ████████████████░░░░░░░░░░        │
└────────────────────────────────────────┘
```

### Features

- **Pad highlighting**: Current articulation/round-robin pad is highlighted
- **Click triggering**: Click any pad to trigger that sample
- **Visual feedback**: Mute/Solo indicators in header
- **Velocity bar**: Real-time velocity display
- **Responsive**: 100 FPS rendering for immediate feedback

### Widget State (Preset Save/Load)

```python
{
    "current_instrument": "snare",      # "snare" or "kick"
    "articulation": 8,                  # 1-16
    "round_robin_index": 4,             # 1-8
    "velocity": 100,                    # 0-127
    "muted": False,
    "soloed": False
}
```

---

## 🎵 GM Drum Note Mapping

Drumbo uses standard General MIDI drum note assignments for Pro Tools compatibility:

| Instrument    | MIDI Note | Note Name | Use Case                              |
|---------------|-----------|-----------|---------------------------------------|
| Kick          | 36        | C1        | Main kick drum trigger                |
| Snare         | 38        | D1        | Main snare drum trigger               |
| Hi-Hat Closed | 42        | F#1       | Future expansion                      |
| Hi-Hat Open   | 46        | A#1       | Future expansion                      |
| Tom Low       | 41        | F1        | Future expansion                      |
| Tom Mid       | 43        | G1        | Future expansion                      |
| Tom High      | 45        | A1        | Future expansion                      |
| Crash Cymbal  | 49        | C#2       | Future expansion                      |

### Pro Tools Integration

When Drumbo receives MIDI note 36 or 38:
1. Maps note to kick or snare
2. Applies current velocity value
3. Triggers sample with current parameter settings (pitch, decay, pan, filter)
4. Uses current articulation/round-robin index

---

## 📦 Sample Library Format

### Directory Structure

```
config/samples/drumbo/
├── snare/
│   ├── articulation_01.wav    # Mic position 1
│   ├── articulation_02.wav    # Mic position 2
│   ├── articulation_03.wav    # Mic position 3
│   ├── ...
│   └── articulation_16.wav    # Mic position 16
└── kick/
    ├── round_robin_01.wav     # Kick variation 1
    ├── round_robin_02.wav     # Kick variation 2
    ├── round_robin_03.wav     # Kick variation 3
    ├── ...
    └── round_robin_08.wav     # Kick variation 8
```

### File Format Requirements

- **Format**: WAV (PCM)
- **Sample Rate**: 44.1kHz or 48kHz
- **Bit Depth**: 16-bit or 24-bit
- **Channels**: Mono or Stereo
- **Length**: Trimmed to minimize latency (attack at sample start)
- **Normalization**: Peak normalized to -3dB to prevent clipping

### Loading Sample Library

```python
from pathlib import Path
from plugins.sampler.instruments.drumbo.module import DrumboInstrument

# In your module initialization
module = DrumboInstrument()
library_path = Path("config/samples/drumbo")
module.load_sample_library(library_path)
```

---

## 🎙️ Recording Workflow (16-Mic Setup)

### Recording Session Setup

1. **Mic Array**: Position 16 microphones around snare drum
   - 4 top mics (different angles)
   - 4 bottom mics (snare wire resonance)
   - 4 room mics (ambient)
   - 4 close mics (attack/body)

2. **Recording**: Capture consistent hits
   - Hit snare with same velocity for each mic
   - Record 3-5 seconds per mic position
   - Trim to same start point (attack aligned)
   - Normalize to -3dB peak

3. **Export**: Save as WAV files
   - `articulation_01.wav` through `articulation_16.wav`
   - Place in `config/samples/drumbo/snare/`

4. **Load in Drumbo**:
   - Navigate to Drumbo page
   - Library auto-loads on init
   - Select articulation via dial 2 or pad grid

### Round-Robin Recording (Kick)

1. **Record 8 Variations**: Hit kick 8 times with slight timing/velocity variation
2. **Export**: Save as `round_robin_01.wav` through `round_robin_08.wav`
3. **Load**: Place in `config/samples/drumbo/kick/`
4. **Playback**: Drumbo cycles through variations automatically

---

## 🔌 Audio Hat Integration

### Required Interface Methods

Your audio hat driver should implement:

#### 1. Recording from Mics
```python
def record_sample(mic_index: int, duration_sec: float) -> bytes:
    """
    Record audio from specified mic channel.
    
    Args:
        mic_index: Mic number (1-16)
        duration_sec: Recording length in seconds
    
    Returns:
        Raw audio data (PCM bytes)
    """
    pass
```

#### 2. Sample Playback
```python
def play_sample(sample_data: bytes, velocity: int, 
                pitch_shift: int, decay: float, 
                pan: float, filter_cutoff: float):
    """
    Play sample with parameter modulation.
    
    Args:
        sample_data: Audio sample (WAV bytes)
        velocity: Velocity (0-127)
        pitch_shift: Semitones (-24 to +24)
        decay: Decay multiplier (0.0-1.0)
        pan: Pan position (-1.0 to +1.0)
        filter_cutoff: Filter frequency (0.0-1.0)
    """
    pass
```

#### 3. MIDI Interface
```python
def send_midi_note(note: int, velocity: int):
    """
    Send MIDI note-on message for DAW sync.
    
    Args:
        note: MIDI note number (36=kick, 38=snare)
        velocity: Note velocity (0-127)
    """
    pass
```

### Integration Example

```python
# In drumbo_plugin.py
from your_audio_driver import AudioHat

class DrumboModule(ModuleBase):
    def __init__(self):
        super().__init__()
        # Initialize audio hat
        self.audio_hat = AudioHat()
    
    def _record_sample(self):
        """Record from 16 mics."""
        if not self.audio_hat:
            showlog.error("[Drumbo] No audio hat available")
            return
        
        for mic_idx in range(1, 17):
            showlog.info(f"[Drumbo] Recording mic {mic_idx}/16...")
            sample_data = self.audio_hat.record_sample(mic_idx, duration_sec=3.0)
            
            # Save to library
            filename = f"articulation_{mic_idx:02d}.wav"
            filepath = Path("config/samples/drumbo/snare") / filename
            self._save_wav(filepath, sample_data)
        
        showlog.info("[Drumbo] Recording complete!")
    
    def _trigger_sample(self):
        """Trigger sample playback."""
        if not self.audio_hat:
            showlog.error("[Drumbo] No audio hat available")
            return
        
        # Get sample path
        if self.current_instrument == "snare":
            sample_key = f"articulation_{self.articulation}"
            midi_note = 38
        else:
            sample_key = f"round_robin_{self.round_robin_index}"
            midi_note = 36
        
        sample_path = self.sample_library[self.current_instrument]["samples"].get(sample_key)
        if not sample_path:
            showlog.error(f"[Drumbo] Sample not found: {sample_key}")
            return
        
        # Load sample data
        with open(sample_path, 'rb') as f:
            sample_data = f.read()
        
        # Convert parameters for audio hat
        decay_normalized = self.decay_time / 127.0
        pan_normalized = self.pan / 63.0
        filter_normalized = self.filter_cutoff / 127.0
        
        # Play with parameters
        self.audio_hat.play_sample(
            sample_data=sample_data,
            velocity=self.velocity,
            pitch_shift=self.pitch_shift,
            decay=decay_normalized,
            pan=pan_normalized,
            filter_cutoff=filter_normalized
        )
        
        # Send MIDI for DAW sync
        self.audio_hat.send_midi_note(midi_note, self.velocity)
        
        showlog.info(f"[Drumbo] Triggered {sample_key} at velocity {self.velocity}")
```

---

## 💾 Preset System

### Preset Storage

Presets are saved to: `config/presets/drumbo/`

Each preset includes:
- All dial values (velocity, articulation, round-robin, pitch, decay, pan, volume, filter)
- Button states (instrument mode, mute, solo)
- Widget state (current instrument, visual state)

### Preset Format (JSON)

```json
{
  "preset_name": "Snare Heavy",
  "buttons": {
    "1": 0,
    "2": 0,
    "3": 0
  },
  "dials": {
    "velocity": 120,
    "articulation": 4,
    "round_robin_index": 1,
    "pitch_shift": 0,
    "decay_time": 80,
    "pan": 0,
    "master_volume": 110,
    "filter_cutoff": 90
  },
  "widget": {
    "current_instrument": "snare",
    "articulation": 4,
    "round_robin_index": 1,
    "velocity": 120,
    "muted": false,
    "soloed": false
  }
}
```

### Creating Presets

1. **Set Parameters**: Adjust dials and buttons to desired settings
2. **Test**: Trigger samples to verify sound
3. **Save**: Press Button 9 (S) to save preset
4. **Name**: Enter preset name via text input dialog
5. **Confirm**: Preset saved to `config/presets/drumbo/`

### Loading Presets

1. **Press Button 7 (P)**: Open preset browser
2. **Select Preset**: Use navigation to choose preset
3. **Load**: Confirm selection
4. **Apply**: All parameters and widget state restored instantly

---

## 🎨 Theme Customization

Drumbo uses a percussion-inspired brown/tan color scheme:

```python
THEME = {
    # Header
    "header_bg_color": "#2C1810",      # Dark brown
    "header_text_color": "#FFE4C4",    # Bisque
    
    # Dials
    "dial_panel_color": "#1A0F08",     # Very dark brown
    "dial_fill_color": "#CD853F",      # Peru
    "dial_outline_color": "#DEB887",   # Burlywood
    "dial_text_color": "#FFE4C4",      # Bisque
    
    # Buttons
    "button_fill": "#8B4513",          # Saddle brown
    "button_outline": "#CD853F",       # Peru
    "button_text": "#FFE4C4",          # Bisque
    "button_active_fill": "#CD853F",   # Peru (lit)
    "button_active_text": "#2C1810",   # Dark brown
}
```

To customize, edit the `THEME` dictionary in `plugins/drumbo_plugin.py`.

---

## 🔧 Development & Extension

### Adding New Instruments

1. **Create Sample Directory**:
   ```bash
   mkdir config/samples/drumbo/hihat
   ```

2. **Update Sample Library**:
   ```python
   self.sample_library["hihat"] = {
       "variations": 8,
       "samples": {}
   }
   ```

3. **Add Button State**:
   ```python
   BUTTONS = [
       {
           "id": "1",
           "states": ["SNARE", "KICK", "HIHAT"]  # Add new state
       }
   ]
   ```

4. **Update Widget**: Modify `DrumboWidget.set_instrument()` to handle new type

### Custom Recording UI

For advanced recording workflows, create a custom recording page:

```python
# In drumbo_plugin.py
def on_button(self, btn_id: str, state_index: int = 0, state_data: dict = None):
    if btn_id == "4":  # REC button
        # Switch to recording page
        from managers import mode_manager
        mode_manager.switch_mode("drumbo_record")
```

Then create `pages/drumbo_record.py` with recording UI.

### Audio Processing Pipeline

For advanced DSP (reverb, compression, EQ), integrate an audio processing library:

```python
import soundfile as sf
import numpy as np
from scipy import signal

def apply_processing(audio_data: np.ndarray) -> np.ndarray:
    # Apply EQ
    sos = signal.butter(4, [300, 5000], 'bandpass', fs=48000, output='sos')
    filtered = signal.sosfilt(sos, audio_data)
    
    # Apply compression (simple)
    threshold = 0.5
    ratio = 4.0
    compressed = np.where(
        np.abs(filtered) > threshold,
        threshold + (np.abs(filtered) - threshold) / ratio,
        filtered
    )
    
    return compressed
```

---

## 🐛 Troubleshooting

### No Sound When Triggering

**Check:**
1. Audio hat driver initialized: `self.audio_hat is not None`
2. Sample library loaded: `self.sample_library["snare"]["samples"]`
3. Sample files exist: `Path(sample_path).exists()`
4. Master volume > 0: `self.master_volume`
5. Not muted: `self.button_states["2"] == 0`

### Samples Not Loading

**Check:**
1. Directory exists: `config/samples/drumbo/snare/`
2. Files named correctly: `articulation_01.wav` (not `articulation_1.wav`)
3. Files are WAV format (not MP3 or FLAC)
4. Permissions allow reading files

### Pads Not Responding

**Check:**
1. Widget loaded: `self.widget is not None`
2. Widget attached: `self.widget._module is self`
3. Event handling enabled: `handle_event()` returns `True` on click
4. Dirty rendering working: `widget.mark_dirty()` called

### MIDI Not Sending

**Check:**
1. MIDI interface initialized in audio hat
2. MIDI output port opened
3. Pro Tools receiving on correct channel
4. GM note mapping correct (36=kick, 38=snare)

---

## 📊 Performance Metrics

### Expected Performance

- **Latency**: <10ms from pad click to audio output
- **FPS**: 100 FPS sustained during interaction
- **CPU Usage**: <5% idle, <15% during playback
- **Memory**: ~50MB for plugin + samples

### Optimization Tips

1. **Pre-load samples**: Load all samples into memory on init
2. **Use audio buffer pool**: Reuse buffers instead of allocating
3. **Optimize widget rendering**: Only redraw dirty regions
4. **Cache pitch-shifted samples**: Pre-render common pitch shifts
5. **Use burst mode**: High FPS only during interaction

---

## 📚 API Reference

### DrumboModule Methods

#### `load_sample_library(library_path: Path)`
Load sample library from disk.

**Args:**
- `library_path`: Path to drumbo sample directory

**Example:**
```python
module.load_sample_library(Path("config/samples/drumbo"))
```

#### `trigger_from_midi(note: int, velocity: int)`
Trigger sample from external MIDI.

**Args:**
- `note`: MIDI note number (36=kick, 38=snare)
- `velocity`: Note velocity (0-127)

**Example:**
```python
module.trigger_from_midi(38, 100)  # Trigger snare at velocity 100
```

#### `_record_sample()`
Record new sample from 16 microphones.

**Example:**
```python
module._record_sample()  # Records all 16 mics sequentially
```

#### `_trigger_sample()`
Trigger current sample with current parameters.

**Example:**
```python
module._trigger_sample()  # Plays snare articulation 8 at velocity 100
```

### DrumboWidget Methods

#### `set_instrument(instrument: str)`
Change current instrument mode.

**Args:**
- `instrument`: "snare" or "kick"

#### `set_articulation(articulation: int)`
Update articulation index (1-16).

#### `set_round_robin_index(index: int)`
Update round-robin index (1-8).

#### `set_velocity(velocity: int)`
Update velocity value (0-127).

#### `get_state() -> dict`
Get widget state for preset saving.

#### `set_state(state: dict)`
Restore widget state from preset.

---

## 📝 Changelog

### Version 1.0.0 (November 4, 2025)
- ✅ Initial implementation
- ✅ ModuleBase integration complete
- ✅ 16 articulation support for snare
- ✅ 8 round-robin support for kick
- ✅ GM drum note mapping
- ✅ Custom 4x4 pad widget
- ✅ 8 dial parameter control
- ✅ Preset save/load support
- ✅ Audio hat interface placeholders
- ✅ Full theme customization

---

## 🎓 Learning Resources

### Related Documentation
- [Plugin Creation Manual](PLUGIN_CREATION_MANUAL_COMPLETE.md) - ModuleBase architecture
- [ASCII Animator Integration](ASCII_ANIMATOR_INTEGRATION_SUMMARY.md) - Similar plugin example
- [Performance Config](../config/performance.py) - FPS and rendering settings

### External Resources
- [General MIDI Drum Map](https://en.wikipedia.org/wiki/General_MIDI#Percussion) - Standard note assignments
- [Pro Tools MIDI](https://www.avidblogs.com/pro-tools-midi-guide/) - DAW integration
- [Audio Programming in Python](https://realpython.com/playing-and-recording-sound-python/) - Audio processing

---

## 🤝 Contributing

To contribute improvements to Drumbo:

1. **Test Changes**: Verify plugin loads and functions correctly
2. **Update Docs**: Add new features to this manual
3. **Follow Patterns**: Use ModuleBase patterns from manual
4. **Log Properly**: Use `showlog.info()` with `[Drumbo]` prefix
5. **Preset Compatible**: Ensure `export_state()`/`import_state()` work

---

## 📄 License

Part of UI-Midi-Pi ecosystem. See project root LICENSE file.

---

**End of Drumbo Implementation Manual**

*Built with ♥ for drummers who demand articulation variety*
