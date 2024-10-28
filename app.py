from flask import Flask, request, render_template_string, send_file
from PIL import Image, ImageDraw, ImageFont
from moviepy.editor import ImageSequenceClip
import docx
import cv2
import numpy as np
from io import BytesIO
import tempfile

app = Flask(__name__)

# HTML form for file uploads and settings
html_form = '''
<!DOCTYPE html>
<html>
<body>
    <h2>Handwriting Animation Creator</h2>
    <form method="POST" enctype="multipart/form-data">
        <label for="docx_file">Upload .docx File:</label><br>
        <input type="file" name="docx_file" required><br><br>
        <label for="hand_image">Upload Hand Image (PNG):</label><br>
        <input type="file" name="hand_image" required><br><br>
        <label for="font_file">Upload Font File (TTF):</label><br>
        <input type="file" name="font_file" required><br><br>
        <label for="font_size">Font Size:</label><br>
        <input type="number" name="font_size" value="30"><br><br>
        <label for="max_lines">Max Lines per Page:</label><br>
        <input type="number" name="max_lines" value="8"><br><br>
        <label for="delay_frames">Delay Frames:</label><br>
        <input type="number" name="delay_frames" value="10"><br><br>
        <label for="fps">Frames per Second (FPS):</label><br>
        <input type="number" name="fps" value="3"><br><br>
        <input type="submit" value="Generate Animation">
    </form>
</body>
</html>
'''

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        # Handle file uploads
        docx_file = request.files.get('docx_file')
        hand_image = request.files.get('hand_image')
        font_file = request.files.get('font_file')

        # Check if files are uploaded correctly
        if not docx_file or not hand_image or not font_file:
            return "All files are required: docx file, hand image, and font file.", 400

        # Animation settings
        font_size = int(request.form.get("font_size", 30))  # Reduced font size
        line_spacing = font_size + 8
        max_lines = int(request.form.get("max_lines", 8))  # Fewer lines per page
        delay_frames = int(request.form.get("delay_frames", 10))  # Reduced delay frames
        fps = int(request.form.get("fps", 3))  # Lower FPS to save memory

        # Reduced canvas size
        canvas_width, canvas_height = 640, 360

        # Load text from .docx file
        try:
            doc = docx.Document(docx_file)
            text = "\n".join([paragraph.text for paragraph in doc.paragraphs])
        except Exception as e:
            return f"Error processing .docx file: {e}", 500

        # Set up font and hand image
        try:
            font = ImageFont.truetype(BytesIO(font_file.read()), font_size)
            hand_img = Image.open(hand_image).convert("RGBA")
        except Exception as e:
            return f"Error loading font or hand image: {e}", 500

        # Prepare frames list
        frames = []
        x_start, y_start = 20, 20
        line_text = ""
        current_line = 0
        frame_text_lines = []

        # Generate frames in a memory-efficient way
        def generate_frames():
            nonlocal line_text, current_line, frame_text_lines
            for char in text:
                line_text += char
                img_pil = Image.new("RGBA", (canvas_width, canvas_height), color="white")
                draw = ImageDraw.Draw(img_pil)

                # Draw previous lines for the current page
                for j, line in enumerate(frame_text_lines):
                    draw.text((x_start, y_start + j * line_spacing), line, font=font, fill="black")

                # Draw the current line up to the current character
                draw.text((x_start, y_start + current_line * line_spacing), line_text, font=font, fill="black")

                # Calculate hand position using getbbox()
                text_width = font.getbbox(line_text)[2]
                hand_x = x_start + text_width
                hand_y = y_start + current_line * line_spacing - 5

                # Overlay the hand image onto the canvas
                img_pil.alpha_composite(hand_img.resize((30, 30)), (hand_x, hand_y))

                # Convert to BGR format for OpenCV
                frame = cv2.cvtColor(np.array(img_pil.convert("RGB")), cv2.COLOR_RGB2BGR)
                yield frame

                # Move to the next line if end of line or newline character
                if char == '\n' or font.getbbox(line_text)[2] + x_start > canvas_width - 30:
                    frame_text_lines.append(line_text)
                    line_text = ""
                    current_line += 1

                    # Add blank frames for a brief delay and reset for next page
                    if current_line >= max_lines:
                        for _ in range(delay_frames):
                            blank_frame = np.ones((canvas_height, canvas_width, 3), dtype=np.uint8) * 255
                            yield blank_frame
                        frame_text_lines = []
                        current_line = 0

            # Render any remaining frames after all characters are processed
            if line_text:
                frame_text_lines.append(line_text)
            for _ in range(delay_frames):
                img_pil = Image.new("RGB", (canvas_width, canvas_height), color="white")
                draw = ImageDraw.Draw(img_pil)
                for j, line in enumerate(frame_text_lines):
                    draw.text((x_start, y_start + j * line_spacing), line, font=font, fill="black")
                frame = cv2.cvtColor(np.array(img_pil), cv2.COLOR_RGB2BGR)
                yield frame

        # Save video to a temporary file
        try:
            temp_video_path = tempfile.mktemp(suffix=".mp4")
            clip = ImageSequenceClip(list(generate_frames()), fps=fps)
            clip.write_videofile(temp_video_path, codec="libx264")
        except Exception as e:
            return f"Error generating video: {e}", 500

        return send_file(temp_video_path, as_attachment=True, download_name="handwriting_animation.mp4", mimetype="video/mp4")

    return render_template_string(html_form)

# Enable debug mode for detailed error messages
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
