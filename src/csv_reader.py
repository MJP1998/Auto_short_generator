import csv

from src.utils import Config


class VideoEntry:
    def __init__(self, script, title, hashtags, description):
        self.script = script
        self.title = title
        self.hashtags = hashtags
        self.description = description



class CSVReader:
    def __init__(self, csv_path=None):
        config = Config()  # Instantiate Config to get settings
        self.file_path = config.csv_path if csv_path is None else csv_path
        self.is_header_row = config.is_header_row
        self.video_entries = []
        self.read_csv()

    def read_csv(self):
        """
        Reads a CSV file and populates the video_entries attribute with VideoEntry objects.
        """
        try:
            with open(self.file_path, mode='r', encoding='utf-8') as file:
                csv_read = csv.reader(file)
                if self.is_header_row:
                    next(csv_read)  # Skip the header row

                for row in csv_read:
                    if len(row) != 4:
                        print(f"Skipping invalid row: {row}")
                        continue

                    script, video_title, hashtags, video_description = row
                    video_entry = VideoEntry(script, video_title, hashtags, video_description)
                    self.video_entries.append(video_entry)

        except FileNotFoundError:
            print(f"File {self.file_path} not found.")
        except Exception as e:
            print(f"An error occurred while reading the CSV file: {e}")

    def get_video_entries(self):
        return self.video_entries


if __name__ == '__main__':
    csv_reader = CSVReader()
    video_entries = csv_reader.get_video_entries()

    for entry in video_entries:
        print(f"Script: {entry.script}, Title: {entry.title}, Description: {entry.description}")
