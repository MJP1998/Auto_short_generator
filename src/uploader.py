class Uploader:
    def __init__(self, video_entry):
        self.video_entry = video_entry

    def upload_to_youtube(self):
        title = self.video_entry.title
        description = self.video_entry.description
        file_path = self.video_entry.file_path
        # Insert code here to upload video to YouTube
        print(f"Uploading {title} to YouTube...")

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