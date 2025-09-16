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
from types import GeneratorType
# from dotenv import load_dotenv

from PIL import Image
import io
import base64

import customtkinter

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

chat_history = []
is_button_active_global = False

BACK_ARROW_B64 = b"iVBORw0KGgoAAAANSUhEUgAAADIAAAAyCAYAAAAeP4ixAAAACXBIWXMAAAsTAAALEwEAmpwYAAAB10lEQVR4nO3XPY9MURzA4bNIWLEKEhIaiUq8RLOFhsLLB0AkohGFaDQSoaRCoaCi2YR6s6g0KDReQr8KIgqFRCLeVpb1yM2eSS6ZmZ3NPTN3jtznA5x7f5m55/xPCI1Go9FoNBr/N2zGSzwMucIefBCFHOEkZlsR2YVgOSbKAdmFYAOetovIJgS78L5TRBYhOIbv3SKGOgRLcXmhgKEOwdribLA4nzCNx5jEBRzA6roituONdObwHKexZlARh/BF//zAbWzqV8AILuK3wZjBFYyljFiFKfV4hR2pQp6p1zccSRHS8bQeoF/FeVU1ZAx3hiTmcIqP/VzcKuv0FVsrxQxo++3FNFamOhBf1xxzqXJIhRElpdkkf7EYswzXFvHwUayL9/hxHMRZ3Ig74183yh5MJgkpBZ2Io0VXPawzGu/5V/Guh5A5bBvqi1XcJffi/gJj0c2kIfHhG7tNARXWHY/TcTufixEqbcn8Q1fgVsqQApbgPH62Wbr6+NIJzsSTOElIC/bFQ7FsIvQT9uNjypACdscxv6X4NkdCP8Wt9gUeJF73+D+/ys6QK9wthZwKucKW0hB7PeQM92LIo5AzHI0hb0POsD6GzITcmR9jntT9Ho1GI9TjD22H/Nq+o1wxAAAAAElFTkSuQmCC"

MIC_B64= b"iVBORw0KGgoAAAANSUhEUgAAADAAAAAwCAYAAABXAvmHAAAACXBIWXMAAAsTAAALEwEAmpwYAAACEElEQVR4nO2YP0scQRiHB3ORCBrbYE4tIiFGP0j+gN/CWFpai4WxUE9N/CAmnQmISRMsPSslFp5aaOOdiYXKIy8ZYXmZ5HZv59wxzAMHx87cb99nmX13b4yJRCJeAUaBClAFzu2nao+NmlABOoGPwDV/5wpYkbkmwOK/kp4vQUnw58pnZdkEtOZlaWRFfjMSgsASrbMQgsBODoHtEAQaOQTqIQjkwhRNFCiaKFA0UaBookDRBC9AkxP6FsC34P8g0FCZPWq8nqP+M5X12PvLHrCnQp+363UaeKHGd30IfFehr9X4Yg6BeZX1Vo1/8yEguwhJPqjxkRx/KV+qrFU1Z8mHwBsVegCUmkimoaIySkBNzXnlQ6AL+KWCxx3bKrJVkpZ14KHKmFBzZEOsK7eADZddtSSHjm4kEstNltOlzdLF9wLH/7o/8gr0ARfqBGtAh2Ou3BML0mFsC27Y7/N6zQuSAXxW2b+BJ8YnwIzjiq64JDJkdkhTcOROey0+cZPplip8kgdQC3mybPSVFzZ1k/Ap0Q8cOU4qx96lObG9EBOONX+bU25L8YkChoB93NRsL5fWOwx028+wfUitOlrlLT+BZ20tPiFRBrbwxw/g6Z0Ur5bCpO3XrXIBTAEP7rR4JTIIzAGnGQo/Ad4DAyYU7BN7DJgFNhxFb9gxmfPIhA4Kc98gChRMFCiaey8QMem4ATKfZRavGuKEAAAAAElFTkSuQmCC"


customtkinter.set_appearance_mode("dark")


# def select_language():
#     languages = [
#         ("English", 'en-IN'),
#         ("Hindi", 'hi-IN'),
#         ("Malayalam", 'ml-IN'),
#         ("Telugu", 'te-IN'),
#     ]

#     title = "Select a language (use arrow keys and Enter): "
    
#     options = [f"{name}" for name, code in languages]

#     selected_option, index = pick(options, title, indicator='======>', default_index=0)

