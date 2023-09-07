import os

import cv2
from moviepy import Clip
from moviepy.video.io.ImageSequenceClip import ImageSequenceClip
from moviepy.video.io.VideoFileClip import VideoFileClip

from src.utils import Config


class Media:
    def __init__(self, path: str, media_duration, clip: Clip = None):
        self.path = path
        config = Config()
        self.final_clip_frame_size = config.frame_size
        self.fps = config.fps
        self.clip = clip
        if clip is None:
            self._load_media()
        self._process_from_name(media_duration)

    def _load_media(self):
        if self.path.lower().endswith(('.mp4', '.avi', '.mov')):
            self.clip = VideoFileClip(self.path)
            self.clip = self.clip.without_audio()
        else:
            self.clip = ImageSequenceClip([self.path], fps=self.fps)

    def _process_from_name(self, media_duration):
        info = parse_filename(self.path)
        if "start" in info and is_float(info["start"]):
            if (start := float(info["start"])) < self.get_duration():
                self.trim(start)

        self.set_duration(media_duration)

        if "crop" in info and info["crop"].isdigit() and int(info["crop"]) == 1:
            self.crop_to_aspect_ratio()
        else:
            self.pad_to_aspect_ratio()

        zoom = True
        shift = True
        if "zoom" in info and info["zoom"].isdigit() and int(info["zoom"]) == 0:
            zoom = False
        if "shift" in info and info["shift"].isdigit() and int(info["shift"]) == 0:
            shift = False

        self.shift_and_zoom(zoom, shift)

    def set_duration(self, duration: float):
        # Do the required processing here
        if isinstance(self.clip, VideoFileClip):
            self.clip = self.clip.set_duration(min(duration, self.clip.duration))
        else:
            self.clip = self.clip.set_duration(duration)

    def shift_and_zoom(self, zoom=True, shift=True):
        clip_width, clip_height = self.final_clip_frame_size
        frame_width, frame_height = self.clip.size
        max_shift_factor = 0.18 if shift else 0

        target_aspect_ratio = frame_width / frame_height
        current_aspect_ratio = clip_width / clip_height

        if current_aspect_ratio > target_aspect_ratio:
            final_height_frame = int(clip_width / target_aspect_ratio)
            height_ratio = 1.1 * final_height_frame / clip_height
        else:
            final_width_frame = int(clip_height / target_aspect_ratio)
            height_ratio = 1.1 * final_width_frame / clip_width

        height_ratio = height_ratio if zoom else 1
        self.clip = self.clip.fl(
            lambda gf, t: shift_and_zoom(gf,
                                         t,
                                         max_shift_factor=max_shift_factor,
                                         max_zoom_factor=height_ratio,
                                         duration=self.get_duration() * 1.2))

    def add_transition(self, transition_type: str, fade_duration: float):
        # Add fade transition here
        if transition_type == "crossfadeout":
            self.clip = self.clip.crossfadeout(fade_duration)
        elif transition_type == "crossfadein":
            self.clip = self.clip.crossfadein(fade_duration)

    def pad_to_aspect_ratio(self):
        # Pad the video to a specific aspect ratio
        self.clip = pad_video_to_aspect_ratio(self.clip,
                                              self.final_clip_frame_size[0],
                                              self.final_clip_frame_size[1])

    def crop_to_aspect_ratio(self):
        """
        Crop the clip to a specific aspect ratio by cutting equally from the top, bottom, left, and right.

        Parameters:
        - clip: The original VideoFileClip
        - target_width: The target width
        - target_height: The target height

        Returns:
        - A new VideoFileClip that has been cropped
        """
        target_width, target_height = self.final_clip_frame_size
        # Calculate the aspect ratios
        target_aspect_ratio = target_width / target_height
        clip_aspect_ratio = self.clip.size[0] / self.clip.size[1]

        # Calculate the new dimensions
        if clip_aspect_ratio > target_aspect_ratio:
            # Clip is too wide. Width will be reduced.
            new_width = int(target_aspect_ratio * self.clip.size[1])
            new_height = self.clip.size[1]
        else:
            # Clip is too tall. Height will be reduced.
            new_height = int(target_height / self.clip.size[0])
            new_width = self.clip.size[0]

        # Calculate the cropping boundaries
        left_crop = (self.clip.size[0] - new_width) // 2
        right_crop = self.clip.size[0] - new_width - left_crop
        top_crop = (self.clip.size[1] - new_height) // 2
        bottom_crop = self.clip.size[1] - new_height - top_crop

        # Crop the clip
        self.clip = self.clip.crop(
            x_center=self.clip.size[0] // 2,
            y_center=self.clip.size[1] // 2,
            width=self.clip.size[0] - left_crop - right_crop,
            height=self.clip.size[1] - top_crop - bottom_crop
        )

    def trim(self, time):
        self.clip = self.clip.subclip(time)

    def set_start(self, start: float):
        self.clip = self.clip.set_start(start)

    def get_duration(self):
        return self.clip.duration


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


def parse_filename(filename):
    base_name = os.path.basename(filename)  # Get the base name of the file
    file_name_without_extension = os.path.splitext(base_name)[0]  # Remove the file extension

    info = {}
    # Remove file extension
    name, ext = os.path.splitext(file_name_without_extension)
    # Split filename by underscore
    parts = name.split("_")
    # Parse each part
    if len(parts) < 2:
        return info
    for part in parts[1:]:  # Skip the first part, which is the actual file name
        split_part = part.split("-")
        if len(split_part) != 2:
            continue
        key, value = split_part
        info[key] = value
    return info


def is_float(string):
    try:
        # float() is a built-in function
        float(string)
        return True
    except ValueError:
        return False
