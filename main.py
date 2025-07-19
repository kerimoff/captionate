from fastapi import FastAPI, Query, BackgroundTasks
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from typing import Literal, Set, List, Union, Optional
from PIL import Image, ImageDraw, ImageFont, ImageEnhance
import requests
import io
import html
from bs4 import BeautifulSoup
from bs4.element import NavigableString
from fastapi.exceptions import HTTPException
import logging
import re
import base64
import os
from typing import Optional
from dotenv import load_dotenv
from dropbox.files import WriteMode
from dropbox.exceptions import ApiError
from video_generator_parameterized import create_video_with_parameters
from scripts.dropbox_utils import get_dbx_client, upload_and_get_temporary_link as upload_and_get_link

load_dotenv()

app = FastAPI()

logging.basicConfig(level=logging.INFO)
logging.getLogger("PIL").setLevel(logging.WARNING)

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
        "Regular": f"{GOOGLE_FONTS_BASE_DIR}/Poppins/Poppins-Regular.ttf",
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
    texts: List[str] = Field(default=[""], alias="text", description="List of texts to render. Supports <b>, <i>, <u>, and <br> tags for formatting.")
    font_family: Literal["Montserrat", "Nunito", "Poppins", "Roboto"] = Field(default="Montserrat", description="Font family to use for the text.")
    text_position: Literal["top", "bottom"] = "bottom"
    background_height: float = Field(default=0.4, ge=0.0, le=1.0)
    background_color: str = "rgba(0, 0, 0, 180)"
    margin_horizontal: int = Field(default=10, ge=0)
    margin_top: int = Field(default=10, ge=0)
    margin_bottom: int = Field(default=10, ge=0)
    transition_proportion: float = Field(default=0.2, ge=0.0, le=1.0)
    dropbox_dir: Optional[str] = None


class VideoGenerationRequest(BaseModel):
    dropbox_folder_path: str
    local_folder_path: Optional[str] = None
    audio_dropbox_path: Optional[str] = None
    save_to_dropbox: bool = False
    video_duration_per_text: float = 5.0
    fade_duration: float = 0.5
    line_horizontal_margin: int = 20
    line_bottom_margin: int = 20
    line_thickness: int = 3
    line_color: str = "#FFFF00"
    fps: int = 30
    codec: str = 'libx264'
    line_segments_per_second: int = 30


def upload_and_get_temporary_link(file_content: bytes, dropbox_path: str) -> Optional[str]:
    try:
        dbx = get_dbx_client()
        return upload_and_get_link(dbx, file_content, dropbox_path)
    except Exception as e:
        logging.error(f"Failed to get Dropbox client or upload: {e}")
        return None


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
    
    if not font_path:
        font_path = family_map.get("Regular", DEFAULT_FALLBACK_STYLE_PATH)

    try:
        return ImageFont.truetype(font_path, base_size)
    except IOError as e:
        logging.warning(f"Failed to load font {font_path} for family {font_family_name} at size {base_size}: {e}. Attempting fallbacks.")
        if font_path != family_map.get("Regular"):
            try:
                regular_path = family_map.get("Regular", DEFAULT_FALLBACK_STYLE_PATH)
                logging.info(f"Falling back to {regular_path} for family {font_family_name}.")
                return ImageFont.truetype(regular_path, base_size)
            except IOError as e_reg:
                logging.warning(f"Failed to load regular style {family_map.get('Regular')} for {font_family_name}: {e_reg}")
        
        if font_path != DEFAULT_FALLBACK_STYLE_PATH and family_map.get("Regular") != DEFAULT_FALLBACK_STYLE_PATH:
            try:
                logging.info(f"Falling back to default application font: {DEFAULT_FALLBACK_STYLE_PATH}.")
                return ImageFont.truetype(DEFAULT_FALLBACK_STYLE_PATH, base_size)
            except IOError as e_default_fallback:
                logging.error(f"Default fallback font {DEFAULT_FALLBACK_STYLE_PATH} also failed: {e_default_fallback}")

        # Last resort: try to create a basic font
        try:
            return ImageFont.truetype("arial.ttf", base_size)
        except IOError:
            try:
                return ImageFont.truetype("/System/Library/Fonts/Arial.ttf", base_size)
            except IOError:
                logging.error("All font fallbacks failed including system fonts.")
                raise Exception("Unable to load any font")