#     if index is not None:
#         selected_name, selected_code = languages[index]
#         print("-" * 50)
#         print(f"Selected Language: {selected_name}")
#         print("-" * 50)
#         print("\n"*2)
#         return selected_name, selected_code
    
#     return "English", 'en-IN'


# language_for_agent = {
#     'en-IN': 'english',
#     'hi-IN': 'hindi',
#     'ml-IN': 'malayalam',
#     'te-IN': 'telugu'
# }.get(lang_code, 'english')


def get_agent_response(user_text):
    from custom import chat_gen  

    response = ""
    agent_stream = chat_gen(user_text, language_for_agent, history=chat_history, return_buffer=False)
    
    if isinstance(agent_stream, GeneratorType):
        for token in agent_stream:
            response += token
    else:
        response = agent_stream  
    
    chat_history.append([user_text, response])
    
    return response



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


def process_and_respond(user_text):
    """
    This function runs in a background thread.
    It gets the agent response and then plays the audio,
    ensuring the GUI does not freeze.
    """
    agent_response = ""
    agent_stream_generator = chat_gen(user_text, language_for_agent, history=chat_history, return_buffer=False)
    for token in agent_stream_generator:
        agent_response += token
    
    if agent_response:
        print("\n[ Agent Response ]:", agent_response)
        chat_history.append([user_text, agent_response])

        rootmain.after(0, lambda: display_message(agent_response, 'agent'))
        out(agent_response)

