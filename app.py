import streamlit as st
import openai
import base64
import fitz
from PIL import Image, ImageDraw, ImageFont
import io
import json
import re

st.set_page_config(page_title="NEO 1.5 Quality Gate", layout="wide")
st.title("Automated ISO GPS Quality Gate")

# Helper: PDF to Image
def pdf_to_image(file_bytes):
    doc = fitz.open(stream=file_bytes, filetype="pdf")
    pix = doc.load_page(0).get_pixmap(matrix=fitz.Matrix(2, 2))
    return Image.frombytes("RGB", [pix.width, pix.height], pix.samples)

with st.sidebar:
    st.header("Config")
    api_key = st.secrets.get("OPENAI_API_KEY")
    base_url = "https://api.anyapi.ai/v1"
    model_name = "google/gemini-3.6-flash"

uploaded_file = st.file_uploader("Upload Drawing", type=["png", "jpg", "jpeg", "pdf"])

if uploaded_file and api_key:
    if st.button("Generate Marked-Up Audit PDF", type="primary"):
        with st.spinner("Analyzing and marking up drawing..."):
            try:
                file_bytes = uploaded_file.read()
                img = pdf_to_image(file_bytes) if uploaded_file.name.lower().endswith(".pdf") else Image.open(io.BytesIO(file_bytes)).convert("RGB")
                
                # Prepare for AI
                buffer = io.BytesIO()
                img.save(buffer, format="JPEG")
                base64_image = base64.b64encode(buffer.getvalue()).decode("utf-8")

                # AI Audit
                client = openai.OpenAI(api_key=api_key, base_url=base_url)
                response = client.chat.completions.create(
                    model=model_name,
                    messages=[{"role": "user", "content": [
                        {"type": "text", "text": "Analyze this drawing for ISO GPS violations. Return strictly JSON: [{\"tag_id\": 1, \"action\": \"DELETE|MODIFY|ADD\", \"box_2d\": [ymin, xmin, ymax, xmax], \"issue\": \"...\", \"replacement_text\": \"...\"}]. Box coords 0-1000."},
                        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}}
                    ]}]
                )
                
                raw = response.choices[0].message.content.replace("```json", "").replace("```", "").strip()
                items = json.loads(raw)

                # MARKUP ENGINE
                draw = ImageDraw.Draw(img)
                w, h = img.size
                colors = {"DELETE": "red", "MODIFY": "orange", "ADD": "blue"}

                for item in items:
                    ymin, xmin, ymax, xmax = item["box_2d"]
                    box = [ (xmin/1000)*w, (ymin/1000)*h, (xmax/1000)*w, (ymax/1000)*h ]
                    draw.rectangle(box, outline=colors.get(item["action"], "white"), width=5)
                    draw.text((box[0], box[1]-20), f"#{item['tag_id']} {item['action']}", fill=colors.get(item["action"], "white"))

                # Create downloadable PDF
                pdf_buffer = io.BytesIO()
                img.save(pdf_buffer, format="PDF")
                
                st.image(img, use_container_width=True)
                st.download_button("📥 Download Marked-Up PDF", data=pdf_buffer.getvalue(), file_name="AUDITED_DRAWING.pdf", mime="application/pdf")
                
                st.subheader("Audit Log")
                for item in items:
                    st.write(f"**{item['action']} #{item['tag_id']}**: {item['issue']}")
                    st.code(item['replacement_text'])

            except Exception as e:
                st.error(f"Failed: {e}")
