import streamlit as st
import openai
import base64
import fitz
from PIL import Image, ImageDraw
import io
import json
import re
import textwrap

st.set_page_config(page_title="NEO 1.5 Quality Gate", layout="wide")
st.title("Automated ISO GPS Quality Gate & R&D Audit Report")

# --- UI Config ---
with st.sidebar:
    api_key = st.secrets.get("OPENAI_API_KEY")
    base_url = "https://api.xkiro.com/v1"
    model_name = "google/gemini-3.6-flash"

col1, col2 = st.columns(2)
drawing_file = col1.file_uploader("Upload 2D Drawing", type=["png", "jpg", "jpeg", "pdf"])
asm_file = col2.file_uploader("Upload Fitment/Assembly Image", type=["png", "jpg", "jpeg"])

if drawing_file and asm_file and api_key:
    if st.button("Generate Pro Audit Report", type="primary"):
        with st.spinner("Executing optimized ISO audit..."):
            try:
                # 1. Image Processing (Resize to 1024px for API stability)
                def get_optimized_img(file):
                    file.seek(0)
                    data = file.read()
                    if file.name.lower().endswith(".pdf"):
                        doc = fitz.open(stream=data, filetype="pdf")
                        pix = doc[0].get_pixmap(matrix=fitz.Matrix(2, 2))
                        img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
                    else:
                        img = Image.open(io.BytesIO(data)).convert("RGB")
                    img.thumbnail((1024, 1024)) # Critical: forces size for API
                    return img

                drawing_img = get_optimized_img(drawing_file)
                asm_img = get_optimized_img(asm_file)
                
                # Combine vertically (one image is better than two for API stability)
                combined = Image.new('RGB', (max(drawing_img.width, asm_img.width), drawing_img.height + asm_img.height))
                combined.paste(drawing_img, (0, 0))
                combined.paste(asm_img, (0, drawing_img.height))
                
                buf = io.BytesIO()
                combined.save(buf, format="JPEG", quality=85)
                b64_img = base64.b64encode(buf.getvalue()).decode("utf-8")

                # 2. AI Audit (Simplified Prompt)
                client = openai.OpenAI(api_key=api_key, base_url=base_url)
                response = client.chat.completions.create(
                    model=model_name,
                    messages=[{"role": "user", "content": [
                        {"type": "text", "text": "ISO GPS Audit. JSON only: [{\"tag_id\": 1, \"action\": \"DELETE|MODIFY|ADD\", \"box_2d\": [ymin, xmin, ymax, xmax], \"issue\": \"...\", \"replacement_text\": \"...\"}]"},
                        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64_img}"}}
                    ]}]
                )
                
                audit_data = json.loads(re.search(r"\[.*\]", response.choices[0].message.content, re.DOTALL).group(0))

                # 3. PDF Generation (Stable)
                pdf = fitz.open()
                # Page 1: Drawing
                p1 = pdf.new_page(width=drawing_img.width, height=drawing_img.height)
                p1.insert_image(p1.rect, stream=drawing_img.tobytes("jpeg", "RGB"))
                
                # Page 2+: Report
                report = pdf.new_page(width=612, height=792)
                y = 50
                for item in audit_data:
                    report.insert_text((50, y), f"TAG #{item['tag_id']} | ACTION: {item['action']}", fontsize=12, fontname="helv-bold")
                    y += 20
                    for line in textwrap.wrap(item['replacement_text'], width=80):
                        report.insert_text((50, y), line, fontsize=10, fontname="cour")
                        y += 12
                    y += 20
                
                st.download_button("📥 Download Final Audit Report", data=pdf.write(), file_name="ISO_AUDIT.pdf", mime="application/pdf")
                st.success("Audit complete.")
            except Exception as e:
                st.error(f"Engine Failure: {e}")
