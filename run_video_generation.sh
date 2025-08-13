#!/bin/bash

# This script sends a POST request to the /generate-video endpoint
# to trigger video generation with specified parameters.

# API endpoint URL
URL="http://127.0.0.1:8000/generate-video"

# JSON payload for the request
# This will generate a video from assets in the specified Dropbox folder
# and save the final output back to the same Dropbox folder.
JSON_PAYLOAD='{
  "dropbox_folder_path": "/n8n/penguins_test/9_16",
  "audio_dropbox_path": "/music_background/1.mp3",
  "save_to_dropbox": true,
  "video_duration_per_text": 4.0,
  "fade_duration": 0.2,
  "gif_offset_proportion": 0.4,
  "gif_width_proportion": 0.8,
  "gif_duration": 4.0,
  "gif_framerate": 60,
  "line_thickness": 5,
  "line_color": "#FFFF00",
  "fps": 60,
  "post_script_video_path": "/outros/outro_instragram_eng.mov"
}'

# Send the POST request using curl

echo $JSON_PAYLOAD
echo "Sending request to generate video..."
curl -X POST "$URL" \
     -H "Content-Type: application/json" \
     -d "$JSON_PAYLOAD"

# Add a newline for better formatting in the terminal
echo 