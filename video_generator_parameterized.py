#!/usr/bin/env python3

import os
import re
import glob
import shutil
from typing import Optional
from dotenv import load_dotenv
import dropbox
from dropbox import files
from moviepy import VideoFileClip, ImageClip, CompositeVideoClip, vfx, ColorClip, AudioFileClip

def create_video_with_parameters(
    dropbox_folder_path: str,
    local_folder_path: Optional[str] = None,
    save_to_dropbox: bool = False,
    video_duration_per_text: float = 5.0,
    fade_duration: float = 0.5,
    line_horizontal_margin: int = 20,
    line_bottom_margin: int = 20,
    line_thickness: int = 3,
    line_color: str = "#FFFF00",
    fps: int = 30,
    codec: str = 'libx264',
    line_segments_per_second: int = 30
):
    """
    Create video using MoviePy with parameterized settings.
    
    Parameters:
    -----------
    dropbox_folder_path : str
        Dropbox folder path (e.g., "/Apps/CaptiOnAte" or "/temp/demo_images")
    local_folder_path : Optional[str], default=None
        Optional local folder path as fallback. If None, will download from Dropbox.
    save_to_dropbox : bool, default=False
        If True, uploads the generated video to the `dropbox_folder_path`.
    video_duration_per_text : float, default=5.0
        Total time each text is displayed (including fade in/out)
    fade_duration : float, default=0.5
        Fade in/out duration in seconds
    line_horizontal_margin : int, default=20
        Total horizontal margin from screen edges (10% each side)
    line_bottom_margin : int, default=20
        Distance from bottom of screen as percentage
    line_thickness : int, default=3
        Line thickness in pixels
    line_color : str, default="#FFFF00"
        Line color in hex format (e.g., "#FFFF00" for yellow)
    fps : int, default=30
        Video frame rate
    codec : str, default='libx264'
        Video codec for output
    line_segments_per_second : int, default=30
        Controls line animation smoothness (higher = smoother)
    
    Expected folder structure:
    -------------------------
    folder/
      ├── background.png
      └── text_only/
          ├── text_01_text.png
          ├── text_02_text.png
          └── ...
    
    Returns:
    --------
    str : Path to the generated video file
    """
    
    # Load environment variables
    load_dotenv()
    
    # Convert hex color to RGB tuple
    def hex_to_rgb(hex_color: str) -> tuple:
        hex_color = hex_color.lstrip('#')
        return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
    
    line_color_rgb = hex_to_rgb(line_color)
    
    # Calculate line animation timing
    text_display_duration = video_duration_per_text - (2 * fade_duration)
    
    # Determine working folder
    if local_folder_path and os.path.exists(local_folder_path):
        working_folder = local_folder_path
        print(f"Using local folder: {working_folder}")
    else:
        # Download from Dropbox
        working_folder = download_from_dropbox(dropbox_folder_path)
        print(f"Downloaded from Dropbox to: {working_folder}")
    
    # File paths
    background_path = os.path.join(working_folder, "background.png")
    text_pattern = os.path.join(working_folder, "text_only", "text_*_text.png")
    
    # Validate files exist
    if not os.path.exists(background_path):
        raise FileNotFoundError(f"Background image not found: {background_path}")
    
    text_files = glob.glob(text_pattern)
    if not text_files:
        raise FileNotFoundError(f"No text images found with pattern: {text_pattern}")
    
    # Sort text files by number
    def extract_number(filename):
        basename = os.path.basename(filename)
        match = re.search(r'text_(\d+)_text\.png', basename)
        return int(match.group(1)) if match else 0
    
    text_files.sort(key=extract_number)
    
    print(f"Found background: {background_path}")
    print(f"Found {len(text_files)} text images:")
    for i, path in enumerate(text_files):
        print(f"  {i+1}: {os.path.basename(path)}")
    
    # Calculate total video duration
    total_duration = len(text_files) * video_duration_per_text
    print(f"Total video duration: {total_duration} seconds")
    
    # Create background clip (constant throughout video)
    print("Creating background clip...")
    background_clip = (ImageClip(background_path)
                      .with_duration(total_duration))

    # Get video dimensions from background clip
    video_height = background_clip.h
    
    # Create text clips with fade animations
    text_clips = []
    for i, text_path in enumerate(text_files):
        start_time = i * video_duration_per_text
        
        print(f"Creating text clip {i+1}/{len(text_files)}: {os.path.basename(text_path)}")
        
        text_clip = (ImageClip(text_path)
                    .with_duration(video_duration_per_text)
                    .with_start(start_time)
                    .resized(height=video_height)
                    .with_effects([vfx.FadeIn(fade_duration), vfx.FadeOut(fade_duration)]))
        
        text_clips.append(text_clip)
    
    # Get video dimensions for line positioning
    video_width = background_clip.w
    
    # Calculate line dimensions and position
    horizontal_margin_each_side = line_horizontal_margin / 2
    line_left_margin = (horizontal_margin_each_side / 100) * video_width
    line_right_margin = (horizontal_margin_each_side / 100) * video_width
    line_width = video_width - line_left_margin - line_right_margin
    line_y_position = video_height - (line_bottom_margin / 100) * video_height
    
    # Create line clips with left-to-right animation
    line_clips = []
    for i, text_path in enumerate(text_files):
        start_time = i * video_duration_per_text
        line_start_time = start_time + fade_duration
        
        print(f"Creating line clip {i+1}/{len(text_files)}")
        
        # The line should finish drawing just as the text starts to fade out.
        line_animation_duration = video_duration_per_text - 2 * fade_duration
        
        if line_animation_duration <= 0:
            print(f"Warning: line_animation_duration is {line_animation_duration}. Check video_duration_per_text and fade_duration.")
            continue

        total_segments = int(line_animation_duration * line_segments_per_second)
        if total_segments == 0:
            print(f"Warning: total_segments is 0. Line animation may not be visible.")
            continue

        segment_width = line_width / total_segments
        segment_delay = line_animation_duration / total_segments
        
        # Create individual line segments
        for segment_idx in range(total_segments):
            segment_start_time = line_start_time + (segment_idx * segment_delay)
            segment_x_position = line_left_margin + (segment_idx * segment_width)
            
            # Duration should make the segment last until the text clip ends.
            segment_duration = (start_time + video_duration_per_text) - segment_start_time
            
            if segment_duration <= 0:
                continue
            
            segment_clip = (ColorClip(size=(max(1, int(segment_width * 2)), line_thickness),
                                    color=line_color_rgb)
                           .with_duration(segment_duration)
                           .with_start(segment_start_time)
                           .with_position((int(segment_x_position), int(line_y_position)))
                           .with_effects([vfx.FadeOut(fade_duration)]))
            
            line_clips.append(segment_clip)
    
    

    print("Compositing video...")
    final_video = CompositeVideoClip([background_clip] + text_clips + line_clips) \
                    .with_fps(fps)                           # v2 keeps with_fps

    # --- Add external music, trimmed to the clip length ---
    audio_path = "music/lofi-for-tiktok-369050.mp3"
    audio_clip = AudioFileClip(audio_path).subclipped(0, final_video.duration)  # trim  [oai_citation:1‡Bastaki Software Solutions L.L.C-FZ](https://bastakiss.com/blog/python-5/exploring-moviepy-2-a-modern-approach-to-video-editing-in-python-618?utm_source=chatgpt.com)
    final_video = final_video.with_audio(audio_clip)                            # v2 helper  [oai_citation:2‡GeeksforGeeks](https://www.geeksforgeeks.org/python/moviepy-assigning-audio-clip-to-video-file/)

    # --- Export ---
    output_path = "media/videos/moviepy_output.mp4"
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    print(f"Exporting video to: {output_path}")
    final_video.write_videofile(
        output_path,
        codec=codec,            # e.g. "libx264"
        audio_codec="aac",      # required for MP4
        audio_bitrate="192k",   # keep MP3 quality
        temp_audiofile="temp-audio.m4a",
        remove_temp=True,
    )
    print("Video creation completed!")
    print(f"Output file: {output_path}")

    if save_to_dropbox:
        # Construct Dropbox upload path, e.g., /temp/20_52_07/moviepy_output.mp4
        dropbox_upload_path = f"{dropbox_folder_path.rstrip('/')}/{os.path.basename(output_path)}"
        try:
            print(f"Uploading to Dropbox: {dropbox_upload_path}")
            upload_to_dropbox(output_path, dropbox_upload_path)
        except Exception as e:
            print(f"Error uploading to Dropbox: {e}")
            
    local_save_path = './downloaded_files'
    # remove the local save path
    shutil.rmtree(local_save_path)

    
    return output_path


