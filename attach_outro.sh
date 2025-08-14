#!/usr/bin/env bash

set -euo pipefail

print_usage() {
  cat <<EOF
Attach an outro clip to the end of a main video, normalizing codecs, fps, size, and audio.

Usage:
  $(basename "$0") <main_video> <outro_video> [output_file]

Examples:
  $(basename "$0") generated_video.mp4 outro_instragram_eng.mov
  $(basename "$0") input.mp4 outro.mov final_with_outro.mp4

Notes:
  - Requires ffmpeg and ffprobe.
  - Both clips will be re-encoded to H.264/AAC with the main video's size and frame rate.
  - Handles cases where a clip has no audio.
EOF
}

require_command() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "Error: Required command '$1' not found in PATH." >&2
    exit 1
  fi
}

escape_for_sed() {
  printf '%s' "$1" | sed -e 's/[\\&]/\\&/g'
}

get_video_size() {
  # Prints WxH (e.g., 1920x1080)
  ffprobe -v error -select_streams v:0 \
    -show_entries stream=width,height -of csv=s=x:p=0 "$1"
}

get_video_fps_rational() {
  # Prints average frame rate in rational form (e.g., 30000/1001 or 25/1)
  ffprobe -v error -select_streams v:0 \
    -show_entries stream=avg_frame_rate -of csv=p=0 "$1"
}

get_duration_seconds() {
  # Prints duration in seconds with decimals
  ffprobe -v error -show_entries format=duration -of csv=p=0 "$1"
}

has_audio_stream() {
  # Returns 0 if audio exists, 1 otherwise (so usable in if ! has_audio_stream ...)
  if ffprobe -v error -select_streams a:0 -show_entries stream=index -of csv=p=0 "$1" >/dev/null 2>&1; then
    return 0
  else
    return 1
  fi
}

