import requests
import json
import base64
import os
from datetime import datetime

# Replace with your actual image URL and texts
request_payload = {
    "image_url": "https://images.unsplash.com/photo-1483519173755-be893fab1f46?q=80&w=3608&auto=format&fit=crop&ixlib=rb-4.1.0&ixid=M3wxMjA3fDB8MHxwaG90by1wYWdlfHx8fGVufDB8fHx8fA%3D%3D", # Replace with a real image URL
    "text": [
        "The human eye can distinguish over 10 million different colors. But again, let's not test that and test if there are more than 10 million colors in this image.",
        "Human eyes can detect a single photon of light.",
        "Your eyes are the same size from birth and never grow.",
        "Brown eyes are actually blue underneath - melanin makes them appear brown.",
        "The cornea is the only part of your body with no blood supply.",
        "Eyes heal incredibly fast - a scratched cornea heals in 24-48 hours.",
        "The eye's lens changes shape 100,000 times per day to focus.",
        "The human eye blinks about 17,000 times per day.",
        "The retina contains 120 million rods and 6 million cones.",
        "Your eyes use 25% of your brain's processing power."
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

# Create results directory with timestamp
current_time = datetime.now().strftime("%H_%M_%S")
output_dir = os.path.join("results", current_time)
os.makedirs(output_dir, exist_ok=True)
print(f"Saving results to: {output_dir}")

try:
    response = requests.post("http://127.0.0.1:8000/caption-image", json=request_payload)
    response.raise_for_status() # Raise an exception for HTTP errors (4xx or 5xx)
    
    response_data = response.json()
    
    if "images" in response_data:
        for i, item in enumerate(response_data["images"]):
            if item.get("success"):
                b64_image_data = item["image"]
                # Decode base64 string to bytes
                image_bytes = base64.b64decode(b64_image_data)
                
                # Save the image to a file in the new directory
                file_name = os.path.join(output_dir, f"captioned_image_{i+1}.png")
                with open(file_name, "wb") as f:
                    f.write(image_bytes)
                print(f"Saved {file_name}")
            else:
                print(f"Error processing image {i+1}: {item.get('error', 'Unknown error')}")
    else:
        print("Unexpected response format: 'images' key not found.")

except requests.exceptions.RequestException as e:
    print(f"Request failed: {e}")
except json.JSONDecodeError:
    print(f"Failed to decode JSON response: {response.text}")
except Exception as e:
    print(f"An unexpected error occurred: {e}")