def download_from_dropbox(dropbox_folder_path: str) -> str:
    """
    Download files from Dropbox using token from .env file.
    
    Parameters:
    -----------
    dropbox_folder_path : str
        Dropbox folder path to download from
        
    Returns:
    --------
    str : Local folder path where files were downloaded
    """
    # Get Dropbox token from environment
    access_token = os.getenv('DROPBOX_ACCESS_TOKEN')
    if not access_token:
        raise ValueError("DROPBOX_ACCESS_TOKEN not found in .env file. Please add it to your .env file.")
    
    # Local folder to save files
    local_save_path = './downloaded_files'
    os.makedirs(local_save_path, exist_ok=True)
    
    # Initialize Dropbox client
    try:
        dbx = dropbox.Dropbox(access_token)
        print(f"Connected to Dropbox, downloading from: {dropbox_folder_path}")
    except Exception as e:
        raise ConnectionError(f"Failed to connect to Dropbox: {e}")
    
    # Download folder recursively
    def download_folder_recursive(dropbox_path: str, local_path: str):
        try:
            entries = dbx.files_list_folder(dropbox_path).entries
            for entry in entries:
                if isinstance(entry, files.FileMetadata):
                    file_path = entry.path_lower
                    file_name = os.path.basename(file_path)
                    local_file = os.path.join(local_path, file_name)
                    print(f"Downloading {file_name}...")
                    with open(local_file, "wb") as f:
                        metadata, res = dbx.files_download(path=file_path)
                        f.write(res.content)
                elif isinstance(entry, files.FolderMetadata):
                    subfolder = os.path.join(local_path, entry.name)
                    os.makedirs(subfolder, exist_ok=True)
                    download_folder_recursive(entry.path_lower, subfolder)
        except Exception as e:
            raise RuntimeError(f"Error downloading from Dropbox: {e}")
    
    download_folder_recursive(dropbox_folder_path, local_save_path)
    return local_save_path


