#!/bin/bash
set -euo pipefail

#===============================================================================
# DYNAMIC FFMPEG VIDEO GENERATOR (Optimized Multi-Pass Version)
#
# This script automatically generates a video with sequential text overlays.
# It uses a multi-pass approach to avoid memory issues with many images.
# 1. Generates an animated GIF.
# 2. Creates a separate video segment for each text image.
# 3. Concatenates all segments into a single video.
# 4. Adds the GIF overlay, music, and an optional post-roll video in a final pass.
#===============================================================================

# --- Default Configuration ---
TEXT_IMG_DIR="text_images"
BACKGROUND_IMG="background.png"
OUTPUT_FILE="output_dynamic_video.mp4"
MUSIC_FILE=""
POST_SCRIPT_VIDEO=""
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
    echo "  -p, --post-script-video <file> Optional video file to append at the end (e.g., outro.mov)"
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
        -p|--post-script-video) POST_SCRIPT_VIDEO="$2"; shift ;;
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
if ! command -v awk &> /dev/null; then
    echo "Error: 'awk' command not found. Please install awk."
    exit 1
fi
if ! command -v ffprobe &> /dev/null; then
    echo "Error: 'ffprobe' command not found. It is part of the ffmpeg suite."
    exit 1
fi


echo "Generating animated line GIF..."
FRAMES_DIR="$TEMP_DIR/frames"
PALETTE_FILE="$TEMP_DIR/palette.png"
mkdir -p "$FRAMES_DIR"
# Use awk for floating point multiplication and round to the nearest integer.
TOTAL_GIF_FRAMES=$(awk -v d="$GIF_DURATION" -v r="$GIF_FRAMERATE" 'BEGIN {printf "%.0f", d*r}')

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

    # Use awk for floating point subtraction.
    fade_out_start=$(awk -v d="$DURATION_PER_TEXT" -v f="$FADE_DURATION" 'BEGIN {print d-f}')

    # Added scale filter to ensure even dimensions for the encoder.
    ffmpeg -y -loop 1 -i "$BACKGROUND_IMG" -loop 1 -i "$text_img_path" \
    -filter_complex "[1:v]format=rgba,fade=in:st=0:d=$FADE_DURATION:alpha=1,fade=out:st=$fade_out_start:d=$FADE_DURATION:alpha=1[txt];[0:v][txt]overlay=(main_w-overlay_w)/2:(main_h-overlay_h)/2,scale=trunc(iw/2)*2:trunc(ih/2)*2" \
    -t "$DURATION_PER_TEXT" -c:v libx264 -pix_fmt yuv420p -r 25 "$segment_output_path" >/dev/null 2>&1
    
    echo "file '$segment_output_path'" >> "$CONCAT_LIST_FILE"
done

# --- 3. Concatenate Segments ---
echo "Concatenating segments..."
CONCAT_VIDEO_PATH="$TEMP_DIR/concatenated.mp4"
ffmpeg -y -f concat -safe 0 -i "$CONCAT_LIST_FILE" -c copy "$CONCAT_VIDEO_PATH" >/dev/null 2>&1

# --- 4. Final Pass: Add GIF, Music, and Optional Post-Roll Video ---
echo "Adding final overlays and music..."

if [ -z "$POST_SCRIPT_VIDEO" ]; then
    # --- SIMPLE PATH: No post-roll video ---
    FINAL_CMD="ffmpeg -y -i \"$CONCAT_VIDEO_PATH\" -stream_loop -1 -i \"$GIF_OVERLAY\""
    if [ -n "$MUSIC_FILE" ]; then
        FINAL_CMD+=" -i \"$MUSIC_FILE\""
    fi
    
    FILTER_COMPLEX="[0:v][1:v]overlay=(main_w-overlay_w)/2:main_h-overlay_h-$GIF_Y_OFFSET:shortest=1[final_v]"
    FINAL_CMD+=" -filter_complex \"$FILTER_COMPLEX\" -map \"[final_v]\""

    if [ -n "$MUSIC_FILE" ]; then
        music_input_index=2
        FINAL_CMD+=" -map ${music_input_index}:a -c:a aac -shortest"
    fi

    FINAL_CMD+=" -c:v libx264 -pix_fmt yuv420p \"$OUTPUT_FILE\""

