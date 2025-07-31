#!/bin/bash

#===============================================================================
# DYNAMIC FFMPEG VIDEO GENERATOR (Optimized Multi-Pass Version)
#
# This script automatically generates a video with sequential text overlays.
# It uses a multi-pass approach to avoid memory issues with many images.
# 1. Generates an animated GIF.
# 2. Creates a separate video segment for each text image.
# 3. Concatenates all segments into a single video.
# 4. Adds the GIF overlay and music in a final pass.
#===============================================================================

# --- Default Configuration ---
TEXT_IMG_DIR="text_images"
BACKGROUND_IMG="background.png"
OUTPUT_FILE="output_dynamic_video.mp4"
MUSIC_FILE=""
DURATION_PER_TEXT=2
FADE_DURATION=0.2
GIF_OVERLAY="line_animation.gif"
GIF_Y_OFFSET=100
GIF_WIDTH=800
GIF_HEIGHT=5
GIF_COLOR="yellow"
GIF_DURATION=2
GIF_FRAMERATE=50

# --- Usage/Help Function ---
usage() {
    echo "Usage: $0 [options]"
    echo
    echo "Options:"
    echo "  -d, --text-dir <dir>         Directory containing text PNGs (Default: $TEXT_IMG_DIR)"
    echo "  -b, --background <file>      Background image file (Default: $BACKGROUND_IMG)"
    echo "  -o, --output <file>          Output video file (Default: $OUTPUT_FILE)"
    echo "  -m, --music <file>           Optional music file to add (e.g., music.mp3)"
    echo "  --duration-per-text <secs>   Display duration for each text image (Default: $DURATION_PER_TEXT)"
    echo "  --fade-duration <secs>       Duration of fade effect (Default: $FADE_DURATION)"
    echo "  --gif-overlay <file>         Filename for the generated GIF (Default: $GIF_OVERLAY)"
    echo "  --gif-y-offset <px>          GIF vertical offset from bottom (Default: $GIF_Y_OFFSET)"
    echo "  --gif-width <px>             Width of the animated line (Default: $GIF_WIDTH)"
    echo "  --gif-height <px>            Height of the animated line (Default: $GIF_HEIGHT)"
    echo "  --gif-color <color>          Color of the animated line (Default: $GIF_COLOR)"
    echo "  --gif-duration <secs>        Duration of the GIF animation (Default: $GIF_DURATION)"
    echo "  --gif-framerate <fps>        Framerate of the GIF (Default: $GIF_FRAMERATE)"
    echo "  -h, --help                   Display this help message"
    echo
    exit 1
}

# --- Parse Command-Line Arguments ---
while [[ "$#" -gt 0 ]]; do
    case $1 in
        -d|--text-dir) TEXT_IMG_DIR="$2"; shift ;;
        -b|--background) BACKGROUND_IMG="$2"; shift ;;
        -o|--output) OUTPUT_FILE="$2"; shift ;;
        -m|--music) MUSIC_FILE="$2"; shift ;;
        --duration-per-text) DURATION_PER_TEXT="$2"; shift ;;
        --fade-duration) FADE_DURATION="$2"; shift ;;
        --gif-overlay) GIF_OVERLAY="$2"; shift ;;
        --gif-y-offset) GIF_Y_OFFSET="$2"; shift ;;
        --gif-width) GIF_WIDTH="$2"; shift ;;
        --gif-height) GIF_HEIGHT="$2"; shift ;;
        --gif-color) GIF_COLOR="$2"; shift ;;
        --gif-duration) GIF_DURATION="$2"; shift ;;
        --gif-framerate) GIF_FRAMERATE="$2"; shift ;;
        -h|--help) usage ;;
        *) echo "Unknown parameter passed: $1"; usage ;;
    esac
    shift
done

# --- Setup Temporary Directory and Cleanup ---
TEMP_DIR=$(mktemp -d)
# Ensure cleanup happens on script exit or interruption
trap 'rm -rf "$TEMP_DIR"' EXIT

# --- 1. Generate the Animated GIF ---
echo "Checking for dependencies..."
if command -v magick &> /dev/null; then
    MAGICK_CMD="magick"
elif command -v convert &> /dev/null; then
    MAGICK_CMD="convert"
else
    echo "Error: Neither 'magick' nor 'convert' command found. Please install ImageMagick."
    exit 1
fi
if ! command -v bc &> /dev/null; then
    echo "Error: 'bc' command not found. Please install bc (basic calculator)."
    exit 1
fi

