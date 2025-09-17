# PRAGATI: Multilingual AI Voice Agent

PRAGATI is a multilingual, AI-powered voice assistant designed to make welfare payments and government schemes instantly verifiable and accessible for rural and semi-urban citizens. It reduces the economic and social burden of repeated bank trips by providing a simple, local, and verifiable way to check financial status, withdrawals, and scheme eligibility—all in the user’s native language.

####  Here is a video demo of the agent:

---



---

## The Inspiration

The idea for PRAGATI came from witnessing the real struggles in rural India—pensioners and daily-wage earners traveling 8–10 km, spending ₹40–₹80, and waiting hours in queues just to ask a single question: *“Has my money arrived?”*

This recurring effort can cost a family over ₹1,300 per month, not including lost wages, and affects over 134 million people who rely on Direct Benefit Transfer (DBT) subsidies. PRAGATI aims to restore dignity, save time, and eliminate this anxiety by offering a local, instant, and accessible verification system.

---

## Key Features

-   **Natural Voice Interaction:** Communicate in multiple Indian languages using your voice.

-   **Instant Financial Verification:** Check the status of DBT credits (NREGA, PM-Kisan, pensions) without visiting a bank.

-   **Resource-Efficient:** Built with lightweight, high-performance models, making it suitable for low-end kiosk hardware.

-   **Responsive & Modern GUI:** An intuitive and user-friendly interface built with CustomTkinter.

-   **Real-Time Audio Streaming:** High-quality, low-latency audio playback for a seamless conversational experience.

---

## System Architecture & Design

PRAGATI is engineered with a modular, event-driven architecture to ensure a responsive user experience, even while handling complex tasks like real-time audio processing and AI inference.

---

### High-Level Flow

1.  **Voice Input:** The user interaction begins within the **CustomTkinter** GUI. A press of the microphone button triggers the `sounddevice` library to start capturing audio from the system's default microphone into an in-memory buffer.
<h3>                </h3>

2.  **Speech-to-Text (STT):** Upon finishing, the captured audio buffer is saved as a temporary WAV file. This file is then processed by **Google's Speech Recognition** service, chosen for its high accuracy in transcribing various Indian languages and accents.
<h3>                </h3>

3.  **LLM Processing & State Management:** The transcribed text becomes the input for our core logic module (`custom.py`). Here, we use **LangChain** to orchestrate a sophisticated interaction with a large language model.
    -   First, an initial LLM call is made to parse the user's input and update a custom **Pydantic** model, `KnowledgeBase`. This model acts as the agent's structured memory, extracting and storing key entities like Aadhaar numbers. This stateful approach ensures context is maintained throughout the conversation.
    -   The updated state and the user's query are then formatted into a carefully engineered prompt. We have tested various models, primarily leveraging **Mixtral-8x22B-Instruct** via the **NVIDIA NIM API** for its powerful reasoning and multilingual capabilities.
    <h3>                </h3>

4.  **Real-Time Text-to-Speech (TTS):** The LLM's text response is immediately streamed to **Piper TTS**, a fast, local, and high-quality neural text-to-speech engine. We do not wait for the entire response to be generated.
<h3>                </h3>

5.  **Low-Latency Audio Playback:** Piper's output is not saved to a file. Instead, its raw audio `stdout` stream is captured in real-time. This stream is placed into a `queue`, which is then consumed by a `sounddevice` callback. Using **NumPy**, we convert the raw audio bytes into a format the audio hardware can play directly. This pipeline starts playback almost instantaneously, delivering an exceptionally low-latency, conversational experience.

---

### System Diagram

```
[User] -> Voice Input
   |
   V
[GUI (CustomTkinter)] --Mic Click--> [Audio Recorder (sounddevice)]
   |
   V
[Google STT API] -> Transcribed Text
   |
   V
[LLM Backend (LangChain + Pydantic State Manager)]
   |
   V
[NVIDIA NIM API (Mixtral Model)] -> LLM Text Response
   |
   V
[Piper TTS Engine] -> Real-time RAW Audio Stream
   |
   V
[Audio Buffer (queue + numpy)]
   |
   V
[Audio Playback (sounddevice)] -> Audible Voice Output
   |
   V
[User]  + [GUI Update]
```

---


## Technology Stack Deep Dive

### AI & Machine Learning

-   **NVIDIA NIM:** We utilize NVIDIA's Inference Microservices to access powerful, enterprise-grade LLMs like **Mixtral-8x22B-Instruct**. This provides a scalable and highly optimized endpoint for our AI agent, offloading the heavy computational work and ensuring fast response times.
<h3>                </h3>

-   **LangChain:** This framework is the backbone of our AI agent. It allows us to chain prompts, LLM calls, and our custom Pydantic output parsers into a coherent and stateful workflow. It simplifies the management of conversation history and the injection of dynamic context (like database lookups) into our prompts.
<h3>                </h3>

-   **Pydantic:** We define a custom class, `KnowledgeBase`, using Pydantic. This is a critical component of our design. Instead of relying on the LLM to remember details from the conversation, we use a separate, structured LLM call to parse the user's input and populate this Pydantic object. This ensures reliable extraction of critical information (like an Aadhaar number) and provides a clean, predictable state that guides the LLM's final response.
<h3>                </h3>

