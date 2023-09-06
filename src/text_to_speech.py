import os
from hashlib import md5
from src.utils import Config, Audio  # Import the Config class from utils module
from elevenlabs import set_api_key, generate


class ElevenLabsAPI:
    def __init__(self):
        self.config = Config()
        self.api_key = self.config.elevenlabs_api_key
        set_api_key(self.api_key)

    def text_to_speech(self, script):
        try:
            audio = generate(
                text=script,
                voice=self.config.elevenlabs_voice,
                model=self.config.elevenlabs_model
            )
            return audio
        except Exception as e:
            print(f"An error occurred while calling the ElevenLabs API: {e}")
            return None


class TextToSpeech:
    def __init__(self):
        self.api = ElevenLabsAPI()  # Instantiate the API class
        config = Config()
        self.audio_dir = config.audio_dir

    def get_audio(self, script):
        # Generate a hash of the script to use for the file name
        script_hash = md5(script.encode()).hexdigest()
        audio_file_path = os.path.join(self.audio_dir, f"{script_hash}.mp3")
        if os.path.isfile(audio_file_path):
            return Audio(audio_file_path)

        # Make an API call to get the audio data
        audio_data = self.api.text_to_speech(script)  # Using ElevenLabsAPI class

        # Save the audio data to a file
        with open(audio_file_path, 'wb') as f:
            f.write(audio_data)

        # Create and return an Audio object
        return Audio(audio_file_path, audio_data)


if __name__ == "__main__":
    tts = TextToSpeech()
    script_sample = "Hello, this is a test script."
    audio_object = tts.get_audio(script_sample)

    print(f"Audio data: {audio_object.data}")
    print(f"Audio file path: {audio_object.file_path}")
