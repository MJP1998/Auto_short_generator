import os
import queue
from collections import defaultdict

import numpy as np
from moviepy.editor import AudioFileClip
from moviepy.editor import CompositeVideoClip
from moviepy.video.fx import all as vfx
from moviepy.editor import VideoFileClip
from PIL import Image, ImageDraw, ImageFont

from moviepy.video.VideoClip import TextClip, ColorClip, ImageClip

from src.media import Media
from src.utils import Config, Audio  # Import the Config class from utils module
import pyfoal
import re


def create_emoji_image_clip(emoji, font_size):
    # Create an image with transparent background
    image = Image.new("RGBA", (font_size, font_size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)

    # Set the font and size
    try:
        font = ImageFont.truetype(os.path.abspath("resources/seguiemj.ttf"),
                                  font_size)  # Replace with the path to a TTF/OTF font file that supports emoji
    except IOError:
        print("Error while loading the font")
        font = ImageFont.truetype("arial.ttf", font_size)

    # Draw the emoji
    draw.text((0, 0), emoji, font=font, fill=(255, 255, 255, 255), embedded_color=True)

    # Create an ImageClip
    emoji_clip = ImageClip(np.array(image))  # 5 seconds duration, adjust as needed

    return emoji_clip


def extract_and_remove_emojis(text):
    emoji_pattern = re.compile(r'[^\x00-\x7F]+', flags=re.UNICODE)

    # Find all emojis and their positions
    emojis_positions = [(m.start(0), m.group(0)) for m in re.finditer(emoji_pattern, text)]
    emojis_positions.sort()

    # Remove all emojis from the original text
    text_without_emojis = re.sub(emoji_pattern, '', text)

    return text_without_emojis, emojis_positions


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


def match_aligned_words_to_text(filtered_aligned_words, original_text, extracted_emojis):
    # Initialize a dictionary to hold the resulting matched words
    word_aligned2text = defaultdict(queue.Queue)
    cleaned_text = re.sub(r"[’'\-_/\\%^$*&éù£¨;àç(_ç'è\"=)—]", "", original_text)
    mapping = create_index_mapping(cleaned_text, original_text)
    # Initialize the search start position to 0
    start_pos = 0
    offset_emojis = 0
    emoji_index = 0

    current_word = filtered_aligned_words[0]['alignedWord'].lower()
    for i in range(len(filtered_aligned_words) - 1):
        next_word = filtered_aligned_words[i + 1]['alignedWord'].lower()
        # Create a pattern that starts with the current word and captures all characters until the next word
        pattern = re.compile(r'{}(.*?)(?={})'.format(re.escape(current_word), re.escape(next_word)), re.DOTALL)

        # Search for the pattern in the original text starting from start_pos
        # Limited the range of the search in order not to find a word too far away in case of mismatch
        match = pattern.search(cleaned_text.lower()[start_pos: start_pos + 25])
        if match:
            # If a match is found, capture the full matched portion from the original text
            start, end = match.span()
            end += start_pos
            mapped_start, mapped_end = mapping[start_pos], mapping[end]
            # Check if an emoji is here

            matched_text = original_text[mapped_start:mapped_end]
            if emoji_index < len(extracted_emojis):
                pos, emoji = extracted_emojis[emoji_index]
                while mapped_start <= pos - offset_emojis <= mapped_end:
                    matched_text = matched_text[:pos - offset_emojis - mapped_start] + emoji + matched_text[
                                                                                               pos - offset_emojis - mapped_start:]
                    offset_emojis += len(emoji)
                    emoji_index += 1
                    if emoji_index >= len(extracted_emojis):
                        break
                    pos, emoji = extracted_emojis[emoji_index]
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
                                                 proportion1=1 - self.config.music_proportion,
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
            media_duration = (media_duration + updated_media_duration) / 2

        clips = []
        last_end = 0
        clip_start = 0
        for i, media_path in enumerate(media_files):
            media = Media(os.path.join(self.media_folder, media_path), media_duration,
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
            clips.append(media.clip.set_position(('center', 'center')))
        # Concatenate all the clips together
        final_clip = CompositeVideoClip(clips)
        # Resize the video
        final_clip = final_clip.resize(newsize=self.frame_size)
        audio_clip = audio_clip.set_duration(final_clip.duration)
        final_clip = final_clip.set_audio(audio_clip)
        # Overlay subtitles
        script_without_emojis, extracted_emojis = extract_and_remove_emojis(script)
        final_clip = self.overlay_subtitles(final_clip, get_alignement(script_without_emojis, audio_object), script,
                                            title, script_without_emojis, extracted_emojis)

        # Save the video
        video_file_path = os.path.join(self.video_dir, filename + ".mp4")
        final_clip.fps = self.fps
        final_clip.write_videofile(video_file_path, codec="libx264", preset="ultrafast", fps=10, bitrate="500k")

        return video_file_path

    def overlay_subtitles(self, final_clip, alignment, script, title, script_without_emojis, extracted_emojis):
        clips_with_subtitles = []
        current_group = []
        last_end_time = 0
        font_size = self.config.subtitle_font_size
        # adapt the font_size to the resolution
        font_size = int(font_size * final_clip.h / 1980)
        # adapt the font_size for the nb of words per line
        title_font_size = int(self.config.title_font_size * final_clip.h /
                              (1980 * self.config.title_nb_word_per_line))
        font_size = int(font_size / self.config.subtitle_nb_word_per_line)

        font = self.config.subtitle_font
        time_threshold = 0.3
        vertical_pos = final_clip.h * self.config.subtitle_pos
        horizontal_pos = final_clip.w // 2
        length_str = 0
        shadow_offset = int(5 * final_clip.h / 1980)

        def group_subtitles_by_lines(word_group: list[dict], max_words_per_line: int) -> list[list[dict]]:
            return [word_group[i:i + max_words_per_line] for i in range(0, len(word_group), max_words_per_line)]

        def create_clips_for_subtitle(subtitle_text, font_size, font, shadow_offset, start_time, end_time,
                                      current_vertical_pos, screen_width, vertical_line_space, proportion=0.8,
                                      color='white', include_background=False):

            # Split the subtitle text into words and emojis
            parts = list(filter(None, re.split(r'([^\x00-\x7F]+|\s+)', subtitle_text)))

            # Initialize variables
            max_line_width = int(screen_width * proportion)
            current_line_width = 0
            current_line_height = 0
            line_clips = []
            all_clips = []
            space_width = TextClip(" ", fontsize=font_size, color=color, font=font).w

            first_word_in_line = True

            for part in parts:
                if part.isspace():  # Skip pure whitespace
                    continue

                # Create the clip and get its dimensions
                if re.match(r'[^\x00-\x7F]+', part):  # For emojis
                    clip = create_emoji_image_clip(part, font_size)  # Replace with your emoji to ImageClip function
                else:
                    clip = TextClip(part, fontsize=font_size, color=color, font=font)

                clip_w, clip_h = clip.w, clip.h

                # Check if adding this word would exceed the max line width
                if current_line_width + clip_w + (0 if first_word_in_line else space_width) > max_line_width:

                    if include_background:
                        # Create and position background for this line
                        bg_clip = ColorClip(size=(current_line_width, current_line_height), color=self.config.background_title)
                        bg_clip = bg_clip.set_opacity(self.config.background_title_opacity)
                        bg_clip = bg_clip.set_duration(end_time - start_time)
                        bg_clip = bg_clip.set_start(start_time).set_end(end_time)
                        bg_clip = bg_clip.set_position(
                            (screen_width // 2 - current_line_width // 2, current_vertical_pos))
                        all_clips.append(bg_clip)

                    # Position the current line's clips and add to all_clips
                    line_start_pos = screen_width // 2 - current_line_width // 2
                    for lc, offset, txt in line_clips:
                        if isinstance(lc, TextClip):
                            lc = lc.set_position((line_start_pos + offset, current_vertical_pos))
                        else:
                            lc = lc.set_position((line_start_pos + offset, current_vertical_pos + lc.h // 3))

                        lc = lc.set_start(start_time).set_end(end_time)

                        # Add shadow if it's a text clip
                        if isinstance(lc, TextClip):
                            shadow_clip = TextClip(txt, fontsize=font_size, color='black',
                                                   font=font)
                            shadow_clip = shadow_clip.set_position((line_start_pos + offset + shadow_offset,
                                                                    current_vertical_pos + shadow_offset // 2))
                            shadow_clip = shadow_clip.set_start(start_time).set_end(end_time).fx(vfx.colorx, 0.7)
                            all_clips.append(shadow_clip)

                        all_clips.append(lc)

                    # Update vertical position for the next line
                    current_vertical_pos += current_line_height + vertical_line_space
                    # Reset current line variables
                    current_line_width = 0
                    current_line_height = 0
                    line_clips = []
                    first_word_in_line = True

                # Add the word to the current line
                if not first_word_in_line:
                    current_line_width += space_width  # Add space between words

                line_clips.append((clip, current_line_width, part))
                current_line_width += clip_w
                current_line_height = max(current_line_height, clip_h)
                first_word_in_line = False

            # Position and add the remaining clips in the last line
            line_start_pos = screen_width // 2 - current_line_width // 2
            if line_clips and include_background:
                # Create and position background for this line
                bg_clip = ColorClip(size=(current_line_width, current_line_height),
                                    color=self.config.background_title)
                bg_clip = bg_clip.set_opacity(self.config.background_title_opacity)
                bg_clip = bg_clip.set_duration(end_time - start_time)
                bg_clip = bg_clip.set_start(start_time).set_end(end_time)
                bg_clip = bg_clip.set_position(
                    (screen_width // 2 - current_line_width // 2, current_vertical_pos))
                all_clips.append(bg_clip)
            for lc, offset, txt in line_clips:
                if isinstance(lc, TextClip):
                    lc = lc.set_position((line_start_pos + offset, current_vertical_pos))
                else:
                    lc = lc.set_position((line_start_pos + offset, current_vertical_pos + lc.h // 3))
                lc = lc.set_start(start_time).set_end(end_time)
                # Add shadow if it's a text clip
                if isinstance(lc, TextClip):
                    shadow_clip = TextClip(txt, fontsize=font_size, color='black', font=font)
                    shadow_clip = shadow_clip.set_position((line_start_pos + offset + shadow_offset,
                                                            current_vertical_pos + shadow_offset // 2))
                    shadow_clip = shadow_clip.set_start(start_time).set_end(end_time).fx(vfx.colorx, 0.7)
                    all_clips.append(shadow_clip)

                all_clips.append(lc)

            return all_clips

        # handle title
        if self.config.show_title and title and not title.isspace():
            current_vertical_pos = vertical_pos
            if title and not title.isspace():
                subtitle_clips = create_clips_for_subtitle(title, title_font_size, font, shadow_offset, 0,
                                                           self.config.time_title,
                                                           current_vertical_pos,
                                                           screen_width=final_clip.w,
                                                           vertical_line_space=title_font_size//5,
                                                           color=self.config.color_title,
                                                           include_background=True)
                clips_with_subtitles.extend(subtitle_clips)

        if not script or script.isspace():
            final_clip = CompositeVideoClip([final_clip] + clips_with_subtitles)
            return final_clip

        filtered_words = [word for word in alignment['words'] if word['alignedWord'] != 'sp']
        aligned_word2text = match_aligned_words_to_text(filtered_words, script_without_emojis, extracted_emojis)

        def add_clips_from_group(group, clips_with_subtitles, end_time):
            start_time = current_group[0]['start']
            current_vertical_pos = vertical_pos
            if start_time < self.config.time_title and self.config.show_title:
                if abs(0.5 - self.config.subtitle_pos) < 0.1:
                    current_vertical_pos = 0.7 * final_clip.h
                else:
                    current_vertical_pos = final_clip.h - vertical_pos
            subtitle_group = [w for w in group if w['alignedWord'].lower() in aligned_word2text]
            if subtitle_group:
                subtitle_text = " ".join([aligned_word2text[w['alignedWord'].lower()].get() for w in subtitle_group
                                      if not aligned_word2text[w['alignedWord'].lower()].empty()])

                if subtitle_text and not subtitle_text.isspace():

                    subtitle_clips = create_clips_for_subtitle(subtitle_text, font_size, font,
                                                               shadow_offset, start_time, end_time,
                                                               current_vertical_pos,
                                                               screen_width=final_clip.w,
                                                               vertical_line_space=font_size // 5)
                    clips_with_subtitles.extend(subtitle_clips)

        for word in filtered_words:
            if (length_str + len(word['alignedWord']) > 5 * self.config.subtitle_nb_word) \
                    or (current_group and word['start'] - last_end_time > time_threshold):
                add_clips_from_group(current_group, clips_with_subtitles, word['start'])

                current_group = []
                length_str = 0

            current_group.append(word)
            length_str += len(word['alignedWord']) + 1
            last_end_time = word['end']
        if current_group:
            add_clips_from_group(current_group, clips_with_subtitles, final_clip.duration)
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
