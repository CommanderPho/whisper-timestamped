#!/usr/bin/env python3
"""
Test script for the LiveWhisperLoggerApp
"""

import tkinter as tk
from whisper_timestamped.pho_launch_live_transcription import LiveWhisperLoggerApp
import sys

def test_app():
    """Test the LiveWhisperLoggerApp"""
    print("Testing LiveWhisperLoggerApp...")
    
    # Check if another instance is running
    if LiveWhisperLoggerApp.is_instance_running():
        print("Another instance is already running. Exiting.")
        return
    
    # Create the main window
    root = tk.Tk()
    
    try:
        # Create the app
        app = LiveWhisperLoggerApp(root)
        
        # Try to acquire singleton lock
        if not app.acquire_singleton_lock():
            print("Failed to acquire singleton lock")
            root.destroy()
            return
        
        print("App initialized successfully!")
        print("Available features:")
        print("- Manual text logging to LSL")
        print("- Live audio transcription (if audio libraries available)")
        print("- XDF recording of LSL streams")
        print("- System tray integration")
        
        # Check audio availability
        try:
            from whisper_timestamped.live import LiveTranscriber, LiveConfig
            import sounddevice as sd
            print("- Audio transcription: AVAILABLE")
            
            # List audio devices
            devices = app.get_audio_devices()
            print(f"- Found {len(devices)} audio input devices")
            
        except ImportError as e:
            print(f"- Audio transcription: NOT AVAILABLE ({e})")
        
        # Set up window close handler
        root.protocol("WM_DELETE_WINDOW", app.on_closing)
        
        print("\nStarting GUI...")
        root.mainloop()
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        root.destroy()

if __name__ == "__main__":
    test_app()