def stop_recording_flag():
    global is_recording
    if is_recording:
        
        is_recording = False
        filea = save_recording() 
        text1 = recognition(filea)
        if text1:
            display_message(text1, 'user')
            
            
            thread = threading.Thread(target=process_and_respond, args=(text1,), daemon=True)
            thread.start()


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
    except speech_recognition.UnknownValueError:
        print("Sorry, could not understand the audio.")
        return None
    except speech_recognition.RequestError:
        print("Error with the recognition service.")
        return None
    except speech_recognition.WaitTimeoutError:
        print("Listening timed out.")
        return None
    except Exception as e:
        print(f"Unexpected recognition error: {e}")
        return None



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
    global rootmain
    rootmain = customtkinter.CTk()
    rootmain.overrideredirect(True)
    rootmain.attributes('-topmost', True)
    window_width = 960
    window_height = 540
    screen_width = rootmain.winfo_screenwidth()
    screen_height = rootmain.winfo_screenheight()
    x_pos = (screen_width // 2) - (window_width // 2)
    y_pos = (screen_height // 2) - (window_height // 2)
    rootmain.geometry(f"{window_width}x{window_height}+{x_pos}+{y_pos}")
    rootmain.configure(bg='#2c2f33')
    rootmain._drag_start_x = 0
    rootmain._drag_start_y = 0
    rootmain._window_start_x = 0
    rootmain._window_start_y = 0
    rootmain.bind("<ButtonPress-1>", on_widget_press)
    rootmain.bind("<B1-Motion>", on_widget_drag)
    show_language_selection()
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



def show_language_selection():
    global lang_name, lang_code, rootmain, button_frame, btn
    for widget in rootmain.winfo_children():
        widget.destroy()
    languages = [("English", 'en-IN'), ("Hindi", 'hi-IN'), ("Malayalam", 'ml-IN'), ("Telugu", 'te-IN')]
    def select_language(l_name, l_code):
        global lang_name, lang_code, language_for_agent
        lang_name = l_name
        lang_code = l_code 
        # selected_name = lang_name
        # selected_code = lang_code
        language_for_agent = {
            'en-IN': 'english',
            'hi-IN': 'hindi',
            'ml-IN': 'malayalam',
            'te-IN': 'telugu'
        }.get(lang_code, 'english')
        print("selected: ", language_for_agent)
        # lang_name = selected_name
        # lang_code = selected_code 
        show_chat_interface()
    button_frame = customtkinter.CTkFrame(rootmain, fg_color='transparent')
    button_frame.place(relx=0.5, rely=0.5, anchor='center')
    for i, (name, code) in enumerate(languages):
        btn = customtkinter.CTkButton(
            button_frame, text=name,
            font=("Arial Rounded MT Bold", 28),  #22
            fg_color='#1a73e8',
            hover_color='#155cba',
            command=lambda n=name, c=code: select_language(n, c),
            corner_radius=25, #15
            width=280,  #180
            height=120,    #70

            #border:
            border_width=1,
            border_color="black"
        )
        btn.grid(row=i//2, column=i%2, padx=35, pady=35) #btn.grid(row=i//2, column=i%2, padx=15, pady=15)



def show_chat_interface():
    global chat_display, record_button, mic_icon, rootmain, back_button
    for widget in rootmain.winfo_children():
        widget.destroy()

    img_data = base64.b64decode(BACK_ARROW_B64)
    img = Image.open(io.BytesIO(img_data))
    back_icon = customtkinter.CTkImage(light_image=img, dark_image=img, size=(40, 40))
    back_button = customtkinter.CTkButton(
        rootmain,
        text="",
        image=back_icon,
        command=show_language_selection,
        width=50,
        height=60,
        corner_radius=20,
        fg_color="#AC3A38",
        hover_color="#942B29"
        # border_width=1,
        # border_color="black"
    )
    back_button.place(relx=1.0, x=-20, y=15, anchor="ne")
    
    img_data = base64.b64decode(MIC_B64)
    img = Image.open(io.BytesIO(img_data))
    mic_icon = customtkinter.CTkImage(light_image=img, dark_image=img, size=(60, 60))    ### BUTTON
    greeting = initial_greeting(language_for_agent)
    argsout = ",,,,,,,,,,,,"+greeting
    threading.Thread(target=out, args=(argsout,), daemon=True).start()
    chat_history.append([None, greeting])
    # Scrollable: 
    chat_display = customtkinter.CTkScrollableFrame(rootmain, fg_color='#1e1f22', corner_radius=15) #'#1e1f22'
    chat_display._scrollbar.grid_forget()

    chat_display.pack(side='left', fill='both', expand=True, padx=10, pady=10)


    # chat_display = customtkinter.CTkFrame(rootmain, fg_color='#1e1f22', corner_radius=15)
    # chat_display.pack(side='left', fill='both', expand=True, padx=10, pady=10)

    display_message(greeting, 'agent')
    record_button = customtkinter.CTkButton(
        rootmain,
        text="",  # REC
        image=mic_icon,
        font=("Arial Rounded MT Bold", 24, "bold"),   #18
        fg_color='#1a73e8',
        hover_color='#155cba',
        command=toggle_recording,
        width=100, #120
        height=120,
        corner_radius= 50   #60
    )
    record_button.pack(side='right', padx=(20, 20), pady=20)  #  pdx = 30, 30    pady = 20


def display_message(message, sender):
    global rootmain, chat_display
    msg_frame = customtkinter.CTkFrame(chat_display, fg_color='transparent', corner_radius=15)  # 15
    msg_frame.pack(anchor='w' if sender == 'agent' else 'e', fill='x', padx=20, pady=15)    #x10  y5
    color = '#4a90e2' if sender == 'agent' else '#2ecc71'
    msg_label = customtkinter.CTkLabel(
        msg_frame,
        text=message,
        font=("Arial", 20), #13
        fg_color=color,
        text_color='white',
        wraplength=500,  #350
        justify='left',
        corner_radius=22   #12      
    )
    msg_label.pack(anchor='w' if sender == 'agent' else 'e', ipady=25, ipadx=25)  # x5 y5
    rootmain.after(10, lambda: chat_display._parent_canvas.yview_moveto(1.0))




def toggle_recording():
    global is_button_active_global, rootmain, record_button
    if not is_button_active_global:
        start_recording_flag()
        record_button.configure(
            text="",  
            image=mic_icon,
            # relief=tk.SUNKEN,
            fg_color="#d62424",
            hover_color="#bb1919"
            # activebackground="#155cba"
        )
        is_button_active_global = True
    else:
        record_button.configure(
            text="",
            image=mic_icon,
            # relief=tk.RAISED,
            fg_color="#1a73e8",
            hover_color='#155cba'
            # activebackground="#1a73e8"
        )
        is_button_active_global = False
        rootmain.after(5, stop_recording_flag)
        # stop_recording_flag()
# tk Main ==============================================================================================


# MAIN &&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&
if __name__ == "__main__":
    # lang_name, lang_code = select_language()
    # language_for_agent = {
    #     'en-IN': 'english',
    #     'hi-IN': 'hindi',
    #     'ml-IN': 'malayalam',
    #     'te-IN': 'telugu'
    # }.get(lang_code, 'english')
    


    # import after selecting the language
    from custom import initial_greeting, chat_gen, get_key_fn, chat_llm, instruct_chat, instruct_llm

    
    # chat_history = [[None, initial_greeting(language_for_agent)]]
    # argsout = ",,,,,,,,,,,,"+chat_history[0][1]
    # threading.Thread(target=out, args=(argsout,), daemon=True).start()
    

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

