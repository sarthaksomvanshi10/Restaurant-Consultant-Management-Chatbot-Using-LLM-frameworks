import streamlit as st
import requests
import json
import os
from datetime import datetime
import pandas as pd

# Configuration
N8N_WEBHOOK_URL = os.getenv('N8N_WEBHOOK_URL', 'http://localhost:8000/chat')

# Page configuration
st.set_page_config(
    page_title="Restaurant Cost Chatbot",
    page_icon="🍕",
    layout="wide"
)

# Clean CSS
st.markdown("""
<style>
    .chatbot-header {
        text-align: center;
        padding: 2rem;
        margin-bottom: 2rem;
        background: linear-gradient(90deg, #ff6b6b, #4ecdc4);
        color: white;
        border-radius: 15px;
    }
    
    .chat-message {
        padding: 1.5rem;
        margin: 1rem 0;
        border-radius: 15px;
        box-shadow: 0 2px 10px rgba(0,0,0,0.1);
    }
    
    .user-message {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        margin-left: 10%;
    }
    
    .assistant-message {
        background: linear-gradient(135deg, #f093fb 0%, #f5f7fa 100%);
        border: 1px solid #e0e0e0;
        margin-right: 10%;
    }
    
    .assistant-message h3 {
        color: #2c3e50;
        margin-top: 0;
        border-bottom: 2px solid #3498db;
        padding-bottom: 0.5rem;
    }
    
    .assistant-message h4 {
        color: #27ae60;
        margin-top: 1.5rem;
        margin-bottom: 0.5rem;
    }
    
    .cost-increase {
        color: #e74c3c;
        font-weight: bold;
    }
    
    .cost-savings {
        color: #27ae60;
        font-weight: bold;
    }
    
    .analysis-section {
        background: #f8f9fa;
        padding: 1rem;
        border-left: 4px solid #3498db;
        margin: 1rem 0;
        border-radius: 5px;
    }
    
    .recommendation-box {
        background: #e8f5e8;
        border: 1px solid #27ae60;
        padding: 1rem;
        border-radius: 8px;
        margin: 1rem 0;
    }
    
    .warning-box {
        background: #fff3cd;
        border: 1px solid #ffc107;
        padding: 1rem;
        border-radius: 8px;
        margin: 1rem 0;
    }
    
    .metric-card {
        background: white;
        padding: 1rem;
        border-radius: 10px;
        box-shadow: 0 2px 5px rgba(0,0,0,0.1);
        margin: 0.5rem 0;
        border-left: 4px solid #e74c3c;
    }
    
    .analysis-entry {
        background: white;
        border: 1px solid #ddd;
        border-radius: 8px;
        padding: 1rem;
        margin-bottom: 1rem;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    }
    
    .analysis-timestamp {
        color: #666;
        font-size: 0.8rem;
        margin-bottom: 0.5rem;
    }
    
    .analysis-query {
        font-weight: bold;
        color: #2c3e50;
        margin-bottom: 0.5rem;
    }
    
    .business-rule {
        background: #f8f9fa;
        border: 1px solid #dee2e6;
        border-radius: 8px;
        padding: 1rem;
        margin: 1rem 0;
        border-left: 4px solid #007bff;
    }
    
    .rule-category {
        background: #e9ecef;
        border-radius: 5px;
        padding: 0.5rem;
        margin-bottom: 0.5rem;
        font-weight: bold;
        color: #495057;
    }
    
    .stButton > button {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        border: none;
        border-radius: 25px;
        padding: 0.75rem 1.5rem;
        font-weight: bold;
        box-shadow: 0 4px 15px rgba(102, 126, 234, 0.3);
        transition: all 0.3s ease;
    }
    
    .stButton > button:hover {
        transform: translateY(-2px);
        box-shadow: 0 6px 20px rgba(102, 126, 234, 0.4);
    }
</style>
""", unsafe_allow_html=True)

# Initialize session state
if "messages" not in st.session_state:
    st.session_state.messages = []
if "analysis_history" not in st.session_state:
    st.session_state.analysis_history = []

def send_message(message: str):
    """Send message directly to FastAPI backend"""
    try:
        payload = {"message": message}
        response = requests.post(
            N8N_WEBHOOK_URL,
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=30
        )
        
        if response.status_code == 200:
            data = response.json()
            return {
                "success": True,
                "response": data.get("response", "No response received")
            }
        else:
            return {
                "success": False,
                "error": f"Server error: {response.status_code} - {response.text}"
            }
            
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }

def format_assistant_response(content: str) -> str:
    """Format assistant response with clean HTML styling"""
    content = content.replace("**PRICE SHOCK ANALYSIS**", "<h3>📊 PRICE SHOCK ANALYSIS</h3>")
    content = content.replace("**SUPPLY DELAY ANALYSIS**", "<h3>⏰ SUPPLY DELAY ANALYSIS</h3>")
    content = content.replace("**PASTA COST BREAKDOWN**", "<h3>🍝 PASTA COST BREAKDOWN</h3>")
    content = content.replace("**PINSA COST BREAKDOWN**", "<h3>🍕 PINSA COST BREAKDOWN</h3>")
    content = content.replace("**SALAD COST BREAKDOWN**", "<h3>🥗 SALAD COST BREAKDOWN</h3>")
    
    # Convert headers
    content = content.replace("**Query Parsed:**", "<h4>🔍 Query Parsed:</h4>")
    content = content.replace("**Impact Analysis:**", "<h4>📈 Impact Analysis:</h4>")
    content = content.replace("**Monthly Impact:**", "<h4>💰 Monthly Impact:</h4>")
    content = content.replace("**Substitution Recommendations:**", "<h4>🔄 Substitution Recommendations:</h4>")
    content = content.replace("**Supply Risk Assessment:**", "<h4>⚠️ Supply Risk Assessment:</h4>")
    content = content.replace("**Impact Timeline:**", "<h4>📅 Impact Timeline:</h4>")
    content = content.replace("**Substitution Strategy:**", "<h4>🎯 Substitution Strategy:</h4>")
    content = content.replace("**Mitigation Plan:**", "<h4>🛡️ Mitigation Plan:</h4>")
    content = content.replace("**Recommendation:**", "<h4>💡 Recommendation:</h4>")
    
    # Style cost increases and savings
    import re
    content = re.sub(r'\+\$(\d+(?:\.\d{2})?)', r'<span class="cost-increase">+$\1</span>', content)
    content = re.sub(r'-\$(\d+(?:\.\d{2})?)', r'<span class="cost-savings">-$\1</span>', content)
    
    # Convert bullet points to lists
    lines = content.split('\n')
    formatted_lines = []
    in_list = False
    
    for line in lines:
        line = line.strip()
        if line.startswith('- ') or line.startswith('• '):
            if not in_list:
                formatted_lines.append('<ul>')
                in_list = True
            formatted_lines.append(f'<li>{line[2:]}</li>')
        elif line.startswith(('1. ', '2. ', '3. ', '4. ', '5. ')):
            if not in_list:
                formatted_lines.append('<ol>')
                in_list = True
            formatted_lines.append(f'<li>{line[3:]}</li>')
        else:
            if in_list:
                formatted_lines.append('</ul>')
                in_list = False
            if line:
                formatted_lines.append(f'<p>{line}</p>')
            else:
                formatted_lines.append('<br>')
    
    if in_list:
        formatted_lines.append('</ul>')
    
    content = '\n'.join(formatted_lines)
    
    # Add styled sections
    content = content.replace('<h4>💰 Monthly Impact:</h4>', 
                            '<div class="metric-card"><h4>💰 Monthly Impact:</h4>')
    content = content.replace('<h4>🔄 Substitution Recommendations:</h4>', 
                            '</div><div class="recommendation-box"><h4>🔄 Substitution Recommendations:</h4>')
    content = content.replace('<h4>💡 Recommendation:</h4>', 
                            '</div><div class="warning-box"><h4>💡 Recommendation:</h4>')
    
    # Close divs
    if 'metric-card' in content or 'recommendation-box' in content or 'warning-box' in content:
        content += '</div>'
    
    return content

def add_to_analysis_history(query: str, response: str, timestamp: str):
    """Add query and response to analysis history"""
    st.session_state.analysis_history.append({
        "timestamp": timestamp,
        "query": query,
        "response": response
    })

# Header
st.markdown("""
<div class="chatbot-header">
    <h1>🍕 Restaurant Cost Chatbot</h1>
    <p>Ask me about ingredient price changes and supply delays</p>
</div>
""", unsafe_allow_html=True)

# Create tabs
tab1, tab2, tab3 = st.tabs(["💬 Chat", "📊 Analysis History", "⚙️ Business Rules"])

