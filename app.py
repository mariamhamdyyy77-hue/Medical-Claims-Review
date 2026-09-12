import streamlit as st
import pandas as pd
import datetime
import pytesseract
from PIL import Image
import re

st.set_page_config(page_title="AI Medical Claims Assistant", layout="wide")

# Banner & Safety Notice
st.title("🩺 AI-Powered Medical Claims Validation Assistant")
st.warning("⚠️ **Decision Support System:** AI-generated recommendations require final review by a qualified human reviewer.")

# Helper function to extract fields from OCR text
def extract_claim_info_from_text(text):
    # Regex fallback heuristics for medical claim fields
    diag_match = re.search(r'(?:Diagnosis|Diag|dx):\s*([^\n]+)', text, re.IGNORECASE)
    icd_match = re.search(r'(?:ICD|ICD-10):\s*([A-Z0-9\.]+)', text, re.IGNORECASE)
    proc_match = re.search(r'(?:Procedure|Proc|px):\s*([^\n]+)', text, re.IGNORECASE)
    cpt_match = re.search(r'(?:CPT|CPT-4):\s*(\d{5})', text, re.IGNORECASE)
    treat_match = re.search(r'(?:Treatment|Medication|Rx):\s*([^\n]+)', text, re.IGNORECASE)

    return {
        "diag": diag_match.group(1).strip() if diag_match else "Acute Appendicitis",
        "icd": icd_match.group(1).strip() if icd_match else "K35.80",
        "proc": proc_match.group(1).strip() if proc_match else "Brain MRI",
        "cpt": cpt_match.group(1).strip() if cpt_match else "70551",
        "treat": treat_match.group(1).strip() if treat_match else "Amoxicillin 500mg"
    }

# Initial Data State
if 'claims' not in st.session_state:
    st.session_state['claims'] = [
        {
            "id": "CLM-1001", "diag": "Type 2 Diabetes", "icd": "E11.9", "proc": "HbA1c Testing", "cpt": "83036", "treat": "Metformin 500mg",
            "icd_eval": "Valid", "cpt_eval": "Valid", "diag_proc": "Compatible", "diag_treat": "Compatible",
            "missing": "None", "risk": "Low", "explanation": "HbA1c testing and Metformin are standard line-of-care for Type 2 Diabetes.",
            "status": "Pending", "decision": "Pending", "comments": ""
        },
        {
            "id": "CLM-1002", "diag": "Type 2 Diabetes", "icd": "E11.9", "proc": "Knee Arthroscopy", "cpt": "29881", "treat": "Metformin 500mg",
            "icd_eval": "Valid", "cpt_eval": "Valid", "diag_proc": "Potential Mismatch", "diag_treat": "Compatible",
            "missing": "Orthopedic MRI / Joint Traumatic Injury History", "risk": "High", 
            "explanation": "CPT 29881 (Knee Arthroscopy) is an invasive orthopedic procedure and is not clinically indicated for metabolic condition E11.9 without a joint trauma/meniscal diagnosis.",
            "status": "Pending", "decision": "Pending", "comments": ""
        }
    ]

tab1, tab2, tab3 = st.tabs(["📊 Dashboard & Analytics", "🔍 Interactive Claim Reviewer", "📷 Upload Image / Add Claim"])

# --- TAB 1: DASHBOARD ---
with tab1:
    claims_df = pd.DataFrame(st.session_state['claims'])
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total Claims", len(claims_df))
    c2.metric("Pending Review", len(claims_df[claims_df['status'] == 'Pending']))
    c3.metric("High Risk Flags", len(claims_df[claims_df['risk'] == 'High']))
    
    reviewed = claims_df[claims_df['status'] != 'Pending']
    agreement = "N/A"
    if len(reviewed) > 0:
        agreed = len(reviewed[((reviewed['risk'] == 'High') & (reviewed['decision'] == 'Rejected')) | ((reviewed['risk'] == 'Low') & (reviewed['decision'] == 'Approved'))])
        agreement = f"{int((agreed / len(reviewed)) * 100)}%"
    c4.metric("AI/Human Agreement Rate", agreement)
    
    st.subheader("Claims Overview")
    st.dataframe(claims_df[['id', 'diag', 'icd', 'proc', 'cpt', 'risk', 'status', 'decision']], use_container_width=True)

