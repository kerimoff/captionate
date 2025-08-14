curl -X POST http://127.0.0.1:8000/attach-outro \
  -H "Content-Type: application/json" \
  -d '{
    "dropbox_main_video_path": "/n8n/honey_badger_2025-08-12_22:08:20/9_16/generated_video.mp4",
    "dropbox_outro_video_path": "/outros/outro_instragram_eng.mov",
    "output_filename": "generated_video_with_outro.mp4",
    "save_to_dropbox": true,
    "dropbox_output_folder": "/n8n/honey_badger_2025-08-12_22:08:20/9_16/"
  }' 