def upload_to_dropbox(local_file_path: str, dropbox_upload_path: str):
    """
    Uploads a local file to a specified Dropbox path.
    
    Parameters:
    -----------
    local_file_path : str
        The path to the local file to upload.
    dropbox_upload_path : str
        The destination path in Dropbox (e.g., "/Apps/CaptiOnAte/my_video.mp4").
    """
    access_token = os.getenv('DROPBOX_ACCESS_TOKEN')
    if not access_token:
        raise ValueError("DROPBOX_ACCESS_TOKEN not found in .env file. Please add it to your .env file.")
    
    try:
        dbx = dropbox.Dropbox(access_token)
        print(f"Connected to Dropbox, attempting to upload to: {dropbox_upload_path}")
    except Exception as e:
        raise ConnectionError(f"Failed to connect to Dropbox: {e}")
    
    with open(local_file_path, "rb") as f:
        try:
            # Use overwrite mode to avoid errors if file exists
            dbx.files_upload(
                f.read(),
                dropbox_upload_path,
                mode=files.WriteMode('overwrite')
            )
            print(f"Successfully uploaded {local_file_path} to {dropbox_upload_path}")
        except Exception as e:
            raise RuntimeError(f"Error during Dropbox upload: {e}")


# Example usage and testing
if __name__ == "__main__":
    try:
        # Example with default parameters
        output_file = create_video_with_parameters(
            dropbox_folder_path="/temp/20_52_07",        # Used for upload path
            # local_folder_path="downloaded_files_new",     # Use existing local files
            save_to_dropbox=True,                       # Set to True to upload result
            video_duration_per_text=5.0,             # 5 seconds per text
            fade_duration=0.2,                       # 0.5 second fade in/out
            line_horizontal_margin=20,               # 20% total margin (10% each side)
            line_bottom_margin=70,                   # 20% from bottom
            line_thickness=5,                        # 3 pixel thick line
            line_color="#FFFF00",                    # Yellow line
            fps=30,                                  # 30 fps for good quality
            codec='libx264',                         # H.264 codec
            line_segments_per_second=60           
        )
        print(f"Successfully created video: {output_file}")
        
    except Exception as e:
        print(f"Error: {e}") 