def parse_html_text(html_text: str) -> list[list[tuple[str, Set[str]]]]:
    text_to_parse = html.unescape(html_text)
    soup = BeautifulSoup(text_to_parse, "html.parser")
    
    logical_lines: list[list[tuple[str, Set[str]]]] = [[]]
    active_styles: Set[str] = set()

    def process_node(node):
        nonlocal logical_lines, active_styles
        if isinstance(node, NavigableString):
            content = str(node)
            if content:
                logical_lines[-1].append((content, active_styles.copy()))
        elif node.name == 'br':
            logical_lines.append([])
        elif node.name in ['b', 'i', 'u']:
            style_map = {'b': 'bold', 'i': 'italic', 'u': 'underline'}
            style = style_map[node.name]
            
            original_style_present = style in active_styles
            if not original_style_present:
                active_styles.add(style)
            
            for child in node.children:
                process_node(child)
            
            if not original_style_present:
                active_styles.remove(style)
        elif node.name and node.name not in ['html', 'body']:
            for child in node.children:
                process_node(child)

    for child_node in soup.children:
        process_node(child_node)

    if len(logical_lines) > 1 and not logical_lines[-1]:
         logical_lines.pop()
    if not any(seg[0].strip() for line in logical_lines for seg in line):
        return [[]]

    return logical_lines

def rgba_from_string(rgba_str: str) -> tuple[int, int, int, int]:
    try:
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
        
        if '.' in a_str and 0.0 <= a_float <= 1.0:
            if len(a_str) > 1 and a_str != "0" and a_str != "1":
                 a = int(round(a_float * 255.0))
            else:
                 a = int(round(a_float))

        else:
            a = int(round(a_float))
            
        return (
            max(0, min(255, r)),
            max(0, min(255, g)),
            max(0, min(255, b)),
            max(0, min(255, a))
        )
    except Exception as e:
        logging.error(f"Error parsing RGBA string '{rgba_str}': {e}. Using default fallback color.")
        return (0, 0, 0, 180)


def _generate_background_once(
    original_img: Image.Image,
    text_position: Literal["top", "bottom"],
    background_height: float,
    background_color: str,
    transition_proportion: float
) -> dict[str, Union[str, Image.Image]]:
    img = original_img.copy()
    width, height = img.size

    bg_height = int(height * background_height)
    
    base_r, base_g, base_b, base_a = rgba_from_string(background_color)
    overlay = Image.new("RGBA", (width, bg_height), (base_r, base_g, base_b, base_a))
    
    transition_height_px = int(round(bg_height * transition_proportion))
    if transition_height_px > 0 and bg_height > 0:
        pixels = overlay.load()
        if pixels is None:
            logging.warning("Failed to load overlay pixels for gradient transition")
        else:
            if text_position == "bottom":
                for y_coord in range(transition_height_px):
                    if transition_height_px == 1:
                        alpha_factor = 0.0 
                    else:
                        alpha_factor = y_coord / (transition_height_px - 1.0)
                    
                    current_alpha = int(round(base_a * alpha_factor))
                    for x_coord in range(width):
                        pixels[x_coord, y_coord] = (base_r, base_g, base_b, current_alpha)
            
            elif text_position == "top":
                transition_zone_start_y = bg_height - transition_height_px
                for y_idx, y_coord in enumerate(range(transition_zone_start_y, bg_height)):
                    if transition_height_px == 1:
                        alpha_factor = 0.0
                    else:
                        alpha_factor = (transition_height_px - 1.0 - y_idx) / (transition_height_px - 1.0)
                    
                    current_alpha = int(round(base_a * alpha_factor))
                    for x_coord in range(width):
                        pixels[x_coord, y_coord] = (base_r, base_g, base_b, current_alpha)

    background_only_img = img.copy()
    if text_position == "bottom":
        position = (0, height - bg_height)
    else:
        position = (0, 0)
    background_only_img.alpha_composite(overlay, dest=position)

    bg_output_buffer = io.BytesIO()
    background_only_img.save(bg_output_buffer, format="PNG")
    bg_output_buffer.seek(0)
    background_only_b64 = base64.b64encode(bg_output_buffer.getvalue()).decode('utf-8')

    return {
        "background_only_b64": background_only_b64,
        "overlay_image": overlay
    }