with tab1:
    # Reset button
    col1, col2, col3 = st.columns([1, 1, 1])
    with col2:
        if st.button("🗑️ Reset Chat", type="secondary", use_container_width=True):
            st.session_state.messages = []
            st.session_state.analysis_history = []
            st.rerun()

    # Chat messages
    if st.session_state.messages:
        for message in st.session_state.messages:
            if message["role"] == "user":
                st.markdown(f"""
                <div class="chat-message user-message">
                    <strong>You:</strong> {message["content"]}
                </div>
                """, unsafe_allow_html=True)
            else:
                formatted_content = format_assistant_response(message["content"])
                st.markdown(f"""
                <div class="chat-message assistant-message">
                    <strong>Assistant:</strong><br>
                    {formatted_content}
                </div>
                """, unsafe_allow_html=True)
    else:
        st.markdown("""
        <div class="analysis-section">
            <h4>👋 Welcome!</h4>
            <p>I can help you analyze ingredient costs and suggest menu changes.</p>
            <p><strong>Try asking about:</strong></p>
            <ul>
                <li>Price increases (e.g., "Tomatoes increased by 22%")</li>
                <li>Supply delays (e.g., "Flour delayed by 5 days")</li>
                <li>Cost breakdowns (e.g., "Show pasta dishes costs")</li>
            </ul>
        </div>
        """, unsafe_allow_html=True)

    # Input area
    user_input = st.text_input(
        "Type your question:",
        placeholder="Ask about price changes or supply delays...",
        key="user_input"
    )

    # Send button
    if st.button("Send Analysis", type="primary", use_container_width=True) and user_input.strip():
        timestamp = datetime.now().isoformat()
        
        # Add user message to chat history
        st.session_state.messages.append({
            "role": "user",
            "content": user_input,
            "timestamp": timestamp
        })
        
        # Get response
        with st.spinner("🔄 Analyzing..."):
            response = send_message(user_input)
        
        # Add response to chat history
        if response.get("success", False):
            bot_response = response.get("response", "Analysis completed.")
            st.session_state.messages.append({
                "role": "assistant",
                "content": bot_response,
                "timestamp": timestamp
            })
            
            # Add to analysis history
            add_to_analysis_history(user_input, bot_response, timestamp)
        else:
            error_msg = f"Error: {response.get('error', 'Unknown error')}"
            st.session_state.messages.append({
                "role": "assistant",
                "content": error_msg,
                "timestamp": timestamp
            })
            
            # Add error to analysis history too
            add_to_analysis_history(user_input, error_msg, timestamp)
        
        st.rerun()

    # Example questions
    example_questions = [
        "The price of tomato_sauce has increased by 22% — how will this impact our monthly costs and what menu changes can mitigate it?",
        "Basil is delayed by 7 days", 
        "The price of mozzarella_fior_di_latte has increased by 25%",
        "Shipments of 00_flour are delayed by 5-6 days - how will this impact us?"
    ]

    col1, col2 = st.columns(2)

    for i, question in enumerate(example_questions):
        column = col1 if i % 2 == 0 else col2
        with column:
            if st.button(f"📊 {question[:35]}...", key=f"example_{i}", use_container_width=True):
                timestamp = datetime.now().isoformat()
                
                # Add example question to chat history
                st.session_state.messages.append({
                    "role": "user",
                    "content": question,
                    "timestamp": timestamp
                })
                
                with st.spinner("🔄 Analyzing..."):
                    response = send_message(question)
                
                if response.get("success", False):
                    bot_response = response.get("response", "Question processed.")
                    st.session_state.messages.append({
                        "role": "assistant",
                        "content": bot_response,
                        "timestamp": timestamp
                    })
                    
                    # Add to analysis history
                    add_to_analysis_history(question, bot_response, timestamp)
                else:
                    error_msg = f"Error: {response.get('error', 'Unknown error')}"
                    st.session_state.messages.append({
                        "role": "assistant",
                        "content": error_msg,
                        "timestamp": timestamp
                    })
                    
                    # Add error to analysis history
                    add_to_analysis_history(question, error_msg, timestamp)
                
                st.rerun()