-   **Piper TTS:** For text-to-speech, we selected Piper for its exceptional performance. It runs locally, eliminating network latency, and uses efficient `.onnx` models to generate high-quality, natural-sounding speech very quickly. Its ability to output a raw audio stream is central to our low-latency playback architecture.
<h3>                </h3>

-   **Google Speech Recognition:** Chosen for its superior accuracy and broad language support, this service provides the crucial transcription bridge from the user's spoken words to text that our agent can process.

---

### Audio Processing & Playback

-   **`sounddevice`:** This library provides a direct, low-level Python binding to the PortAudio library, giving us precise control over audio input and output streams. We use it to capture microphone data and, more importantly, to play back the raw audio stream from Piper with minimal latency through its callback mechanism.
<h3>                </h3>

-   **`numpy`:** NumPy is indispensable for our real-time audio pipeline. The raw byte stream from Piper is converted into a NumPy array of integers (`int16`), which is the format required by the `sounddevice` output stream. This conversion is incredibly fast and memory-efficient.

---

### Graphical User Interface (GUI)

-   **`customtkinter`:** To provide a modern and professional user experience, we opted for CustomTkinter over the standard Tkinter library. It offers improved aesthetics, theming capabilities (like dark mode), and a richer set of widgets, allowing us to build a responsive and visually appealing interface that is far superior to a basic command-line tool.


---

## Core Engineering Explained

### Real-Time TTS Pipeline with Piper

Achieving low-latency audio playback was a primary engineering goal. Our solution avoids the common pitfall of generating an entire audio file before playing it.
<h3>                </h3>

1.  **Process Piping:** We initiate `piper.exe` as a subprocess. The LLM's text response is written directly to Piper's `stdin`.
<h3>                </h3>

2.  **Streaming Output:** Piper immediately begins processing the text and writes the resulting raw PCM audio data to its `stdout` stream.
<h3>                </h3>

3.  **Producer-Consumer Model:** A dedicated Python thread (the "producer") reads this `stdout` stream in small, manageable chunks (e.g., 1024 bytes) and puts them into a thread-safe `queue.Queue`.
<h3>                </h3>

4.  **Callback-Driven Playback:** The `sounddevice.OutputStream` is configured with a callback function (the "consumer"). This function is automatically called by the audio driver whenever it needs more data. The callback retrieves a chunk from the queue, converts it to a NumPy array, and feeds it directly to the audio hardware buffer.

This architecture ensures that playback begins milliseconds after the LLM starts generating its response, creating a fluid and natural conversational flow.

---

### Solving the GUI Responsiveness Challenge

A significant challenge in developing applications like this is that GUI toolkits like Tkinter are single-threaded and not thread-safe. Any long-running or blocking task (like an API call, file I/O, or audio processing) executed on the main thread will freeze the entire application.

We solved this using a robust multi-threading strategy:
-   **The Main Thread:** Is exclusively responsible for running the CustomTkinter event loop (`rootmain.mainloop()`). It handles all user interactions and UI rendering.
<h3>                </h3>

-   **Worker Threads:** All blocking operations are offloaded to background worker threads using Python's `threading` module. This includes:
    -   Recording and saving audio.
    -   Calling the Google STT and NVIDIA NIM APIs.
    -   Running the Piper TTS process and listening to its output.
    <h3>                </h3>

-   **Thread-Safe UI Updates:** When a worker thread completes a task and needs to update the GUI (e.g., to display the transcribed text or an agent's response), it cannot directly modify a widget. Instead, it uses the `rootmain.after(0, function, *args)` method. This schedules the `function` to be executed safely on the main thread during its next idle cycle, ensuring UI consistency and preventing race conditions.

This strict separation of concerns is critical for maintaining a smooth, responsive, and crash-free user experience.

---

## Supported Languages

The agent is currently optimized for interaction in the following languages:

-   **English**
-   **Hindi**
-   **Malayalam**
-   **Telugu**


---

## Installation

1.  **Clone the Repository:**
    ```bash
    git clone https://github.com/LovejeetM/gen_ai_hackathon
    cd gen_ai_hackathon
    ```

2.  **Create a Virtual Environment (Recommended) or you can skip to the next step:**
    ```bash
    python -m venv venv
    source venv/bin/activate  
    ```

3.  **Install Dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

4.  **Set Up Environment Variables:**
    This project requires an NVIDIA API Key for the LLM. Create a file named `.env` in the project's root directory and add your key:
    ```
    NVIDIA_API_KEY="       ----  API KEY HERE  -----             "
    ```

---

## Usage

Run the main application script from the project's root directory:

```bash
python voice.py
```

1.  The application will launch, presenting you with a language selection screen.
2.  Choose your preferred language.
3.  The chat interface will appear. Click the microphone icon to start speaking. Click it again when you are finished.
4.  The agent will process your request and respond with both voice and text in the chat window.

---

## License

This project is licensed under the MIT License. See the [LICENSE.txt](./LICENSE.txt) file for details.

---