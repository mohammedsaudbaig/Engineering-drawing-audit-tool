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

# --- UI Sidebar ---
with st.sidebar:
    st.header("1. Part Configuration")
    mfg_method = st.selectbox("Manufacturing Process", ["Machined", "Sheet Metal", "Welded Assembly", "Polymer/Plastic"])
    fitment_area = st.selectbox("Fitment Area", ["Stationary Frame", "Relative Motion", "Power Transmission"])
    api_key = st.secrets.get("OPENAI_API_KEY")

# --- File Uploader ---
col1, col2 = st.columns(2)
drawing_file = col1.file_uploader("Upload 2D Drawing (PDF/JPG)", type=["png", "jpg", "jpeg", "pdf"])
assembly_file = col2.file_uploader("Upload Assembly/Fitment Context Image", type=["png", "jpg", "jpeg"])

if drawing_file and assembly_file and api_key:
    if st.button("Generate Professional Audit Report", type="primary"):
        with st.spinner("Analyzing Functional Fitment..."):
            try:
                # Process Images
                def to_base64(file):
                    file_bytes = file.read()
                    if file.name.lower().endswith(".pdf"):
                        doc = fitz.open(stream=file_bytes, filetype="pdf")
                        pix = doc[0].get_pixmap(matrix=fitz.Matrix(2, 2))
                        img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
                    else:
                        img = Image.open(io.BytesIO(file_bytes)).convert("RGB")
                    buf = io.BytesIO()
                    img.save(buf, format="JPEG")
                    return base64.b64encode(buf.getvalue()).decode("utf-8"), img

                drawing_b64, drawing_img = to_base64(drawing_file)
                asm_b64, _ = to_base64(assembly_file)

                # AI Analysis
                client = openai.OpenAI(api_key=api_key, base_url="https://api.anyapi.ai/v1")
                prompt = f"""
                You are a Principal R&D Architect. 
                Task: Audit the drawing for ISO GPS violations (ISO 1101, 5459, 14405-1).
                Context: Part is a {mfg_method} used in a {fitment_area} interface.
                If tolerances/GD&T are missing, infer standard ISO 2768-mK or ISO 286 fits based on the interface.
                Return strictly JSON: 
                [{"tag_id": 1, "action": "DELETE|MODIFY|ADD", "box_2d": [ymin, xmin, ymax, xmax], "issue": "...", "replacement_text": "..."}]
                """
                
                response = client.chat.completions.create(
                    model="google/gemini-3.6-flash",
                    messages=[{"role": "user", "content": [
                        {"type": "text", "text": prompt},
                        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{drawing_b64}"}},
                        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{asm_b64}"}}
                    ]}]
                )
                audit_data = json.loads(re.search(r"\[.*\]", response.choices[0].message.content, re.DOTALL).group(0))

                # --- PDF Generation (Professional Report) ---
                output_pdf = fitz.open()
                
                # Page 1: Marked Drawing
                draw = ImageDraw.Draw(drawing_img)
                w, h = drawing_img.size
                colors = {"DELETE": "red", "MODIFY": "orange", "ADD": "blue"}
                for item in audit_data:
                    ymin, xmin, ymax, xmax = item["box_2d"]
                    draw.rectangle([(xmin/1000)*w, (ymin/1000)*h, (xmax/1000)*w, (ymax/1000)*h], outline=colors[item["action"]], width=10)
                    draw.text(((xmin/1000)*w, (ymin/1000)*h-40), f"#{item['tag_id']}", fill="black", font_size=50)

                p1 = output_pdf.new_page(width=drawing_img.width, height=drawing_img.height)
                p1.insert_image(p1.rect, stream=drawing_img.tobytes("jpeg", "RGB"))

                # Detailed Report (Page 2+)
                curr_page = output_pdf.new_page(width=595, height=842) # A4
                y = 50
                curr_page.insert_text((50, y), "R&D ISO GPS AUDIT REPORT", fontsize=20, fontname="helv-bold")
                y += 40
                
                for item in audit_data:
                    if y > 750: # Page break
                        curr_page = output_pdf.new_page(width=595, height=842)
                        y = 50
                    
                    text = f"TAG #{item['tag_id']} [{item['action']}] - {item['issue']}"
                    fix = f"FIX: {item['replacement_text']}"
                    
                    # Wrapped text
                    curr_page.insert_text((50, y), text, fontsize=12, fontname="helv-bold")
                    y += 20
                    for line in textwrap.wrap(fix, 80):
                        curr_page.insert_text((50, y), line, fontsize=10, fontname="cour")
                        y += 15
                    y += 20
                    curr_page.draw_line(fitz.Point(50, y), fitz.Point(545, y), width=0.5)
                    y += 20

                final_bytes = output_pdf.write()
                st.download_button("📥 Download Official Audit Report", data=final_bytes, file_name="R&D_AUDIT_REPORT.pdf", mime="application/pdf")
                st.success("Report generated.")

            except Exception as e:
                st.error(f"Engine Error: {e}")
