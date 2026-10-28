import streamlit as st
import openai
import base64
import fitz  # PyMuPDF
from PIL import Image
import io
import json
import re

st.set_page_config(page_title="Quality Gate", layout="wide")
st.title("Automated ISO GPS Quality Gate")

with st.sidebar:
    st.header("Configuration")
    api_key = st.secrets.get("OPENAI_API_KEY")
    base_url = st.text_input("API Base URL", value="https://api.xkiro.com/v1")
    model_name = st.text_input("Model Name", value="google/gemini-3.6-flash")

uploaded_file = st.file_uploader("Upload Drawing", type=["png", "jpg", "jpeg", "pdf"])

if uploaded_file and api_key:
    if st.button("Generate Audit Report", type="primary"):
        try:
            with st.spinner("Processing file..."):
                file_bytes = uploaded_file.read()
                
                # Robust Conversion: PDF to Image using fitz more safely
                if uploaded_file.name.lower().endswith(".pdf"):
                    doc = fitz.open(stream=file_bytes, filetype="pdf")
                    page = doc.load_page(0) 
                    pix = page.get_pixmap(matrix=fitz.Matrix(2, 2)) # 2x zoom for clarity
                    img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
                    buffer = io.BytesIO()
                    img.save(buffer, format="JPEG")
                    img_bytes = buffer.getvalue()
                else:
                    img_bytes = file_bytes
                    img = Image.open(io.BytesIO(img_bytes)).convert("RGB")
                    buffer = io.BytesIO()
                    img.save(buffer, format="JPEG")
                    img_bytes = buffer.getvalue()

                base64_image = base64.b64encode(img_bytes).decode("utf-8")

            client = openai.OpenAI(api_key=api_key, base_url=base_url)

            with st.spinner("Analyzing..."):
                response = client.chat.completions.create(
                    model=model_name,
                    messages=[
                        {"role": "user", "content": [
                            {"type": "text", "text": "Analyze this drawing as an ISO GPS expert. Return ONLY valid JSON: [{\"tag_id\": 1, \"action\": \"DELETE|MODIFY|ADD\", \"box_2d\": [ymin, xmin, ymax, xmax], \"current_text\": \"...\", \"issue\": \"...\", \"replacement_text\": \"...\"}]"},
                            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}}
                        ]}
                    ]
                )
                
                # Cleanup output
                raw_content = response.choices[0].message.content.replace("```json", "").replace("```", "").strip()
                audit_items = json.loads(raw_content)

                st.success(f"Audit Complete! Identified {len(audit_items)} improvements.")
                
                # Display Results
                for item in audit_items:
                    action = item.get("action", "MODIFY")
                    st.write(f"**{action} #{item.get('tag_id')}**: {item.get('issue')}")
                    st.code(item.get("replacement_text"), language="text")

        except Exception as e:
            st.error(f"Engine Error: {str(e)}")
