from fastapi import FastAPI, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from typing import Literal, Set # Added Set
from PIL import Image, ImageDraw, ImageFont, ImageEnhance
import requests
import io
import html # Retained for potential unescape, though BeautifulSoup handles most
from bs4 import BeautifulSoup, NavigableString # Added NavigableString
from fastapi.exceptions import HTTPException
import logging
import re # Imported for regex operations in text processing

app = FastAPI()

# Configure logging
logging.basicConfig(level=logging.INFO) # Changed to INFO for more verbose logging during dev/debug
logging.getLogger("PIL").setLevel(logging.WARNING) # Quieten PIL's own INFO logs if any

# --- Font Paths Configuration ---
# Base directory for Google Fonts
GOOGLE_FONTS_BASE_DIR = "google-fonts"

FONT_FAMILY_PATHS = {
    "Montserrat": {
        "Regular": f"{GOOGLE_FONTS_BASE_DIR}/Montserrat/static/Montserrat-Regular.ttf",
        "Bold": f"{GOOGLE_FONTS_BASE_DIR}/Montserrat/static/Montserrat-Bold.ttf",
        "Italic": f"{GOOGLE_FONTS_BASE_DIR}/Montserrat/static/Montserrat-Italic.ttf",
        "BoldItalic": f"{GOOGLE_FONTS_BASE_DIR}/Montserrat/static/Montserrat-BoldItalic.ttf",
    },
    "Nunito": {
        "Regular": f"{GOOGLE_FONTS_BASE_DIR}/Nunito/static/Nunito-Regular.ttf",
        "Bold": f"{GOOGLE_FONTS_BASE_DIR}/Nunito/static/Nunito-Bold.ttf",
        "Italic": f"{GOOGLE_FONTS_BASE_DIR}/Nunito/static/Nunito-Italic.ttf",
        "BoldItalic": f"{GOOGLE_FONTS_BASE_DIR}/Nunito/static/Nunito-BoldItalic.ttf",
    },
    "Poppins": {
        "Regular": f"{GOOGLE_FONTS_BASE_DIR}/Poppins/Poppins-Regular.ttf", # Poppins static is not in a sub-static dir
        "Bold": f"{GOOGLE_FONTS_BASE_DIR}/Poppins/Poppins-Bold.ttf",
        "Italic": f"{GOOGLE_FONTS_BASE_DIR}/Poppins/Poppins-Italic.ttf",
        "BoldItalic": f"{GOOGLE_FONTS_BASE_DIR}/Poppins/Poppins-BoldItalic.ttf",
    },
    "Roboto": {
        "Regular": f"{GOOGLE_FONTS_BASE_DIR}/Roboto/static/Roboto-Regular.ttf",
        "Bold": f"{GOOGLE_FONTS_BASE_DIR}/Roboto/static/Roboto-Bold.ttf",
        "Italic": f"{GOOGLE_FONTS_BASE_DIR}/Roboto/static/Roboto-Italic.ttf",
        "BoldItalic": f"{GOOGLE_FONTS_BASE_DIR}/Roboto/static/Roboto-BoldItalic.ttf",
    },
}

DEFAULT_FALLBACK_FONT_FAMILY = "Montserrat"
DEFAULT_FALLBACK_STYLE_PATH = FONT_FAMILY_PATHS[DEFAULT_FALLBACK_FONT_FAMILY]["Regular"]


class CaptionRequest(BaseModel):
    image_url: str
    text: str = Field(default="", description="Text to render. Supports <b>, <i>, <u>, and <br> tags for formatting.")
    font_family: Literal["Montserrat", "Nunito", "Poppins", "Roboto"] = Field(default="Montserrat", description="Font family to use for the text.")
    text_position: Literal["top", "bottom"] = "bottom"
    background_height: float = Field(default=0.4, ge=0.0, le=1.0)
    background_color: str = "rgba(0, 0, 0, 180)"
    margin_horizontal: int = Field(default=10, ge=0)
    margin_top: int = Field(default=10, ge=0)
    margin_bottom: int = Field(default=10, ge=0)
    transition_proportion: float = Field(default=0.2, ge=0.0, le=1.0)


