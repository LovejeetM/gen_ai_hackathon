import customtkinter
import threading
from custom import initial_greeting, chat_gen

chat_history = []
is_button_active_global = False

customtkinter.set_appearance_mode("dark")

def start_app():
    global root
    root = customtkinter.CTk()
    root.overrideredirect(True)
    root.attributes('-topmost', True)
    window_width = 960
    window_height = 540
    screen_width = root.winfo_screenwidth()
    screen_height = root.winfo_screenheight()
    x_pos = (screen_width // 2) - (window_width // 2)
    y_pos = (screen_height // 2) - (window_height // 2)
    root.geometry(f"{window_width}x{window_height}+{x_pos}+{y_pos}")
    root.configure(fg_color='#2c2f33')
    root._drag_start_x = 0
    root._drag_start_y = 0
    root._window_start_x = 0
    root._window_start_y = 0
    root.bind("<ButtonPress-1>", on_widget_press)
    root.bind("<B1-Motion>", on_widget_drag)
    show_language_selection()
    root.mainloop()

def on_widget_press(event):
    global root
    root._drag_start_x = event.x_root
    root._drag_start_y = event.y_root
    root._window_start_x = root.winfo_x()
    root._window_start_y = root.winfo_y()

def on_widget_drag(event):
    global root
    delta_x = event.x_root - root._drag_start_x
    delta_y = event.y_root - root._drag_start_y
    new_x = root._window_start_x + delta_x
    new_y = root._window_start_y + delta_y
    root.geometry(f"+{new_x}+{new_y}")

def show_language_selection():
    for widget in root.winfo_children():
        widget.destroy()
    languages = [("English", 'en-IN'), ("Hindi", 'hi-IN'), ("Malayalam", 'ml-IN'), ("Telugu", 'te-IN')]
    def select_language(lang_name, lang_code):
        global selected_language_name, selected_language_code, language_for_agent
        selected_language_name = lang_name
        selected_language_code = lang_code
        language_for_agent = {
            'en-IN': 'english',
            'hi-IN': 'hindi',
            'ml-IN': 'malayalam',
            'te-IN': 'telugu'
        }.get(lang_code, 'english')
        show_chat_interface()
    button_frame = customtkinter.CTkFrame(root, fg_color='transparent')
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
    global chat_display, record_button
    for widget in root.winfo_children():
        widget.destroy()
    greeting = initial_greeting(language_for_agent)
    chat_history.append([None, greeting])
    chat_display = customtkinter.CTkFrame(root, fg_color='#1e1f22', corner_radius=15)
    chat_display.pack(side='left', fill='both', expand=True, padx=10, pady=10)
    display_message(greeting, 'agent')
    record_button = customtkinter.CTkButton(
        root,
        text="REC",
        font=("Arial Rounded MT Bold", 24, "bold"),   #18
        fg_color='#1a73e8',
        hover_color='#155cba',
        command=toggle_recording,
        width=160, #120
        height=120,
        corner_radius=50   #60
    )
    record_button.pack(side='right', padx=(30, 30), pady=20)

def display_message(message, sender):
    msg_frame = customtkinter.CTkFrame(chat_display, fg_color='transparent', corner_radius=15)  # 15
    msg_frame.pack(anchor='w' if sender == 'agent' else 'e', fill='x', padx=20, pady=35)    #x10  y5
    color = '#4a90e2' if sender == 'agent' else '#2ecc71'
    msg_label = customtkinter.CTkLabel(
        msg_frame,
        text=message,
        font=("Arial", 20), #13
        fg_color=color,
        text_color='white',
        wraplength=350,  #350
        justify='left',
        corner_radius=22   #12
    )
    msg_label.pack(anchor='w' if sender == 'agent' else 'e', ipady=25, ipadx=25)  # x5 y5

def toggle_recording():
    global is_button_active_global
    if not is_button_active_global:
        is_button_active_global = True
        record_button.configure(text="STOP", fg_color='#155cba')
        threading.Thread(target=handle_audio_interaction, daemon=True).start()
    else:
        is_button_active_global = False
        record_button.configure(text="REC", fg_color='#1a73e8')

def handle_audio_interaction():
    global is_button_active_global
    import sounddevice as sd
    import numpy as np
    import wave
    from main import recognition, extract_aadhaar
    filename = "temp_audio.wav"
    duration = 5
    fs = 44100
    recording = sd.rec(int(duration * fs), samplerate=fs, channels=1, dtype='float32')
    sd.wait()
    wavefile = wave.open(filename, 'wb')
    wavefile.setnchannels(1)
    wavefile.setsampwidth(2)
    wavefile.setframerate(fs)
    wavefile.writeframes((recording * 32767).astype(np.int16).tobytes())
    wavefile.close()
    user_text = recognition(filename)
    if user_text:
        display_message(user_text, 'user')
        agent_response = ""
        agent_stream = chat_gen(user_text, language_for_agent, history=chat_history, return_buffer=False)
        for token in agent_stream:
            agent_response += token
        display_message(agent_response, 'agent')
        from main import out
        threading.Thread(target=out, args=([",,,,,,,," + agent_response]), daemon=True).start()
    is_button_active_global = False
    record_button.configure(text="REC", fg_color='#1a73e8')

start_app()