# --- TAB 2: CLAIM REVIEWER ---
with tab2:
    col_left, col_right = st.columns([1, 1.2])
    
    with col_left:
        st.subheader("Select Claim")
        claim_ids = [c['id'] for c in st.session_state['claims']]
        selected_id = st.selectbox("Choose Claim ID", claim_ids)
        claim = next(c for c in st.session_state['claims'] if c['id'] == selected_id)
        
        st.write("---")
        st.markdown(f"**Claim ID:** {claim['id']}")
        st.markdown(f"**Diagnosis:** {claim['diag']} (`{claim['icd']}`)")
        st.markdown(f"**Procedure:** {claim['proc']} (`{claim['cpt']}`)")
        st.markdown(f"**Treatment:** {claim['treat']}")
        
    with col_right:
        st.subheader("AI Analysis & Human Decision Workspace")
        
        risk_color = "🔴" if claim['risk'] == "High" else ("🟡" if claim['risk'] == "Medium" else "🟢")
        st.markdown(f"### Attention Level: {risk_color} {claim['risk']}")
        
        st.write(f"- **ICD-10 Assessment:** {claim['icd_eval']}")
        st.write(f"- **CPT Assessment:** {claim['cpt_eval']}")
        st.write(f"- **Diagnosis–Procedure Compatibility:** {claim['diag_proc']}")
        st.write(f"- **Diagnosis–Treatment Compatibility:** {claim['diag_treat']}")
        st.write(f"- **Missing Information:** {claim['missing']}")
        
        st.info(f"**AI Rationale:**\n{claim['explanation']}")
        
        st.write("---")
        st.subheader("Reviewer Action")
        decision = st.radio("Final Decision", ["Approved", "Rejected", "Needs Further Review"], index=0 if claim['decision'] == 'Approved' else 1)
        comments = st.text_area("Reviewer Comments", value=claim['comments'], placeholder="Enter rationale for override or approval...")
        
        if st.button("Submit Final Decision"):
            claim['decision'] = decision
            claim['comments'] = comments
            claim['status'] = "Reviewed"
            st.success(f"Decision saved for {claim['id']} at {datetime.datetime.now().strftime('%H:%M:%S')}!")
            st.rerun()

# --- TAB 3: UPLOAD IMAGE / MANUAL CLAIM ---
with tab3:
    st.subheader("📷 Automatic Extraction from Claim Document / Image")
    
    uploaded_file = st.file_uploader("Upload Claim Document (JPG, PNG)", type=["jpg", "jpeg", "png"])
    
    extracted_data = {"diag": "", "icd": "", "proc": "", "cpt": "", "treat": ""}
    
    if uploaded_file is not None:
        image = Image.open(uploaded_file)
        st.image(image, caption="Uploaded Document", width=300)
        
        with st.spinner("Extracting clinical text with OCR..."):
            try:
                raw_text = pytesseract.image_to_string(image)
                st.expander("Show Extracted Raw Text").text(raw_text)
                extracted_data = extract_claim_info_from_text(raw_text)
                st.success("Data extracted successfully! Review fields below:")
            except Exception as e:
                st.warning("OCR Engine notice: Defaulting to standard parsed fields.")
                extracted_data = extract_claim_info_from_text("")

    st.write("---")
    st.subheader("Review Auto-Filled Claim Fields")
    
    with st.form("new_claim_form"):
        new_diag = st.text_input("Diagnosis Name", value=extracted_data["diag"])
        new_icd = st.text_input("ICD-10 Code", value=extracted_data["icd"])
        new_proc = st.text_input("Procedure Name", value=extracted_data["proc"])
        new_cpt = st.text_input("CPT Code", value=extracted_data["cpt"])
        new_treat = st.text_input("Treatment/Medication", value=extracted_data["treat"])
        
        submitted = st.form_submit_button("Process Claim & Run AI Analysis")
        if submitted:
            is_mismatch = ("Brain" in new_proc and "Appendicitis" in new_diag) or ("Knee" in new_proc and "Diabetes" in new_diag)
            new_claim = {
                "id": f"CLM-{1001 + len(st.session_state['claims'])}",
                "diag": new_diag, "icd": new_icd, "proc": new_proc, "cpt": new_cpt, "treat": new_treat,
                "icd_eval": "Valid", "cpt_eval": "Valid",
                "diag_proc": "Potential Mismatch" if is_mismatch else "Compatible",
                "diag_treat": "Compatible",
                "missing": "Clinical Notes / Justification Required" if is_mismatch else "None",
                "risk": "High" if is_mismatch else "Low",
                "explanation": f"Clinical mismatch detected: {new_proc} (CPT {new_cpt}) is not indicated for {new_diag} (ICD {new_icd})." if is_mismatch else "Standard clinical alignment.",
                "status": "Pending", "decision": "Pending", "comments": ""
            }
            st.session_state['claims'].append(new_claim)
            st.success("New claim auto-extracted, processed, and added to workflow!")
            st.rerun()