def get_font_for_style(font_family_name: str, base_size: int, styles: Set[str]) -> ImageFont.FreeTypeFont:
    is_bold = 'bold' in styles
    is_italic = 'italic' in styles
    
    family_map = FONT_FAMILY_PATHS.get(font_family_name, FONT_FAMILY_PATHS[DEFAULT_FALLBACK_FONT_FAMILY])
    font_path = None

    if is_bold and is_italic:
        font_path = family_map.get("BoldItalic")
    elif is_bold:
        font_path = family_map.get("Bold")
    elif is_italic:
        font_path = family_map.get("Italic")
    
    if not font_path: # Default to Regular if specific style not found or not requested
        font_path = family_map.get("Regular", DEFAULT_FALLBACK_STYLE_PATH)

    try:
        return ImageFont.truetype(font_path, base_size)
    except IOError as e:
        logging.warning(f"Failed to load font {font_path} for family {font_family_name} at size {base_size}: {e}. Attempting fallbacks.")
        # Fallback 1: Regular style of the requested family
        if font_path != family_map.get("Regular"):
            try:
                regular_path = family_map.get("Regular", DEFAULT_FALLBACK_STYLE_PATH)
                logging.info(f"Falling back to {regular_path} for family {font_family_name}.")
                return ImageFont.truetype(regular_path, base_size)
            except IOError as e_reg:
                logging.warning(f"Failed to load regular style {family_map.get('Regular')} for {font_family_name}: {e_reg}")
        
        # Fallback 2: Default fallback font (e.g., Montserrat Regular)
        if font_path != DEFAULT_FALLBACK_STYLE_PATH and family_map.get("Regular") != DEFAULT_FALLBACK_STYLE_PATH:
            try:
                logging.info(f"Falling back to default application font: {DEFAULT_FALLBACK_STYLE_PATH}.")
                return ImageFont.truetype(DEFAULT_FALLBACK_STYLE_PATH, base_size)
            except IOError as e_default_fallback:
                logging.error(f"Default fallback font {DEFAULT_FALLBACK_STYLE_PATH} also failed: {e_default_fallback}")

        # Last resort: Pillow's built-in default font
        logging.error("All font fallbacks failed. Using Pillow's load_default().")
        return ImageFont.load_default() 


def parse_html_text(html_text: str) -> list[list[tuple[str, Set[str]]]]:
    """
    Parses HTML-like text into a list of logical lines.
    Each logical line is a list of (text_segment, styles_set) tuples.
    Supported styles: 'bold', 'italic', 'underline'.
    Supported tags: <b>, <i>, <u>, <br>.
    """
    # Unescape HTML entities first
    text_to_parse = html.unescape(html_text)
    soup = BeautifulSoup(text_to_parse, "html.parser")
    
    logical_lines: list[list[tuple[str, Set[str]]]] = [[]]
    active_styles: Set[str] = set()

    def process_node(node):
        nonlocal logical_lines, active_styles
        if isinstance(node, NavigableString):
            content = str(node)
            # Preserve spaces, but maybe not leading/trailing on a line start/end unless intended
            # For now, keep all content as is from BS.
            if content: # Add if there's any content, even just spaces
                logical_lines[-1].append((content, active_styles.copy()))
        elif node.name == 'br':
            # Add a new line only if current line has content or if it's not the first line and we want to preserve multiple <br>
            # A <br> always means a new line, even if the current one is empty.
            logical_lines.append([])
        elif node.name in ['b', 'i', 'u']:
            style_map = {'b': 'bold', 'i': 'italic', 'u': 'underline'}
            style = style_map[node.name]
            
            original_style_present = style in active_styles
            if not original_style_present:
                active_styles.add(style)
            
            for child in node.children:
                process_node(child)
            
            if not original_style_present: # Remove style only if this node instance was the one to add it
                active_styles.remove(style)
        elif node.name and node.name not in ['html', 'body']: # Process children of other known/container tags
            for child in node.children:
                process_node(child)
        # Silently ignore unknown tags or specific tags like 'html', 'body'

    # Process all top-level children of the parsed soup
    for child_node in soup.children:
        process_node(child_node)

    # Clean up: remove any trailing empty line if it was added unnecessarily
    # and the line before it was also empty (e.g. from multiple <br><br> at the end)
    # However, if the user explicitly puts <br> at the end, they might want a blank line.
    # For now, only remove the very last line if it's empty AND it's not the only line.
    if len(logical_lines) > 1 and not logical_lines[-1]:
         logical_lines.pop()
    # If the input was empty or only whitespace, result might be [[]] or [[('', set())]]. Normalize to [[]] for empty.
    if not any(seg[0].strip() for line in logical_lines for seg in line):
        return [[]] # Represents no renderable text

    return logical_lines

