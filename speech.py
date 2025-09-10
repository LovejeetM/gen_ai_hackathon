from pick import pick

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
        print(f"You selected: {selected_name}")
        print(f"The language code is: '{selected_code}'")
        print("-" * 50)
        return selected_name, selected_code
    
    return None, None


if __name__ == "__main__":
    # Run the selection function
    name, code = select_language()

    # You can now use the 'code' variable in your speech recognition function
    if code:
        print(f"\nReady to use '{code}' with speech_recognition.recognize_google(audio, language='{code}')")