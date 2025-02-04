import streamlit as st
import sqlite3
import os
from datetime import datetime
from openai import OpenAI  # Use the new client instantiation

# ---------------------------
# OpenAI API Setup
# ---------------------------
api_key = os.getenv("OPENAI_API_KEY")
if not api_key:
    st.error("Please set your OPENAI_API_KEY environment variable.")
# Instantiate the client using the new API
client = OpenAI(api_key=api_key)

# ---------------------------
# Database Setup and Helper Functions
# ---------------------------
@st.cache_resource(show_spinner=False)
def init_db():
    conn = sqlite3.connect("patients.db", check_same_thread=False)
    c = conn.cursor()
    # Create table for patients if it does not exist.
    c.execute('''
        CREATE TABLE IF NOT EXISTS patients (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            patient_number TEXT UNIQUE,
            name TEXT,
            sex TEXT,
            age INTEGER,
            additional_info TEXT
        )
    ''')
    # Create table for chat history.
    c.execute('''
        CREATE TABLE IF NOT EXISTS chat_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            patient_number TEXT,
            agent TEXT,
            role TEXT,
            message TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    return conn

conn = init_db()

def add_patient(patient_number, name, sex, age, additional_info):
    try:
        c = conn.cursor()
        c.execute(
            "INSERT INTO patients (patient_number, name, sex, age, additional_info) VALUES (?, ?, ?, ?, ?)",
            (patient_number, name, sex, age, additional_info)
        )
        conn.commit()
    except Exception as e:
        st.error(f"Error adding patient: {e}")

def get_patients():
    c = conn.cursor()
    c.execute("SELECT patient_number, name FROM patients")
    return c.fetchall()

def add_chat_message(patient_number, agent, role, message):
    c = conn.cursor()
    c.execute(
        "INSERT INTO chat_history (patient_number, agent, role, message) VALUES (?, ?, ?, ?)",
        (patient_number, agent, role, message)
    )
    conn.commit()

def get_chat_history(patient_number):
    c = conn.cursor()
    c.execute(
        "SELECT agent, role, message, timestamp FROM chat_history WHERE patient_number=? ORDER BY timestamp",
        (patient_number,)
    )
    return c.fetchall()

# ---------------------------
# Agent Functions Using the New OpenAI Client
# ---------------------------
def call_agent_input(messages):
    """
    Agent_Input: Gather patient/case details interactively.
    """
    system_prompt = (
        "You are a diagnostic assistant collecting patient case information. "
        "Ask clarifying questions to gather all necessary details about the patient's symptoms, history, and relevant data. "
        "Wait for the physician's input. When the physician types 'READY', indicate that you have gathered sufficient information."
    )
    conversation = [{"role": "system", "content": system_prompt}] + messages
    response = client.chat.completions.create(
        model="gpt-4",  # or "gpt-3.5-turbo" as desired
        messages=conversation,
        temperature=0.7,
        max_tokens=300
    )
    return response.choices[0].message.content

def call_agent_notes(agent_input_history, anamnesis_format):
    """
    Agent_Notes: Organize the collected case details into medical notes in the specified format.
    """
    system_prompt = (
        f"You are a medical note-taking assistant. Based on the conversation below regarding the patient's case, "
        f"produce organized medical notes in the {anamnesis_format} format. Include all relevant patient details."
    )
    conversation = [{"role": "system", "content": system_prompt}] + agent_input_history
    response = client.chat.completions.create(
        model="gpt-4",
        messages=conversation,
        temperature=0.5,
        max_tokens=500
    )
    return response.choices[0].message.content

def call_agent_diagnosis(agent_input_history, agent_notes_output):
    """
    Agent_Diagnosis: List potential diagnoses with supporting details.
    """
    system_prompt = (
        "You are a diagnostic reasoning assistant. Based on the patient's case details and the provided notes, "
        "list potential diagnoses from most likely to least likely. Include reasoning, differential diagnosis, epidemiology, and treatment suggestions."
    )
    conversation = [{"role": "system", "content": system_prompt}] + agent_input_history
    conversation.append({
        "role": "assistant",
        "content": f"Patient Notes:\n{agent_notes_output}"
    })
    response = client.chat.completions.create(
        model="gpt-4",
        messages=conversation,
        temperature=0.7,
        max_tokens=500
    )
    return response.choices[0].message.content

def call_agent_conduct(agent_input_history, agent_notes_output, agent_diagnosis_output):
    """
    Agent_Conduct: Suggest clinical management plans based on the overall case.
    """
    system_prompt = (
        "You are a clinical management assistant. Based on the patient's case details, organized notes, "
        "and diagnosis information, propose a series of suggested clinical management plans."
    )
    conversation = [{"role": "system", "content": system_prompt}] + agent_input_history
    conversation.append({
        "role": "assistant",
        "content": f"Patient Notes:\n{agent_notes_output}"
    })
    conversation.append({
        "role": "assistant",
        "content": f"Diagnosis Details:\n{agent_diagnosis_output}"
    })
    response = client.chat.completions.create(
        model="gpt-4",
        messages=conversation,
        temperature=0.7,
        max_tokens=500
    )
    return response.choices[0].message.content

# ---------------------------
# Streamlit App
# ---------------------------
def main():
    st.title("Physician Diagnostic Chatbot")

    # ---------------------------
    # Sidebar – Patient Information
    # ---------------------------
    st.sidebar.header("Patient Information")
    patients = get_patients()
    patient_options = {f"{name} ({patient_number})": patient_number for patient_number, name in patients}
    selection = st.sidebar.selectbox("Select Patient", options=["New Patient"] + list(patient_options.keys()))
    
    if selection == "New Patient":
        st.sidebar.subheader("Enter New Patient Information")
        with st.sidebar.form("new_patient_form", clear_on_submit=True):
            patient_number = st.text_input("Patient Number")
            name = st.text_input("Patient Name")
            sex = st.selectbox("Sex", options=["Male", "Female", "Other"])
            age = st.number_input("Age", min_value=0, max_value=120, step=1)
            additional_info = st.text_area("Additional Info")
            submitted = st.form_submit_button("Add Patient")
            if submitted:
                if patient_number and name:
                    add_patient(patient_number, name, sex, age, additional_info)
                    st.sidebar.success("Patient added!")
                    st.session_state.current_patient = patient_number
                else:
                    st.sidebar.error("Please enter at least a patient number and name.")
    else:
        patient_number = patient_options.get(selection, None)
        st.session_state.current_patient = patient_number

    if "current_patient" not in st.session_state or not st.session_state.current_patient:
        st.info("Please select or add a patient from the sidebar.")
        return

    # ---------------------------
    # Main – Chat Interface and Agent Workflow
    # ---------------------------
    st.subheader("Anamnesis Output Format")
    anamnesis_format = st.selectbox("Select Anamnesis Format", options=["Traditional Anamnesis", "SOAP Notes"])
    st.session_state.anamnesis_format = anamnesis_format

    st.write("### Chat Interface (Agent Input)")
    if "agent_input_history" not in st.session_state:
        st.session_state.agent_input_history = []

    # Display previous messages.
    for msg in st.session_state.agent_input_history:
        if msg["role"] == "user":
            st.markdown(f"**Physician:** {msg['content']}")
        else:
            st.markdown(f"**Agent Input:** {msg['content']}")

    user_input = st.text_input("Enter your message (type 'READY' to finish data collection):", key="chat_input")
    if st.button("Send"):
        if user_input:
            # Append user message and store it in the database.
            user_msg = {"role": "user", "content": user_input}
            st.session_state.agent_input_history.append(user_msg)
            add_chat_message(st.session_state.current_patient, "agent_input", "user", user_input)
            
            if user_input.strip().upper() == "READY":
                st.info("Finalizing data collection...")
                final_response = call_agent_input(st.session_state.agent_input_history)
                st.session_state.agent_input_history.append({"role": "assistant", "content": final_response})
                add_chat_message(st.session_state.current_patient, "agent_input", "assistant", final_response)
            else:
                assistant_reply = call_agent_input(st.session_state.agent_input_history)
                st.session_state.agent_input_history.append({"role": "assistant", "content": assistant_reply})
                add_chat_message(st.session_state.current_patient, "agent_input", "assistant", assistant_reply)
            
            # FIXED: Use experimental_rerun instead of set_query_params
            st.rerun()

    # ---------------------------
    # After Data Collection is Finalized – Run Other Agents
    # ---------------------------
    if st.session_state.agent_input_history:
        ready_flag = any(msg["content"].strip().upper() == "READY" for msg in st.session_state.agent_input_history if msg["role"] == "user")
        last_assistant = st.session_state.agent_input_history[-1]["content"].lower() if st.session_state.agent_input_history[-1]["role"] == "assistant" else ""
        if ready_flag or "sufficient" in last_assistant:
            st.write("---")
            st.header("Organized Case Summary and Recommendations")
            
            # Agent_Notes
            st.subheader("Medical Notes")
            agent_notes_output = call_agent_notes(st.session_state.agent_input_history, anamnesis_format)
            st.write(agent_notes_output)
            add_chat_message(st.session_state.current_patient, "agent_notes", "assistant", agent_notes_output)
            
            # Agent_Diagnosis
            st.subheader("Differential Diagnosis")
            agent_diagnosis_output = call_agent_diagnosis(st.session_state.agent_input_history, agent_notes_output)
            st.write(agent_diagnosis_output)
            add_chat_message(st.session_state.current_patient, "agent_diagnosis", "assistant", agent_diagnosis_output)
            
            # Agent_Conduct
            st.subheader("Suggested Conduct")
            agent_conduct_output = call_agent_conduct(st.session_state.agent_input_history, agent_notes_output, agent_diagnosis_output)
            st.write(agent_conduct_output)
            add_chat_message(st.session_state.current_patient, "agent_conduct", "assistant", agent_conduct_output)
            
    # ---------------------------
    # Optional: Display Chat History
    # ---------------------------
    with st.expander("View Complete Chat History for This Patient"):
        chat_hist = get_chat_history(st.session_state.current_patient)
        if chat_hist:
            for record in chat_hist:
                agent, role, message, timestamp = record
                st.markdown(f"**[{timestamp}] {agent} - {role.capitalize()}:** {message}")
        else:
            st.write("No chat history yet.")

if __name__ == "__main__":
    main()