def rgba_from_string(rgba_str: str) -> tuple[int, int, int, int]:
    """
    Parses rgba(r, g, b, a) string into a tuple of 4 integers (0-255).
    Handles alpha as 0-1 float (scales by 255) or as 0-255 int.
    """
    try:
        # Remove "rgba(" and ")" and split by comma
        parts_str = rgba_str.strip().lower()
        if not parts_str.startswith("rgba(") or not parts_str.endswith(")"):
            raise ValueError("Invalid RGBA string format")
            
        parts_str_list = parts_str[5:-1].split(',')
        if len(parts_str_list) != 4:
            raise ValueError("RGBA string must have 4 parts (r, g, b, a)")
        
        r = int(round(float(parts_str_list[0].strip())))
        g = int(round(float(parts_str_list[1].strip())))
        b = int(round(float(parts_str_list[2].strip())))
        
        a_str = parts_str_list[3].strip()
        a_float = float(a_str)
        
        # If alpha string contains '.' and its float value is between 0 and 1,
        # assume it's a 0.0-1.0 float that needs scaling.
        # Otherwise, assume it's already a 0-255 value.
        if '.' in a_str and 0.0 <= a_float <= 1.0:
            # Check if it's something like "1.0" which is effectively an integer after float conversion
            # A more robust check might be needed if "1.0" should be treated as 1 out of 255 vs 1.0 * 255
            # For now, this heuristic: if it looks like a typical float 0-1, scale it.
            if len(a_str) > 1 and a_str != "0" and a_str != "1": # Avoid scaling "0" or "1" if they were meant as 0-255
                 a = int(round(a_float * 255.0))
            else: # Treat "0", "1", "0.0", "1.0" as direct values if not clearly fractional for scaling
                 a = int(round(a_float))

        else:
            a = int(round(a_float))
            
        # Clamp all values to 0-255
        return (
            max(0, min(255, r)),
            max(0, min(255, g)),
            max(0, min(255, b)),
            max(0, min(255, a))
        )
    except Exception as e:
        logging.error(f"Error parsing RGBA string '{rgba_str}': {e}. Using default fallback color.")
        return (0, 0, 0, 180) # Default fallback: semi-transparent black


