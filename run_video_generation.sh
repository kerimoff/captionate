#!/bin/bash

# This script sends a POST request to the /generate-video endpoint
# to trigger video generation with specified parameters.

# API endpoint URL
URL="http://127.0.0.1:8000/generate-video"

# JSON payload for the request
# This will generate a video from assets in the specified Dropbox folder
# and save the final output back to the same Dropbox folder.
JSON_PAYLOAD='{
  "dropbox_folder_path": "/n8n/quantum_2025-07-30_10:07:36",
  "audio_dropbox_path": "/music_background/suspense-in-the-wood-360052.mp3",
  "local_folder_path": null,
  "save_to_dropbox": true,
  "video_duration_per_text": 3.0,
  "fade_duration": 0.2,
  "line_horizontal_margin": 20,
  "line_bottom_margin": 20,
  "line_thickness": 5,
  "line_color": "#FFFF00",
  "fps": 30,
  "codec": "libx264",
  "line_segments_per_second": 30
}'

# Send the POST request using curl

echo $JSON_PAYLOAD
echo "Sending request to generate video..."
curl -X POST "$URL" \
     -H "Content-Type: application/json" \
     -d "$JSON_PAYLOAD"

# Add a newline for better formatting in the terminal
echo 