with tab2:
    st.header("📊 Analysis History")
    
    if st.session_state.analysis_history:
        # Show analysis count
        st.info(f"Total analyses performed this session: {len(st.session_state.analysis_history)}")
        
        # Display each analysis entry
        for i, entry in enumerate(reversed(st.session_state.analysis_history)):
            with st.expander(f"Analysis #{len(st.session_state.analysis_history) - i} - {datetime.fromisoformat(entry['timestamp']).strftime('%H:%M:%S')}"):
                st.markdown(f"""
                <div class="analysis-entry">
                    <div class="analysis-timestamp">
                        {datetime.fromisoformat(entry['timestamp']).strftime('%Y-%m-%d %H:%M:%S')}
                    </div>
                    <div class="analysis-query">
                        Query: {entry['query']}
                    </div>
                    <hr>
                    <div>
                        {format_assistant_response(entry['response'])}
                    </div>
                </div>
                """, unsafe_allow_html=True)
        
        # Export functionality
        if st.button("📥 Export Analysis History", use_container_width=True):
            # Create DataFrame for export
            export_data = []
            for entry in st.session_state.analysis_history:
                export_data.append({
                    "Timestamp": datetime.fromisoformat(entry['timestamp']).strftime('%Y-%m-%d %H:%M:%S'),
                    "Query": entry['query'],
                    "Response": entry['response']
                })
            
            df = pd.DataFrame(export_data)
            csv = df.to_csv(index=False)
            
            st.download_button(
                label="Download CSV",
                data=csv,
                file_name=f"restaurant_analysis_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                mime="text/csv"
            )
    else:
        st.info("No analyses performed yet. Start by asking questions in the Chat tab!")

with tab3:
    st.header("⚙️ Business Rules & Assumptions")
    
    # Cost Engine Rules
    st.subheader("💰 Cost Engine Rules")
    
    st.markdown("""
    <div class="business-rule">
        <div class="rule-category">Sales Volume Assumptions</div>
        <strong>Monthly Sales per Dish:</strong> 100 units<br>
        <em>Used for calculating monthly cost impact projections</em>
    </div>
    """, unsafe_allow_html=True)
    
    st.markdown("""
    <div class="business-rule">
        <div class="rule-category">Cost Calculation Method</div>
        <strong>Price Shock Formula:</strong> quantity × unit_price × (1 + shock_pct/100)<br>
        <strong>Total Dish Cost:</strong> Sum of all ingredient costs for the dish<br>
        <em>Baseline costs calculated from CSV data, shocks applied as percentage increases</em>
    </div>
    """, unsafe_allow_html=True)
    
    st.markdown("""
    <div class="business-rule">
        <div class="rule-category">Risk Assessment Thresholds</div>
        <strong>Lead Time Threshold:</strong> 5 days<br>
        <strong>High Risk:</strong> New lead time > 5 days<br>
        <strong>Medium Risk:</strong> Additional delay > 2 days<br>
        <strong>Low Risk:</strong> All other delays<br>
        <em>Used to classify supply chain disruption severity</em>
    </div>
    """, unsafe_allow_html=True)
    
    st.markdown("""
    <div class="business-rule">
        <div class="rule-category">Revenue Impact Calculation</div>
        <strong>Weekly Revenue at Risk:</strong> affected_dishes × $15 × 7 days<br>
        <em>Assumes $15 average dish price for supply delay scenarios</em>
    </div>
    """, unsafe_allow_html=True)
    
    # Substitution Engine Rules
    st.subheader("🔄 Substitution Engine Rules")
    
    st.markdown("""
    <div class="business-rule">
        <div class="rule-category">Substitution Matching Logic</div>
        <strong>Context Matching:</strong> Substitutions filtered by dish category (pasta, pinsa, salad)<br>
        <strong>Allowed Flag:</strong> Only substitutions marked as 'allowed=True' in CSV are considered<br>
        <strong>Duplicate Removal:</strong> Same substitution rule shown once per analysis<br>
        <em>Ensures contextually appropriate ingredient swaps</em>
    </div>
    """, unsafe_allow_html=True)
    
    st.markdown("""
    <div class="business-rule">
        <div class="rule-category">Cost Impact Analysis</div>
        <strong>Cost Comparison:</strong> substitute_cost - original_cost<br>
        <strong>Savings Identification:</strong> Negative cost difference = cheaper alternative<br>
        <strong>Cost Display:</strong> Shows absolute dollar difference and percentage change<br>
        <em>Helps identify cost-effective substitution opportunities</em>
    </div>
    """, unsafe_allow_html=True)
    
    st.markdown("""
    <div class="business-rule">
        <div class="rule-category">Lead Time Optimization</div>
        <strong>Delivery Comparison:</strong> substitute_lead_time - original_lead_time<br>
        <strong>Faster Options:</strong> Negative difference = quicker delivery<br>
        <strong>Supply Chain Priority:</strong> Faster delivery prioritized for delay scenarios<br>
        <em>Optimizes for supply chain continuity during disruptions</em>
    </div>
    """, unsafe_allow_html=True)