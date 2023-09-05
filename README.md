# Auto Short/Reels/Tiktok Generator 🎬🤖

![Generated Short Example](https://github.com/MJP1998/Auto_short_generator/assets/64918024/1ad8e130-ec2c-40ba-8e0b-ecf8d0a14a75)
> [Watch one of the generated videos](https://youtube.com/shorts/KagZs4jwyfM?feature=share)

## Overview

Welcome to Auto Short/Reels/Tiktok Generator! This project aims to automate the production of short-form videos using AI. Built during my spare time, this project is a creative attempt to leverage AI for generating a large amount of content with minimal effort.

From providing a script and media files, the application takes care of everything:

- Text-to-Speech conversion
- Video editing and effects
- Subtitle generation with forced alignment
- Background music integration

## Flexibility and Extensibility

One of the core philosophies behind this project is flexibility. We understand that automated doesn't have to mean rigid. Therefore, various parts of the video generation can be modified to fit your specific needs.

## Tech Stack 🛠

- **PyDub**: For audio processing
- **MoviePy**: For video editing
- **ElevenLabs API**: For Text-to-Speech conversion
- **PyFoal**: For forced alignment of subtitles

## Getting Started 🚀

### Prerequisites

- Python 3.x
- ffmpeg

### Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/yourusername/your-repo-name.git
   ```
2. Install the required packages:
   ```bash
   pip install -r requirements.txt
   ```
### Usage
Add your script and media files to the respective directories.
Run the main script:
   ```bash
   python main.py
   ```

### Configuration 📁
You can set up your own API keys and other private settings in config/settings_private.json.

### Contributing 🤝
Feel free to open issues or submit pull requests. Your contributions are welcome!

### License 📄
This project is licensed under the MIT License - see the LICENSE.md file for details.

### Next steps
-Integrating the chatgpt prompt to generate script, title, hashtags and description
-Integrating stable diffusion model so as to generate the entire video with only the prompt