echo "Generating animated line GIF..."
FRAMES_DIR="$TEMP_DIR/frames"
PALETTE_FILE="$TEMP_DIR/palette.png"
mkdir -p "$FRAMES_DIR"
TOTAL_GIF_FRAMES=$(echo "$GIF_DURATION * $GIF_FRAMERATE" | bc)

for i in $(seq 1 $TOTAL_GIF_FRAMES); do
  current_width=$((i * GIF_WIDTH / TOTAL_GIF_FRAMES))
  "$MAGICK_CMD" -size ${GIF_WIDTH}x${GIF_HEIGHT} xc:none -fill "$GIF_COLOR" -draw "rectangle 0,0 $current_width,${GIF_HEIGHT}" "$FRAMES_DIR/frame_$(printf "%03d" $i).png"
done

ffmpeg -y -i "$FRAMES_DIR/frame_%03d.png" -vf "palettegen=reserve_transparent=on" -y "$PALETTE_FILE" >/dev/null 2>&1
ffmpeg -y -framerate "$GIF_FRAMERATE" -i "$FRAMES_DIR/frame_%03d.png" -i "$PALETTE_FILE" -lavfi "[0:v][1:v]paletteuse" -y "$GIF_OVERLAY" >/dev/null 2>&1
echo "GIF generation complete."

# --- 2. Generate Individual Video Segments ---
echo "Generating individual video segments..."
TEXT_IMAGES=($(ls "$TEXT_IMG_DIR"/*.png 2>/dev/null | sort -V))
NUM_TEXT_IMAGES=${#TEXT_IMAGES[@]}
if [ "$NUM_TEXT_IMAGES" -eq 0 ]; then
    echo "Error: No text images found in '$TEXT_IMG_DIR'."
    exit 1
fi

CONCAT_LIST_FILE="$TEMP_DIR/concat_list.txt"
for i in $(seq 0 $(($NUM_TEXT_IMAGES - 1))); do
    text_img_path="${TEXT_IMAGES[$i]}"
    segment_output_path="$TEMP_DIR/segment_$((i+1)).mp4"
    echo "Processing $text_img_path -> $segment_output_path"

    fade_out_start=$(echo "$DURATION_PER_TEXT - $FADE_DURATION" | bc)

    ffmpeg -y -loop 1 -i "$BACKGROUND_IMG" -loop 1 -i "$text_img_path" \
    -filter_complex "[1:v]format=rgba,fade=in:st=0:d=$FADE_DURATION:alpha=1,fade=out:st=$fade_out_start:d=$FADE_DURATION:alpha=1[txt];[0:v][txt]overlay=(main_w-overlay_w)/2:(main_h-overlay_h)/2" \
    -t "$DURATION_PER_TEXT" -c:v libx264 -pix_fmt yuv420p -r 25 "$segment_output_path" >/dev/null 2>&1
    
    echo "file '$segment_output_path'" >> "$CONCAT_LIST_FILE"
done

# --- 3. Concatenate Segments ---
echo "Concatenating segments..."
CONCAT_VIDEO_PATH="$TEMP_DIR/concatenated.mp4"
ffmpeg -y -f concat -safe 0 -i "$CONCAT_LIST_FILE" -c copy "$CONCAT_VIDEO_PATH" >/dev/null 2>&1

# --- 4. Final Pass: Add GIF and Music ---
echo "Adding final overlays and music..."
FINAL_CMD="ffmpeg -y -i \"$CONCAT_VIDEO_PATH\" -stream_loop -1 -i \"$GIF_OVERLAY\""
if [ -n "$MUSIC_FILE" ]; then
    FINAL_CMD+=" -i \"$MUSIC_FILE\""
fi

# Apply 'shortest=1' to the overlay filter to ensure it terminates with the main video.
FILTER_COMPLEX="[0:v][1:v]overlay=(main_w-overlay_w)/2:main_h-overlay_h-$GIF_Y_OFFSET:shortest=1[final_v]"
FINAL_CMD+=" -filter_complex \"$FILTER_COMPLEX\" -map \"[final_v]\""

if [ -n "$MUSIC_FILE" ]; then
    # Map the audio stream and use -shortest to trim it to the video length.
    FINAL_CMD+=" -map 2:a -c:a aac -shortest"
fi

FINAL_CMD+=" -c:v libx264 -pix_fmt yuv420p \"$OUTPUT_FILE\""

eval "$FINAL_CMD"

echo "Video generation complete! Output file: $OUTPUT_FILE"
