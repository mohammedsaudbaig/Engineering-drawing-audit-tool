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

# --- Sidebar ---
with st.sidebar:
    st.header("Config")
    api_key = st.secrets.get("OPENAI_API_KEY")
    base_url = "https://api.anyapi.ai/v1"
    model_name = "google/gemini-3.6-flash"

# --- Uploads ---
col1, col2 = st.columns(2)
drawing_file = col1.file_uploader("Upload 2D Drawing (PDF/JPG)", type=["png", "jpg", "jpeg", "pdf"])
assembly_file = col2.file_uploader("Upload Assembly/Fitment Context Image", type=["png", "jpg", "jpeg"])

# --- Main Logic ---
if drawing_file and assembly_file and api_key:
    if st.button("Generate Complete Audit Package", type="primary"):
        with st.spinner("Executing ISO Audit..."):
            try:
                # Helper to convert to Base64
                def file_to_b64(file):
                    file.seek(0) # Reset pointer
                    data = file.read()
                    if file.name.lower().endswith(".pdf"):
                        doc = fitz.open(stream=data, filetype="pdf")
                        pix = doc[0].get_pixmap(matrix=fitz.Matrix(2, 2))
                        img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
                    else:
                        img = Image.open(io.BytesIO(data)).convert("RGB")
                    buf = io.BytesIO()
                    img.save(buf, format="JPEG")
                    return base64.b64encode(buf.getvalue()).decode("utf-8"), img

                drawing_b64, drawing_img = file_to_b64(drawing_file)
                asm_b64, _ = file_to_b64(assembly_file)

                # AI Audit
                client = openai.OpenAI(api_key=api_key, base_url=base_url)
                
                # ESCAPED BRACES HERE: {{ }} instead of { }
                prompt = f"""
                You are an expert ISO GPS Mechanical Systems Architect.
                Analyze the drawing. Identify violations (ISO 1101, 5459, 14405-1).
                If tolerances are missing, infer standard fits based on the interface.
                Return strictly JSON: 
                [{{ "tag_id": 1, "action": "DELETE|MODIFY|ADD", "box_2d": [ymin, xmin, ymax, xmax], "issue": "ISO Rule violated", "replacement_text": "Exact text for Creo" }}].
                """
                
                response = client.chat.completions.create(
                    model=model_name,
                    messages=[{"role": "user", "content": [
                        {"type": "text", "text": prompt},
                        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{drawing_b64}"}},
                        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{asm_b64}"}}
                    ]}]
                )
                audit_data = json.loads(re.search(r"\[.*\]", response.choices[0].message.content, re.DOTALL).group(0))

                # --- PDF Markup ---
                output_pdf = fitz.open()
                draw = ImageDraw.Draw(drawing_img)
                w, h = drawing_img.size
                colors = {"DELETE": "red", "MODIFY": "orange", "ADD": "blue"}
                
                for item in audit_data:
                    ymin, xmin, ymax, xmax = item["box_2d"]
                    box = [(xmin/1000)*w, (ymin/1000)*h, (xmax/1000)*w, (ymax/1000)*h]
                    draw.rectangle(box, outline=colors.get(item["action"], "white"), width=15)
                    draw.text((box[0], box[1]-50), f"#{item['tag_id']}", fill="black", font_size=60)

                # Add Marked Image
                p1 = output_pdf.new_page(width=drawing_img.width, height=drawing_img.height)
                p1.insert_image(p1.rect, stream=drawing_img.tobytes("jpeg", "RGB"))
                
                # Add Report Pages
                for item in audit_data:
                    report_page = output_pdf.new_page(width=595, height=842)
                    report_page.insert_text((50, 50), f"AUDIT TAG #{item['tag_id']}: {item['action']}", fontsize=18)
                    report_page.insert_text((50, 80), f"ISSUE: {item['issue']}", fontsize=12)
                    report_page.insert_text((50, 110), "CREO 7.0 FIX / ISO TEXT:", fontsize=12)
                    # Safe text wrapping
                    lines = textwrap.wrap(item['replacement_text'], width=80)
                    for i, line in enumerate(lines):
                        report_page.insert_text((50, 130 + (i*15)), line, fontsize=10)

                final_bytes = output_pdf.write()
                st.download_button("📥 Download Official Audit Report", data=final_bytes, file_name="ISO_AUDIT_REPORT.pdf", mime="application/pdf")
                st.success("Audit complete.")

            except Exception as e:
                st.error(f"Engine Error: {e}")
