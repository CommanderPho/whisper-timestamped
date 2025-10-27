from copy import deepcopy
from RealtimeSTT import AudioToTextRecorder
import pyautogui
import pylsl
import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox, filedialog
import pylsl
import pyxdf
from datetime import datetime, timedelta
import os
import threading
import time
import numpy as np
import json
import pickle
import mne
from pathlib import Path
import pystray
from PIL import Image, ImageDraw
import keyboard
import pyautogui
import socket
import sys
import logging

from phopylslhelper.general_helpers import unwrap_single_element_listlike_if_needed, readable_dt_str, from_readable_dt_str, localize_datetime_to_timezone, tz_UTC, tz_Eastern, _default_tz
from phopylslhelper.easy_time_sync import EasyTimeSyncParsingMixin
from whisper_timestamped.mixins.live_whisper_transcription import LiveWhisperTranscriptionAppMixin

# Import the live transcription components
# from whisper_timestamped.live import LiveTranscriber, LiveConfig
# try:
#     import sounddevice as sd
#     AUDIO_AVAILABLE = True
# except ImportError:
#     AUDIO_AVAILABLE = False
#     sd = None

import os  # add at top if not present
program_lock_port = int(os.environ.get("LIVE_WHISPER_LOCK_PORT", 13371))

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


_default_xdf_folder = Path(r'E:/Dropbox (Personal)/Databases/UnparsedData/PhoLogToLabStreamingLayer_logs').resolve()
# _default_xdf_folder = Path('/media/halechr/MAX/cloud/University of Michigan Dropbox/Pho Hale/Personal/LabRecordedTextLog').resolve() ## Lab computer

whisper_audio_out_dir: Path = Path("L:/ScreenRecordings/EyeTrackerVR_Recordings/audio").resolve()
whisper_transcripts_dir: Path = Path("L:/ScreenRecordings/EyeTrackerVR_Recordings/transcriptions").resolve()
whisper_lsl_converted_transcripts_dir: Path = whisper_transcripts_dir.joinpath('LSL_Converted').resolve()
whisper_live_transcripts_dir: Path = Path("E:/Dropbox (Personal)/Databases/UnparsedData/PhoLogToLabStreamingLayer_logs/live_transcripts").resolve()


