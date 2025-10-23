# Project Context

## Purpose
Provide multilingual Automatic Speech Recognition (ASR) with accurate word-level timestamps and confidence scores, built on OpenAI Whisper and compatible backends. The project offers:
- Word-level timestamps via DTW alignment on cross-attention
- Confidence per word and segment
- Optional pre-VAD (Silero, Auditok) to reduce hallucinations
- CLI tools for batch transcription and subtitle generation
- Near real-time microphone transcription (JSONL stream, optional LSL markers)
- Utilities for formatting outputs (CSV, TSV, SRT, VTT, words.* variants)

## Tech Stack
- **Language**: Python (>=3.10,<3.11)
- **Core ML**: OpenAI Whisper, faster-whisper (CTranslate2)
- **DL Runtime**: PyTorch (with CUDA on GPU; CPU supported)
- **Audio/Signal**: torchaudio, numpy, scipy, ffmpeg
- **VAD**: silero-vad (onnxruntime), auditok
- **Model Hub**: huggingface-hub, transformers (optional backend/models)
- **Live I/O**: sounddevice, soundfile, pylsl, mne/mne-lsl, phopylslhelper
- **CLI/Packaging**: setuptools entry points, PyInstaller specs, uv
- **Container**: Dockerfiles (GPU and CPU variants)

## Project Conventions

### Code Style
- Follow PEP 8 naming and layout; prefer descriptive names over abbreviations
- Use type hints where practical; dataclasses for simple configs (see `LiveConfig`)
- Minimize deep nesting; prefer early returns; avoid broad try/except
- Keep functions cohesive; split long routines when feasible
- Docstrings for public functions; comments only for non-obvious reasoning
- No enforced formatter in repo; keep consistent whitespace and imports

### Architecture Patterns
- Library-first design with CLI entry points via `pyproject.toml` `[project.scripts]`:
  - `whisper_timestamped` → `whisper_timestamped.transcribe:cli`
  - `whisper_timestamped_make_subtitles` → `whisper_timestamped.make_subtitles:cli`
  - `whisper_timestamped_live` → `whisper_timestamped.live:cli`
  - `whisper_timestamped_watch` → `whisper_timestamped.watcher:cli`
- Core module `whisper_timestamped/transcribe.py` implements transcription, word alignment (DTW on attention), confidence, formatting, and file writers
- Real-time module `whisper_timestamped/live.py` uses faster-whisper for low-latency mic capture and emits JSONL (+ optional LSL markers)
- Support modules: `make_subtitles.py` (split/format subs), `watcher.py` (batch/watch), `parse_video_filename.py`
- Tests assert non-regression via golden outputs (`tests/expected`) with JSON schema validation
- Optional backend flexibility: OpenAI Whisper and Transformers/HF models supported by `load_model`

### Testing Strategy
- Python `unittest` suite in `tests/` with runner `tests/run_tests.py`
- Non-regression tests compare generated files to fixtures in `tests/expected/` (files per option set)
- JSON outputs validated against `tests/json_schema.json`
- Device-aware gating: long tests or device-specific outputs are skipped or suffixed for CPU; CUDA runs enable more cases
- CLI exercised end-to-end (stdout and filesystem artifacts) with configurable options
- Flags to manage fixtures: `--generate`, `--generate_all`, `--generate_device`, `--generate_new`, `--long`

### Git Workflow
- Branching: feature branches `feature/*`, merge via PR into main branch
- Keep commits scoped and descriptive; prefer PR reviews before merging
- Large or behavior-changing work should go through an OpenSpec change proposal under `openspec/changes/`

## Domain Context
- Whisper provides segment-level timestamps; project adds word-level alignment using cross-attention + DTW
- VAD pre-processing reduces hallucinations by trimming non-speech before transcription
- Confidence scores enable downstream filtering and subtitle quality control
- Multiple output formats produced simultaneously, including `*.words.*` variants for per-word timing
- Real-time mode deduplicates emissions and can broadcast text via Lab Streaming Layer (LSL)

## Important Constraints
- Python version: `>=3.10,<3.11`
- FFmpeg must be installed and available on PATH for audio processing
- GPU recommended for medium/large models; CPU mode supported with lighter models
- Some outputs are device-dependent (CPU vs CUDA) and duration-dependent; tests account for this
- OnnxRuntime pinned `<1.23` for Silero VAD compatibility
- Large model downloads may require adequate disk and network throughput

## External Dependencies
- OpenAI Whisper (ASR); Transformers/HuggingFace Hub (optional backend/models)
- faster-whisper / CTranslate2 (real-time transcription backend)
- PyTorch, torchaudio, numpy, scipy (DL and audio processing)
- silero-vad (ONNX) and auditok (VAD)
- onnxruntime (for Silero), ffmpeg, PortAudio (via `portaudio19-dev` in Docker)
- sounddevice, soundfile (I/O), pylsl and mne-lsl (LSL streaming)
- matplotlib (optional for alignment/VAD plots)
- jsonschema (test validation), setuptools/pyinstaller/uv (packaging/build)
