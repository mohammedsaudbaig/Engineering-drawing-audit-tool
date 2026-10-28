import streamlit as st
import openai
import base64
import fitz  # PyMuPDF
from PIL import Image, ImageDraw
import io
import json
import re

st.set_page_config(page_title="NEO 1.5 Quality Gate", layout="wide")
st.title("Automated ISO GPS Quality Gate & Audit Report")

with st.sidebar:
    st.header("Config")
    api_key = st.secrets.get("OPENAI_API_KEY")
    base_url = "https://api.anyapi.ai/v1"
    model_name = "google/gemini-3.6-flash"

uploaded_file = st.file_uploader("Upload Drawing", type=["png", "jpg", "jpeg", "pdf"])

if uploaded_file and api_key:
    if st.button("Generate Complete Audit Package", type="primary"):
        with st.spinner("Executing ISO Audit..."):
            try:
                # 1. Process File
                file_bytes = uploaded_file.read()
                
                if uploaded_file.name.lower().endswith(".pdf"):
                    doc = fitz.open(stream=file_bytes, filetype="pdf")
                    page = doc[0]
                    pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))
                    img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
                else:
                    img = Image.open(io.BytesIO(file_bytes)).convert("RGB")

                # 2. AI Reasoning
                buffer = io.BytesIO()
                img.save(buffer, format="JPEG")
                base64_image = base64.b64encode(buffer.getvalue()).decode("utf-8")

                client = openai.OpenAI(api_key=api_key, base_url=base_url)
                response = client.chat.completions.create(
                    model=model_name,
                    messages=[{"role": "user", "content": [
                        {"type": "text", "text": "Analyze for ISO GPS violations. Return strictly JSON: [{\"tag_id\": 1, \"action\": \"DELETE|MODIFY|ADD\", \"box_2d\": [ymin, xmin, ymax, xmax], \"issue\": \"ISO Rule violated\", \"replacement_text\": \"Exact text for Creo\"}]."},
                        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}}
                    ]}]
                )
                
                audit_data = json.loads(re.search(r"\[.*\]", response.choices[0].message.content, re.DOTALL).group(0))

                # 3. Markup
                draw = ImageDraw.Draw(img)
                w, h = img.size
                colors = {"DELETE": "red", "MODIFY": "orange", "ADD": "blue"}
                
                for item in audit_data:
                    ymin, xmin, ymax, xmax = item["box_2d"]
                    box = [(xmin/1000)*w, (ymin/1000)*h, (xmax/1000)*w, (ymax/1000)*h]
                    draw.rectangle(box, outline=colors.get(item["action"], "white"), width=10)

                # 4. Create Detailed Audit PDF using robust fitz methods
                output_pdf = fitz.open()
                
                # Page 1: Add Image
                page = output_pdf.new_page(width=img.width, height=img.height)
                page.insert_image(page.rect, stream=img.tobytes("jpeg", "RGB"))
                
                # Pages 2+: Detailed Report
                for item in audit_data:
                    report_page = output_pdf.new_page(width=595, height=842)
                    # Using standard system font handling
                    report_page.insert_text((50, 50), f"AUDIT TAG #{item['tag_id']}: {item['action']}", fontsize=20)
                    report_page.insert_text((50, 90), f"ISSUE: {item['issue']}", fontsize=12)
                    report_page.insert_text((50, 130), "CREO 7.0 FIX:", fontsize=12)
                    report_page.insert_text((50, 150), item['replacement_text'], fontsize=12)

                final_bytes = output_pdf.write()
                st.success("Audit PDF Ready!")
                st.download_button("📥 Download Final Audit Package", data=final_bytes, file_name="ISO_AUDIT_REPORT.pdf", mime="application/pdf")

            except Exception as e:
                st.error(f"Audit Engine Error: {e}")
