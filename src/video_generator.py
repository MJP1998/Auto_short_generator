import os
import queue
from collections import defaultdict

from moviepy.editor import AudioFileClip
from moviepy.editor import CompositeVideoClip
from moviepy.video.fx import all as vfx
from moviepy.editor import VideoFileClip

from moviepy.video.VideoClip import TextClip, ColorClip

from src.media import Media
from src.utils import Config, Audio  # Import the Config class from utils module
import pyfoal
import re


def get_alignement(text, audio_object):
    return pyfoal.align(text, audio_object.get_audio_np_array(), audio_object.get_sample_rate()).json()


def create_index_mapping(cleaned_text, original_text):
    mapping = {}
    j = 0
    for i in range(len(cleaned_text)):
        while j < len(original_text) and original_text[j] != cleaned_text[i]:
            j += 1
        if j < len(original_text):
            mapping[i] = j
            j += 1
    return mapping


def match_aligned_words_to_text(filtered_aligned_words, original_text):
    # Initialize a dictionary to hold the resulting matched words
    word_aligned2text = defaultdict(queue.Queue)
    cleaned_text = re.sub(r"[’'\-_/\\%^$*&éù£¨;àç(_ç'è\"=)—]", "", original_text)
    mapping = create_index_mapping(cleaned_text, original_text)
    # Initialize the search start position to 0
    start_pos = 0
    current_word = filtered_aligned_words[0]['alignedWord'].lower()

    for i in range(len(filtered_aligned_words) - 1):
        next_word = filtered_aligned_words[i + 1]['alignedWord'].lower()
        # Create a pattern that starts with the current word and captures all characters until the next word
        pattern = re.compile(r'{}(.*?)(?={})'.format(re.escape(current_word), re.escape(next_word)), re.DOTALL)

        # Search for the pattern in the original text starting from start_pos
        match = pattern.search(cleaned_text.lower(), start_pos)
        if match:
            # If a match is found, capture the full matched portion from the original text
            start, end = match.span()
            matched_text = original_text[mapping[start_pos]:mapping[end]]
            word_aligned2text[current_word].put(matched_text)

            # Update start_pos for the next search
            start_pos = end


        current_word = next_word

    # Handling the last word separately to capture any trailing content
    last_word = next_word
    matched_text = original_text[start_pos:]
    word_aligned2text[last_word].put(matched_text.strip())

    return word_aligned2text


