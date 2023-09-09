import json
import os

from src.csv_reader import CSVReader
from src.uploader_utils import upload_youtube_video
from src.utils import Config


class Uploader:
    def __init__(self, video_entry):
        self.video_entry = video_entry
        self.config = Config()
        self.file_path = os.path.join(self.config.video_dir, self.video_entry.filename + ".mp4")

    def upload_to_youtube(self):
        # File path
        file_path = self.config.config_dir + "client_secrets.json"

        # Check if the file exists
        if not os.path.exists(file_path):
            # Create the file with the required structure
            data = {
                "web": {
                    "client_id": self.config.youtube_id,
                    "client_secret": self.config.youtube_secret_key,
                    "redirect_uris": [],
                    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                    "token_uri": "https://accounts.google.com/o/oauth2/token"
                }
            }

            with open(file_path, "w") as f:
                json.dump(data, f, indent=4)

        title = self.video_entry.title
        description = self.video_entry.description
        hashtags = self.video_entry.hashtags
        description += "\n" + hashtags
        keywords = ','.join(list(filter(None, hashtags.split("#"))))
        video_file_path = self.file_path
        # Insert code here to upload video to YouTube
        upload_youtube_video(video_file_path, file_path, title, description, keywords=keywords)

    def upload_to_tiktok(self):
        title = self.video_entry.title
        description = self.video_entry.description
        file_path = self.video_entry.file_path
        # Insert code here to upload video to TikTok
        print(f"Uploading {title} to TikTok...")

    def upload_to_instagram(self):
        title = self.video_entry.title
        description = self.video_entry.description
        file_path = self.video_entry.file_path
        # Insert code here to upload video to Instagram
        print(f"Uploading {title} to Instagram...")

    def upload_to_all(self):
        self.upload_to_youtube()
        self.upload_to_tiktok()
        self.upload_to_instagram()


if __name__ == "__main__":
    csv_name = "dancingman"
    csv_reader = CSVReader(f"csv/{csv_name}.csv")
    videos = csv_reader.get_video_entries()
    video = videos[0]
    uploader = Uploader(video)
    uploader.upload_to_youtube()