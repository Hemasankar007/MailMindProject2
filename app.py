import os

import warnings
warnings.filterwarnings("ignore", category=RuntimeWarning)

import streamlit as st
from typing import List, Dict, Any
import time
from datetime import datetime, timedelta

from auth_service import GmailAuthService
from gmail_service import GmailService
from ai_service import AIService
from memory_service import MemoryService

# Page configuration
st.set_page_config(
    page_title="Gmail AI Agent",
    page_icon="✉️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Initialize services
def init_services():
    try:
        auth_service = GmailAuthService()
        gmail_service = GmailService(auth_service)
        ai_service = AIService()
        memory_service = MemoryService()
        return gmail_service, ai_service, memory_service, None
    except Exception as e:
        return None, None, None, str(e)

def main():
    st.title("✉️ Gmail AI Agent")
    st.markdown("Process and respond to emails based on time intervals")
    
    # Initialize services
    gmail_service, ai_service, memory_service, error = init_services()
    
    if error:
        st.error(f"Failed to initialize services: {error}")
        st.info("Please make sure you have set up your credentials correctly.")
        
        if "invalid_scope" in error.lower():
            st.info("""
            **Troubleshooting Steps:**
            1. Delete the `token.json` file if it exists
            2. Make sure your `credentials.json` is from Google Cloud Console
            3. Verify Gmail API is enabled in your Google Cloud project
            4. Check that the OAuth consent screen is configured
            """)
        return
    
    # Sidebar controls
    st.sidebar.header("Email Selection & Operations")

    # Filter Type
    filter_type = st.sidebar.radio(
        "Select filter type:",
        ["Date Range", "Starred emails"]
    )

    emails = [] # Initialize emails list

    if filter_type == "Date Range":
        st.sidebar.subheader("Date Range Details")
        start_date = st.sidebar.date_input("Start Date", datetime.today() - timedelta(days=7), key="start_date_input")
        end_date = st.sidebar.date_input("End Date", datetime.today(), key="end_date_input")

        # Combine date and time (always use min/max time as time selection is removed)
        start_datetime = datetime.combine(start_date, datetime.min.time())
        end_datetime = datetime.combine(end_date, datetime.max.time())

    st.sidebar.markdown("---") # Separator

    # Label filtering
    label_options = ["ALL", "INBOX", "UNREAD", "IMPORTANT", "PROMOTIONAL"] # Added "PROMOTIONAL"
    selected_label = st.sidebar.selectbox(
        "Filter by label:",
        label_options,
        index=0
    )
    
    st.sidebar.markdown("---") # Separator

    # Operation mode
    operation_mode = st.sidebar.radio(
        "Operation Mode",
        ["Draft", "Auto-Send"],
        help="Draft mode creates drafts for review, Auto-Send sends replies automatically"
    )
    
    # Main content
    tab1, tab2, tab3 = st.tabs(["📨 Process Emails", "⚙️ Settings", "📊 Statistics"])
    
    with tab1:
        st.header("Process Emails")
        
        if 'response_style' not in st.session_state:
            st.session_state.response_style = "Professional"

        if st.button("📥 Fetch Emails"):
            with st.spinner("Fetching and analyzing emails..."):
                try:
                    if filter_type == "Starred emails":
                        emails = gmail_service.get_starred_emails(selected_label)
                    elif filter_type == "Date Range":
                        emails = gmail_service.get_emails_by_time_range(start_datetime, end_datetime, selected_label)
                    
                    if emails:
                        st.session_state.emails = emails
                        
                        email_analysis_results = []
                        for email_obj in emails:
                            email_content = gmail_service.extract_email_content(email_obj)
                            context = memory_service.get_conversation_context(email_obj.get('threadId'))
                            analysis = ai_service.analyze_email(email_content, context, st.session_state.response_style)
                            
                            summary = gmail_service.get_email_summary(email_obj)
                            analysis['from'] = summary['from']
                            analysis['subject'] = summary['subject']
                            analysis['date'] = summary['date']
                            analysis['labels'] = summary['labels']
                            
                            email_analysis_results.append(analysis)
                        
                        st.session_state.email_analysis = email_analysis_results
                        st.success(f"Found and analyzed {len(emails)} emails.")
                    else:
                        st.info("No emails found for the selected criteria.")
                        
                except Exception as e:
                    st.error(f"Error fetching or analyzing emails: {e}")
        
        if 'email_analysis' in st.session_state:
            st.subheader(f"Emails to Process ({len(st.session_state.email_analysis)})")
            
            summary_data = []
            for i, analysis in enumerate(st.session_state.email_analysis):
                summary_data.append({
                    "ID": i + 1,
                    "Score": analysis.get('score', 'N/A'),
                    "Reply Needed": "✅" if analysis.get('reply_needed') else "❌",
                    "From": analysis['from'],
                    "Subject": analysis['subject'],
                    "Preview": analysis['summary'],
                    "Date": analysis['date']
                })
            
            st.dataframe(summary_data, use_container_width=True)
            
            for i, (email, analysis) in enumerate(zip(st.session_state.emails, st.session_state.email_analysis)):
                with st.expander(f"Email {i+1}: {analysis['subject']}"):
                    col1, col2 = st.columns([1, 3])
                    
                    with col1:
                        st.write("**From:**", analysis['from'])
                        st.write("**Date:**", analysis['date'])
                        st.write("**Labels:**", ", ".join(analysis['labels']))
                    
                    with col2:
                        content = gmail_service.extract_email_content(email)
                        st.text_area("Email Content", content, height=200, key=f"content_{i}")
                        
                        st.info(f"**Summary:** {analysis['summary']}")
                        
                        response = st.text_area("AI Response", analysis['response'], height=200, key=f"resp_{i}")
                        
                        if st.button("Create Draft", key=f"draft_{i}"):
                            try:
                                success = gmail_service.create_draft_reply(email, response)
                                if success:
                                    thread_id = email.get('threadId')
                                    memory_service.mark_email_processed(email['id'], thread_id)
                                    if thread_id:
                                        memory_service.update_conversation(thread_id, content, response)
                                    st.success("Draft created successfully!")
                                else:
                                    st.error("Failed to create draft")
                            except Exception as e:
                                st.error(f"Error creating draft: {e}")

    with tab2:
        st.header("Settings")
        st.info("Configure your Gmail AI Agent settings")
        
        st.subheader("API Configuration")
        gemini_key = st.text_input("Gemini API Key", type="password", value="", key="gemini_key")
        
        if gemini_key:
            ai_service.set_api_keys(gemini_key)
        
        st.subheader("Response Style")
        st.session_state.response_style = st.selectbox(
            "Default Response Style",
            ["Professional", "Friendly", "Formal", "Casual"],
            index=["Professional", "Friendly", "Formal", "Casual"].index(st.session_state.get("response_style", "Professional")),
            key="response_style_selector"
        )
        
        st.subheader("Auto-Processing")
        st.checkbox("Process emails automatically", value=False)
        st.slider("Max emails to process per run", 1, 50, 10)
    
    with tab3:
        st.header("Statistics")
        st.info("View usage statistics and performance metrics")
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.metric("Processed Emails", len(memory_service.memory["processed_emails"]))
        
        with col2:
            st.metric("Active Conversations", len(memory_service.memory["conversations"]))
        
        with col3:
            st.metric("Known Entities", len(memory_service.memory["entities"]))
        
        st.subheader("Email Priority Statistics")
        if 'email_analysis' in st.session_state:
            high_priority_emails = [s for s in st.session_state.email_analysis if s.get('score', 0) >= 8]
            st.metric("High Priority Emails (Score >= 8)", len(high_priority_emails))
        else:
            st.info("No email summaries available for priority statistics.")

        st.subheader("Recent Processed Emails")
        if memory_service.memory["processed_emails"]:
            for email_id, details in list(memory_service.memory["processed_emails"].items())[-5:]:
                st.text(f"Email {email_id[:8]}... - {details['processed_at']}")
        else:
            st.info("No emails processed yet")
        
        st.subheader("Conversation Topics")
        topics = {}
        for conv in memory_service.memory["conversations"].values():
            topic = conv.get('topic', 'unknown')
            topics[topic] = topics.get(topic, 0) + 1
        
        if topics:
            max_count = max(topics.values())
            for topic, count in topics.items():
                progress_value = count / max_count if max_count > 0 else 0
                st.progress(progress_value, text=f"{topic}: {count}")
        else:
            st.info("No conversation topics yet")

if __name__ == "__main__":
    main()