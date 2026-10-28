import streamlit as st
import google.generativeai as genai
from PIL import Image
import io
import fitz
import json

st.set_page_config(page_title="NEO 1.5 Quality Gate", layout="wide")
st.title("Automated ISO GPS Quality Gate")

# 1. Config: Use Gemini native SDK
with st.sidebar:
    api_key = st.secrets.get("GEMINI_API_KEY")
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel('gemini-1.5-flash') # Native, stable model

drawing_file = st.file_uploader("Upload Drawing", type=["png", "jpg", "jpeg", "pdf"])

if drawing_file and api_key:
    if st.button("Generate Pro Audit Report"):
        with st.spinner("Processing..."):
            try:
                # Process File
                file_bytes = drawing_file.read()
                if drawing_file.name.lower().endswith(".pdf"):
                    doc = fitz.open(stream=file_bytes, filetype="pdf")
                    pix = doc[0].get_pixmap(matrix=fitz.Matrix(2, 2))
                    img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
                else:
                    img = Image.open(io.BytesIO(file_bytes)).convert("RGB")
                
                # Native Generation
                prompt = "Analyze this drawing for ISO GPS violations (ISO 1101, 5459, 14405-1). Return STRICT JSON format: [{\"tag_id\": 1, \"action\": \"DELETE|MODIFY|ADD\", \"box_2d\": [ymin, xmin, ymax, xmax], \"issue\": \"...\", \"replacement_text\": \"...\"}]"
                
                response = model.generate_content([prompt, img])
                audit_data = json.loads(response.text.replace("```json", "").replace("```", "").strip())

                # PDF Report (Internal)
                pdf = fitz.open()
                p1 = pdf.new_page(width=img.width, height=img.height)
                img_buf = io.BytesIO()
                img.save(img_buf, format="JPEG")
                p1.insert_image(p1.rect, stream=img_buf.getvalue())
                
                report = pdf.new_page(width=595, height=842)
                y = 50
                for item in audit_data:
                    report.insert_text((50, y), f"TAG #{item['tag_id']} | {item['issue']}", fontsize=12)
                    y += 30
                    report.insert_text((50, y), f"FIX: {item['replacement_text']}", fontsize=10)
                    y += 40
                
                st.download_button("📥 Download Report", data=pdf.write(), file_name="AUDIT.pdf", mime="application/pdf")
                st.success("Audit complete.")
            except Exception as e:
                st.error(f"Engine Failure: {e}")
