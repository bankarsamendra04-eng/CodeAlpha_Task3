# Audio Rendering Guide: MIDI to Playable Audio (WAV/MP3)

The **AI Music Studio** generates symbolic musical compositions (MIDI). To listen to these compositions directly without external DAWs, the studio includes an audio synthesis engine powered by **FluidSynth** and General MIDI SoundFonts.

---

## 1. Architecture Overview

```
Generated LSTM Music
        ↓
Standard MIDI File (.mid) in output/midi/
        ↓
scripts/render_audio.py
        ↓
FluidSynth Synthesizer + General MIDI SoundFont (.sf2)
        ↓
Playable WAV Audio (.wav) in output/audio/
        ↓ [Optional]
FFmpeg (MP3 / OGG compression)
```

### Graceful Degradation Guarantee
* **Non-Blocking Operation**: If FluidSynth or a SoundFont is missing on your machine, MIDI generation **continues without interruption**.
* Symbolic MIDI files are always created and preserved.
* When audio rendering tools are configured, audio will render automatically.

---

## 2. Prerequisites & Setup Instructions

To enable direct WAV audio rendering, FluidSynth and a General MIDI SoundFont are required.

### A. Installing FluidSynth

#### Windows
* **Using Chocolatey**:
  ```powershell
  choco install fluidsynth
  ```
* **Using Scoop**:
  ```powershell
  scoop install fluidsynth
  ```
* **Manual Binary Download**:
  1. Download the latest Windows release zip from [FluidSynth GitHub Releases](https://github.com/FluidSynth/fluidsynth/releases).
  2. Extract to a folder (e.g. `C:\tools\fluidsynth\`).
  3. Add `C:\tools\fluidsynth\bin` to your system `PATH`, OR set `FLUIDSYNTH_PATH` in `.env`:
     ```ini
     FLUIDSYNTH_PATH=C:\tools\fluidsynth\bin\fluidsynth.exe
     ```

#### Linux (Debian / Ubuntu / WSL)
```bash
sudo apt-get update
sudo apt-get install -y fluidsynth
```

#### macOS (Homebrew)
```bash
brew install fluidsynth
```

---

### B. SoundFont (.sf2) Configuration

FluidSynth is a wavetable software synthesizer and requires sample tables (SoundFont `.sf2`) to produce instrument sounds (grand piano, guitars, violins, etc.).

#### Recommended Free SoundFonts:
| SoundFont | Approximate Size | Characteristics | Recommended For |
|:---|:---|:---|:---|
| **FluidR3_GM.sf2** | ~140 MB | Rich, high-fidelity GM standard | Studio-grade rendering |
| **GeneralUser GS** | ~30 MB | Highly balanced, expressive acoustic instruments | General versatile use |
| **TimGM6mb.sf2** | ~6 MB | Ultra-compact, fast loading | Low-spec machines / testing |

#### Configuration Options:
1. Place any `.sf2` file in the project's `soundfonts/` directory:
   ```
   AI-Music-Studio/
   └── soundfonts/
       └── default.sf2
   ```
2. Or configure the absolute path in `.env`:
   ```ini
   SOUNDFONT_PATH=C:\path\to\GeneralUser_GS.sf2
   ```

---

### C. Optional: FFmpeg (Format Conversion)

FFmpeg is only utilized if compressed formats (such as MP3 or OGG streaming) are requested:
* **Windows**: `winget install Gyan.FFmpeg` or `choco install ffmpeg`
* **Linux**: `sudo apt install ffmpeg`
* **macOS**: `brew install ffmpeg`

---

## 3. Usage

### Command Line Rendering

#### Basic Render:
```bash
python scripts/render_audio.py output/midi/music_studio_sample.mid
```
* The rendered `.wav` will be placed in `output/audio/<midi_name>.wav`.

#### Custom Output Path and SoundFont:
```bash
python scripts/render_audio.py path/to/song.mid --output output/audio/my_track.wav --soundfont soundfonts/FluidR3_GM.sf2
```

#### Diagnostic Check:
Check your system's FluidSynth and SoundFont readiness without rendering:
```bash
python scripts/render_audio.py --check-only dummy
```

---

## 4. Programmatic API Integration

You can invoke audio rendering programmatically within the Python engine:

```python
from scripts.render_audio import convert_midi_to_wav

success, wav_path, info = convert_midi_to_wav(
    midi_path="output/midi/my_song.mid",
    output_wav_path="output/audio/my_song.wav",
)

if success:
    print(f"Audio ready at: {wav_path}")
    print(f"Duration: {info['validation']['duration_seconds']}s")
else:
    print("Audio rendering unavailable, using MIDI fallback.")
```

---

## 5. Validation Standards

Every rendered WAV file is verified against:
1. **RIFF Wave Header Compliance**: Standard canonical header inspection.
2. **Audio Channels**: Mono (1) or Stereo (2).
3. **Sample Rate**: Minimum standard sample rate $\ge 8000$ Hz (default: $44100$ Hz).
4. **Frame Integrity**: Verifies non-empty audio data frames and valid duration.