####################################################################
## The desired object-oriented class-based manager for the live app
# TODO: not fully implemented, copied from another similar app but haven't made it work yet.
class LiveWhisperLoggerApp(LiveWhisperTranscriptionAppMixin, EasyTimeSyncParsingMixin):
    # Class variable to track if an instance is already running
    _instance_running = False
    _lock_port = program_lock_port  # Port to use for singleton check

    @classmethod
    def is_instance_running(cls):
        """Check if another instance is already running"""
        try:
            # Try to bind to a specific port
            test_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            test_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            test_socket.bind(('localhost', cls._lock_port))
            test_socket.close()
            return False
        except OSError:
            # Port is already in use, another instance is running
            return True

    @classmethod
    def mark_instance_running(cls):
        """Mark that an instance is now running"""
        cls._instance_running = True

    @classmethod
    def mark_instance_stopped(cls):
        """Mark that the instance has stopped"""
        cls._instance_running = False

    def __init__(self, root):
        logger.info(f"__init__(root={root})  hit")
        self.root = root
        self.root.title("LSL Live Audio Transcript Logger with XDF Recording")
        self.root.geometry("800x700")

        # Set application icon
        self.setup_app_icon()

        # Recording state
        self.recording = False
        self.recording_thread = None
        self.inlet = None
        self.recorded_data = []
        self.recording_start_time = None

        self.init_EasyTimeSyncParsingMixin()

        # Live transcription state
        self.init_LiveWhisperTranscriptionAppMixin()

        # System tray and hotkey state
        self.system_tray = None
        self.hotkey_popover = None
        self.is_minimized = False

        # Singleton lock socket
        self._lock_socket = None

        # Shutdown flag to prevent GUI updates during shutdown
        self._shutting_down = False

        # Timestamp tracking for text entry
        self.main_text_timestamp = None
        self.popover_text_timestamp = None

        # EventBoard configuration and outlet
        self.eventboard_config = None
        self.eventboard_outlet = None
        self.eventboard_buttons = {}
        self.eventboard_toggle_states = {}  # Track toggle states
        self.eventboard_time_offsets = {}   # Track time offset dropdowns


        ## capture start timestamps:
        self.capture_stream_start_timestamps() ## `EasyTimeSyncParsingMixin`: capture timestamps for use in LSL streams
        self.capture_recording_start_timestamps() ## capture timestamps for use in LSL streams

        logger.info(f"\t set stream timestamps.")

        # Create GUI elements first
        self.setup_gui()

        # Setup transcription configuration
        self.setup_LiveWhisperTranscriptionAppMixin()

        # Check for recovery files
        self.check_for_recovery()

        # Then create LSL outlets
        self.setup_lsl_outlet()

        # Setup system tray and global hotkey
        self.setup_system_tray()

    def setup_app_icon(self):
        """Setup application icon from PNG file based on system theme"""
        try:
            # Detect system theme and choose appropriate icon
            icon_filename = self.get_theme_appropriate_icon()
            icon_path = Path("icons") / icon_filename

            if icon_path.exists():
                # Set window icon
                self.root.iconphoto(True, tk.PhotoImage(file=str(icon_path)))
                print(f"Application icon set from {icon_path}")
            else:
                print(f"Icon file not found: {icon_path}")
        except Exception as e:
            print(f"Error setting application icon: {e}")

    def get_theme_appropriate_icon(self):
        """Get the appropriate icon filename based on system theme"""
        try:
            import platform

            if platform.system() == "Windows":
                return self.detect_windows_theme()
            else:
                # For other systems, use a simple heuristic
                return self.detect_theme_simple()

        except Exception as e:
            print(f"Error detecting theme: {e}")
            # Fallback to dark icon
            return "LogToLabStreamingLayerIcon.png"

    def detect_windows_theme(self):
        """Detect Windows theme using registry"""
        try:
            import winreg

            # Check Windows 10/11 dark mode setting
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize") as key:
                try:
                    # Check if dark mode is enabled
                    dark_mode = winreg.QueryValueEx(key, "AppsUseLightTheme")[0]
                    if dark_mode == 0:  # Dark mode enabled
                        return "LogToLabStreamingLayerIcon.png"
                    else:  # Light mode
                        return "LogToLabStreamingLayerIcon_Light.png"
                except FileNotFoundError:
                    # Registry key doesn't exist, fall back to simple detection
                    return self.detect_theme_simple()
        except Exception as e:
            print(f"Error reading Windows theme registry: {e}")
            return self.detect_theme_simple()

    def detect_theme_simple(self):
        """Simple theme detection using tkinter"""
        try:
            import tkinter as tk

            # Create a temporary root to test theme
            temp_root = tk.Tk()
            temp_root.withdraw()  # Hide the window

            try:
                # Check the default background color
                bg_color = temp_root.cget('bg')

                # Simple heuristic: if background is very dark, use light icon
                if bg_color in ['#2e2e2e', '#3c3c3c', '#404040', 'SystemButtonFace']:
                    return "LogToLabStreamingLayerIcon.png"
                else:
                    return "LogToLabStreamingLayerIcon_Light.png"
            finally:
                temp_root.destroy()

        except Exception as e:
            print(f"Error in simple theme detection: {e}")
            # Default to dark icon
            return "LogToLabStreamingLayerIcon_Light.png"


    def acquire_singleton_lock(self):
        """Acquire the singleton lock by binding to the port"""
        try:
            self._lock_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self._lock_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self._lock_socket.bind(('localhost', self._lock_port))
            self._lock_socket.listen(1)
            self.mark_instance_running()
            print("Singleton lock acquired successfully")
            return True
        except OSError as e:
            print(f"Failed to acquire singleton lock: {e}")
            return False

    def release_singleton_lock(self):
        """Release the singleton lock and clean up the socket"""
        try:
            if self._lock_socket:
                self._lock_socket.close()
                self._lock_socket = None
            self.mark_instance_stopped()
            print("Singleton lock released")
        except Exception as e:
            print(f"Error releasing singleton lock: {e}")

    def setup_recording_inlet(self):
        """Setup inlet to record our own stream"""
        try:
            # Look for our own stream
            streams = pylsl.resolve_byprop('name', 'WhisperLiveLogger', timeout=2.0)
            if streams:
                self.inlet = pylsl.StreamInlet(streams[0])
                print("Recording inlet created successfully")

                # Auto-start recording after inlet is ready
                self.root.after(500, self.auto_start_recording)

            else:
                print("Could not find WhisperLiveLogger stream for recording")
                self.inlet = None
        except Exception as e:
            print(f"Error creating recording inlet: {e}")
            self.inlet = None
    # ---------------------------------------------------------------------------- #
    #                               Recording Methods                              #
    # ---------------------------------------------------------------------------- #

    def setup_lsl_outlet(self):
        """Create an LSL outlet for sending messages"""
        self.setup_lsl_outlet_LiveWhisperTranscriptionAppMixin()

    # ---------------------------------------------------------------------------- #
    #                           Live Transcription Methods                         #
    # ---------------------------------------------------------------------------- #

    # def setup_transcription_config(self):
    #     """Setup default transcription configuration

    #     captures: whisper_live_transcripts_dir

    #     """
    #     self.transcription_config = LiveConfig(
    #         model="medium",  # Good balance of speed and accuracy
    #         device=None,  # Auto-detect
    #         compute_type=None,  # Auto-detect
    #         language=None,  # Auto-detect
    #         beam_size=1,
    #         vad_filter=True,
    #         chunk_length_s=15.0,
    #         step_s=2.0,
    #         sample_rate=16000,
    #         channels=1,
    #         dtype="float32",
    #         output_dir=whisper_live_transcripts_dir,
    #         session_name=None,
    #         write_audio_wav=True,
    #         lsl=False,  # We'll handle LSL ourselves
    #         mic_device=None,
    #         word_timestamps=True,
    #         no_speech_threshold=0.6,
    #         logprob_threshold=-1.0,
    #         temperature=0.0
    #     )


    # @property
    # def whisper_live_transcripts_dir(self) -> Path:
    #     """The whisper_live_transcripts_dir property."""
    #     return self.transcription_config.output_dir
    # @whisper_live_transcripts_dir.setter
    # def whisper_live_transcripts_dir(self, value: Path):
    #     self.transcription_config.output_dir = value


    # def get_audio_devices(self):
    #     """Get list of available audio input devices"""
    #     if not AUDIO_AVAILABLE:
    #         return []

    #     try:
    #         devices = sd.query_devices()
    #         input_devices = []
    #         for i, device in enumerate(devices):
    #             if device['max_input_channels'] > 0:
    #                 input_devices.append((i, device['name']))
    #         return input_devices
    #     except Exception as e:
    #         print(f"Error getting audio devices: {e}")
    #         return []


    # def start_live_transcription(self):
    #     """Start live audio transcription"""
    #     if not AUDIO_AVAILABLE:
    #         messagebox.showerror("Error", "Audio libraries not available. Please install sounddevice and soundfile.")
    #         return

    #     logger.info(f".start_live_transcription()  hit")

    #     if self.transcription_active:
    #         return

    #     try:
    #         # Setup configuration if not already done
    #         if not self.transcription_config:
    #             self.setup_transcription_config()

    #         # Set session name with timestamp
    #         session_name = datetime.now().strftime("%Y%m%d_%H%M%S")
    #         self.transcription_config.session_name = session_name

    #         # Set selected audio device
    #         selected_device = self.audio_device_var.get()
    #         if selected_device != "Default":
    #             # Extract device index from the selection
    #             device_index = int(selected_device.split(":")[0])
    #             self.transcription_config.mic_device = device_index

    #         # Create transcriber instance
    #         self.live_transcriber = LiveTranscriber(self.transcription_config)
    #         logger.info(f"\t created live transcriber instance.")

    #         # Override the _emit method to send to our LSL stream
    #         original_emit = self.live_transcriber._emit
    #         def custom_emit(segments):
    #             # Send to our LSL outlet
    #             logger.info(f".custom_emit(segments={segments})  hit")
    #             for seg in segments:
    #                 text = seg.get("text", "").strip()
    #                 if text:
    #                     self.send_lsl_message(text)
    #                     # Update GUI display
    #                     timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    #                     self.update_log_display(f"[TRANSCRIBED] {text}", timestamp)

    #             # Also call original emit for file logging
    #             original_emit(segments)

    #         self.live_transcriber._emit = custom_emit

    #         # Start transcription
    #         self.live_transcriber.start()
    #         logger.info(f"\t started live transcription.")
            
    #         self.transcription_active = True

    #         # Update GUI
    #         try:
    #             if not self._shutting_down:
    #                 self.transcription_status_label.config(text="Transcribing...", foreground="green")
    #                 self.start_transcription_button.config(state="disabled")
    #                 self.stop_transcription_button.config(state="normal")
    #                 self.transcription_settings_button.config(state="disabled")
    #         except tk.TclError:
    #             pass

    #         self.update_log_display("Live transcription started", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    #         print(f"Live transcription started with session: {session_name}")

    #     except Exception as e:
    #         logger.error(f".start_live_transcription()  error: {e}")
    #         messagebox.showerror("Error", f"Failed to start live transcription: {str(e)}")
    #         print(f"Error starting transcription: {e}")
    #         import traceback
    #         traceback.print_exc()


    # def stop_live_transcription(self):
    #     """Stop live audio transcription"""
    #     logger.info(f".stop_live_transcription()  hit")
    #     if not self.transcription_active:
    #         return

    #     try:
    #         if self.live_transcriber:
    #             self.live_transcriber.stop()
    #             self.live_transcriber = None

    #         self.transcription_active = False

    #         # Update GUI
    #         try:
    #             if not self._shutting_down:
    #                 self.transcription_status_label.config(text="Not Transcribing", foreground="red")
    #                 self.start_transcription_button.config(state="normal")
    #                 self.stop_transcription_button.config(state="disabled")
    #                 self.transcription_settings_button.config(state="normal")
    #         except tk.TclError:
    #             pass

    #         self.update_log_display("Live transcription stopped", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    #         print("Live transcription stopped")

    #     except Exception as e:
    #         print(f"Error stopping transcription: {e}")


    # def show_transcription_settings(self):
    #     """Show transcription settings dialog"""
    #     if not self.transcription_config:
    #         self.setup_transcription_config()

    #     settings_window = tk.Toplevel(self.root)
    #     settings_window.title("Transcription Settings")
    #     settings_window.geometry("400x500")
    #     settings_window.transient(self.root)
    #     settings_window.grab_set()

    #     # Center the window
    #     settings_window.update_idletasks()
    #     x = (settings_window.winfo_screenwidth() // 2) - (400 // 2)
    #     y = (settings_window.winfo_screenheight() // 2) - (500 // 2)
    #     settings_window.geometry(f"+{x}+{y}")

    #     main_frame = ttk.Frame(settings_window, padding="10")
    #     main_frame.pack(fill=tk.BOTH, expand=True)

    #     # Model selection
    #     ttk.Label(main_frame, text="Whisper Model:").pack(anchor=tk.W, pady=(0, 5))
    #     model_var = tk.StringVar(value=self.transcription_config.model)
    #     model_combo = ttk.Combobox(main_frame, textvariable=model_var,
    #                               values=["tiny", "base", "small", "medium", "large-v3"],
    #                               state="readonly")
    #     model_combo.pack(fill=tk.X, pady=(0, 10))

    #     # Language selection
    #     ttk.Label(main_frame, text="Language (leave empty for auto-detect):").pack(anchor=tk.W, pady=(0, 5))
    #     language_var = tk.StringVar(value=self.transcription_config.language or "")
    #     language_entry = ttk.Entry(main_frame, textvariable=language_var)
    #     language_entry.pack(fill=tk.X, pady=(0, 10))

    #     # Device selection
    #     ttk.Label(main_frame, text="Processing Device:").pack(anchor=tk.W, pady=(0, 5))
    #     device_var = tk.StringVar(value=self.transcription_config.device or "auto")
    #     device_combo = ttk.Combobox(main_frame, textvariable=device_var,
    #                                values=["auto", "cpu", "cuda"], state="readonly")
    #     device_combo.pack(fill=tk.X, pady=(0, 10))

    #     # VAD filter
    #     vad_var = tk.BooleanVar(value=self.transcription_config.vad_filter)
    #     ttk.Checkbutton(main_frame, text="Enable Voice Activity Detection (VAD)",
    #                    variable=vad_var).pack(anchor=tk.W, pady=(0, 10))

    #     # Chunk length
    #     ttk.Label(main_frame, text="Chunk Length (seconds):").pack(anchor=tk.W, pady=(0, 5))
    #     chunk_var = tk.DoubleVar(value=self.transcription_config.chunk_length_s)
    #     chunk_spin = ttk.Spinbox(main_frame, from_=5.0, to=30.0, increment=1.0,
    #                             textvariable=chunk_var, format="%.1f")
    #     chunk_spin.pack(fill=tk.X, pady=(0, 10))

    #     # Step size
    #     ttk.Label(main_frame, text="Step Size (seconds):").pack(anchor=tk.W, pady=(0, 5))
    #     step_var = tk.DoubleVar(value=self.transcription_config.step_s)
    #     step_spin = ttk.Spinbox(main_frame, from_=0.5, to=10.0, increment=0.5,
    #                            textvariable=step_var, format="%.1f")
    #     step_spin.pack(fill=tk.X, pady=(0, 10))

    #     # Save audio
    #     save_audio_var = tk.BooleanVar(value=self.transcription_config.write_audio_wav)
    #     ttk.Checkbutton(main_frame, text="Save audio to WAV file",
    #                    variable=save_audio_var).pack(anchor=tk.W, pady=(0, 10))

    #     # Buttons
    #     button_frame = ttk.Frame(main_frame)
    #     button_frame.pack(fill=tk.X, pady=(20, 0))

    #     def save_settings():
    #         self.transcription_config.model = model_var.get()
    #         self.transcription_config.language = language_var.get() or None
    #         self.transcription_config.device = device_var.get() if device_var.get() != "auto" else None
    #         self.transcription_config.vad_filter = vad_var.get()
    #         self.transcription_config.chunk_length_s = chunk_var.get()
    #         self.transcription_config.step_s = step_var.get()
    #         self.transcription_config.write_audio_wav = save_audio_var.get()
    #         settings_window.destroy()

    #     ttk.Button(button_frame, text="Save", command=save_settings).pack(side=tk.RIGHT, padx=(5, 0))
    #     ttk.Button(button_frame, text="Cancel", command=settings_window.destroy).pack(side=tk.RIGHT)


    # def refresh_audio_devices(self):
    #     """Refresh the list of available audio devices"""
    #     devices = self.get_audio_devices()
    #     device_list = ["Default"]

    #     for device_id, device_name in devices:
    #         device_list.append(f"{device_id}: {device_name}")

    #     self.audio_device_combo['values'] = device_list

    #     # Set to default if current selection is not in the list
    #     if self.audio_device_var.get() not in device_list:
    #         self.audio_device_var.set("Default")


    # ==================================================================================================================================================================================================================================================================================== #
    # Shared/Common Stuff                                                                                                                                                                                                                                                                  #
    # ==================================================================================================================================================================================================================================================================================== #

    def setup_system_tray(self):
        """Setup system tray icon and menu"""
        try:
            # Create a simple icon (you can replace this with a custom icon file)
            icon_image = self.create_tray_icon()

            # Create system tray menu
            menu = pystray.Menu(
                pystray.MenuItem("Show App", self.show_app),
                pystray.MenuItem("Exit", self.quit_app)
            )

            # Create system tray icon
            self.system_tray = pystray.Icon(
                "logger_app",
                icon_image,
                "LSL Live Transcription",
                menu
            )

            # Add double-click handler to show app
            self.system_tray.on_activate = self.show_app ## double-clicking doesn't foreground the app by default. Also clicking the windows close "X" just hides it to taskbar by default which I don't want.

            # Start system tray in a separate thread
            threading.Thread(target=self.system_tray.run, daemon=True).start()

        except Exception as e:
            print(f"Error setting up system tray: {e}")


    def create_tray_icon(self):
        """Create icon for the system tray from PNG file based on system theme"""
        try:
            # Use the same theme detection as the main icon
            icon_filename = self.get_theme_appropriate_icon()
            icon_path = Path("icons") / icon_filename

            if icon_path.exists():
                # Load and resize the PNG icon for system tray
                image = Image.open(str(icon_path))
                # Resize to appropriate size for system tray (16x16 or 32x32)
                image = image.resize((16, 16), Image.Resampling.LANCZOS)
                return image
            else:
                print(f"Tray icon file not found: {icon_path}, using default")
                return self.create_default_tray_icon()
        except Exception as e:
            print(f"Error loading tray icon: {e}, using default")
            return self.create_default_tray_icon()

    def create_default_tray_icon(self):
        """Create a simple default icon for the system tray"""
        # Create a 16x16 icon with a simple design
        width = 16
        height = 16

        # Create image with a dark background
        image = Image.new('RGB', (width, height), color='#2c3e50')
        draw = ImageDraw.Draw(image)

        # Draw a simple "L" shape in white
        draw.rectangle([2, 2, 6, 14], fill='white')  # Vertical line
        draw.rectangle([2, 10, 12, 14], fill='white')  # Horizontal line

        return image

    # def setup_global_hotkey(self):
    #     """Setup global hotkey for quick log entry"""
    #     try:
    #         # Register Ctrl+Alt+L as the global hotkey
    #         keyboard.add_hotkey('ctrl+alt+l', self.show_hotkey_popover)
    #         print("Global hotkey Ctrl+Alt+L registered successfully")
    #     except Exception as e:
    #         print(f"Error setting up global hotkey: {e}")

    # def show_hotkey_popover(self):
    #     """Show the hotkey popover for quick log entry"""
    #     if self.hotkey_popover:
    #         # If popover already exists, just focus it and select text
    #         self.hotkey_popover.focus_force()
    #         self.hotkey_popover.lift()
    #         self.quick_log_entry.focus()
    #         self.quick_log_entry.select_range(0, tk.END)
    #         # Additional focus handling for existing popover
    #         self.hotkey_popover.after(10, self.ensure_focus)
    #         return

    #     # Create popover window
    #     self.hotkey_popover = tk.Toplevel()
    #     self.hotkey_popover.title("LSL Live Transcription")
    #     self.hotkey_popover.geometry("600x220")

    #     # Center the popover on the screen
    #     self.center_popover_on_active_monitor()

    #     # Make it always on top
    #     self.hotkey_popover.attributes('-topmost', True)

    #     # Remove window decorations for a cleaner look
    #     self.hotkey_popover.overrideredirect(True)

    #     # Force the popover to grab focus first
    #     self.hotkey_popover.focus_force()
    #     self.hotkey_popover.grab_set()  # Make it modal

    #     # Create content
    #     content_frame = ttk.Frame(self.hotkey_popover, padding="20")
    #     content_frame.pack(fill=tk.BOTH, expand=True)

    #     # Title label
    #     title_label = ttk.Label(content_frame, text="LSL Live Transcription", font=("Arial", 14, "bold"))
    #     title_label.pack(pady=(0, 15))

    #     # Entry field
    #     entry_frame = ttk.Frame(content_frame)
    #     entry_frame.pack(fill=tk.X, pady=(0, 10))

    #     entry_label = ttk.Label(entry_frame, text="Message:")
    #     entry_label.pack(anchor=tk.W)

    #     self.quick_log_entry = tk.Entry(entry_frame, font=("Arial", 12))
    #     self.quick_log_entry.pack(fill=tk.X, pady=(5, 0))
    #     self.quick_log_entry.bind('<Key>', self.on_popover_text_change)  # Track first keystroke
    #     self.quick_log_entry.bind('<BackSpace>', self.on_popover_text_clear)
    #     self.quick_log_entry.bind('<Delete>', self.on_popover_text_clear)

    #     # Instructions label
    #     instructions_label = ttk.Label(content_frame, text="Press Enter to log, Esc to cancel",
    #                                  font=("Arial", 9), foreground="gray")
    #     instructions_label.pack(pady=(5, 0))

    #     # Bind Enter key to log and close
    #     self.quick_log_entry.bind('<Return>', lambda e: self.quick_log_and_close())

    #     # Bind Escape key to close without logging
    #     self.hotkey_popover.bind('<Escape>', lambda e: self.close_hotkey_popover())

    #     # Focus the entry field and select all text
    #     self.quick_log_entry.focus()
    #     self.quick_log_entry.select_range(0, tk.END)

    #     # Additional focus handling to ensure it works reliably
    #     self.hotkey_popover.after(10, self.ensure_focus)

    #     # Handle window close
    #     self.hotkey_popover.protocol("WM_DELETE_WINDOW", self.close_hotkey_popover)

    def ensure_focus(self):
        """Ensure the text entry field has focus"""
        if self.hotkey_popover and self.quick_log_entry:
            self.quick_log_entry.focus_force()
            self.quick_log_entry.select_range(0, tk.END)

    def on_main_text_change(self, event=None):
        """Track when user first types in main text field"""
        if self.main_text_timestamp is None:
            self.main_text_timestamp = datetime.now()

    def on_popover_text_change(self, event=None):
        """Track when user first types in popover text field"""
        if self.popover_text_timestamp is None:
            self.popover_text_timestamp = datetime.now()

    def on_main_text_clear(self, event=None):
        """Reset timestamp when main text field is cleared"""
        if event and event.keysym in ['BackSpace', 'Delete']:
            # Check if field is now empty
            if not self.text_entry.get().strip():
                self.main_text_timestamp = None

    def on_popover_text_clear(self, event=None):
        """Reset timestamp when popover text field is cleared"""
        if event and event.keysym in ['BackSpace', 'Delete']:
            # Check if field is now empty
            if not self.quick_log_entry.get().strip():
                self.popover_text_timestamp = None

    def get_main_text_timestamp(self):
        """Get the timestamp when user first started typing in main field"""
        if self.main_text_timestamp:
            timestamp = self.main_text_timestamp
            self.main_text_timestamp = None  # Reset for next entry
            return timestamp
        return datetime.now()

    def get_popover_text_timestamp(self):
        """Get the timestamp when user first started typing in popover field"""
        if self.popover_text_timestamp:
            timestamp = self.popover_text_timestamp
            self.popover_text_timestamp = None  # Reset for next entry
            return timestamp
        return datetime.now()

    def center_popover_on_active_monitor(self):
        """Center the popover on the currently active monitor"""
        try:
            # Get screen dimensions and center the popover
            screen_width = self.hotkey_popover.winfo_screenwidth()
            screen_height = self.hotkey_popover.winfo_screenheight()
            x = (screen_width - 400) // 2
            y = (screen_height - 150) // 2
            self.hotkey_popover.geometry(f"+{x}+{y}")

        except Exception as e:
            print(f"Error centering popover: {e}")
            # Fallback to screen center
            screen_width = self.hotkey_popover.winfo_screenwidth()
            screen_height = self.hotkey_popover.winfo_screenheight()
            x = (screen_width - 400) // 2
            y = (screen_height - 150) // 2
            self.hotkey_popover.geometry(f"+{x}+{y}")

    def quick_log_and_close(self):
        """Log the message and close the popover"""
        message = self.quick_log_entry.get().strip()
        if message:
            # Send LSL message
            self.send_lsl_message(message)

            # Update main app display if visible
            if not self.is_minimized:
                # Use the timestamp when user first started typing in popover
                timestamp = self.get_popover_text_timestamp().strftime("%Y-%m-%d %H:%M:%S")
                self.update_log_display(message, timestamp)

            # Clear entry
            self.quick_log_entry.delete(0, tk.END)

        # Close popover
        self.close_hotkey_popover()

    def close_hotkey_popover(self):
        """Close the hotkey popover"""
        if self.hotkey_popover:
            self.hotkey_popover.destroy()
            self.hotkey_popover = None

    def show_app(self):
        """Show the main application window"""
        self.is_minimized = False
        self.root.deiconify()
        self.root.lift()
        self.root.focus_force()

    def minimize_to_tray(self):
        """Minimize the app to system tray"""
        self.is_minimized = True
        self.root.withdraw()  # Hide the window
        try:
            if not self._shutting_down:
                self.minimize_button.config(text="Restore from Tray")
        except tk.TclError:
            pass  # GUI is being destroyed

    def restore_from_tray(self):
        """Restore the app from system tray"""
        self.is_minimized = False
        self.root.deiconify()
        self.root.lift()
        self.root.focus_force()
        try:
            if not self._shutting_down:
                self.minimize_button.config(text="Minimize to Tray")
        except tk.TclError:
            pass  # GUI is being destroyed

    def toggle_minimize(self):
        """Toggle between minimize and restore"""
        if self.is_minimized:
            self.restore_from_tray()
        else:
            self.minimize_to_tray()

    def quit_app(self):
        """Quit the application completely"""
        if self.system_tray:
            self.system_tray.stop()
        self.on_closing()


    def setup_gui(self):
        """Create the GUI elements"""
        # Main frame
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

        # Configure grid weights
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(1, weight=1)
        main_frame.rowconfigure(4, weight=1)

        # LSL Status label
        self.lsl_status_label = ttk.Label(main_frame, text="LSL Status: Initializing...", foreground="orange")
        self.lsl_status_label.grid(row=0, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=(0, 10))

        # Recording control frame
        recording_frame = ttk.LabelFrame(main_frame, text="XDF Recording", padding="5")
        recording_frame.grid(row=1, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=(0, 10))
        recording_frame.columnconfigure(1, weight=1)

        # Recording status
        self.recording_status_label = ttk.Label(recording_frame, text="Not Recording", foreground="red")
        self.recording_status_label.grid(row=0, column=0, sticky=tk.W, padx=(0, 10))

        # Recording buttons
        self.start_recording_button = ttk.Button(recording_frame, text="Start Recording", command=self.start_recording)
        self.start_recording_button.grid(row=0, column=1, padx=5)

        self.stop_recording_button = ttk.Button(recording_frame, text="Stop Recording", command=self.stop_recording, state="disabled")
        self.stop_recording_button.grid(row=0, column=2, padx=5)

        # Add Split Recording button
        self.split_recording_button = ttk.Button(recording_frame, text="Split Recording", command=self.split_recording, state="disabled")
        self.split_recording_button.grid(row=0, column=3, padx=5)

        # Add Minimize to Tray button
        self.minimize_button = ttk.Button(recording_frame, text="Minimize to Tray", command=self.toggle_minimize)
        self.minimize_button.grid(row=0, column=4, padx=5)

        # Live Transcription control frame
        self.setup_gui_LiveWhisperTranscriptionAppMixin(main_frame)

        # transcription_frame = ttk.LabelFrame(main_frame, text="Live Audio Transcription", padding="5")
        # transcription_frame.grid(row=2, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=(0, 10))
        # transcription_frame.columnconfigure(2, weight=1)

        # # Transcription status
        # self.transcription_status_label = ttk.Label(transcription_frame, text="Not Transcribing", foreground="red")
        # self.transcription_status_label.grid(row=0, column=0, sticky=tk.W, padx=(0, 10))

        # # Transcription buttons
        # self.start_transcription_button = ttk.Button(transcription_frame, text="Start Transcription",
        #                                            command=self.start_live_transcription)
        # self.start_transcription_button.grid(row=0, column=1, padx=5)

        # self.stop_transcription_button = ttk.Button(transcription_frame, text="Stop Transcription",
        #                                           command=self.stop_live_transcription, state="disabled")
        # self.stop_transcription_button.grid(row=0, column=2, padx=5)

        # self.transcription_settings_button = ttk.Button(transcription_frame, text="Settings",
        #                                                command=self.show_transcription_settings)
        # self.transcription_settings_button.grid(row=0, column=3, padx=5)

        # # Audio device selection
        # ttk.Label(transcription_frame, text="Audio Device:").grid(row=1, column=0, sticky=tk.W, padx=(0, 10), pady=(5, 0))

        # self.audio_device_var = tk.StringVar(value="Default")
        # self.audio_device_combo = ttk.Combobox(transcription_frame, textvariable=self.audio_device_var,
        #                                      state="readonly", width=30)
        # self.audio_device_combo.grid(row=1, column=1, columnspan=2, sticky=(tk.W, tk.E), padx=5, pady=(5, 0))

        # # Populate audio devices
        # self.refresh_audio_devices()

        # # Refresh devices button
        # ttk.Button(transcription_frame, text="Refresh", command=self.refresh_audio_devices).grid(row=1, column=3, padx=5, pady=(5, 0))

        # EventBoard frame
        self.setup_eventboard_gui(main_frame)

        # Text input label and entry frame
        input_frame = ttk.Frame(main_frame)
        input_frame.grid(row=4, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=(0, 10))
        input_frame.columnconfigure(1, weight=1)

        ttk.Label(input_frame, text="Message:").grid(row=0, column=0, sticky=tk.W, padx=(0, 10))

        # Text input box
        self.text_entry = tk.Entry(input_frame, width=50)
        self.text_entry.grid(row=0, column=1, sticky=(tk.W, tk.E), padx=(0, 10))
        self.text_entry.bind('<Return>', lambda event: self.log_message())
        self.text_entry.bind('<Key>', self.on_main_text_change)  # Track first keystroke
        self.text_entry.bind('<BackSpace>', self.on_main_text_clear)
        self.text_entry.bind('<Delete>', self.on_main_text_clear)

        # Log button
        self.log_button = ttk.Button(input_frame, text="Log", command=self.log_message)
        self.log_button.grid(row=0, column=2)

        # Log display area
        ttk.Label(main_frame, text="Log History:").grid(row=5, column=0, sticky=(tk.W, tk.N), pady=(10, 5))

        # Scrolled text widget for log history
        self.log_display = scrolledtext.ScrolledText(main_frame, height=15, width=70)
        self.log_display.grid(row=6, column=0, columnspan=3, sticky=(tk.W, tk.E, tk.N, tk.S), pady=(0, 10))

        # Bottom frame for buttons and info
        bottom_frame = ttk.Frame(main_frame)
        bottom_frame.grid(row=7, column=0, columnspan=3, sticky=(tk.W, tk.E))
        bottom_frame.columnconfigure(1, weight=1)

        # Clear log button
        ttk.Button(bottom_frame, text="Clear Log Display", command=self.clear_log_display).grid(row=0, column=0, sticky=tk.W)

        # Status info
        self.status_info_label = ttk.Label(bottom_frame, text="Ready")
        self.status_info_label.grid(row=0, column=2, sticky=tk.E)

        # Focus on text entry
        self.text_entry.focus()

    def setup_eventboard_gui(self, main_frame):
        """Setup EventBoard GUI (placeholder for now)"""
        # EventBoard frame - placeholder for future implementation
        eventboard_frame = ttk.LabelFrame(main_frame, text="EventBoard (Future Feature)", padding="5")
        eventboard_frame.grid(row=3, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=(0, 10))

        ttk.Label(eventboard_frame, text="EventBoard functionality will be implemented here",
                 foreground="gray").pack(pady=10)

    # ---------------------------------------------------------------------------- #
    #                               Recording Methods                              #
    # ---------------------------------------------------------------------------- #

    def user_select_xdf_folder_if_needed(self) -> Path:
        """Ensures the self.xdf_folder is valid, otherwise forces the user to select a valid one. returns the valid folder.
        """
        self.xdf_folder = whisper_live_transcripts_dir
        if (self.xdf_folder is not None) and (self.xdf_folder.exists()) and (self.xdf_folder.is_dir()):
            ## already had valid folder, just return it
            return self.xdf_folder
        else:        
            self.xdf_folder = Path(filedialog.askdirectory(initialdir=str(self.xdf_folder), title="Select output XDF Folder - PhoLogToLabStreamingLayer_logs")).resolve()
            assert self.xdf_folder.exists(), f"XDF folder does not exist: {self.xdf_folder}"
            assert self.xdf_folder.is_dir(), f"XDF folder is not a directory: {self.xdf_folder}"
            self.update_log_display(f"XDF folder selected: {self.xdf_folder}", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
            print(f"XDF folder selected: {self.xdf_folder}")
            return self.xdf_folder


    def _common_capture_recording_start_timestamps(self):
        """Common code for capturing recording start timestamps"""
        # self.recording_start_datetime = datetime.now()
        # self.recording_start_datetime = datetime.now(datetime.timezone.utc)
        # self.recording_start_lsl_local_offset = pylsl.local_clock()
        self.capture_recording_start_timestamps()
        return (self.recording_start_datetime, self.recording_start_lsl_local_offset)


    def _common_initiate_recording(self, allow_prompt_user_for_filename: bool = True):
        """Common code for initiating recording
        called by `self.start_recording()` and `self.auto_start_recording()`, and also by `self.split_recording()`

        Usage:

            new_filename, (new_recording_start_datetime, new_recording_start_lsl_local_offset) = self._common_initiate_recording(allow_prompt_user_for_filename=True)

        """
        ## Capture recording timestamps:
        self._common_capture_recording_start_timestamps()

        # Create default filename with timestamp
        current_timestamp = self.recording_start_datetime.strftime("%Y%m%d_%H%M%S")
        default_filename = f"{current_timestamp}_log.xdf"

        # Ensure the default directory exists
        self.xdf_folder = self.user_select_xdf_folder_if_needed()
        self.xdf_folder.mkdir(parents=True, exist_ok=True)
        assert self.xdf_folder.exists(), f"XDF folder does not exist: {self.xdf_folder}"
        assert self.xdf_folder.is_dir(), f"XDF folder is not a directory: {self.xdf_folder}"

        # Set new filename directly
        if allow_prompt_user_for_filename:
            filename = filedialog.asksaveasfilename(initialdir=str(self.xdf_folder), initialfile=default_filename, defaultextension=".xdf", filetypes=[("XDF files", "*.xdf"), ("All files", "*.*")], title="Save XDF Recording As")
        else:
            filename = str(self.xdf_folder / default_filename)

        if not filename:
            return

        self.recording = True
        self.recorded_data = [] ## clear recorded data

        self.xdf_filename = filename

        # Create backup file for crash recovery
        self.backup_filename = str(Path(filename).with_suffix('.backup.json'))
        return self.xdf_filename, (self.recording_start_datetime, self.recording_start_lsl_local_offset)




    def start_recording(self):
        """Start XDF recording"""
        if not self.inlet:
            messagebox.showerror("Error", "No LSL inlet available for recording")
            return

        # Create default filename with timestamp
        new_filename, (new_recording_start_datetime, new_recording_start_lsl_local_offset) = self._common_initiate_recording(allow_prompt_user_for_filename=True)

        if not new_filename:
            return


        # Update GUI
        try:
            if not self._shutting_down:
                self.recording_status_label.config(text="Recording...", foreground="green")
                self.start_recording_button.config(state="disabled")
                self.stop_recording_button.config(state="normal")
                self.split_recording_button.config(state="normal")  # Enable split button
                self.status_info_label.config(text=f"Recording to: {os.path.basename(new_filename)}")
        except tk.TclError:
            pass  # GUI is being destroyed

        # Start recording thread
        self.recording_thread = threading.Thread(target=self.recording_worker, daemon=True)
        self.recording_thread.start()

        self.update_log_display("XDF Recording started", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))


    def auto_start_recording(self):
        """Automatically start recording on app launch if inlet is available"""
        if not self.inlet:
            print("Cannot auto-start recording: no inlet available")
            return

        try:
            # Create default filename with timestamp
            new_filename, (new_recording_start_datetime, new_recording_start_lsl_local_offset) = self._common_initiate_recording(allow_prompt_user_for_filename=True)

            # Update GUI
            try:
                if not self._shutting_down:
                    self.recording_status_label.config(text="Recording...", foreground="green")
                    self.start_recording_button.config(state="disabled")
                    self.stop_recording_button.config(state="normal")
                    self.split_recording_button.config(state="normal")  # Enable split button
                    self.status_info_label.config(text=f"Auto-recording to: {os.path.basename(self.xdf_filename)}")
            except tk.TclError:
                pass  # GUI is being destroyed

            # Start recording thread
            self.recording_thread = threading.Thread(target=self.recording_worker, daemon=True)
            self.recording_thread.start()

            self.update_log_display("XDF Recording auto-started", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
            print(f"Auto-started recording to: {self.xdf_filename}")

            # Log the auto-start event both in GUI and via LSL
            auto_start_message = f"RECORDING_AUTO_STARTED: {new_filename}"
            self.send_lsl_message(auto_start_message)  # Send via LSL
            self.update_log_display("XDF Recording auto-started", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
            print(f"Auto-started recording to: {self.xdf_filename}")

        except Exception as e:
            print(f"Error auto-starting recording: {e}")
            self.update_log_display(f"Auto-start failed: {str(e)}", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))


    def recording_worker(self):
        """Background thread for recording LSL data with incremental backup"""
        sample_count = 0

        while self.recording and self.inlet:
            try:
                sample, timestamp = self.inlet.pull_sample(timeout=1.0)
                if sample:
                    data_point = {
                        'sample': sample,
                        'timestamp': timestamp
                    }
                    self.recorded_data.append(data_point)
                    sample_count += 1

                    # Auto-save every 10 samples to backup file
                    if sample_count % 10 == 0:
                        self.save_backup()

            except Exception as e:
                print(f"Error in recording worker: {e}")
                break

    def stop_recording(self):
        """Stop XDF recording and save file"""
        if not self.recording:
            return

        self.recording = False

        # Log the stop event via LSL before saving
        stop_message = f"RECORDING_STOPPED: {os.path.basename(self.xdf_filename)}"
        self.send_lsl_message(stop_message)

        # Wait for recording thread to finish
        if self.recording_thread and self.recording_thread.is_alive():
            self.recording_thread.join(timeout=2.0)


        # Save XDF file
        self.save_xdf_file()

        # Clean up backup file
        try:
            if hasattr(self, 'backup_filename') and os.path.exists(self.backup_filename):
                os.remove(self.backup_filename)
        except Exception as e:
            print(f"Error removing backup file: {e}")

        # Update GUI
        try:
            if not self._shutting_down:
                self.recording_status_label.config(text="Not Recording", foreground="red")
                self.start_recording_button.config(state="normal")
                self.stop_recording_button.config(state="disabled")
                self.split_recording_button.config(state="disabled")  # Disable split button
                self.status_info_label.config(text="Ready")
        except tk.TclError:
            pass  # GUI is being destroyed

        self.update_log_display("XDF Recording stopped and saved", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))


    def split_recording(self):
        """Split recording into a new file - stop current and start new"""
        if not self.recording:
            return

        try:
            # Stop current recording (this will save the current data)
            self.stop_recording()

            # Wait a moment for the stop to complete
            self.root.after(100, self.start_new_split_recording)

        except Exception as e:
            print(f"Error splitting recording: {e}")
            self.update_log_display(f"Split recording failed: {str(e)}", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))


    def start_new_split_recording(self):
        """Start new recording after split"""
        if not self.inlet:
            print("Cannot split recording: no inlet available")
            return

        try:
            # Create new filename with timestamp
            # Set new filename directly
            new_filename, (new_recording_start_datetime, new_recording_start_lsl_local_offset) = self._common_initiate_recording(allow_prompt_user_for_filename=False)

            # Update GUI
            try:
                if not self._shutting_down:
                    self.recording_status_label.config(text="Recording...", foreground="green")
                    self.start_recording_button.config(state="disabled")
                    self.stop_recording_button.config(state="normal")
                    self.split_recording_button.config(state="normal")
                    self.status_info_label.config(text=f"Split to: {os.path.basename(self.xdf_filename)}")
            except tk.TclError:
                pass  # GUI is being destroyed

            # Start recording thread
            self.recording_thread = threading.Thread(target=self.recording_worker, daemon=True)
            self.recording_thread.start()

            self.update_log_display(f"Recording split to new file: {new_filename}", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
            print(f"Split recording to new file: {self.xdf_filename}")

            # Log the split event both in GUI and via LSL
            split_message = f"RECORDING_SPLIT_NEW_FILE: {new_filename}"
            self.send_lsl_message(split_message)  # Send via LSL
            self.update_log_display(f"Recording split to new file: {new_filename}", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
            print(f"Split recording to new file: {self.xdf_filename}")

        except Exception as e:
            print(f"Error starting new split recording: {e}")
            self.update_log_display(f"Split restart failed: {str(e)}", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))


    # ---------------------------------------------------------------------------- #
    #                             Backups and Recovery                             #
    # ---------------------------------------------------------------------------- #
    def save_backup(self):
        """Save current data to backup file"""
        try:
            backup_data = {
                'recorded_data': self.recorded_data,
                'recording_start_time': self.recording_start_time,
                'sample_count': len(self.recorded_data)
            }

            with open(self.backup_filename, 'w') as f:
                json.dump(backup_data, f, default=str)

        except Exception as e:
            print(f"Error saving backup: {e}")


    def check_for_recovery(self):
        """Check for backup files and offer recovery on startup"""
        backup_files = list(_default_xdf_folder.glob('*.backup.json'))

        if backup_files:
            response = messagebox.askyesno(
                "Recovery Available",
                f"Found {len(backup_files)} backup file(s) from previous sessions. "
                "Would you like to recover them?"
            )

            if response:
                for backup_file in backup_files:
                    self.recover_from_backup(backup_file)

    def recover_from_backup(self, backup_file):
        """Recover data from backup file"""
        try:
            with open(backup_file, 'r') as f:
                backup_data = json.load(f)

            # Ask user for recovery filename
            original_name = backup_file.stem.replace('.backup', '')
            recovery_filename = filedialog.asksaveasfilename(
                initialdir=str(_default_xdf_folder),
                initialfile=f"{original_name}_recovered.xdf",
                defaultextension=".xdf",
                filetypes=[("XDF files", "*.xdf"), ("All files", "*.*")],
                title="Save Recovered XDF As"
            )

            if recovery_filename:
                # Restore data
                self.recorded_data = backup_data['recorded_data']
                self.xdf_filename = recovery_filename

                # Save as XDF
                self.save_xdf_file()

                # Remove backup file
                os.remove(backup_file)

                messagebox.showinfo("Recovery Complete",
                    f"Recovered {len(self.recorded_data)} samples to {recovery_filename}")

        except Exception as e:
            messagebox.showerror("Recovery Error", f"Failed to recover from backup: {str(e)}")

    # ---------------------------------------------------------------------------- #
    #                              Save/Write Methods                              #
    # ---------------------------------------------------------------------------- #
    def save_xdf_file(self):
        """Save recorded data using MNE"""
        if not self.recorded_data:
            messagebox.showwarning("Warning", "No data to save")
            return

        try:
            # Extract messages and timestamps
            messages = []
            timestamps = []

            for data_point in self.recorded_data:
                message = data_point['sample'][0] if data_point['sample'] else ''
                timestamp = data_point['timestamp']
                messages.append(message)
                timestamps.append(timestamp)

            # Convert timestamps to relative times (from first sample)
            if timestamps:
                first_timestamp = timestamps[0]
                relative_timestamps = [ts - first_timestamp for ts in timestamps]
            else:
                relative_timestamps = []

            # Create annotations (MNE's way of handling markers/events)
            # Set orig_time=None to avoid timing conflicts
            annotations = mne.Annotations(
                onset=relative_timestamps,
                duration=[0.0] * len(relative_timestamps),  # Instantaneous events
                description=messages,
                orig_time=None  # This fixes the timing conflict
            )

            # Create a minimal info structure for the markers
            info = mne.create_info(
                ch_names=['TextLogger_Markers'],
                sfreq=1000,  # Dummy sampling rate for the minimal channel
                ch_types=['misc']
            )

            # Create raw object with minimal dummy data
            # We need at least some data points to create a valid Raw object
            if len(timestamps) > 0:
                # Create dummy data spanning the recording duration
                duration = relative_timestamps[-1] if relative_timestamps else 1.0
                n_samples = int(duration * 1000) + 1000  # Add buffer
                dummy_data = np.zeros((1, n_samples))
            else:
                dummy_data = np.zeros((1, 1000))  # Minimum 1 second of data

            raw = mne.io.RawArray(dummy_data, info)

            # Set measurement date to match the first timestamp
            if timestamps:
                raw.set_meas_date(timestamps[0])

            raw.set_annotations(annotations)

            # Add metadata to the raw object
            raw.info['description'] = 'TextLogger LSL Stream Recording'
            raw.info['experimenter'] = 'PhoLogToLabStreamingLayer'

            # Determine output filename and format
            if self.xdf_filename.endswith('.xdf'):
                # Save as FIF (MNE's native format)
                fif_filename = self.xdf_filename.replace('.xdf', '.fif')
                raw.save(fif_filename, overwrite=True)
                actual_filename = fif_filename
                file_type = "FIF"
            else:
                # Use the original filename
                raw.save(self.xdf_filename, overwrite=True)
                actual_filename = self.xdf_filename
                file_type = "FIF"

            # Also save a CSV for easy reading


            if isinstance(actual_filename, str):
                actual_filename = Path(actual_filename).resolve()

            _default_CSV_folder = actual_filename.parent.joinpath('CSV')
            _default_CSV_folder.mkdir(parents=True, exist_ok=True)
            print(f'_default_CSV_folder: "{_default_CSV_folder}"')

            csv_filename: str = actual_filename.name.replace('.fif', '_events.csv')
            csv_filepath: Path = _default_CSV_folder.joinpath(csv_filename).resolve()

            self.save_events_csv(csv_filepath, messages, timestamps)

            _status_str: str = (f"{file_type} file saved: '{actual_filename}'\n"
                f"Events CSV saved: '{csv_filepath}'\n"
                f"Recorded {len(self.recorded_data)} samples")
            self.update_log_display(_status_str, timestamp=None)
            # messagebox.showinfo("Success", _status_str)

        except Exception as e:
            messagebox.showerror("Error", f"Failed to save file: {str(e)}")
            print(f"Detailed error: {e}")
            import traceback
            traceback.print_exc()


    def save_events_csv(self, csv_filename, messages, timestamps):
        """Save events as CSV for easy reading"""
        try:
            import csv

            with open(csv_filename, 'w', newline='', encoding='utf-8') as csvfile:
                writer = csv.writer(csvfile)
                writer.writerow(['Timestamp', 'LSL_Time', 'Message'])

                for i, (message, lsl_time) in enumerate(zip(messages, timestamps)):
                    # Convert LSL timestamp to readable datetime
                    readable_time = datetime.fromtimestamp(lsl_time).strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]
                    writer.writerow([readable_time, lsl_time, message])

        except Exception as e:
            print(f"Error saving CSV: {e}")


    def log_message(self):
        """Handle log button click"""
        message = self.text_entry.get().strip()

        if not message:
            messagebox.showwarning("Warning", "Please enter a message to log.")
            return

        # Use the timestamp when user first started typing
        timestamp = self.get_main_text_timestamp().strftime("%Y-%m-%d %H:%M:%S")

        # Send LSL message
        self.send_lsl_message(message)

        # Update display
        self.update_log_display(message, timestamp)

        # Clear text entry
        self.text_entry.delete(0, tk.END)
        self.text_entry.focus()

    def send_lsl_message(self, message):
        """Send message via LSL"""
        if self.LiveWhisperTranscriptionAppMixin_outlet:
            try:
                # Send message with timestamp
                self.LiveWhisperTranscriptionAppMixin_outlet.push_sample([message])
                print(f"LSL message sent: {message}")
            except Exception as e:
                print(f"Error sending LSL message: {e}")
                messagebox.showerror("LSL Error", f"Failed to send LSL message: {str(e)}")
        else:
            print("LSL outlet not available")

    def update_log_display(self, message, timestamp=None):
        """Update the log display area"""
        # Don't update GUI if app is shutting down
        if self._shutting_down:
            return

        if timestamp is None:
            ## get now as the timestamp
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        try:
            log_entry = f"[{timestamp}] {message}\n"
            self.log_display.insert(tk.END, log_entry)
            self.log_display.see(tk.END)  # Auto-scroll to bottom
        except tk.TclError:
            # GUI is being destroyed, ignore the error
            pass

    def clear_log_display(self):
        """Clear the log display area"""
        self.log_display.delete(1.0, tk.END)

    def on_closing(self):
        """Handle window closing"""
        # Set shutdown flag to prevent GUI updates
        self._shutting_down = True

        # Stop transcription if active
        if self.transcription_active:
            self.stop_live_transcription()

        # Stop recording if active
        if self.recording:
            self.stop_recording()

        # Clean up hotkey
        try:
            keyboard.remove_hotkey('ctrl+alt+l')
        except:
            pass

        # Clean up system tray
        if self.system_tray:
            self.system_tray.stop()

        # Clean up LSL resources
        if hasattr(self, 'outlet') and self.LiveWhisperTranscriptionAppMixin_outlet:
            del self.LiveWhisperTranscriptionAppMixin_outlet
        if hasattr(self, 'inlet') and self.inlet:
            del self.inlet
        if hasattr(self, 'eventboard_outlet') and self.eventboard_outlet:
            del self.eventboard_outlet

        # Release singleton lock
        self.release_singleton_lock()

        self.root.destroy()


#############################################
## The main (completely working) Code
def start_callback():
    print("Recording started!")

def stop_callback():
    print("Recording stopped!")


def wakeword_detected_callback():
    print("Wakeword Detected!")

def wakeword_timeout_callback():
    print("\t...wakeword timeout")

def process_text(text):
    print(text)
    # pyautogui.typewrite(text + " ")


def main():
    # Check if another instance is already running
    if LiveWhisperLoggerApp.is_instance_running():
        messagebox.showerror("Instance Already Running",
                            "Another instance of LSL Logger is already running.\n"
                            "Only one instance can run at a time.")
        sys.exit(1)

    root = tk.Tk()
    app = LiveWhisperLoggerApp(root)

    # Try to acquire the singleton lock
    if not app.acquire_singleton_lock():
        messagebox.showerror("Startup Error",
                            "Failed to acquire singleton lock.\n"
                            "Another instance may be running.")
        root.destroy()
        sys.exit(1)

    # # Handle window closing - minimize to tray instead of closing
    # def on_closing():
    #     app.minimize_to_tray()
    # root.protocol("WM_DELETE_WINDOW", on_closing)

    # Start the GUI
    root.mainloop()

if __name__ == "__main__":
    main()


