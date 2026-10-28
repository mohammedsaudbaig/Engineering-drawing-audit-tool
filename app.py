import streamlit as st
import openai
import base64
import fitz  # PyMuPDF
from PIL import Image
import io
import json
import re

st.set_page_config(page_title="NEO 1.5 Quality Gate", layout="wide")
st.title("Automated ISO GPS Quality Gate & Drawing Markup Engine")
st.caption("Falcon Autotech / Mobile Robotics R&D — ISO 1101, 5459, 8015, 14405-1")

with st.sidebar:
    st.header("Configuration")
    api_key = st.secrets.get("OPENAI_API_KEY")
    base_url = st.text_input("API Base URL", value="https://api.anyapi.ai/v1")
    model_name = st.text_input("Model Name", value="google/gemini-3.6-flash")
    st.divider()
    st.markdown("**Color Key:**")
    st.markdown("🔴 **RED:** Delete (Closed loop / Redundant)")
    st.markdown("🟡 **YELLOW:** Modify (Basic Box / Envelope / Syntax)")
    st.markdown("🔵 **BLUE:** Add (Datum Tag / Feature Control Frame)")

uploaded_file = st.file_uploader("Upload 2D Drawing (PDF, PNG, JPG)", type=["pdf", "png", "jpg", "jpeg"])

SYSTEM_INSTRUCTIONS = """
You are a Principal Mechanical Systems Architect and ISO GPS Quality Auditor.
Analyze the provided 2D engineering drawing image carefully.

Find all ISO GPS violations, title block conflicts, over-dimensioning loops, datum errors, and fit ambiguities.
For every defect or required improvement, estimate its bounding box coordinates on the image.

YOU MUST RESPOND ONLY WITH A VALID JSON LIST OF OBJECTS. NO PROSE, NO MARKDOWN OUTSIDE THE JSON BLOCK.
Format:
[
  {
    "tag_id": 1,
    "action": "DELETE",
    "box_2d": [ymin, xmin, ymax, xmax],
    "current_text": "e.g., 453.85 REF or closed chain dim",
    "issue": "Detailed ISO GPS violation",
    "replacement_text": "EXACT TEXT TO REPLACE OR APPLY IN CREO"
  },
  {
    "tag_id": 2,
    "action": "MODIFY",
    "box_2d": [ymin, xmin, ymax, xmax],
    "current_text": "e.g., [ Flatness | 0.1 | A ]",
    "issue": "Flatness is a form control; cannot reference Datum A (ISO 1101)",
    "replacement_text": "[ Flatness | 0.05 ] or change symbol to Parallelism [ // | 0.1 | A ]"
  },
  {
    "tag_id": 3,
    "action": "ADD",
    "box_2d": [ymin, xmin, ymax, xmax],
    "current_text": "Ø20.0 bearing journal",
    "issue": "Missing Envelope requirement and Runout control relative to axis",
    "replacement_text": "Ø20.0 k6 (E) + [ Circular Runout | 0.02 | A-B ]"
  }
]

Note on box_2d: Coordinates are normalized integers from 0 to 1000 [ymin, xmin, ymax, xmax].
action must be strictly one of: "DELETE", "MODIFY", "ADD".
"""

