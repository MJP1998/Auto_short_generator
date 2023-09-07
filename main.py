import os

from src.csv_reader import CSVReader
from src.text_to_speech import TextToSpeech
from src.utils import Config, Audio
from src.video_generator import VideoGeneration


def main():
    # Read CSV
    config = Config()
    csv_name = "stuck"
    csv_reader = CSVReader(f"csv/{csv_name}.csv")
    tts = TextToSpeech()
    video_generator = VideoGeneration(config.image_dir + f"{csv_name}/")
    videos = csv_reader.get_video_entries()

    for video in videos:
        # Generate audio from script
        audio_object = tts.get_audio(video.script)
        music_file_path = os.path.join(config.music_dir, f"1.mp3")
        music_object = Audio(music_file_path)

        video_file_path = video_generator.generate_video(audio_object, video.script, video.title, csv_name, music_object)

        # (Optional) Upload video to a platform
        # upload_video(video_path)


if __name__ == "__main__":
    main()
