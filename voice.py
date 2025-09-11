import sounddevice as sd
import numpy as np 
import speech_recognition
from pick import pick
import wave
import time
import threading
import os
import queue
import sys
import re
import subprocess
import tkinter as tk
# from dotenv import load_dotenv


# load_dotenv()
# key = os.environ.get('API_KEY')

OUTPUT_FILENAME = "test_sd.wav"
SAMPLE_RATE = 44100
CHANNELS = 1 
DEVICE = None 
BLOCK_DURATION_MS = 50 


sr = speech_recognition.Recognizer()
output_path = os.path.join(".", OUTPUT_FILENAME)
audio_queue = queue.Queue()
is_recording = False
recorded_frames = []
stream = None
writer_thread = None
stop_writer = threading.Event() 

TRANSPARENT_COLOR = '#abcdef'
lang_name = "English"
lang_code = "en-IN"


def select_language():
    languages = [
        ("English", 'en-IN'),
        ("Hindi", 'hi-IN'),
        ("Malayalam", 'ml-IN'),
        ("Telugu", 'te-IN'),
    ]

    title = "Select a language (use arrow keys and Enter): "
    
    options = [f"{name}" for name, code in languages]

    selected_option, index = pick(options, title, indicator='======>', default_index=0)

    if index is not None:
        selected_name, selected_code = languages[index]
        print("-" * 50)
        print(f"Selected Language: {selected_name}")
        print("-" * 50)
        print("\n"*2)
        return selected_name, selected_code
    
    return "English", 'en-IN'




def audio_callback(indata, frames, time, status):
    if status:
        print(status, file=sys.stderr)
    audio_queue.put(indata.copy())

def save_recording():
    global recorded_frames
    if not recorded_frames:
        print("No audio data recorded.")
        return

    print(f"Saving {len(recorded_frames)} frames to {output_path}...")
    wf = wave.open(output_path, 'wb')
    wf.setnchannels(CHANNELS)
    audio_data = np.concatenate(recorded_frames)
    audio_data_int16 = (audio_data * 32767).astype(np.int16)
    bytes_per_sample = audio_data_int16.dtype.itemsize
    wf.setsampwidth(bytes_per_sample)
    wf.setframerate(SAMPLE_RATE)
    wf.writeframes(audio_data_int16.tobytes())
    wf.close()
    print(f"Recording saved successfully to {output_path}")
    recorded_frames = [] 
    return OUTPUT_FILENAME


def process_audio_queue():
    global recorded_frames, is_recording
    while not stop_writer.is_set():
        try:
            data = audio_queue.get(timeout=0.1)
            if is_recording:
                recorded_frames.append(data)
        except queue.Empty:
            continue
        except Exception as e:
            
            time.sleep(0.1)


def start_recording_flag():
    global is_recording, recorded_frames
    if not is_recording:
        
        is_recording = True

def stop_recording_flag():
    global is_recording
    if is_recording:
        
        is_recording = False
        filea = save_recording()
        text1 = recognition(filea)
        # send text1 to model and get resp
        # process_text(text1) # --------------------------------------------------------------------
        out(text1)



