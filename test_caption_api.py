import requests
import json
import base64
import os
from datetime import datetime
import time

# Replace with your actual image URL and texts
request_payload = {
    "image_url": "https://www.dropbox.com/scl/fi/rhi3thkgcat4ywe6ri5jw/9_16.jpg?rlkey=3m9ir1zyxzmps901apbnpmbf0&st=x56gwxnh&dl=1", # Replace with a real image URL
    "dropbox_dir": "/n8n/penguins_test/9_16",
    "text": [
        "Octopuses have <b>three hearts</b> that pump blue blood through their bodies.",
        "An octopus can squeeze through any opening <b>larger than its beak</b>.",
        "Each octopus arm has <b>its own brain</b> and can taste what it touches."
    ],
    "font_family": "Montserrat",
    "text_position": "bottom",
    "background_height": 0.9,
    "background_color": "rgba(0, 0, 0, 200)",
    "margin_horizontal": 24,
    "margin_top": 30,
    "margin_bottom": 50,
    "transition_proportion": 0.2
}

# Create results directory with timestamp (DD_MM_YYYY/HH_MM_SS)
current_date = datetime.now().strftime("%d_%m_%Y")
current_time = datetime.now().strftime("%H_%M_%S")
output_dir = os.path.join("results", current_date, current_time)
os.makedirs(output_dir, exist_ok=True)
print(f"Saving results to: {output_dir}")

start_time = time.time()
try:
    response = requests.post("http://127.0.0.1:8000/caption-image", json=request_payload)
    response.raise_for_status() # Raise an exception for HTTP errors (4xx or 5xx)
    
    response_data = response.json()

    if request_payload.get("dropbox_dir"):
        print("Dropbox directory was provided. Saving links.")
        links_file_path = os.path.join(output_dir, "dropbox_links.json")
        with open(links_file_path, "w") as f:
            json.dump(response_data, f, indent=4)
        
        print(f"Saved Dropbox links to {links_file_path}")
        print("Received links:")
        print(json.dumps(response_data, indent=4))
    else:
        print("No Dropbox directory provided. Saving images locally.")
        # Save background_only image
        if "background_only" in response_data:
            bg_image_bytes = base64.b64decode(response_data["background_only"])
            bg_file_name = os.path.join(output_dir, "background.png")
            with open(bg_file_name, "wb") as f:
                f.write(bg_image_bytes)
            print(f"Saved {bg_file_name}")
        else:
            print("Warning: 'background_only' not found in response.")

        # Create subdirectories for text_only and final_combined images
        text_only_dir = os.path.join(output_dir, 'text_only')
        final_combined_dir = os.path.join(output_dir, 'final_combined')
        os.makedirs(text_only_dir, exist_ok=True)
        os.makedirs(final_combined_dir, exist_ok=True)
        
        if "images" in response_data:
            for i, item in enumerate(response_data["images"]):
                if item.get("success"):
                    # Save text_only image
                    if "text_only" in item:
                        text_only_bytes = base64.b64decode(item["text_only"])
                        text_only_filename = os.path.join(text_only_dir, f"text_{i+1:02d}_text.png")
                        with open(text_only_filename, "wb") as f:
                            f.write(text_only_bytes)
                        print(f"Saved {text_only_filename}")
                    else:
                        print(f"Warning: 'text_only' not found for item {i+1}")

                    # Save final_combined image
                    if "final_combined" in item:
                        final_combined_bytes = base64.b64decode(item["final_combined"])
                        final_combined_filename = os.path.join(final_combined_dir, f"text_{i+1:02d}_combined.png")
                        with open(final_combined_filename, "wb") as f:
                            f.write(final_combined_bytes)
                        print(f"Saved {final_combined_filename}")
                    else:
                        print(f"Warning: 'final_combined' not found for item {i+1}")
                else:
                    print(f"Error processing image {i+1}: {item.get('error', 'Unknown error')}")
        else:
            print("Unexpected response format: 'images' key not found.")
            print(f"Response: {response_data}")

except requests.exceptions.RequestException as e:
    print(f"Request failed: {e}")
except json.JSONDecodeError:
    print(f"Failed to decode JSON response: {response.text}")
except Exception as e:
    print(f"An unexpected error occurred: {e}")
    print(f"Response content: {response.text if 'response' in locals() else 'No response received'}")

end_time = time.time()
duration = end_time - start_time
print(f"This run took {duration:.2f} seconds")