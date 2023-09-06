import os
import queue
from collections import defaultdict

import cv2

from moviepy.editor import ImageSequenceClip, concatenate_videoclips, AudioFileClip
from moviepy.editor import CompositeVideoClip
from moviepy.video.fx import all as vfx
from moviepy.editor import VideoFileClip

from moviepy.video.VideoClip import TextClip

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
            matched_text = original_text[mapping[start]:mapping[end]]
            word_aligned2text[current_word].put(matched_text)

            # Update start_pos for the next search
            start_pos = end
        else:
            print(current_word, next_word, original_text[start_pos:])
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

    def generate_video(self, audio_object, script, title, music_object=None):
        # Get all files from the media folder
        all_files = os.listdir(self.media_folder)
        fade_duration = self.config.fade_duration
        media_files = sorted([f for f in all_files if f.lower().endswith(('.png', '.jpg', '.jpeg', '.mp4', '.avi',
                                                                          '.mov'))])
        video_files = [f for f in all_files if f.lower().endswith(('.mp4', '.avi', '.mov'))]
        image_files = [f for f in all_files if f.lower().endswith(('.png', '.jpg', '.jpeg'))]
        # Set the audio of the video clip
        video_audio = audio_object.overlay_audio(music_object, proportion1=0.9, proportion2=0.1)
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

        def shift_and_zoom(get_frame, t, max_shift_factor=0.18, max_zoom_factor=5, duration=10.0):
            """
            Shifts the center of the frame towards the top and zoom into it,
            based on the time t in the video.

            :param get_frame: Function to get the current frame at time t
            :param t: Current time in the video
            :param max_shift_factor: Maximum factor by which to shift the center towards the top
            :param max_zoom_factor: Maximum factor by which to zoom the frame
            :param duration: Duration of the video clip
            :return: Shifted and zoomed frame
            """

            frame = get_frame(t)

            height, width, _ = frame.shape

            # Calculate shift and zoom factors based on time
            shift_factor = max_shift_factor * (t / duration)
            zoom_factor = 1 + ((max_zoom_factor - 1) * (t / duration))

            # Calculate the amount to shift
            shift_amount = int(height * shift_factor)

            # Perform the shift using UMat
            shifted_frame_umat = cv2.UMat(frame[shift_amount:, :, :])
            shifted_frame_umat = cv2.copyMakeBorder(shifted_frame_umat, 0, shift_amount, 0, 0, cv2.BORDER_CONSTANT,
                                                    value=[0, 0, 0])

            # Calculate new size for zoom
            new_width = width * zoom_factor
            new_height = height * zoom_factor

            # Perform zoom
            zoomed_frame_umat = cv2.resize(shifted_frame_umat, (round(new_width), round(new_height)))

            # Calculate top and left positions for cropping
            top = int((new_height - height) / 2)
            left = int((new_width - width) / 2)

            # Crop to original frame size
            zoomed_frame = zoomed_frame_umat.get()[top:top + height, left:left + width]

            return zoomed_frame

        def pad_video_to_aspect_ratio(video_clip, width, height):
            """
            Pad the video to a specific aspect ratio.

            :param video_clip: The original video clip
            :param target_aspect_ratio: The target aspect ratio (width / height)
            :return: A new video clip with padding
            """
            target_aspect_ratio = width / height
            current_aspect_ratio = video_clip.size[0] / video_clip.size[1]

            if current_aspect_ratio > target_aspect_ratio:
                video_clip = video_clip.resize(width=width)
                # The video is too wide, need to add padding at the top and bottom
                new_height = int(video_clip.size[0] / target_aspect_ratio)
                padding = (new_height - video_clip.size[1]) // 2
                padded_clip = video_clip.margin(top=int(padding * 1.3), bottom=int(padding * 0.7), color=(0, 0, 0))
            else:
                video_clip = video_clip.resize(height=height)
                # The video is too tall, need to add padding on the sides
                new_width = int(video_clip.size[1] * target_aspect_ratio)
                padding = (new_width - video_clip.size[0]) // 2
                padded_clip = video_clip.margin(left=padding, right=padding, color=(0, 0, 0))

            return padded_clip

        # Handle images first
        def process_image(img_file):
            img_path = os.path.join(self.media_folder, img_file)
            clip = ImageSequenceClip([img_path], fps=self.fps, durations=[media_duration])

            clip_width, clip_height = clip.size
            frame_width, frame_height = self.frame_size

            target_aspect_ratio = frame_width / frame_height
            current_aspect_ratio = clip_width / clip_height

            if current_aspect_ratio > target_aspect_ratio:
                final_height_frame = int(clip_width / target_aspect_ratio)
                height_ratio = 1.1 * final_height_frame / clip_height
            else:
                final_width_frame = int(clip_height / target_aspect_ratio)
                height_ratio = 1.1 * final_width_frame / clip_width
            clip = pad_video_to_aspect_ratio(clip, self.frame_size[0], self.frame_size[1])

            clip = clip.fl(
                lambda gf, t: shift_and_zoom(gf, t, max_zoom_factor=height_ratio, duration=media_duration * 1.2))

            # Set the duration of each image in the video clip
            clip = clip.set_duration(media_duration)

            # Add fade transition
            return clip

        def process_video(video_path):
            video = video_path2video[video_path]
            video_clip = video.set_duration(
                min(media_duration, video.duration))  # Take the first 'media_duration' seconds
            # Calculate new height while maintaining aspect ratio
            video_clip = video_clip.without_audio()  # Remove audio
            clip_width, clip_height = video_clip.size
            frame_width, frame_height = self.frame_size

            target_aspect_ratio = frame_width / frame_height
            current_aspect_ratio = clip_width / clip_height

            if current_aspect_ratio > target_aspect_ratio:
                final_height_frame = int(clip_width / target_aspect_ratio)
                height_ratio = 1.1 * final_height_frame / clip_height
            else:
                final_width_frame = int(clip_height / target_aspect_ratio)
                height_ratio = 1.1 * final_width_frame / clip_width

            video_clip = pad_video_to_aspect_ratio(video_clip, self.frame_size[0], self.frame_size[1])
            video_clip = video_clip.fl(
                lambda gf, t: shift_and_zoom(gf, t, max_zoom_factor=height_ratio, duration=video_clip.duration * 1.2))
            return video_clip

        clips = []
        last_end = 0
        clip_start = 0
        for i, media_path in enumerate(media_files):
            if media_path.lower().endswith(('.mp4', '.avi', '.mov')):
                clip = process_video(media_path)
            else:
                clip = process_image(media_path)
            if i > 0:
                clip_start = last_end - fade_duration
                # Make the first clip fade out
                clips[-1] = clips[-1].crossfadeout(fade_duration)
                # Make the second clip fade in
                clip = clip.crossfadein(fade_duration)
                # Shift the second clip's start time back by `fade_duration` to make it start fading in before the first clip ends
            clip = clip.set_start(clip_start)
            last_end = clip_start + clip.duration
            clips.append(clip)

        # Concatenate all the clips together
        final_clip = CompositeVideoClip(clips)

        # Resize the video
        final_clip = final_clip.resize(newsize=self.frame_size)

        audio_clip = audio_clip.set_duration(final_clip.duration)
        final_clip = final_clip.set_audio(audio_clip)
        # Overlay subtitles
        final_clip = self.overlay_subtitles(final_clip, get_alignement(script, audio_object), script)

        # Save the video
        video_file_path = os.path.join(self.video_dir, title + ".mp4")
        final_clip.fps = self.fps

        final_clip.write_videofile(video_file_path, codec="libx264", preset="ultrafast", fps=10, bitrate="500k")

        return video_file_path

    def overlay_subtitles(self, final_clip, alignment, script):
        clips_with_subtitles = []
        current_group = []
        last_end_time = 0
        first_start_time = 0
        font_size = int(self.config.subtitle_font_size * final_clip.h / 1980)
        font = self.config.subtitle_font
        time_threshold = 0.5
        vertical_pos = final_clip.h // 3
        horizontal_pos = final_clip.w // 2
        length_str = 0

        filtered_words = [word for word in alignment['words'] if word['alignedWord'] != 'sp']
        aligned_word2text = match_aligned_words_to_text(filtered_words, script)

        for word in filtered_words:
            if last_end_time - first_start_time > 0.7 or length_str + len(word['alignedWord']) > 10 or (
                    current_group and word['start'] - last_end_time > time_threshold):
                start_time = current_group[0]['start']
                end_time = word['start']
                subtitle_text = " ".join([aligned_word2text[w['alignedWord'].lower()].get() for w in current_group])
                length_str = 0
                subtitle_clip = TextClip(subtitle_text, fontsize=font_size, color='white', font=font)
                subtitle_clip = subtitle_clip.set_position(
                    (horizontal_pos - subtitle_clip.w // 2, vertical_pos - subtitle_clip.h // 2))
                # Shadow text
                shadow_offset = int(5 * final_clip.h / 1980)
                shadow_clip = TextClip(subtitle_text, fontsize=font_size, color='black', font=font)
                shadow_clip.get_frame(0)

                shadow_clip = shadow_clip.set_position((horizontal_pos - subtitle_clip.w // 2 + shadow_offset,
                                                        vertical_pos + shadow_offset - subtitle_clip.h // 2))
                shadow_clip = shadow_clip.fx(vfx.colorx, 0.7)

                subtitle_clip = subtitle_clip.set_start(start_time).set_end(end_time)
                shadow_clip = shadow_clip.set_start(start_time).set_end(end_time)

                clips_with_subtitles.extend([shadow_clip, subtitle_clip])
                first_start_time = word['start']
                current_group = []

            current_group.append(word)
            length_str += len(word['alignedWord']) + 1
            last_end_time = word['end']

        if current_group:
            start_time = current_group[0]['start']

            end_time = final_clip.duration
            subtitle_text = " ".join([aligned_word2text[w['alignedWord'].lower()].get() for w in current_group])
            subtitle_clip = TextClip(subtitle_text, fontsize=font_size, color='white', font=font)
            subtitle_clip = subtitle_clip.set_position(
                (horizontal_pos - subtitle_clip.w // 2, vertical_pos - subtitle_clip.h // 2))
            # Shadow text
            shadow_offset = int(5 * final_clip.h / 1980)
            shadow_clip = TextClip(subtitle_text, fontsize=font_size, color='black', font=font).set_position(
                lambda t: (
                    (final_clip.w - subtitle_clip.w) // 2 + shadow_offset,
                    vertical_pos + shadow_offset - subtitle_clip.h // 2))
            shadow_clip = shadow_clip.fx(vfx.colorx, 0.7)

            subtitle_clip = subtitle_clip.set_start(start_time).set_end(end_time)
            shadow_clip = shadow_clip.set_start(start_time).set_end(end_time)

            clips_with_subtitles.extend([shadow_clip, subtitle_clip])

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
