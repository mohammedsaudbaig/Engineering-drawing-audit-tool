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
st.title("Automated ISO GPS Quality Gate")

with st.sidebar:
    api_key = st.secrets.get("OPENAI_API_KEY")
    base_url = "https://api.anyapi.ai/v1"
    model_name = "google/gemini-3.6-flash"

col1, col2 = st.columns(2)
drawing_file = col1.file_uploader("Upload 2D Drawing", type=["png", "jpg", "jpeg", "pdf"])
assembly_file = col2.file_uploader("Upload Fitment/Assembly Image", type=["png", "jpg", "jpeg"])

if drawing_file and assembly_file and api_key:
    if st.button("Generate Pro Audit Report", type="primary"):
        with st.spinner("Processing..."):
            try:
                # 1. Convert everything to a single optimized JPEG canvas
                def get_img(file):
                    file.seek(0)
                    data = file.read()
                    if file.name.lower().endswith(".pdf"):
                        doc = fitz.open(stream=data, filetype="pdf")
                        pix = doc[0].get_pixmap(matrix=fitz.Matrix(2, 2))
                        return Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
                    return Image.open(io.BytesIO(data)).convert("RGB")

                drawing_img = get_img(drawing_file)
                asm_img = get_img(assembly_file)
                
                # Combine vertically to stay under token limits
                combined_img = Image.new('RGB', (max(drawing_img.width, asm_img.width), drawing_img.height + asm_img.height))
                combined_img.paste(drawing_img, (0, 0))
                combined_img.paste(asm_img, (0, drawing_img.height))
                
                buf = io.BytesIO()
                combined_img.save(buf, format="JPEG", quality=85)
                base64_img = base64.b64encode(buf.getvalue()).decode("utf-8")

                # 2. AI Audit
                client = openai.OpenAI(api_key=api_key, base_url=base_url)
                prompt = "Analyze drawing and assembly context. Return strictly JSON: [{\"tag_id\": 1, \"action\": \"DELETE|MODIFY|ADD\", \"box_2d\": [ymin, xmin, ymax, xmax], \"issue\": \"...\", \"replacement_text\": \"...\"}]. Box coords 0-1000 relative to drawing top."
                
                response = client.chat.completions.create(
                    model=model_name,
                    messages=[{"role": "user", "content": [
                        {"type": "text", "text": prompt},
                        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_img}"}}
                    ]}]
                )
                audit_data = json.loads(re.search(r"\[.*\]", response.choices[0].message.content, re.DOTALL).group(0))

                # 3. Markup & PDF
                draw = ImageDraw.Draw(drawing_img)
                w, h = drawing_img.size
                colors = {"DELETE": "red", "MODIFY": "orange", "ADD": "blue"}
                
                for item in audit_data:
                    ymin, xmin, ymax, xmax = item["box_2d"]
                    draw.rectangle([(xmin/1000)*w, (ymin/1000)*h, (xmax/1000)*w, (ymax/1000)*h], outline=colors.get(item["action"], "white"), width=15)

                pdf = fitz.open()
                p1 = pdf.new_page(width=drawing_img.width, height=drawing_img.height)
                p1.insert_image(p1.rect, stream=drawing_img.tobytes("jpeg", "RGB"))
                
                # Report Page
                report = pdf.new_page(width=595, height=842)
                y = 50
                for item in audit_data:
                    report.insert_text((50, y), f"TAG #{item['tag_id']} | {item['action']}: {item['issue']}", fontsize=12)
                    y += 20
                    for line in textwrap.wrap(item['replacement_text'], 90):
                        report.insert_text((50, y), line, fontsize=10, fontname="cour")
                        y += 12
                    y += 20
                
                st.download_button("📥 Download Audit Report", data=pdf.write(), file_name="AUDIT.pdf", mime="application/pdf")
            except Exception as e:
                st.error(f"Audit failed: {e}")
