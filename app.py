import streamlit as st
import openai
import base64

st.set_page_config(page_title="Quality Gate", layout="wide")
st.title("Automated ISO GPS Quality Gate")

with st.sidebar:
    st.header("Configuration")
    api_key = st.secrets.get("OPENAI_API_KEY") # We keep the secret name, but it holds your AnyAPI key
    # Gemini models often require different naming conventions
    model_name = st.text_input("Model Name", value="google/gemini-3.6-flash") 

uploaded_file = st.file_uploader("Upload Drawing", type=["png", "jpg", "jpeg"])

if uploaded_file and api_key:
    if st.button("Generate Audit Report"):
        try:
            # Convert image
            bytes_data = uploaded_file.getvalue()
            base64_image = base64.b64encode(bytes_data).decode('utf-8')
            
            client = openai.OpenAI(
                api_key=api_key, 
                base_url="https://api.anyapi.ai/v1"
            )
            
            with st.spinner("Analyzing with Gemini..."):
                response = client.chat.completions.create(
                    model=model_name,
                    messages=[
                        {"role": "user", "content": [
                            {"type": "text", "text": "You are an expert ISO GPS Mechanical Systems Architect. Analyze this drawing. 1. Classify functionality. 2. Audit 3-2-1 Datum Reference Frame. 3. Check for syntax errors (ISO 1101/8015). Output a Markdown table: Feature | Audit Finding | Production Fix."},
                            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}}
                        ]}
                    ]
                )
                st.markdown(response.choices[0].message.content)
        except Exception as e:
            st.error(f"Engine Error: {str(e)}")