if uploaded_file and api_key:
    if st.button("Audit Drawing & Generate Marked PDF", type="primary"):
        try:
            with st.spinner("Extracting drawing view..."):
                file_bytes = uploaded_file.read()
                is_pdf = uploaded_file.type == "application/pdf" or uploaded_file.name.lower().endswith(".pdf")
                
                if is_pdf:
                    doc = fitz.open(stream=file_bytes, filetype="pdf")
                    page = doc[0]
                    # Render high-resolution image for AI analysis
                    pix = page.get_pixmap(dpi=200)
                    img_bytes = pix.tobytes("jpeg")
                else:
                    img_bytes = file_bytes
                    # Create an in-memory PDF from image for markup
                    img = Image.open(io.BytesIO(img_bytes)).convert("RGB")
                    pdf_bytes = io.BytesIO()
                    img.save(pdf_bytes, format="PDF")
                    doc = fitz.open(stream=pdf_bytes.getvalue(), filetype="pdf")
                    page = doc[0]

                base64_image = base64.b64encode(img_bytes).decode("utf-8")

            client = openai.OpenAI(api_key=api_key, base_url=base_url)

            with st.spinner("Analyzing drawing with ISO GPS Engine..."):
                response = client.chat.completions.create(
                    model=model_name,
                    messages=[
                        {"role": "user", "content": [
                            {"type": "text", "text": SYSTEM_INSTRUCTIONS},
                            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}}
                        ]}
                    ]
                )
                raw_content = response.choices[0].message.content.strip()

            # Clean and parse JSON response
            json_match = re.search(r"\[.*\]", raw_content, re.DOTALL)
            if json_match:
                audit_items = json.loads(json_match.group(0))
            else:
                audit_items = json.loads(raw_content)

            # Colors (RGB normalized 0-1 for PyMuPDF)
            colors = {
                "DELETE": (0.9, 0.1, 0.1),   # Red
                "MODIFY": (0.95, 0.6, 0.0),  # Yellow/Orange
                "ADD": (0.1, 0.45, 0.95)     # Blue
            }

            page_width = page.rect.width
            page_height = page.rect.height

            # Annotate Page 1 with colored boxes and tag labels
            for item in audit_items:
                tag = str(item.get("tag_id", "!"))
                action = item.get("action", "MODIFY").upper()
                box = item.get("box_2d", [0, 0, 100, 100])
                
                # Convert normalized 0-1000 coordinates to PDF coordinates
                ymin, xmin, ymax, xmax = box
                x0 = (xmin / 1000.0) * page_width
                y0 = (ymin / 1000.0) * page_height
                x1 = (xmax / 1000.0) * page_width
                y1 = (ymax / 1000.0) * page_height

                # Ensure minimum box size for small dimensions
                if (x1 - x0) < 15: x1 = x0 + 20
                if (y1 - y0) < 10: y1 = y0 + 15

                rect = fitz.Rect(x0, y0, x1, y1)
                color = colors.get(action, (0.5, 0.5, 0.5))

                # Draw bounding box rectangle
                page.draw_rect(rect, color=color, width=1.8)

                # Draw numbered Tag pill above the box
                tag_rect = fitz.Rect(x0, max(0, y0 - 12), x0 + 22, y0)
                page.draw_rect(tag_rect, color=color, fill=color)
                page.insert_text((x0 + 3, y0 - 2), f"#{tag}", fontsize=8, color=(1, 1, 1), fontname="helv")

            # Append Page 2: Structured Drawing Release Audit Sheet
            audit_page = doc.new_page(width=page_width, height=page_height)
            audit_page.insert_text((36, 40), "ISO GPS DRAWING RELEASE AUDIT REPORT", fontsize=16, fontname="hebo", color=(0.1, 0.2, 0.4))
            audit_page.insert_text((36, 56), f"Part File: {uploaded_file.name} | Total Actions Required: {len(audit_items)}", fontsize=9, color=(0.4, 0.4, 0.4))
            audit_page.draw_line(fitz.Point(36, 64), fitz.Point(page_width - 36, 64), color=(0.7, 0.7, 0.7), width=1)

            # Print audit table on Page 2
            y = 85
            for item in audit_items:
                if y > page_height - 60:
                    audit_page = doc.new_page(width=page_width, height=page_height)
                    y = 50

                action = item.get("action", "MODIFY").upper()
                c = colors.get(action, (0, 0, 0))
                tag = item.get("tag_id", "")
                curr = item.get("current_text", "")
                issue = item.get("issue", "")
                fix = item.get("replacement_text", "")

                # Tag badge
                badge = fitz.Rect(36, y - 2, 75, y + 12)
                audit_page.draw_rect(badge, color=c, fill=c)
                audit_page.insert_text((40, y + 8), f"#{tag} {action}", fontsize=8, color=(1, 1, 1), fontname="hebo")

                # Text details
                audit_page.insert_text((85, y + 8), f"Current: {curr}", fontsize=9, fontname="hebo", color=(0.1, 0.1, 0.1))
                y += 14
                audit_page.insert_text((85, y + 8), f"Defect: {issue}", fontsize=8, color=(0.3, 0.3, 0.3))
                y += 12
                audit_page.insert_text((85, y + 8), f"Creo 7.0 Fix: {fix}", fontsize=9, fontname="hebo", color=(0.0, 0.4, 0.1))
                y += 18
                audit_page.draw_line(fitz.Point(36, y - 4), fitz.Point(page_width - 36, y - 4), color=(0.9, 0.9, 0.9), width=0.5)

            # Generate final marked-up PDF
            marked_pdf_bytes = doc.write()

            st.success(f"Audit Complete! Identified {len(audit_items)} design improvements.")

            # Download Button
            st.download_button(
                label="📥 Download Marked-up Drawing (PDF with Red-Lines)",
                data=marked_pdf_bytes,
                file_name=f"AUDITED_{uploaded_file.name}.pdf",
                mime="application/pdf",
                type="primary"
            )

            # Display side-by-side view in the browser
            col1, col2 = st.columns([1.2, 1.0])

            with col1:
                st.subheader("Marked-Up Drawing Preview")
                preview_pix = page.get_pixmap(dpi=150)
                st.image(preview_pix.tobytes("jpeg"), use_container_width=True)

            with col2:
                st.subheader("Creo 7.0 Execution Checklist")
                for item in audit_items:
                    action = item.get("action", "MODIFY").upper()
                    tag = item.get("tag_id", "")
                    icon = "🔴" if action == "DELETE" else ("🟡" if action == "MODIFY" else "🔵")
                    
                    with st.expander(f"{icon} #{tag} [{action}] {item.get('current_text', '')}", expanded=True):
                        st.markdown(f"**Issue:** {item.get('issue', '')}")
                        st.markdown(f"**Exact Creo Replacement:**")
                        st.code(item.get("replacement_text", ""), language="text")

        except Exception as e:
            st.error(f"Processing Error: {str(e)}")
            st.info("Check if your API key balance is active and the selected model supports vision.")
