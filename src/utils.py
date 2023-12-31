import os

from pydub import AudioSegment
import numpy as np
import wave

import json

def load_config():
    # Load public config
    with open("config/settings.json", "r") as f:
        config = json.load(f)

    # Load private config
    try:
        with open("config/settings_private.json", "r") as f:
            private_config = json.load(f)
        # Overwrite public settings with private ones
        config.update(private_config)
    except FileNotFoundError:
        print("Private config file not found. Using public config.")

    return config



class Config:
    def __init__(self):
        try:
            settings = load_config()
            self.elevenlabs_api_key = settings["api"]["eleven_labs"]["API_KEY"]
            self.elevenlabs_voice = settings["api"]["eleven_labs"]["voice"]
            self.elevenlabs_model = settings["api"]["eleven_labs"]["model"]

            self.youtube_id = settings["api"]["youtube"]["id"]
            self.youtube_secret_key = settings["api"]["youtube"]["secret_key"]

            self.frame_size = tuple(settings["video_settings"]["frame_size"])
            self.fps = settings["video_settings"]["fps"]
            self.music_proportion = settings["video_settings"]["music_proportion"]

            self.subtitle_pos = settings["video_settings"]["subtitle"]["y_pos"]
            self.subtitle_nb_word = settings["video_settings"]["subtitle"]["nb_word"]
            self.subtitle_nb_word_per_line = settings["video_settings"]["subtitle"]["nb_word_per_line"]
            self.subtitle_font = settings["video_settings"]["font"]
            self.subtitle_font_size = settings["video_settings"]["subtitle"]["font_size"]
            self.fade_duration = settings["video_settings"]["fade_duration"]

            self.show_title = settings["video_settings"]["title"]["show"]
            self.time_title = settings["video_settings"]["title"]["duration"]
            self.title_font_size = settings["video_settings"]["title"]["font_size"]
            self.background_title = tuple(map(int, settings["video_settings"]["title"]["background_color"].split(',')))
            self.background_title_opacity = settings["video_settings"]["title"]["background_opacity"]
            self.color_title = settings["video_settings"]["title"]["color"]
            self.title_nb_word_per_line = settings["video_settings"]["title"]["nb_word_per_line"]

            self.audio_dir = settings["directories"]["audio_dir"]
            self.image_dir = settings["directories"]["image_dir"]
            self.video_dir = settings["directories"]["video_dir"]
            self.music_dir = settings["directories"]["music_dir"]
            self.config_dir = settings["directories"]["config_dir"]

            self.user_data_dir = settings["selenium"]["user_data_dir"]
            self.user_profile_dir_tiktok = settings["selenium"]["user_profile_dir_tiktok"]
            self.user_profile_dir_fb = settings["selenium"]["user_profile_dir_fb"]
            self.user_profile_dir_youtube = settings["selenium"]["user_profile_dir_youtube"]
            self.fb_asset_id = settings["selenium"]["fb_asset_id"]
            self.fb_business_id = settings["selenium"]["fb_business_id"]
            self.youtube_channel_id = settings["selenium"]["youtube_channel_id"]

            self.aligned_dir = settings["directories"]["aligned_dir"]

            self.csv_path = settings["input_files"]["csv_path"]
            self.is_header_row = settings["input_files"]["is_header_row"]

            self.acoustic_model_path = settings["alignment_model"]["acoustic_model_path"]
            self.dict_model_path = settings["alignment_model"]["dict_model_path"]

        except FileNotFoundError:
            print(f"Configuration file not found.")
        except KeyError as e:
            print(f"Missing key in configuration file: {e}")
        except Exception as e:
            print(f"An error occurred while reading the configuration file: {e}")


def generate_save_path(audio1, audio2, extension="mp3"):
    """
    Generate a save path based on the filenames of two audio objects.

    :param audio1: The first Audio object
    :param audio2: The second Audio object
    :param extension: The file extension for the new audio file
    :return: A string representing the new save path
    """
    # Get the directory and filenames
    dir1, filename1_with_extension = os.path.split(audio1.file_path)
    dir2, filename2_with_extension = os.path.split(audio2.file_path)

    # Get the filenames without extensions
    filename1, _ = os.path.splitext(filename1_with_extension)
    filename2, _ = os.path.splitext(filename2_with_extension)

    # Generate the new filename and save path
    new_filename = f"{filename1}_{filename2}.{extension}"
    new_save_path = os.path.join(dir1, new_filename)

    return new_save_path


class Audio:
    def __init__(self, file_path=None, data=None, audio_segment=None):
        if audio_segment is None:
            audio_segment = AudioSegment.from_mp3(os.path.abspath(file_path))
        if data is None:
            data = audio_segment.raw_data

        if file_path is None:
            # Save the audio segment to the temporary file
            audio_folder = Config().audio_dir
            file_path = audio_folder + "temp.wav"

            audio_segment.export(file_path, format="wav")
        self.audio_segment = audio_segment
        self.data = data  # The binary audio data
        self.file_path = file_path  # The path to the audio file

    def get_audio_np_array(self):
        # Convert to single channel (mono)
        audio = self.audio_segment.set_channels(1)

        # Convert to numpy array
        return np.array(audio.get_array_of_samples())

    def get_sample_rate(self):
        return self.audio_segment.frame_rate

    def overlay_audio(self, other_audio, position_ms=0, proportion1=0.9, proportion2=0.1, save_audio=True):
        """
        Overlay another audio onto this audio.

        :param other_audio: Another Audio object to be overlaid
        :param position_ms: Position where the new audio will be overlaid on the original audio
        :param proportion1: Proportion of the first audio in the overlay
        :param proportion2: Proportion of the second audio in the overlay
        :return: A new Audio object containing the overlaid audio
        """
        if other_audio is None:
            return self
        # Make sure both audio segments have the same frame rate

        if self.get_sample_rate() != other_audio.get_sample_rate():
            other_audio.audio_segment.set_frame_rate(self.audio_segment.frame_rate)

            #raise ValueError("Both audio segments must have the same frame rate for overlay.")

        # Cut the second audio to the same length as the first
        other_audio_segment = other_audio.audio_segment[:len(self.audio_segment)]

        # Scale the audio segments based on the given proportions
        self_adjusted = self.audio_segment - (1 - proportion1) * 20
        other_adjusted = other_audio_segment - (1 - proportion2) * 20

        # Overlay the audio segments
        overlaid_audio_segment = self_adjusted.overlay(other_adjusted, position=position_ms)
        new_audio_path = generate_save_path(self, other_audio, extension="wav")

        if save_audio:
            overlaid_audio_segment.export(new_audio_path, format="wav")
        # Create a new Audio object for the overlaid audio
        overlaid_audio = Audio(new_audio_path, audio_segment=overlaid_audio_segment)

        return overlaid_audio


def save_wav(audio_bytes, filename, n_channels=1, sampwidth=2, framerate=44100):
    with wave.open(filename, 'wb') as wav_file:
        wav_file.setnchannels(n_channels)
        wav_file.setsampwidth(sampwidth)
        wav_file.setframerate(framerate)
        wav_file.writeframes(audio_bytes)