def _generate_text_and_combined_image_from_background(
    original_img: Image.Image,
    overlay_image: Image.Image,
    text_content: str,
    font_family: Literal["Montserrat", "Nunito", "Poppins", "Roboto"],
    text_position: Literal["top", "bottom"],
    background_height: float,
    margin_horizontal: int,
    margin_top: int,
    margin_bottom: int,
) -> dict[str, str]:
    img = original_img.copy()
    width, height = img.size
    bg_height = int(height * background_height)
    margin_x_px = int((margin_horizontal / 100) * width / 2)
    margin_top_px = int((margin_top / 100) * bg_height)
    margin_bottom_px = int((margin_bottom / 100) * bg_height)

    text_only_overlay = Image.new("RGBA", (width, bg_height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(text_only_overlay)
    
    logical_lines_styled = parse_html_text(text_content)

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
                    placeholder_font = get_font_for_style(font_family, font_size_iter, set())
                    ph_ascent, ph_descent = placeholder_font.getmetrics()
                    current_iter_total_height += (ph_ascent + ph_descent)
                    current_iter_renderable_lines.append([]) 
                    continue

                for unit_text, styles_unit in drawable_units:
                    font_obj = get_font_for_style(font_family, font_size_iter, styles_unit)
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

    if best_font_size > 0 and final_renderable_lines_layout:
        font = get_font_for_style(font_family, best_font_size, set())
        
        actual_total_text_height = sum(line_info["height"] for line_info in final_renderable_lines_layout if isinstance(line_info, dict) and "height" in line_info)
        
        available_height_for_text = bg_height - margin_top_px - margin_bottom_px
        padding_top_final = 0
        if actual_total_text_height > 0 and actual_total_text_height < available_height_for_text:
            padding_top_final = (available_height_for_text - actual_total_text_height) // 2
        
        current_y = margin_top_px + padding_top_final

        for line_info in final_renderable_lines_layout:
            if not line_info:
                dummy_font_for_empty_line = get_font_for_style(font_family, best_font_size, set())
                empty_line_ascent, empty_line_descent = dummy_font_for_empty_line.getmetrics()
                current_y += (empty_line_ascent + empty_line_descent)
                continue

            line_segments = line_info["segments"]
            line_actual_height = line_info["height"]
            line_max_ascent = line_info["max_ascent"]

            current_line_total_width = sum(seg["width"] for seg in line_segments)
            
            start_x_for_line = margin_x_px + (width - 2 * margin_x_px - current_line_total_width) // 2
            start_x_for_line = max(margin_x_px, start_x_for_line)

            current_x_draw = start_x_for_line
            
            for segment in line_segments:
                seg_text = segment["text"]
                seg_font = segment["font"]
                seg_styles = segment["styles"]
                
                y_draw_pos = current_y + (line_max_ascent - segment["ascent"])

                draw.text((current_x_draw, y_draw_pos), seg_text, font=seg_font, fill="white")

                if 'underline' in seg_styles:
                    underline_y_pos = y_draw_pos + segment["ascent"] + 2
                    draw.line([(current_x_draw, underline_y_pos), 
                               (current_x_draw + segment["width"], underline_y_pos)], 
                              fill="white", width=1)

                current_x_draw += segment["width"]
            
            current_y += line_actual_height
    
    text_output_buffer = io.BytesIO()
    text_only_overlay.save(text_output_buffer, format="PNG")
    text_output_buffer.seek(0)
    text_only_b64 = base64.b64encode(text_output_buffer.getvalue()).decode('utf-8')

    final_overlay_with_text = overlay_image.copy()
    final_overlay_with_text.alpha_composite(text_only_overlay, (0, 0))

    final_combined_img = img.copy()
    if text_position == "bottom":
        position = (0, height - bg_height)
    else:
        position = (0, 0)
    final_combined_img.alpha_composite(final_overlay_with_text, dest=position)

    final_output_buffer = io.BytesIO()
    final_combined_img.save(final_output_buffer, format="PNG")
    final_output_buffer.seek(0)
    final_combined_b64 = base64.b64encode(final_output_buffer.getvalue()).decode('utf-8')

    result = {
        "text_only": text_only_b64,
        "final_combined": final_combined_b64
    }
    return result

@app.get("/test")
def test_endpoint():
    return {"message": "Server is running updated code with three image outputs", "timestamp": "2025-07-17"}

@app.post("/caption-image")
def caption_image(req: CaptionRequest):
    try:
        logging.info(f"Received request: {req}")

        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }
        response = requests.get(req.image_url, headers=headers)
        response.raise_for_status()
        original_img = Image.open(io.BytesIO(response.content)).convert("RGBA")

        background_data = _generate_background_once(
            original_img=original_img,
            text_position=req.text_position,
            background_height=req.background_height,
            background_color=req.background_color,
            transition_proportion=req.transition_proportion
        )
        overlay_image = background_data["overlay_image"]
        
        if not isinstance(overlay_image, Image.Image):
            raise TypeError("Generated overlay is not a valid PIL Image")

        results = []
        for i, text_content in enumerate(req.texts):
            try:
                captioned_images = _generate_text_and_combined_image_from_background(
                    original_img=original_img,
                    overlay_image=overlay_image,
                    text_content=text_content,
                    font_family=req.font_family,
                    text_position=req.text_position,
                    background_height=req.background_height,
                    margin_horizontal=req.margin_horizontal,
                    margin_top=req.margin_top,
                    margin_bottom=req.margin_bottom,
                )

                if req.dropbox_dir:
                    text_only_link = upload_and_get_temporary_link(
                        base64.b64decode(captioned_images["text_only"]),
                        f"{req.dropbox_dir}/text_only/text_{i+1:02d}_text.png"
                    )
                    final_combined_link = upload_and_get_temporary_link(
                        base64.b64decode(captioned_images["final_combined"]),
                        f"{req.dropbox_dir}/final_combined/text_{i+1:02d}_combined.png"
                    )
                    results.append({
                        "success": True, 
                        "text_only": text_only_link, 
                        "final_combined": final_combined_link
                    })
                else:
                    results.append({
                        "success": True, 
                        "text_only": captioned_images["text_only"], 
                        "final_combined": captioned_images["final_combined"]
                    })
            except Exception as e:
                logging.error(f"Error processing text '{text_content}': {e}", exc_info=True)
                results.append({"success": False, "error": str(e)})
        
        if req.dropbox_dir:
            background_link = None
            background_b64 = background_data.get("background_only_b64")
            if isinstance(background_b64, str):
                background_link = upload_and_get_temporary_link(
                    base64.b64decode(background_b64),
                    f"{req.dropbox_dir}/background.png"
                )
            return {
                "background_only": background_link,
                "images": results
            }
        else:
            return {
                "background_only": background_data["background_only_b64"],
                "images": results
            }

    except requests.exceptions.RequestException as e:
        logging.error(f"Error fetching image: {e}")
        raise HTTPException(status_code=400, detail="Error fetching image from the provided URL.")
    except Exception as e:
        logging.error(f"Unexpected error in caption_image: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred: {str(e)}")


@app.post("/generate-video")
async def generate_video(req: VideoGenerationRequest, background_tasks: BackgroundTasks):
    background_tasks.add_task(
        create_video_with_parameters,
        dropbox_folder_path=req.dropbox_folder_path,
        audio_dropbox_path=req.audio_dropbox_path,
        local_folder_path=req.local_folder_path,
        save_to_dropbox=req.save_to_dropbox,
        video_duration_per_text=req.video_duration_per_text,
        fade_duration=req.fade_duration,
        line_horizontal_margin=req.line_horizontal_margin,
        line_bottom_margin=req.line_bottom_margin,
        line_thickness=req.line_thickness,
        line_color=req.line_color,
        fps=req.fps,
        codec=req.codec,
        line_segments_per_second=req.line_segments_per_second,
    )

    response_data = {
        "message": "Video generation started in the background."
    }

    if req.save_to_dropbox:
        video_name = "moviepy_output.mp4"
        response_data["dropbox_video_path"] = f"{req.dropbox_folder_path.rstrip('/')}/{video_name}"
    else:
        response_data["local_video_path"] = "media/videos/moviepy_output.mp4"

    return response_data