class VideoGeneration:
    def __init__(self, media_folder=None):
        self.config = Config()
        self.video_dir = self.config.video_dir
        self.frame_size = self.config.frame_size
        self.media_folder = media_folder if media_folder is not None else self.config.image_dir
        self.fps = self.config.fps

    def generate_video(self, audio_object, script, title, filename, music_object=None):
        # Get all files from the media folder
        all_files = os.listdir(self.media_folder)
        fade_duration = self.config.fade_duration
        media_files = sorted([f for f in all_files if f.lower().endswith(('.png', '.jpg', '.jpeg',
                                                                          '.mp4', '.avi', '.mov'))])
        video_files = [f for f in all_files if f.lower().endswith(('.mp4', '.avi', '.mov'))]
        image_files = [f for f in all_files if f.lower().endswith(('.png', '.jpg', '.jpeg'))]
        # Set the audio of the video clip
        video_audio = audio_object.overlay_audio(music_object,
                                                 proportion1=1-self.config.music_proportion,
                                                 proportion2=self.config.music_proportion)

        audio_clip = AudioFileClip(video_audio.file_path)
        # Calculate the duration each media should be displayed to match the audio length
        audio_duration = audio_clip.duration + (fade_duration * (len(media_files) - 1))  # Assuming audio is 44.1 kHz
        # Initial estimate
        total_media_count = len(media_files)
        media_duration = audio_duration / total_media_count
        video_path2video = {}
        for video_file in video_files:
            video_path = os.path.join(self.media_folder, video_file)
            video_clip = VideoFileClip(video_path)
            video_path2video[video_file] = video_clip

        while True:
            total_video_duration = 0
            video_with_more_time = 0
            for video in video_path2video.values():
                total_video_duration += min(media_duration, video.duration)
                if media_duration <= video.duration:
                    video_with_more_time += 1
            try:
                updated_media_duration = (
                    (audio_duration - total_video_duration) / len(image_files) if len(image_files) > 0
                    else (audio_duration - total_video_duration
                          + video_with_more_time * media_duration)
                         / video_with_more_time)
            except:
                print("Not enough content to cover the full video")
                break

            if abs(media_duration - updated_media_duration) < 0.01:  # Convergence criteria
                break

            media_duration = updated_media_duration

        clips = []
        last_end = 0
        clip_start = 0
        for i, media_path in enumerate(media_files):
            media = Media(media_path, media_duration,
                          video_path2video[media_path] if media_path in video_path2video else None)
            media.set_duration(media_duration)
            if i != len(media_files) - 1:
                # Make the first clip fade out
                media.add_transition("crossfadeout", fade_duration)
            if i > 0:
                clip_start = last_end - fade_duration
                # Make the second clip fade in
                media.add_transition("crossfadein", fade_duration)
            # Shift the second clip's start time back by `fade_duration` to make it
            # start fading in before the first clip ends
            media.set_start(clip_start)
            last_end = clip_start + media.get_duration()
            clips.append(media.clip)
        # Concatenate all the clips together
        final_clip = CompositeVideoClip(clips)
        # Resize the video
        final_clip = final_clip.resize(newsize=self.frame_size)
        audio_clip = audio_clip.set_duration(final_clip.duration)
        final_clip = final_clip.set_audio(audio_clip)
        # Overlay subtitles
        final_clip = self.overlay_subtitles(final_clip, get_alignement(script, audio_object), script, title)

        # Save the video
        video_file_path = os.path.join(self.video_dir, filename + ".mp4")
        final_clip.fps = self.fps
        final_clip.write_videofile(video_file_path, codec="libx264", preset="ultrafast", fps=10, bitrate="500k")

        return video_file_path

    def overlay_subtitles(self, final_clip, alignment, script, title):
        clips_with_subtitles = []
        current_group = []
        last_end_time = 0
        first_start_time = 0
        font_size = self.config.subtitle_font_size
        # adapt the font_size to the resolution
        font_size = int(font_size * final_clip.h / 1980)
        # adapt the font_size for the nb of words per line
        title_font_size = int(font_size*1.2/self.config.title_nb_word_per_line)
        font_size = int(font_size / self.config.subtitle_nb_word_per_line)

        font = self.config.subtitle_font
        time_threshold = 0.3
        vertical_pos = final_clip.h * self.config.subtitle_pos
        horizontal_pos = final_clip.w // 2
        length_str = 0
        line_height_offset = font_size * 1.3
        shadow_offset = int(5 * final_clip.h / 1980)

        def group_subtitles_by_lines(word_group: list[dict], max_words_per_line: int) -> list[list[dict]]:
            return [word_group[i:i + max_words_per_line] for i in range(0, len(word_group), max_words_per_line)]

        # handle title
        if self.config.show_title:
            current_vertical_pos = vertical_pos
            title_lines = group_subtitles_by_lines(title.split(" "), self.config.title_nb_word_per_line)
            for line in title_lines:
                title_text = " ".join(line)
                title_clip = TextClip(title_text, fontsize=title_font_size, color=self.config.color_title, font=font)
                title_clip = title_clip.set_position(
                    (horizontal_pos - title_clip.w // 2, current_vertical_pos - title_clip.h // 2))
                # Shadow text
                shadow_clip = TextClip(title_text, fontsize=title_font_size, color='black', font=font)
                shadow_clip.get_frame(0)

                shadow_clip = shadow_clip.set_position((horizontal_pos - title_clip.w // 2 + shadow_offset,
                                                        current_vertical_pos + shadow_offset - title_clip.h // 2))
                shadow_clip = shadow_clip.fx(vfx.colorx, 0.7)

                title_clip = title_clip.set_start(0).set_end(self.config.time_title)
                shadow_clip = shadow_clip.set_start(0).set_end(self.config.time_title)

                # Create a black background with the same size as subtitle_clip
                bg_clip = ColorClip(size=title_clip.size, color=self.config.background_title)

                # Set the opacity of the background to 0.4
                bg_clip = bg_clip.set_opacity(max(0., min(1., float(self.config.background_title_opacity))))

                # Set the duration and start/end time of the background to match subtitle_clip
                bg_clip = bg_clip.set_duration(title_clip.duration)
                bg_clip = bg_clip.set_start(0).set_end(self.config.time_title)

                # Position the background
                bg_clip = bg_clip.set_position((horizontal_pos - title_clip.w // 2,
                                                current_vertical_pos - title_clip.h // 2))

                clips_with_subtitles.extend([bg_clip, shadow_clip, title_clip])
                current_vertical_pos += line_height_offset

        filtered_words = [word for word in alignment['words'] if word['alignedWord'] != 'sp']
        aligned_word2text = match_aligned_words_to_text(filtered_words, script)
        for word in filtered_words:
            if (length_str + len(word['alignedWord']) > 5 * self.config.subtitle_nb_word) \
                    or (current_group and word['start'] - last_end_time > time_threshold):

                lines = group_subtitles_by_lines(current_group, self.config.subtitle_nb_word_per_line)
                start_time = current_group[0]['start']
                current_vertical_pos = vertical_pos
                if start_time < self.config.time_title and self.config.show_title:
                    if abs(0.5 - self.config.subtitle_pos) < 0.1:
                        current_vertical_pos = 0.7 * final_clip.h
                    else:
                        current_vertical_pos = final_clip.g - vertical_pos

                end_time = word['start']
                for line in lines:
                    line = [w for w in line if w['alignedWord'].lower() in aligned_word2text]
                    if not line:
                        continue
                    subtitle_text = " ".join([aligned_word2text[w['alignedWord'].lower()].get() for w in line
                                              if not aligned_word2text[w['alignedWord'].lower()].empty()])
                    if subtitle_text.isspace() or not subtitle_text:
                        continue

                    subtitle_clip = TextClip(subtitle_text, fontsize=font_size, color='white', font=font)
                    subtitle_clip = subtitle_clip.set_position(
                        (horizontal_pos - subtitle_clip.w // 2, current_vertical_pos - subtitle_clip.h // 2))
                    # Shadow text
                    shadow_clip = TextClip(subtitle_text, fontsize=font_size, color='black', font=font)
                    shadow_clip.get_frame(0)

                    shadow_clip = shadow_clip.set_position((horizontal_pos - subtitle_clip.w // 2 + shadow_offset,
                                                            current_vertical_pos + shadow_offset - subtitle_clip.h // 2))
                    shadow_clip = shadow_clip.fx(vfx.colorx, 0.7)

                    subtitle_clip = subtitle_clip.set_start(start_time).set_end(end_time)
                    shadow_clip = shadow_clip.set_start(start_time).set_end(end_time)
                    clips_with_subtitles.extend([shadow_clip, subtitle_clip])
                    current_vertical_pos += line_height_offset

                current_group = []
                length_str = 0

            current_group.append(word)
            length_str += len(word['alignedWord']) + 1
            last_end_time = word['end']
        if current_group:
            lines = group_subtitles_by_lines(current_group, self.config.subtitle_nb_word_per_line)
            current_vertical_pos = vertical_pos
            start_time = current_group[0]['start']
            end_time = final_clip.duration

            for line in lines:
                line = [w for w in line if w['alignedWord'].lower() in aligned_word2text]
                if not line:
                    continue
                subtitle_text = " ".join([aligned_word2text[w['alignedWord'].lower()].get() for w in line
                                          if not aligned_word2text[w['alignedWord'].lower()].empty()])
                if subtitle_text.isspace() or not subtitle_text:
                    continue
                subtitle_clip = TextClip(subtitle_text, fontsize=font_size, color='white', font=font)
                subtitle_clip = subtitle_clip.set_position(
                    (horizontal_pos - subtitle_clip.w // 2, current_vertical_pos - subtitle_clip.h // 2))
                # Shadow text
                shadow_clip = TextClip(subtitle_text, fontsize=font_size, color='black', font=font)
                shadow_clip.get_frame(0)

                shadow_clip = shadow_clip.set_position((horizontal_pos - subtitle_clip.w // 2 + shadow_offset,
                                                        current_vertical_pos + shadow_offset - subtitle_clip.h // 2))
                shadow_clip = shadow_clip.fx(vfx.colorx, 0.7)

                subtitle_clip = subtitle_clip.set_start(start_time).set_end(end_time)
                shadow_clip = shadow_clip.set_start(start_time).set_end(end_time)

                clips_with_subtitles.extend([shadow_clip, subtitle_clip])
                current_vertical_pos += line_height_offset
        final_clip = CompositeVideoClip([final_clip] + clips_with_subtitles)
        return final_clip


if __name__ == "__main__":
    # Example image paths (you should provide actual paths to images in your resources folder)
    image_paths = ["resources/images/test_1.jpg", "resources/images/test_2.jpg"]

    text = "Hello, this is a test script."
    # tts = TextToSpeech()
    # audio_object = tts.get_audio(text)
    # Example audio data and file path (you should provide actual audio data and path)
    audio_file_path = "./resources/audio_clips/test.mp3"  # Placeholder

    # Create an example Audio object
    audio_object = Audio(audio_file_path)
    # Generate video
    video_gen = VideoGeneration()
    video_file_path = video_gen.generate_video(audio_object, text, "generated_video")

    print(f"Generated video saved at {video_file_path}")