else
    # --- ADVANCED PATH: Post-roll video is present ---
	MAIN_DURATION=$(ffprobe -v error -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 "$CONCAT_VIDEO_PATH")
	AUDIO_FADE_START=$(awk -v d="$MAIN_DURATION" -v f="$FADE_DURATION" 'BEGIN {print d-f}')

	# Probe main video properties to normalize outro for safe concat
	MAIN_WIDTH=$(ffprobe -v error -select_streams v:0 -show_entries stream=width -of csv=p=0 "$CONCAT_VIDEO_PATH")
	MAIN_HEIGHT=$(ffprobe -v error -select_streams v:0 -show_entries stream=height -of csv=p=0 "$CONCAT_VIDEO_PATH")
	MAIN_FPS_RAW=$(ffprobe -v error -select_streams v:0 -show_entries stream=r_frame_rate -of csv=p=0 "$CONCAT_VIDEO_PATH")
	# Convert r_frame_rate (e.g., 25/1) to integer fps
	MAIN_FPS=$(awk -v fps="$MAIN_FPS_RAW" 'BEGIN{split(fps,a,"/"); if (length(a)==2 && a[2] != 0) printf "%.0f", a[1]/a[2]; else if (fps!="") printf "%.0f", fps; else print 25}')

	# Detect outro audio presence and duration
	POST_HAS_AUDIO=$(ffprobe -v error -select_streams a:0 -show_entries stream=codec_type -of csv=p=0 "$POST_SCRIPT_VIDEO" | wc -l | tr -d ' ')
	POST_DURATION=$(ffprobe -v error -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 "$POST_SCRIPT_VIDEO")

    # Build inputs dynamically
    FINAL_CMD="ffmpeg -y -i \"$CONCAT_VIDEO_PATH\" -stream_loop -1 -i \"$GIF_OVERLAY\""
    INPUT_COUNT=2
    if [ -n "$MUSIC_FILE" ]; then
        FINAL_CMD+=" -i \"$MUSIC_FILE\""
        MUSIC_INPUT_IDX=$INPUT_COUNT
        INPUT_COUNT=$((INPUT_COUNT + 1))
    fi
    FINAL_CMD+=" -i \"$POST_SCRIPT_VIDEO\""
    POST_SCRIPT_INPUT_IDX=$INPUT_COUNT

	# Build filter_complex dynamically
	# 1) Overlay GIF on main segment, then normalize main video to width/height/fps/pix_fmt
	FILTER_COMPLEX="[0:v][1:v]overlay=(main_w-overlay_w)/2:main_h-overlay_h-$GIF_Y_OFFSET:shortest=1[main_v_base];"
	FILTER_COMPLEX+="[main_v_base]fps=${MAIN_FPS},format=yuv420p,scale=${MAIN_WIDTH}:${MAIN_HEIGHT}:flags=bicubic[main_v];"
    
	# 2) Normalize outro video to match main
	FILTER_COMPLEX+="[${POST_SCRIPT_INPUT_IDX}:v]scale=${MAIN_WIDTH}:${MAIN_HEIGHT}:force_original_aspect_ratio=decrease:flags=bicubic,pad=${MAIN_WIDTH}:${MAIN_HEIGHT}:(ow-iw)/2:(oh-ih)/2:color=black,fps=${MAIN_FPS},format=yuv420p[post_v];"

	VIDEO_CONCAT_STREAMS="[main_v][post_v]"
	AUDIO_CONCAT_STREAMS=""
	CONCAT_STREAMS=""

    if [ -n "$MUSIC_FILE" ]; then
		# 3a) With music: trim to main duration, reset PTS, fade out; normalize outro or synthesize if missing
		FILTER_COMPLEX+="[${MUSIC_INPUT_IDX}:a]aformat=channel_layouts=stereo,aresample=44100,atrim=duration=${MAIN_DURATION},asetpts=N/SR/TB,afade=t=out:st=${AUDIO_FADE_START}:d=${FADE_DURATION}[main_a];"
		if [ "${POST_HAS_AUDIO}" -gt 0 ]; then
			FILTER_COMPLEX+="[${POST_SCRIPT_INPUT_IDX}:a]aformat=channel_layouts=stereo,aresample=44100,asetpts=N/SR/TB[post_a];"
		else
			FILTER_COMPLEX+="anullsrc=r=44100:cl=stereo,atrim=duration=${POST_DURATION},asetpts=N/SR/TB[post_a];"
		fi
		AUDIO_CONCAT_STREAMS="[main_a][post_a]"
		CONCAT_STREAMS="[main_v][main_a][post_v][post_a]"
    else
		# 3b) No music: synthesize main silent stereo 44.1k; normalize outro or synthesize if missing
		FILTER_COMPLEX+="anullsrc=r=44100:cl=stereo,atrim=duration=${MAIN_DURATION},asetpts=N/SR/TB[silent_audio];"
		if [ "${POST_HAS_AUDIO}" -gt 0 ]; then
			FILTER_COMPLEX+="[${POST_SCRIPT_INPUT_IDX}:a]aformat=channel_layouts=stereo,aresample=44100,asetpts=N/SR/TB[post_a];"
		else
			FILTER_COMPLEX+="anullsrc=r=44100:cl=stereo,atrim=duration=${POST_DURATION},asetpts=N/SR/TB[post_a];"
		fi
		AUDIO_CONCAT_STREAMS="[silent_audio][post_a]"
		CONCAT_STREAMS="[main_v][silent_audio][post_v][post_a]"
    fi

	# concat expects inputs in order: v0,a0,v1,a1 for n=2,v=1,a=1
	FILTER_COMPLEX+="${CONCAT_STREAMS}concat=n=2:v=1:a=1[final_v][final_a]"
    
    FINAL_CMD+=" -filter_complex \"$FILTER_COMPLEX\" -map \"[final_v]\" -map \"[final_a]\""
    FINAL_CMD+=" -c:v libx264 -pix_fmt yuv420p \"$OUTPUT_FILE\""
fi

set +e
eval "$FINAL_CMD"
ffmpeg_status=$?
set -e

if [ $ffmpeg_status -ne 0 ]; then
  echo "Error: Final ffmpeg step failed with exit code $ffmpeg_status" >&2
  exit $ffmpeg_status
fi

if [ ! -f "$OUTPUT_FILE" ]; then
  echo "Error: Expected output file not found at '$OUTPUT_FILE' after ffmpeg completed." >&2
  exit 1
fi

echo "Video generation complete! Output file: $OUTPUT_FILE"
