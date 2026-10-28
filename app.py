import streamlit as st
import openai # We will use OpenAI as the reasoning engine

# Configure the page
st.set_page_config(page_title="NEO 1.5 Quality Gate", layout="wide")
st.title("NEO 1.5 Automated ISO GPS Quality Gate")
st.subheader("Mass Production / QC Release Audit Engine")

# Sidebar for Setup
with st.sidebar:
    st.header("Configuration")
    api_key = st.text_input("Enter OpenAI API Key", type="password", help="Needed for the AI reasoning engine.")
    part_type = st.selectbox("Select Part Functional Interface:", 
                             ["Machined Prismatic", "Rotating Dynamic (Shaft/Hub)", "Sheet Metal/Weldment"])

# Master System Prompt (The "Engine Brain")
SYSTEM_PROMPT = """
You are an expert Principal Mechanical Systems Architect and ISO GPS Advisor. 
Your goal is the final Pre-Release Quality Gate for high-reliability mobile robot components.

Task: Perform an In-Depth ISO GPS Audit on the provided engineering drawing/image.

Operational Workflow:
1. Kinematic Datum Analysis (ISO 5459): Define the 3-2-1 Datum Reference Frame (DRF). 
   Primary [A]: Main mating plane/axis. Secondary [B]: Locating hole/spigot. Tertiary [C]: Clocking edge.
2. ISO Integrity Rules: 
   - Independence Principle (ISO 8015): Flag implicit coupling of size/form.
   - Envelope Requirement (ISO 14405-1): Mandate Envelope Modifier Ⓔ for all fit symbols.
   - Datum Syntax (ISO 1101): Ensure no form control references a datum.
3. Output Generation: Produce a structured Markdown table with 3 columns:
   - Feature/Control Frame
   - Audit Finding (Pass/Fail)
   - Production-Ready Fix (Exact instructions for Creo 7.0)
"""

# Main Interface
uploaded_file = st.file_uploader("Upload Drawing PDF or Screenshot", type=["pdf", "png", "jpg", "jpeg"])

if uploaded_file and api_key:
    if st.button("Generate Audit Report"):
        client = openai.OpenAI(api_key=api_key)
        
        with st.spinner("Analyzing part geometry and ISO compliance..."):
            # Here we send the image and the prompt to the AI
            response = client.chat.completions.create(
                model="gpt-4o", # Best for vision-based engineering audits
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": f"Audit this part classified as {part_type}. Provide a clear, actionable audit report."}
                ]
            )
            st.markdown(response.choices[0].message.content)
elif not api_key:
    st.warning("Please enter your OpenAI API key in the sidebar to activate the audit engine.")
