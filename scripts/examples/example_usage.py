#!/usr/bin/env python3
"""
Example usage of the LiveWhisperLoggerApp
"""

import tkinter as tk
import time
import threading
from whisper_timestamped.pho_launch_live_transcription import LiveWhisperLoggerApp

def example_automated_session():
    """
    Example of running an automated transcription session
    """
    print("Starting automated transcription session...")
    
    # Create the app
    root = tk.Tk()
    app = LiveWhisperLoggerApp(root)
    
    if not app.acquire_singleton_lock():
        print("Could not acquire singleton lock")
        return
    
    # Set up close handler
    root.protocol("WM_DELETE_WINDOW", app.on_closing)
    
    def automated_sequence():
        """Run automated sequence in a separate thread"""
        try:
            # Wait for GUI to initialize
            time.sleep(2)
            
            # Send some manual messages
            print("Sending manual test messages...")
            app.send_lsl_message("Session started - automated test")
            app.update_log_display("Session started - automated test", None)
            
            time.sleep(1)
            
            # Start XDF recording
            print("Starting XDF recording...")
            app.auto_start_recording()
            
            time.sleep(2)
            
            # Send more test messages
            test_messages = [
                "Testing message 1",
                "Testing message 2", 
                "Testing message 3"
            ]
            
            for i, msg in enumerate(test_messages):
                print(f"Sending test message {i+1}: {msg}")
                app.send_lsl_message(msg)
                app.update_log_display(msg, None)
                time.sleep(1)
            
            # Try to start live transcription (if available)
            try:
                print("Attempting to start live transcription...")
                app.start_live_transcription()
                print("Live transcription started successfully!")
                
                # Let it run for a bit
                time.sleep(10)
                
                print("Stopping live transcription...")
                app.stop_live_transcription()
                
            except Exception as e:
                print(f"Live transcription not available: {e}")
            
            # Stop recording
            print("Stopping XDF recording...")
            app.stop_recording()
            
            print("Automated sequence completed!")
            
        except Exception as e:
            print(f"Error in automated sequence: {e}")
            import traceback
            traceback.print_exc()
    
    # Start automated sequence in background
    automation_thread = threading.Thread(target=automated_sequence, daemon=True)
    automation_thread.start()
    
    # Start GUI
    print("Starting GUI (automated sequence will run in background)...")
    root.mainloop()

def example_manual_session():
    """
    Example of running a manual session with user interaction
    """
    print("Starting manual transcription session...")
    print("Use the GUI to:")
    print("1. Select your audio device")
    print("2. Configure transcription settings")
    print("3. Start live transcription")
    print("4. Start XDF recording")
    print("5. Speak into your microphone")
    print("6. Add manual text entries")
    print("7. Stop when done")
    
    # Create and run the app normally
    root = tk.Tk()
    app = LiveWhisperLoggerApp(root)
    
    if not app.acquire_singleton_lock():
        print("Could not acquire singleton lock")
        return
    
    root.protocol("WM_DELETE_WINDOW", app.on_closing)
    root.mainloop()

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "auto":
        example_automated_session()
    else:
        example_manual_session()