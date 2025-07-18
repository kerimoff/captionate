import requests
import json
import base64
import os
from datetime import datetime

# Replace with your actual image URL and texts
request_payload = {
    "image_url": "https://i.ibb.co/F4bPwd6T/mosquito.jpg", # Replace with a real image URL
    "text": [
        "The eye's lens changes shape <b>100,000 times per day</b> to focus.",
        "The human eye blinks about 17,000 times per day.",
        "The retina contains <b>120 million rods</b> and <b>6 million cones</b>."
    ],
    "font_family": "Montserrat",
    "text_position": "bottom",
    "background_height": 1,
    "background_color": "rgba(0, 0, 0, 150)",
    "margin_horizontal": 5,
    "margin_top": 40,
    "margin_bottom": 40,
    "transition_proportion": 0.2
}

# Create results directory with timestamp (DD_MM_YYYY/HH_MM_SS)
current_date = datetime.now().strftime("%d_%m_%Y")
current_time = datetime.now().strftime("%H_%M_%S")
output_dir = os.path.join("results", current_date, current_time)
os.makedirs(output_dir, exist_ok=True)
print(f"Saving results to: {output_dir}")

try:
    response = requests.post("http://127.0.0.1:8000/caption-image", json=request_payload)
    response.raise_for_status() # Raise an exception for HTTP errors (4xx or 5xx)
    
    response_data = response.json()
    
    if "images" in response_data:
        for i, item in enumerate(response_data["images"]):
            if item.get("success"):
                # Save all three image types
                image_types = {
                    "background_only": "background",
                    "text_only": "text", 
                    "final_combined": "combined"
                }
                
                for image_key, image_type in image_types.items():
                    if image_key in item:
                        b64_image_data = item[image_key]
                        # Decode base64 string to bytes
                        image_bytes = base64.b64decode(b64_image_data)
                        
                        # Save the image to a file in the new directory
                        file_name = os.path.join(output_dir, f"text_{i+1:02d}_{image_type}.png")
                        with open(file_name, "wb") as f:
                            f.write(image_bytes)
                        print(f"Saved {file_name}")
                    else:
                        print(f"Warning: {image_key} not found in response for text {i+1}")
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