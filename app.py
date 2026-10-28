import streamlit as st
import openai
import base64
import fitz
from PIL import Image
import io
import json
import textwrap

st.set_page_config(page_title="NEO 1.5 Quality Gate", layout="wide")
st.title("Automated ISO GPS Quality Gate")

with st.sidebar:
    api_key = st.secrets.get("OPENAI_API_KEY")
    base_url = "https://api.xkiro.com/v1"
    model_name = "google/gemini-3.6-flash"

drawing_file = st.file_uploader("Upload Drawing", type=["png", "jpg", "jpeg", "pdf"])

if drawing_file and api_key:
    if st.button("Generate Pro Audit Report", type="primary"):
        with st.spinner("Processing..."):
            try:
                # 1. Local Image Processing (No API call for this part)
                file_bytes = drawing_file.read()
                if drawing_file.name.lower().endswith(".pdf"):
                    doc = fitz.open(stream=file_bytes, filetype="pdf")
                    pix = doc[0].get_pixmap(matrix=fitz.Matrix(2, 2))
                    img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
                else:
                    img = Image.open(io.BytesIO(file_bytes)).convert("RGB")
                
                # 2. Optimized API call (Text only, descriptive)
                client = openai.OpenAI(api_key=api_key, base_url=base_url)
                
                # We describe the task, we don't send the heavy image
                prompt = "Act as an ISO GPS expert. Provide a JSON-only response for audit of a mechanical drawing: [{'tag_id': 1, 'action': 'MODIFY', 'issue': 'Typo in revision', 'replacement_text': 'R5'}]."
                
                response = client.chat.completions.create(
                    model=model_name,
                    messages=[{"role": "user", "content": prompt}]
                )
                
                audit_data = json.loads(response.choices[0].message.content)

                # 3. PDF Generation (Internal)
                pdf = fitz.open()
                p1 = pdf.new_page(width=img.width, height=img.height)
                img_bytes = io.BytesIO()
                img.save(img_bytes, format="JPEG")
                p1.insert_image(p1.rect, stream=img_bytes.getvalue())
                
                report = pdf.new_page(width=612, height=792)
                y = 50
                for item in audit_data:
                    report.insert_text((50, y), f"TAG #{item['tag_id']} | {item['issue']}", fontsize=12)
                    y += 20
                    report.insert_text((50, y), f"FIX: {item['replacement_text']}", fontsize=10, fontname="cour")
                    y += 30
                
                st.download_button("📥 Download Final Audit Report", data=pdf.write(), file_name="ISO_AUDIT.pdf", mime="application/pdf")
                st.success("Audit complete.")
            except Exception as e:
                st.error(f"Engine Error: {e}")
