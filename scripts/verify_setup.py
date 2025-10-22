#!/usr/bin/env python3
"""
Verify that all dependencies for LiveWhisperLoggerApp are properly installed
"""

import sys
from pathlib import Path

def check_python_version():
    """Check Python version compatibility"""
    print("Checking Python version...")
    version = sys.version_info
    print(f"Python version: {version.major}.{version.minor}.{version.micro}")
    
    if version.major != 3 or version.minor != 10:
        print("⚠️  WARNING: This application is designed for Python 3.10")
        print("   Other versions may work but are not officially supported")
    else:
        print("✅ Python version is compatible")
    
    return True

def check_required_imports():
    """Check if all required packages can be imported"""
    print("\nChecking required packages...")
    
    required_packages = [
        ("tkinter", "GUI framework"),
        ("numpy", "Numerical computing"),
        ("pandas", "Data manipulation"),
        ("mne", "Neurophysiology data handling"),
        ("pylsl", "Lab Streaming Layer"),
        ("pyxdf", "XDF file handling"),
        ("pathlib", "Path handling"),
        ("threading", "Multi-threading"),
        ("json", "JSON handling"),
        ("datetime", "Date/time handling"),
    ]
    
    optional_packages = [
        ("sounddevice", "Audio capture"),
        ("soundfile", "Audio file handling"),
        ("faster_whisper", "Whisper transcription"),
        ("torch", "PyTorch for GPU acceleration"),
        ("pystray", "System tray integration"),
        ("PIL", "Image handling"),
        ("keyboard", "Global hotkeys"),
    ]
    
    all_good = True
    
    # Check required packages
    for package, description in required_packages:
        try:
            __import__(package)
            print(f"✅ {package:15} - {description}")
        except ImportError as e:
            print(f"❌ {package:15} - {description} (MISSING: {e})")
            all_good = False
    
    print("\nChecking optional packages...")
    
    # Check optional packages
    optional_available = 0
    for package, description in optional_packages:
        try:
            __import__(package)
            print(f"✅ {package:15} - {description}")
            optional_available += 1
        except ImportError as e:
            print(f"⚠️  {package:15} - {description} (optional, not available)")
    
    print(f"\nOptional packages available: {optional_available}/{len(optional_packages)}")
    
    return all_good

def check_whisper_models():
    """Check if Whisper models can be loaded"""
    print("\nChecking Whisper model availability...")
    
    try:
        from faster_whisper import WhisperModel
        print("✅ faster-whisper is available")
        
        # Try to load a small model
        try:
            print("Testing model loading (this may take a moment)...")
            model = WhisperModel("tiny", device="cpu", compute_type="int8")
            print("✅ Whisper model loading successful")
            del model  # Clean up
            return True
        except Exception as e:
            print(f"⚠️  Whisper model loading failed: {e}")
            return False
            
    except ImportError:
        print("❌ faster-whisper not available - live transcription will not work")
        return False

def check_audio_devices():
    """Check available audio devices"""
    print("\nChecking audio devices...")
    
    try:
        import sounddevice as sd
        devices = sd.query_devices()
        
        input_devices = []
        for i, device in enumerate(devices):
            if device['max_input_channels'] > 0:
                input_devices.append((i, device['name']))
        
        print(f"✅ Found {len(input_devices)} audio input devices:")
        for device_id, device_name in input_devices[:5]:  # Show first 5
            print(f"   {device_id}: {device_name}")
        
        if len(input_devices) > 5:
            print(f"   ... and {len(input_devices) - 5} more")
        
        return len(input_devices) > 0
        
    except ImportError:
        print("❌ sounddevice not available - audio capture will not work")
        return False
    except Exception as e:
        print(f"⚠️  Error checking audio devices: {e}")
        return False

def check_lsl_functionality():
    """Check LSL functionality"""
    print("\nChecking LSL functionality...")
    
    try:
        import pylsl
        
        # Test creating a stream
        info = pylsl.StreamInfo(
            name='test_stream',
            type='Markers',
            channel_count=1,
            nominal_srate=pylsl.IRREGULAR_RATE,
            channel_format=pylsl.cf_string,
            source_id='test_verification'
        )
        
        outlet = pylsl.StreamOutlet(info)
        print("✅ LSL outlet creation successful")
        
        # Test sending a sample
        outlet.push_sample(['test_message'])
        print("✅ LSL sample transmission successful")
        
        del outlet
        return True
        
    except ImportError:
        print("❌ pylsl not available - LSL functionality will not work")
        return False
    except Exception as e:
        print(f"⚠️  LSL functionality test failed: {e}")
        return False

def check_file_permissions():
    """Check file system permissions"""
    print("\nChecking file system permissions...")
    
    try:
        # Check if we can create files in the current directory
        test_file = Path("test_permissions.tmp")
        test_file.write_text("test")
        test_file.unlink()
        print("✅ File creation permissions OK")
        
        # Check if default output directory can be created
        from whisper_timestamped.pho_launch_live_transcription import _default_xdf_folder
        _default_xdf_folder.mkdir(parents=True, exist_ok=True)
        print(f"✅ Default output directory accessible: {_default_xdf_folder}")
        
        return True
        
    except Exception as e:
        print(f"❌ File system permission error: {e}")
        return False

def main():
    """Run all verification checks"""
    print("LiveWhisperLoggerApp Setup Verification")
    print("=" * 50)
    
    checks = [
        ("Python Version", check_python_version),
        ("Required Packages", check_required_imports),
        ("Whisper Models", check_whisper_models),
        ("Audio Devices", check_audio_devices),
        ("LSL Functionality", check_lsl_functionality),
        ("File Permissions", check_file_permissions),
    ]
    
    results = {}
    
    for check_name, check_func in checks:
        try:
            results[check_name] = check_func()
        except Exception as e:
            print(f"❌ {check_name} check failed with error: {e}")
            results[check_name] = False
    
    print("\n" + "=" * 50)
    print("VERIFICATION SUMMARY")
    print("=" * 50)
    
    all_critical_passed = True
    critical_checks = ["Python Version", "Required Packages", "LSL Functionality", "File Permissions"]
    
    for check_name, passed in results.items():
        status = "✅ PASS" if passed else "❌ FAIL"
        criticality = "CRITICAL" if check_name in critical_checks else "OPTIONAL"
        print(f"{status} {check_name:20} ({criticality})")
        
        if check_name in critical_checks and not passed:
            all_critical_passed = False
    
    print("\n" + "=" * 50)
    
    if all_critical_passed:
        print("🎉 SETUP VERIFICATION SUCCESSFUL!")
        print("The LiveWhisperLoggerApp should work with basic functionality.")
        
        optional_features = ["Whisper Models", "Audio Devices"]
        optional_passed = sum(results.get(check, False) for check in optional_features)
        
        if optional_passed == len(optional_features):
            print("🚀 All optional features are also available!")
        else:
            print(f"⚠️  {len(optional_features) - optional_passed} optional features are not available.")
            print("   The app will work but some features may be limited.")
    else:
        print("❌ SETUP VERIFICATION FAILED!")
        print("Critical dependencies are missing. Please install required packages.")
        print("\nTo install missing packages, try:")
        print("pip install -e .")
        print("or")
        print("pip install -e \".[live,full]\"")
    
    return all_critical_passed

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)