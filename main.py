import os

from pydub import AudioSegment

from src.csv_reader import CSVReader
from src.text_to_speech import TextToSpeech
from src.uploader import Uploader
from src.utils import Config, Audio
from src.video_generator import VideoGeneration


def main():
    # Read CSV
    config = Config()
    csv_name = "SkyColors"
    csv_reader = CSVReader(f"csv/{csv_name}.csv")
    tts = TextToSpeech()
    videos = csv_reader.get_video_entries()

    for video in videos:
        media_folder = config.image_dir
        if video.filename is None:
            media_folder += f"{csv_name}/"
        else:
            media_folder += video.filename
        video_generator = VideoGeneration(media_folder)

        # Generate audio from script
        audio_object = tts.get_audio(video.script) if not video.script.isspace() and video.script else Audio(audio_segment=AudioSegment.silent(duration=40000))
        music_file_path = os.path.join(config.music_dir, f"1.mp3")
        music_object = Audio(music_file_path)
        video_file_path = video_generator.generate_video(audio_object, video.script, video.title,
                                                         video.filename or csv_name, music_object)

        # (Optional) Upload video to a platform
        # uploader = Uploader(video)
        # schedule = True
        # schedule_day = "17"
        # schedule_time = "00:30"
        # # uploader.upload_to_youtube(schedule, schedule_day, schedule_time)
        # # uploader.upload_to_tiktok(schedule, schedule_day, schedule_time)
        # # uploader.upload_to_instagram(schedule, schedule_day, schedule_time)
        # uploader.upload_to_all(schedule, schedule_day, schedule_time)


if __name__ == "__main__":
    main()