def synthesize_speech_ffplay(text, model_filename):
    piper_executable = os.path.join(os.getcwd(), 'piper', 'piper.exe')
    model_path = os.path.join(os.getcwd(), 'piper', model_filename)
    
    if not os.path.exists(piper_executable):
        print(f"Error: Piper executable not found at {piper_executable}")
        return
    if not os.path.exists(model_path):
        print(f"Error: Piper model not found at {model_path}")
        return

    sample_rate = 22050
    channels = 1
    dtype = 'int16'
    bytes_per_sample = np.dtype(dtype).itemsize

    piper_command_list = [
        piper_executable,
        "-m", model_path,
        "--output-raw"
    ]

    audio_queue = queue.Queue(maxsize=200)
    piper_process = None
    stream = None
    reader_thread = None
    
    stop_event = threading.Event()
    playback_finished_event = threading.Event()
    
    internal_callback_buffer = bytearray()

    def piper_reader_thread_func(proc_stdout, audio_q, stop_evt):
        try:
            while not stop_evt.is_set():
                chunk = proc_stdout.read(1024 * bytes_per_sample * channels)
                if not chunk:
                    break
                audio_q.put(chunk)
        except Exception:
            pass 
        finally:
            audio_q.put(None)

    def sounddevice_callback(outdata, frames, time_info, status):
        nonlocal internal_callback_buffer
        if status:
            print(f"Sounddevice callback status: {status}", flush=True)
            

        requested_bytes = frames * bytes_per_sample * channels
        
        while len(internal_callback_buffer) < requested_bytes:
            try:
                chunk = audio_queue.get(block=True, timeout=0.05) 
                if chunk is None:
                    audio_queue.put(None) 
                    if len(internal_callback_buffer) > 0:
                        available_frames = len(internal_callback_buffer) // (bytes_per_sample * channels)
                        actual_frames_to_copy = min(frames, available_frames)
                        
                        data_to_play = np.frombuffer(internal_callback_buffer[:actual_frames_to_copy * bytes_per_sample * channels], dtype=dtype).reshape(-1, channels)
                        outdata[:actual_frames_to_copy] = data_to_play
                        
                        if actual_frames_to_copy < frames:
                            outdata[actual_frames_to_copy:] = 0 
                        internal_callback_buffer = internal_callback_buffer[actual_frames_to_copy * bytes_per_sample * channels:]
                    else:
                        outdata[:] = 0
                    raise sd.CallbackStop("End of audio stream signaled.")
                internal_callback_buffer.extend(chunk)
                audio_queue.task_done()
            except queue.Empty:
                if piper_process.poll() is not None and audio_queue.empty() and not any(item is not None for item in list(audio_queue.queue)):
                    if len(internal_callback_buffer) > 0: 
                        available_frames = len(internal_callback_buffer) // (bytes_per_sample * channels)
                        actual_frames_to_copy = min(frames, available_frames)
                        data_to_play = np.frombuffer(internal_callback_buffer[:actual_frames_to_copy * bytes_per_sample * channels], dtype=dtype).reshape(-1, channels)
                        outdata[:actual_frames_to_copy] = data_to_play
                        if actual_frames_to_copy < frames:
                            outdata[actual_frames_to_copy:] = 0
                        internal_callback_buffer = internal_callback_buffer[actual_frames_to_copy * bytes_per_sample * channels:]
                    else:
                        outdata[:] = 0
                    raise sd.CallbackStop("Piper process ended and queue depleted.")
                outdata[:] = 0 
                return

        if len(internal_callback_buffer) >= requested_bytes:
            data_chunk_bytes = internal_callback_buffer[:requested_bytes]
            internal_callback_buffer = internal_callback_buffer[requested_bytes:]
            
            data_np = np.frombuffer(data_chunk_bytes, dtype=dtype).reshape(frames, channels)
            outdata[:] = data_np
        else:
            outdata[:] = 0


    try:
        print(f"Preparing to run Piper: {' '.join(piper_command_list)}")
        piper_process = subprocess.Popen(
            piper_command_list,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            bufsize=0 
        )

        reader_thread = threading.Thread(target=piper_reader_thread_func, args=(piper_process.stdout, audio_queue, stop_event))
        reader_thread.daemon = True 
        reader_thread.start()

        if piper_process.stdin:
            piper_process.stdin.write(text.encode('utf-8'))
            piper_process.stdin.close()

        time.sleep(0.15) # Time for the Piper to start (adjust) and fill initial queue buffer

        stream = sd.OutputStream(
            samplerate=sample_rate,
            channels=channels,
            dtype=dtype,
            callback=sounddevice_callback,
            finished_callback=playback_finished_event.set
        )
        
        print(f"Starting audio stream...")
        with stream:
            playback_finished_event.wait()

        print("Audio stream finished.")
        
        piper_stderr_bytes = piper_process.stderr.read()
        piper_return_code = piper_process.wait() 

        if piper_return_code != 0:
            print(f"Piper process error (Return Code: {piper_return_code}).")
            if piper_stderr_bytes:
                print("--- Piper Stderr ---")
                print(piper_stderr_bytes.decode('utf-8', errors='ignore').strip())
                print("--------------------")

    except sd.CallbackStop:
        print("Playback stopped by callback.")
    except FileNotFoundError:
         print(f"Error: Cannot find piper. Check path.")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        import traceback
        traceback.print_exc()
    finally:
        stop_event.set() 

        if reader_thread and reader_thread.is_alive():
            reader_thread.join(timeout=1)

        if piper_process:
            if piper_process.stdin and not piper_process.stdin.closed:
                try: piper_process.stdin.close()
                except BrokenPipeError: pass
            if piper_process.stdout and not piper_process.stdout.closed:
                piper_process.stdout.close()
            if piper_process.stderr and not piper_process.stderr.closed:
                remaining_stderr = piper_process.stderr.read() 
                if remaining_stderr:
                     print("--- Piper Stderr (at finally) ---")
                     print(remaining_stderr.decode('utf-8', errors='ignore').strip())
                     print("-------------------------")
                piper_process.stderr.close()

            if piper_process.poll() is None: 
                piper_process.terminate()
                try:
                    piper_process.wait(timeout=0.5)
                except subprocess.TimeoutExpired:
                    piper_process.kill()
                    piper_process.wait(timeout=0.5)
        while not audio_queue.empty():
            try:
                audio_queue.get_nowait()
                audio_queue.task_done()
            except queue.Empty:
                break




