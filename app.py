import streamlit as st
import openai
import base64
import fitz
from PIL import Image, ImageDraw, ImageOps
import io
import json
import re
import textwrap

st.set_page_config(page_title="NEO 1.5 Quality Gate", layout="wide")
st.title("Automated ISO GPS Quality Gate & R&D Audit Report")

with st.sidebar:
    api_key = st.secrets.get("OPENAI_API_KEY")
    base_url = "https://api.anyapi.ai/v1"
    model_name = "google/gemini-3.6-flash"

col1, col2 = st.columns(2)
drawing_file = col1.file_uploader("Upload 2D Drawing", type=["png", "jpg", "jpeg", "pdf"])
asm_file = col2.file_uploader("Upload Fitment/Assembly Image", type=["png", "jpg", "jpeg"])

if drawing_file and asm_file and api_key:
    if st.button("Generate Pro Audit Report", type="primary"):
        with st.spinner("Executing deep engineering audit..."):
            try:
                # High-Fidelity Image Processing (300 DPI)
                def get_hi_res(file):
                    file.seek(0)
                    data = file.read()
                    if file.name.lower().endswith(".pdf"):
                        doc = fitz.open(stream=data, filetype="pdf")
                        pix = doc[0].get_pixmap(matrix=fitz.Matrix(4, 4)) # Ultra-High Res
                        return Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
                    return Image.open(io.BytesIO(data)).convert("RGB")

                drawing_img = get_hi_res(drawing_file)
                asm_img = get_hi_res(asm_file)
                
                # Canvas preparation
                buf = io.BytesIO()
                drawing_img.save(buf, format="JPEG", quality=95)
                b64_img = base64.b64encode(buf.getvalue()).decode("utf-8")

                client = openai.OpenAI(api_key=api_key, base_url=base_url)
                
                # Strict Audit Prompt
                prompt = """
                You are a Senior R&D Architect performing a critical ISO GPS audit.
                Analyze the drawing image and assembly context.
                Identify at least 5 distinct ISO 1101/5459/14405-1 violations.
                Ignore shallow revision issues; focus on GD&T, datum selection, and dimensioning loops.
                Return strictly JSON format: 
                [{"tag_id": 1, "action": "DELETE|MODIFY|ADD", "box_2d": [ymin, xmin, ymax, xmax], "issue": "Professional engineering explanation of the rule violation", "replacement_text": "Exact ISO-compliant text to paste in Creo"}]
                """
                
                response = client.chat.completions.create(
                    model=model_name,
                    messages=[{"role": "user", "content": [
                        {"type": "text", "text": prompt},
                        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64_img}"}}
                    ]}]
                )
                
                audit_data = json.loads(re.search(r"\[.*\]", response.choices[0].message.content, re.DOTALL).group(0))

                # Graphic Overlay
                draw = ImageDraw.Draw(drawing_img)
                w, h = drawing_img.size
                for item in audit_data:
                    ymin, xmin, ymax, xmax = item["box_2d"]
                    # Thick, crisp lines
                    draw.rectangle([(xmin/1000)*w, (ymin/1000)*h, (xmax/1000)*w, (ymax/1000)*h], outline="red", width=20)
                    draw.text(((xmin/1000)*w, (ymin/1000)*h-80), f"#{item['tag_id']}", fill="red", font_size=100)

                # PDF Generation (High Quality)
                pdf = fitz.open()
                p1 = pdf.new_page(width=drawing_img.width, height=drawing_img.height)
                p1.insert_image(p1.rect, stream=drawing_img.tobytes("jpeg", "RGB"))
                
                # Correctly structured report page
                report = pdf.new_page(width=612, height=792) # Letter size
                report.insert_text((50, 50), "ISO GPS ENGINEERING AUDIT REPORT", fontsize=24, fontname="helv-bold")
                
                y = 100
                for item in audit_data:
                    if y > 700:
                        report = pdf.new_page(width=612, height=792)
                        y = 50
                    report.insert_text((50, y), f"TAG #{item['tag_id']} - {item['action']}", fontsize=14, fontname="helv-bold")
                    y += 20
                    report.insert_text((50, y), f"ISSUE: {item['issue']}", fontsize=12)
                    y += 20
                    report.insert_text((50, y), f"CREO FIX:", fontsize=12, color=(0,0.5,0))
                    y += 15
                    for line in textwrap.wrap(item['replacement_text'], width=100):
                        report.insert_text((50, y), line, fontsize=10, fontname="cour")
                        y += 12
                    y += 30

                st.download_button("📥 Download Final Audit Report", data=pdf.write(), file_name="ISO_AUDIT.pdf", mime="application/pdf")
                st.success("Audit complete.")
            except Exception as e:
                st.error(f"Audit Engine Failure: {e}")
