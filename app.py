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
    st.header("Config")
    api_key = st.secrets.get("OPENAI_API_KEY")
    base_url = "https://api.anyapi.ai/v1"
    model_name = "google/gemini-3.6-flash"

col1, col2 = st.columns(2)
drawing_file = col1.file_uploader("Upload 2D Drawing", type=["png", "jpg", "jpeg", "pdf"])
assembly_file = col2.file_uploader("Upload Fitment/Assembly Image", type=["png", "jpg", "jpeg"])

if drawing_file and assembly_file and api_key:
    if st.button("Generate Pro Audit Report", type="primary"):
        with st.spinner("Executing high-fidelity ISO audit..."):
            try:
                # 1. High-Res Image Prep
                def get_img(file):
                    file.seek(0)
                    data = file.read()
                    if file.name.lower().endswith(".pdf"):
                        doc = fitz.open(stream=data, filetype="pdf")
                        pix = doc[0].get_pixmap(matrix=fitz.Matrix(3, 3)) # 3x Resolution
                        return Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
                    return Image.open(io.BytesIO(data)).convert("RGB")

                img = get_img(drawing_file)
                asm_b64 = base64.b64encode(get_img(assembly_file).tobytes()).decode("utf-8")
                
                # 2. AI Audit
                draw_buf = io.BytesIO()
                img.save(draw_buf, format="JPEG")
                draw_b64 = base64.b64encode(draw_buf.getvalue()).decode("utf-8")
                
                client = openai.OpenAI(api_key=api_key, base_url=base_url)
                prompt = f"""Analyze for ISO GPS violations. Return strictly JSON: 
                [{{ "tag_id": 1, "action": "DELETE|MODIFY|ADD", "box_2d": [ymin, xmin, ymax, xmax], "issue": "...", "replacement_text": "..." }}]."""
                
                response = client.chat.completions.create(
                    model=model_name,
                    messages=[{"role": "user", "content": [
                        {"type": "text", "text": prompt},
                        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{draw_b64}"}},
                        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{asm_b64}"}}
                    ]}]
                )
                audit_data = json.loads(re.search(r"\[.*\]", response.choices[0].message.content, re.DOTALL).group(0))

                # 3. Graphics Engine
                draw = ImageDraw.Draw(img)
                w, h = img.size
                colors = {"DELETE": (255, 0, 0), "MODIFY": (255, 165, 0), "ADD": (0, 0, 255)}
                
                for item in audit_data:
                    ymin, xmin, ymax, xmax = item["box_2d"]
                    box = [(xmin/1000)*w, (ymin/1000)*h, (xmax/1000)*w, (ymax/1000)*h]
                    draw.rectangle(box, outline=colors[item["action"]], width=15)
                    draw.text((box[0]+20, box[1]-50), f"#{item['tag_id']}", fill="black", font_size=80)

                # 4. Generate Professional PDF
                pdf = fitz.open()
                # Page 1: Drawing
                p1 = pdf.new_page(width=img.width, height=img.height)
                p1.insert_image(p1.rect, stream=img.tobytes("jpeg", "RGB"))
                
                # Report Page: Multi-item layout
                report = pdf.new_page(width=595, height=842)
                report.insert_text((50, 50), "ENGINEERING ISO GPS AUDIT SUMMARY", fontsize=20, color=(0.1, 0.3, 0.6))
                y = 100
                for item in audit_data:
                    if y > 750: # Page break
                        report = pdf.new_page(width=595, height=842)
                        y = 50
                    # Action Box
                    report.draw_rect(fitz.Rect(50, y, 545, y+50), color=(0.9, 0.9, 0.9), fill=(0.9, 0.9, 0.9))
                    report.insert_text((60, y+20), f"TAG #{item['tag_id']} | ACTION: {item['action']}", fontsize=12, fontname="helv-bold")
                    y += 60
                    report.insert_text((60, y), f"ISSUE: {item['issue']}", fontsize=10)
                    y += 20
                    report.insert_text((60, y), f"CREO FIX:", fontsize=10, color=(0, 0.5, 0))
                    y += 15
                    for line in textwrap.wrap(item['replacement_text'], width=90):
                        report.insert_text((60, y), line, fontsize=9, fontname="cour")
                        y += 12
                    y += 30

                st.download_button("📥 Download Marked-Up Audit Package", data=pdf.write(), file_name="R&D_AUDIT_REPORT.pdf", mime="application/pdf")
                st.success("High-fidelity report ready.")
            except Exception as e:
                st.error(f"Error: {e}")