def recognition(audiofile1):
    try: 
        with speech_recognition.AudioFile(audiofile1) as source:
            audio_data = sr.record(source)
        said_text = sr.recognize_google(audio_data, language=lang_code)
        print("You said:", said_text)
        return said_text
    except sr.UnknownValueError:
        print("Sorry, could not understand the audio.")
    except sr.RequestError:
        print("Error with the recognition service.")
    except sr.WaitTimeoutError:
        print("Listening timed out.")



def out(speechtext):
    sil= ",,,,,,"+speechtext
    lang_map = {
        'en-IN': "en_GB-northern_english_male-medium.onnx",
        'hi-IN': "hi_IN-pratham-medium.onnx",
        'ml-IN': "ml_IN-arjun-medium.onnx",
        'te-IN': "te_IN-maya-medium.onnx"
    }
    synthesize_speech_ffplay(sil, lang_map[lang_code])




# tk Main ==============================================================================================
def makeroot():
    global rootmain, is_button_active_global
    rootmain = tk.Tk()
    is_button_active_global = False

    rootmain.overrideredirect(True)
    rootmain.attributes('-topmost', True)

    widget_width = 70
    widget_height = 70
    screen_width = rootmain.winfo_screenwidth()

    x_pos = screen_width - widget_width - 20
    y_pos = 20
    rootmain.geometry(f"{widget_width}x{widget_height}+{x_pos}+{y_pos}")

    rootmain.configure(bg='#202124')

    rootmain._drag_start_x = 0
    rootmain._drag_start_y = 0
    rootmain._window_start_x = 0
    rootmain._window_start_y = 0

    rootmain.bind("<ButtonPress-1>", on_widget_press)
    rootmain.bind("<B1-Motion>", on_widget_drag)

    rootmain.record_button = tk.Button(
        rootmain,
        text="REC",
        command=toggle_recording,
        font=("Franklin Gothic", 12, "bold"),
        relief=tk.RAISED,
        bg="#1a73e8",
        activebackground="#1a73e8"
    )
    rootmain.record_button.pack(expand=True, fill=tk.BOTH, padx=14, pady=14)

    rootmain.mainloop()


def on_widget_press(event):
    global rootmain
    rootmain._drag_start_x = event.x_root
    rootmain._drag_start_y = event.y_root
    rootmain._window_start_x = rootmain.winfo_x()
    rootmain._window_start_y = rootmain.winfo_y()

def on_widget_drag(event):
    global rootmain
    delta_x = event.x_root - rootmain._drag_start_x
    delta_y = event.y_root - rootmain._drag_start_y
    new_x = rootmain._window_start_x + delta_x
    new_y = rootmain._window_start_y + delta_y
    rootmain.geometry(f"+{new_x}+{new_y}")

def toggle_recording():
    global is_button_active_global, rootmain
    if not is_button_active_global:
        start_recording_flag()
        rootmain.record_button.config(
            text="STOP",
            relief=tk.SUNKEN,
            bg="#155cba",
            activebackground="#155cba"
        )
        is_button_active_global = True
    else:
        rootmain.record_button.config(
            text="REC",
            relief=tk.RAISED,
            bg="#1a73e8",
            activebackground="#1a73e8"
        )
        is_button_active_global = False
        rootmain.after(5, stop_recording_flag)
# tk Main ==============================================================================================


# MAIN &&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&
if __name__ == "__main__":
    lang_name, lang_code = select_language()
    while True:
        try:
            blocksize = int(SAMPLE_RATE * BLOCK_DURATION_MS / 1000)
            stream = sd.InputStream(
                samplerate=SAMPLE_RATE,
                device=DEVICE,
                channels=CHANNELS,
                callback=audio_callback,
                blocksize=blocksize,
                dtype='float32' 
            )
            stream.start()
            print(f"Audio stream started with blocksize {blocksize}...")

            stop_writer.clear()
            writer_thread = threading.Thread(target=process_audio_queue, daemon=True)
            writer_thread.start()
            print("Audio processing thread started.")
            makeroot()
                
        except Exception as e:
            print(f"\nAn error occurred: {e}")

        finally:
            print("\nExiting...")
            if stream is not None:
                print("Stopping audio stream...")
                stream.stop()
                stream.close()
                print("Audio stream closed.")

            if writer_thread is not None:
                    print("Stopping writer thread...")
                    stop_writer.set()
                    writer_thread.join(timeout=1.0)
                    if writer_thread.is_alive():
                        print("Writer thread did not stop gracefully.")
                    else:
                        print("Writer thread stopped.")

            if is_recording:
                    print("Saving recording that was in progress...")
                    is_recording = False
                    time.sleep(0.2)
                    save_recording()

