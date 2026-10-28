import streamlit as st
import requests
import fitz
import io
import json
from PIL import Image

st.set_page_config(page_title="NEO 1.5 Quality Gate", layout="wide")
st.title("Automated ISO GPS Quality Gate")

with st.sidebar:
    api_key = st.secrets.get("OPENAI_API_KEY")
    api_url = "https://api.xkiro.com/v1/chat/completions" # Direct endpoint

drawing_file = st.file_uploader("Upload Drawing", type=["png", "jpg", "jpeg", "pdf"])

if drawing_file and api_key:
    if st.button("Generate Pro Audit Report", type="primary"):
        with st.spinner("Processing..."):
            try:
                # 1. Process Image
                file_bytes = drawing_file.read()
                if drawing_file.name.lower().endswith(".pdf"):
                    doc = fitz.open(stream=file_bytes, filetype="pdf")
                    pix = doc[0].get_pixmap(matrix=fitz.Matrix(2, 2))
                    img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
                else:
                    img = Image.open(io.BytesIO(file_bytes)).convert("RGB")
                
                # 2. Raw HTTP Request (Bypasses OpenAI library issues)
                headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
                payload = {
                    "model": "google/gemini-3.6-flash",
                    "messages": [{"role": "user", "content": "Analyze drawing for ISO GPS violations. Return valid JSON only: [{'tag_id': 1, 'action': 'MODIFY', 'issue': '...', 'replacement_text': '...'}]"}]
                }
                
                response = requests.post(api_url, headers=headers, json=payload, timeout=60)
                
                if response.status_code != 200:
                    st.error(f"API Error ({response.status_code}): {response.text}")
                    st.stop()

                audit_data = json.loads(response.json()['choices'][0]['message']['content'])

                # 3. PDF generation
                pdf = fitz.open()
                p1 = pdf.new_page(width=img.width, height=img.height)
                img_bytes = io.BytesIO()
                img.save(img_bytes, format="JPEG")
                p1.insert_image(p1.rect, stream=img_bytes.getvalue())
                
                report = pdf.new_page(width=612, height=792)
                y = 50
                for item in audit_data:
                    report.insert_text((50, y), f"TAG #{item['tag_id']} | {item['action']}: {item['issue']}", fontsize=12)
                    y += 30
                    report.insert_text((50, y), f"FIX: {item['replacement_text']}", fontsize=10)
                    y += 40
                
                st.download_button("📥 Download Audit Report", data=pdf.write(), file_name="ISO_AUDIT.pdf", mime="application/pdf")
            except Exception as e:
                st.error(f"Failed: {e}")
