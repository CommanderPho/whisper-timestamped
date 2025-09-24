from RealtimeSTT import AudioToTextRecorder
import pyautogui
import pylsl


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

if __name__ == '__main__':
    
    wake_word_config = dict(wake_words="jarvis")
    always_listening_config = dict()

    active_config = always_listening_config    
    recorder = AudioToTextRecorder(**active_config, on_recording_start=start_callback, on_recording_stop=stop_callback,
                                   on_wakeword_detected=wakeword_detected_callback, on_wakeword_timeout=wakeword_timeout_callback,
                                                                    #   on_vad_detect_start=
                                                                      )
    print(f'will start listening soon!')
    # print('Say "Jarvis" then speak.')
    # print(recorder.text())
    # recorder = AudioToTextRecorder()

    while True:
        recorder.text(process_text)
        