@app.post("/caption-image")
def caption_image(req: CaptionRequest):
    try:
        logging.info(f"Received request: {req}")

        # Load image from URL
        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }
        response = requests.get(req.image_url, headers=headers)
        response.raise_for_status()
        logging.info("Image fetched successfully.")

        img = Image.open(io.BytesIO(response.content)).convert("RGBA")
        width, height = img.size
        logging.info(f"Image dimensions: {width}x{height}")

        bg_height = int(height * req.background_height)
        margin_x_px = int((req.margin_horizontal / 100) * width / 2) # Renamed for clarity
        margin_top_px = int((req.margin_top / 100) * bg_height)
        margin_bottom_px = int((req.margin_bottom / 100) * bg_height)
        logging.info(f"Background height: {bg_height}, MarginX_px: {margin_x_px}, MarginTopPx: {margin_top_px}, MarginBottomPx: {margin_bottom_px}")

        base_r, base_g, base_b, base_a = rgba_from_string(req.background_color)
        overlay = Image.new("RGBA", (width, bg_height), (base_r, base_g, base_b, base_a))
        
        transition_height_px = int(round(bg_height * req.transition_proportion))
        if transition_height_px > 0 and bg_height > 0:
            pixels = overlay.load()
            logging.info(f"Applying gradient transition. Height: {transition_height_px}px, Position: {req.text_position}, Base Alpha: {base_a}")

            if req.text_position == "bottom": # Gradient at the top of the overlay
                # Alpha goes from 0 (at y=0) to base_a (at y=transition_height_px-1)
                for y_coord in range(transition_height_px):
                    if transition_height_px == 1: # Single line of transition, make it fully transparent
                        alpha_factor = 0.0 
                    else:
                        alpha_factor = y_coord / (transition_height_px - 1.0)
                    
                    current_alpha = int(round(base_a * alpha_factor))
                    for x_coord in range(width):
                        pixels[x_coord, y_coord] = (base_r, base_g, base_b, current_alpha)
            
            elif req.text_position == "top": # Gradient at the bottom of the overlay
                # Alpha goes from base_a (at y=bg_height-transition_height_px) to 0 (at y=bg_height-1)
                transition_zone_start_y = bg_height - transition_height_px
                for y_idx, y_coord in enumerate(range(transition_zone_start_y, bg_height)):
                    # y_idx goes from 0 to transition_height_px-1
                    if transition_height_px == 1: # Single line of transition, make it fully transparent
                        alpha_factor = 0.0
                    else:
                        alpha_factor = (transition_height_px - 1.0 - y_idx) / (transition_height_px - 1.0)
                    
                    current_alpha = int(round(base_a * alpha_factor))
                    for x_coord in range(width):
                        pixels[x_coord, y_coord] = (base_r, base_g, base_b, current_alpha)
            logging.info("Gradient applied to overlay.")
        else:
            logging.info("No gradient transition to apply (transition_height_px <= 0 or bg_height <= 0).")

        # Prepare drawing context on the (potentially gradient) overlay
        draw = ImageDraw.Draw(overlay)
        
        # --- NEW RICH TEXT PROCESSING ---
        logical_lines_styled = parse_html_text(req.text)
        logging.info(f"Parsed logical lines: {logical_lines_styled}")

        best_font_size = 0
        final_renderable_lines_layout = [] 

        if any(line for line in logical_lines_styled):
            font_size_iter = 1
            max_iter_font_size = max(1, min(bg_height, width, 200))

            while font_size_iter <= max_iter_font_size:
                current_iter_renderable_lines = []
                current_iter_total_height = 0
                possible_to_fit_this_size = True

                for logical_line in logical_lines_styled:
                    if not possible_to_fit_this_size: break
                    current_x = 0
                    max_ascent_in_line = 0
                    max_descent_in_line = 0
                    segments_for_current_render_line = []
                    drawable_units = []
                    for text_segment, styles_segment in logical_line:
                        parts = [p for p in re.split(r'(\s+)', text_segment) if p]
                        for part_text in parts:
                            drawable_units.append((part_text, styles_segment))
                    
                    if not drawable_units and not logical_line: 
                        placeholder_font = get_font_for_style(req.font_family, font_size_iter, set())
                        ph_ascent, ph_descent = placeholder_font.getmetrics()
                        current_iter_total_height += (ph_ascent + ph_descent)
                        current_iter_renderable_lines.append([]) 
                        continue

                    for unit_text, styles_unit in drawable_units:
                        font_obj = get_font_for_style(req.font_family, font_size_iter, styles_unit)
                        unit_width_measure = draw.textlength(unit_text, font=font_obj)
                        ascent, descent = font_obj.getmetrics()
                        if not unit_text.isspace() and current_x == 0 and unit_width_measure > (width - 2 * margin_x_px):
                            possible_to_fit_this_size = False; break 
                        if not unit_text.isspace() and current_x != 0 and (current_x + unit_width_measure) > (width - 2 * margin_x_px):
                            if segments_for_current_render_line: 
                                current_iter_renderable_lines.append({
                                    "segments": segments_for_current_render_line,
                                    "height": max_ascent_in_line + max_descent_in_line,
                                    "max_ascent": max_ascent_in_line
                                })
                                current_iter_total_height += (max_ascent_in_line + max_descent_in_line)
                            segments_for_current_render_line = []
                            current_x = 0
                            max_ascent_in_line = 0
                            max_descent_in_line = 0
                        max_ascent_in_line = max(max_ascent_in_line, ascent)
                        max_descent_in_line = max(max_descent_in_line, descent)
                        segments_for_current_render_line.append({
                            "text": unit_text, "styles": styles_unit, "font": font_obj,
                            "width": unit_width_measure, "ascent": ascent, "descent": descent,
                            "bbox": font_obj.getbbox(unit_text)
                        })
                        current_x += unit_width_measure
                    if not possible_to_fit_this_size: break
                    if segments_for_current_render_line:
                        current_iter_renderable_lines.append({
                            "segments": segments_for_current_render_line,
                            "height": max_ascent_in_line + max_descent_in_line,
                            "max_ascent": max_ascent_in_line
                        })
                        current_iter_total_height += (max_ascent_in_line + max_descent_in_line)
                if possible_to_fit_this_size and current_iter_total_height < (bg_height - margin_top_px - margin_bottom_px):
                    best_font_size = font_size_iter
                    final_renderable_lines_layout = current_iter_renderable_lines 
                    font_size_iter += 1
                else:
                    break 
        logging.info(f"Best font size for rich text: {best_font_size}")

        # --- Drawing Rich Text ---
        if best_font_size > 0 and final_renderable_lines_layout:
            # Corrected call to get_font_for_style:
            # font = get_font_for_style(best_font_size, set()) # OLD BUGGY LINE
            font = get_font_for_style(req.font_family, best_font_size, set()) # FIXED: Added req.font_family and corrected argument order
            
            # Calculate total block height from the final layout for centering
            actual_total_text_height = sum(line_info["height"] for line_info in final_renderable_lines_layout if isinstance(line_info, dict) and "height" in line_info) # Added check for dict
            
            available_height_for_text = bg_height - margin_top_px - margin_bottom_px
            padding_top_final = 0
            if actual_total_text_height > 0 and actual_total_text_height < available_height_for_text:
                padding_top_final = (available_height_for_text - actual_total_text_height) // 2
            
            current_y = margin_top_px + padding_top_final

            for line_info in final_renderable_lines_layout:
                if not line_info: # Handle explicitly empty lines from <br><br>
                    # This case needs refinement: how much height for an empty line?
                    # For now, assume it was accounted for if placeholder_font was used.
                    # If line_info is truly empty list from parser, it means a <br>
                    # We need a consistent line height. Let's use a dummy regular font for that.
                    dummy_font_for_empty_line = get_font_for_style(req.font_family, best_font_size, set())
                    empty_line_ascent, empty_line_descent = dummy_font_for_empty_line.getmetrics()
                    current_y += (empty_line_ascent + empty_line_descent)
                    continue

                line_segments = line_info["segments"]
                line_actual_height = line_info["height"] # Max ascent + max descent for this line
                line_max_ascent = line_info["max_ascent"]

                # Calculate total width of this specific line for horizontal centering
                current_line_total_width = sum(seg["width"] for seg in line_segments)
                
                start_x_for_line = margin_x_px + (width - 2 * margin_x_px - current_line_total_width) // 2
                start_x_for_line = max(margin_x_px, start_x_for_line) # Ensure left margin

                current_x_draw = start_x_for_line
                
                for segment in line_segments:
                    seg_text = segment["text"]
                    seg_font = segment["font"] # Font object already created at correct size
                    seg_styles = segment["styles"]
                    # seg_width = segment["width"] # Calculated width
                    seg_bbox = segment["bbox"] # (x1, y1, x2, y2)
                    
                    # Drawing text at (x, y) means y is the baseline for most fonts.
                    # We need to align baselines of all segments in a line.
                    # The line's y is current_y + line_max_ascent (baseline of the line)
                    # Pillow's draw.text uses (left, top_of_text_bbox_relative_to_baseline) if anchor is not set.
                    # Or, more simply, if xy is top-left, it handles baseline internally.
                    # Let's use xy as the top-left for the segment, adjusted by its ascent relative to line's max_ascent
                    # No, draw.text(xy, text) xy is the top-left corner of the text bounding box if anchor="la" (left-ascent)
                    # Default anchor is "la".
                    # xy is the position of the top-left corner of the text.
                    # To align baselines: y_pos_for_segment = baseline_y - segment_ascent
                    
                    # Simpler: draw.text's y is the point for the baseline.
                    # So, current_y + line_max_ascent is the common baseline for this line.
                    
                    # Pillow's default draw.text(xy,...) xy is the top-left of the bounding box.
                    # To align different fonts on a baseline, it's complex.
                    # A common approach: draw each segment at (current_x_draw, baseline_y - segment_ascent)
                    # This aligns the top of the ascent boxes.
                    # OR, use the baseline: current_y + line_max_ascent. Pillow text expects top-left.
                    # So, y_draw_pos = (current_y + line_max_ascent) - segment_ascent
                    
                    y_draw_pos = current_y + (line_max_ascent - segment["ascent"])

                    # Corrected drawing position:
                    # current_x_draw is the left of the segment.
                    # baseline_y is the common baseline for the line.
                    # Pillow's text() method with default anchor "la" means xy is the top-left of the text.
                    # The top of the text is at baseline_y - segment_ascent.
                    # So, draw.text at (current_x_draw, baseline_y - segment["ascent"])

                    draw.text((current_x_draw, y_draw_pos), seg_text, font=seg_font, fill="white")

                    if 'underline' in seg_styles:
                        # Underline position: just below the text. Baseline + small offset.
                        # Text bottom is baseline_y + segment_descent.
                        # Or, more simply, bottom of the bbox for this segment.
                        # bbox[3] is y2 (bottom). So, final_y_draw_pos + (seg_bbox[3]-seg_bbox[1]) is bottom of ink.
                        # Underline y should be at final_y_draw_pos + (segment_bbox[3] - seg_bbox[1]) + offset
                        # Let's try baseline + descent + offset.
                        underline_y = y_draw_pos + segment["ascent"] + 1 # 1 pixel below baseline
                        # A segment's ink bottom is at final_y_draw_pos + (seg_bbox[3] - seg_bbox[1])
                        # Let's try to place it relative to the segment's own baseline.
                        # Segment baseline is at final_y_draw_pos + segment["ascent"]
                        underline_y_pos = y_draw_pos + segment["ascent"] + 2 # Offset below baseline
                        draw.line([(current_x_draw, underline_y_pos), 
                                   (current_x_draw + segment["width"], underline_y_pos)], 
                                  fill="white", width=1) # Simple underline

                    current_x_draw += segment["width"] # Use calculated width for advancing
                
                current_y += line_actual_height # Move to the next line's top
            logging.info("Rich text drawn on overlay.")

        elif not final_renderable_lines_layout and req.text.strip():
             logging.info("Text was provided but could not be fitted into the margins with rich text.")
        else:
            logging.info("No text to draw or no fitting font size for rich text.")
            
        # Composite the overlay
        result = img.copy()
        if req.text_position == "bottom":
            position = (0, height - bg_height)
        else:
            position = (0, 0)
        result.alpha_composite(overlay, dest=position)
        logging.info("Overlay composited onto image.")

        # Prepare output
        output_buffer = io.BytesIO()
        result.save(output_buffer, format="PNG")
        output_buffer.seek(0)
        logging.info("Image saved to buffer.")
        return StreamingResponse(output_buffer, media_type="image/png")

    except requests.exceptions.RequestException as e:
        logging.error(f"Error fetching image: {e}")
        raise HTTPException(status_code=400, detail="Error fetching image from the provided URL.")
    except FileNotFoundError as e: # Should be less likely with fallbacks
        logging.error(f"Font file not found and fallback failed: {e}")
        raise HTTPException(status_code=500, detail="Critical font file not found on the server.")
    except Exception as e:
        logging.error(f"Unexpected error in caption_image: {e}", exc_info=True) # Add exc_info for traceback
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred: {str(e)}")

# ... (rest of the file, if any) ...