main() {
  if [ "${1:-}" = "-h" ] || [ "${1:-}" = "--help" ] || [ $# -lt 2 ]; then
    print_usage
    exit 0
  fi

  require_command ffmpeg
  require_command ffprobe

  MAIN_INPUT="$1"
  OUTRO_INPUT="$2"
  OUTPUT_FILE="${3:-}"

  if [ ! -f "$MAIN_INPUT" ]; then
    echo "Error: Main video not found: $MAIN_INPUT" >&2
    exit 1
  fi
  if [ ! -f "$OUTRO_INPUT" ]; then
    echo "Error: Outro video not found: $OUTRO_INPUT" >&2
    exit 1
  fi

  if [ -z "$OUTPUT_FILE" ]; then
    base_name="$(basename "$MAIN_INPUT")"
    base_no_ext="${base_name%.*}"
    OUTPUT_FILE="${base_no_ext}_with_outro.mp4"
  fi

  # Probe main video for size and fps
  main_size="$(get_video_size "$MAIN_INPUT")"
  if [ -z "$main_size" ]; then
    echo "Error: Could not determine main video size." >&2
    exit 1
  fi
  main_w="${main_size%x*}"
  main_h="${main_size#*x}"

  # Ensure even dimensions to satisfy encoders like libx264
  even_w=$(( main_w - (main_w % 2) ))
  even_h=$(( main_h - (main_h % 2) ))
  if [ "$even_w" -lt 2 ] || [ "$even_h" -lt 2 ]; then
    echo "Error: Computed invalid target dimensions: ${even_w}x${even_h}" >&2
    exit 1
  fi

  fps_rational="$(get_video_fps_rational "$MAIN_INPUT")"
  if [ -z "$fps_rational" ] || [ "$fps_rational" = "0/0" ]; then
    # Sensible default
    fps_rational="30/1"
  fi

  # Audio presence
  main_has_audio=0
  outro_has_audio=0
  if has_audio_stream "$MAIN_INPUT"; then main_has_audio=1; fi
  if has_audio_stream "$OUTRO_INPUT"; then outro_has_audio=1; fi

  # Calculate durations if we need to synthesize silence
  main_duration=""
  outro_duration=""
  need_audio_concat=0
  if [ $main_has_audio -eq 1 ] || [ $outro_has_audio -eq 1 ]; then
    need_audio_concat=1
  fi
  if [ $need_audio_concat -eq 1 ]; then
    main_duration="$(get_duration_seconds "$MAIN_INPUT")"
    outro_duration="$(get_duration_seconds "$OUTRO_INPUT")"
    [ -z "$main_duration" ] && main_duration=0
    [ -z "$outro_duration" ] && outro_duration=0
  fi

  # Build ffmpeg command
  # Inputs: 0=main, 1=outro, optionally 2/3 for silence
  ff_args=(
    -hide_banner -y
    -i "$MAIN_INPUT"
    -i "$OUTRO_INPUT"
  )

  # Track indices for optional silence inputs
  next_index=2
  main_audio_in="0:a"
  outro_audio_in="1:a"

  if [ $need_audio_concat -eq 1 ]; then
    if [ $main_has_audio -eq 0 ]; then
      ff_args+=( -f lavfi -t "$main_duration" -i anullsrc=r=48000:cl=stereo )
      main_audio_in="${next_index}:a"
      next_index=$((next_index + 1))
    fi
    if [ $outro_has_audio -eq 0 ]; then
      ff_args+=( -f lavfi -t "$outro_duration" -i anullsrc=r=48000:cl=stereo )
      outro_audio_in="${next_index}:a"
      next_index=$((next_index + 1))
    fi
  fi

  # Build filter_complex
  # Normalize video to main's size/fps/pixel format and concat
  vnorm_main="[0:v]fps=${fps_rational},scale=${even_w}:${even_h}:flags=lanczos,format=yuv420p,setsar=1[v0]"
  vnorm_outro="[1:v]fps=${fps_rational},scale=${even_w}:${even_h}:flags=lanczos,format=yuv420p,setsar=1[v1]"

  if [ $need_audio_concat -eq 1 ]; then
    anorm_main="[${main_audio_in}]aformat=sample_fmts=fltp:sample_rates=48000:channel_layouts=stereo,aresample=async=1[a0]"
    anorm_outro="[${outro_audio_in}]aformat=sample_fmts=fltp:sample_rates=48000:channel_layouts=stereo,aresample=async=1[a1]"
    concat_line="[v0][a0][v1][a1]concat=n=2:v=1:a=1[v][a]"
    map_args=( -map "[v]" -map "[a]" )
  else
    anorm_main=""
    anorm_outro=""
    concat_line="[v0][v1]concat=n=2:v=1:a=0[v]"
    map_args=( -map "[v]" )
  fi

  # Build the filter string with explicit semicolons between chains
  filter_parts=(
    "$vnorm_main"
    "$vnorm_outro"
  )
  if [ -n "$anorm_main" ]; then
    filter_parts+=( "$anorm_main" )
  fi
  if [ -n "$anorm_outro" ]; then
    filter_parts+=( "$anorm_outro" )
  fi
  filter_parts+=( "$concat_line" )
  IFS=';'; filter_complex="${filter_parts[*]}"; unset IFS

  # Assemble final args
  ff_args+=(
    -filter_complex "$filter_complex"
    "${map_args[@]}"
    -c:v libx264 -profile:v high -preset veryfast -crf 18 -pix_fmt yuv420p
  )

  if [ $need_audio_concat -eq 1 ]; then
    ff_args+=( -c:a aac -b:a 192k -ar 48000 )
  fi

  ff_args+=( -movflags +faststart "$OUTPUT_FILE" )

  echo "Attaching outro..."
  echo "- Main:  $MAIN_INPUT"
  echo "- Outro: $OUTRO_INPUT"
  echo "- Size:  ${even_w}x${even_h}"
  echo "- FPS:   ${fps_rational}"
  echo "- Out:   $OUTPUT_FILE"
  echo

  # shellcheck disable=SC2068
  ffmpeg "${ff_args[@]}"

  echo "Done: $OUTPUT_FILE"
}

main "$@"


