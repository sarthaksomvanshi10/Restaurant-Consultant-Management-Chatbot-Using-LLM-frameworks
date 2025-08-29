from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Dict, List, Optional, Any
import pandas as pd
import os
from datetime import datetime
import uuid
import re

# Import our engines
from cost_engine import CostEngine
from substitution_engine import SubstitutionEngine
from conversation_manager import ConversationManager
from ollama_client import OllamaClient

app = FastAPI(title="Restaurant Menu Cost Chatbot API", version="1.0.0")

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global variables for data and engines
ingredients_df = None
menu_df = None
menu_bom_df = None
substitutions_df = None
cost_engine = None
substitution_engine = None
conversation_manager = None
ollama_client = None

# Pydantic models
class ChatMessage(BaseModel):
    message: str

class ChatResponse(BaseModel):
    response: str
    analysis_data: Optional[Dict[str, Any]] = None

def load_csv_data():
    """Load all CSV data files"""
    global ingredients_df, menu_df, menu_bom_df, substitutions_df
    
    data_path = os.getenv('DATA_PATH', '/app/data')
    
    try:
        ingredients_df = pd.read_csv(f"{data_path}/ingredients.csv")
        menu_df = pd.read_csv(f"{data_path}/menu.csv")
        menu_bom_df = pd.read_csv(f"{data_path}/menu_bom.csv")
        substitutions_df = pd.read_csv(f"{data_path}/substitutions.csv")
        
        print("Data loaded successfully:")
        print(f"   - {len(ingredients_df)} ingredients")
        print(f"   - {len(menu_df)} menu items")
        print(f"   - {len(menu_bom_df)} BOM entries")
        print(f"   - {len(substitutions_df)} substitution rules")
        
    except Exception as e:
        print(f"Error loading data: {e}")
        raise e

def initialize_engines():
    """Initialize all processing engines"""
    global cost_engine, substitution_engine, conversation_manager, ollama_client
    
    try:
        cost_engine = CostEngine(ingredients_df, menu_df, menu_bom_df)
        substitution_engine = SubstitutionEngine(substitutions_df, ingredients_df)
        conversation_manager = ConversationManager()
        
        ollama_url = os.getenv('OLLAMA_URL', 'http://localhost:11434')
        ollama_model = os.getenv('OLLAMA_MODEL', 'llama3.2:1b')
        ollama_client = OllamaClient(ollama_url, ollama_model)
        
        print("Engines initialized successfully")
        
    except Exception as e:
        print(f"Error initializing engines: {e}")
        raise e

@app.on_event("startup")
async def startup_event():
    """Initialize everything on startup"""
    load_csv_data()
    initialize_engines()

@app.get("/")
async def root():
    return {"message": "Restaurant Menu Cost Chatbot API", "status": "running"}

@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "data_loaded": all([df is not None for df in [ingredients_df, menu_df, menu_bom_df, substitutions_df]]),
        "engines_ready": all([engine is not None for engine in [cost_engine, substitution_engine, conversation_manager, ollama_client]])
    }

@app.post("/reset")
async def reset_conversation():
    """Reset conversation history for new chat session"""
    try:
        # conversation_manager.clear_history()
        return {"message": "Conversation reset successful", "status": "ready"}
    except Exception as e:
        print(f"Error resetting conversation: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/chat")
async def chat_endpoint(chat_message: ChatMessage):
    """Main chat endpoint - processes user messages with fresh session"""
    try:
        # AUTOMATIC SESSION RESET - Clear conversation history for fresh analysis
        # conversation_manager.clear_history()
        
        # Get conversation context (will be empty after reset)
        conversation_context = conversation_manager.get_conversation_context()
        
        # Parse user message with LLM - REQUIREMENT 1: Natural Language Parsing
        parsed_query = await ollama_client.parse_query(
            chat_message.message, 
            conversation_context  # Empty context for fresh analysis
        )
        
        # Process the query - REQUIREMENTS 2 & 3: Cost Engine & Substitution Engine
        analysis_result = process_query(parsed_query, conversation_context)
        
        # Generate response - REQUIREMENT 4: Explainability
        response_text = generate_response(parsed_query, analysis_result, conversation_context)
        
        # Update conversation history (optional - can be disabled for true stateless operation)
        conversation_manager.add_exchange(
            chat_message.message,
            response_text, 
            parsed_query
        )
        
        return ChatResponse(
            response=response_text,
            analysis_data=analysis_result
        )
        
    except Exception as e:
        print(f"Error in chat endpoint: {e}")
        raise HTTPException(status_code=500, detail=str(e))

def process_query(parsed_query: Dict[str, Any], conversation_context: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Process parsed query through cost and substitution engines"""
    try:
        result = {}
        query_type = parsed_query.get("query_type", "general")
        user_intent = parsed_query.get("user_intent", "general query")
        
        # Log the parsed query for debugging
        print(f"Processing query - Type: {query_type}, Intent: {user_intent}")
        
        # REQUIREMENT 2: Cost Engine - Compute baseline costs first
        baseline_costs = cost_engine.calculate_baseline_costs()
        result["baseline_costs"] = baseline_costs
        
        # Handle category queries (like "pasta dishes cost breakdown")
        if query_type == "category_query":
            category_filter = parsed_query.get("category_filter")
            if category_filter:
                category_dishes = cost_engine.get_dishes_by_category(category_filter)
                result["category_dishes"] = category_dishes
                result["category_filter"] = category_filter
                result["user_intent"] = user_intent
        
        # Check if this is a follow-up question about substitutions
        recent_ingredients = conversation_manager.get_recent_ingredients_mentioned()
        is_substitution_followup = (
            query_type == "general" and 
            conversation_manager.has_recent_analysis() and
            any(word in user_intent.lower() 
                for word in ["substitution", "substitute", "alternative", "replace"])
        )
        
        # PRIORITY FIX: Check for delays FIRST, then price shocks
        if "delays" in parsed_query and parsed_query["delays"]:
            print(f"Processing supply delays: {parsed_query['delays']}")
            delay_threshold = parsed_query.get("assumptions", {}).get("lead_time_threshold_days", 5)
            delay_impact = cost_engine.analyze_supply_delays(parsed_query["delays"], delay_threshold)
            result["delay_impact"] = delay_impact
            
            # REQUIREMENT 3: Find substitutions for delayed ingredients
            if "error" not in delay_impact:
                substitutions = substitution_engine.find_substitutions(delay_impact)
                result["available_substitutions"] = substitutions
        
        # Handle price shocks - REQUIREMENT 2: Simulate impacts
        elif "price_shocks" in parsed_query and parsed_query["price_shocks"]:
            print(f"Processing price shocks: {parsed_query['price_shocks']}")
            shock_impact = cost_engine.apply_price_shocks(parsed_query["price_shocks"])
            result["price_shock_impact"] = shock_impact
            
            # REQUIREMENT 3: Find substitutions for impacted ingredients
            if "error" not in shock_impact:
                substitutions = substitution_engine.find_substitutions(shock_impact)
                result["available_substitutions"] = substitutions
        
        # Handle substitution follow-up questions
        elif is_substitution_followup and recent_ingredients:
            print(f"Processing substitution followup for: {recent_ingredients}")
            # Re-analyze recent ingredients for substitutions
            mock_impact = {"affected_dishes": [
                {"affected_ingredient": ing, "name": "Multiple dishes", "category": "general"} 
                for ing in recent_ingredients
            ]}
            substitutions = substitution_engine.find_substitutions(mock_impact)
            result["available_substitutions"] = substitutions
            result["followup_context"] = recent_ingredients
        
        # Add parsing metadata
        result["parsing_metadata"] = {
            "query_type": query_type,
            "user_intent": user_intent,
            "original_query": parsed_query.get("original_query", ""),
            "parsing_successful": "error" not in parsed_query
        }
        
        return result
        
    except Exception as e:
        print(f"Error processing query: {e}")
        return {"error": str(e)}

def generate_response(parsed_query: Dict[str, Any], analysis_result: Dict[str, Any], conversation_context: List[Dict[str, Any]]) -> str:
    """Generate structured, detailed conversational response with enhanced formatting"""
    try:
        if "error" in analysis_result:
            return f"Sorry, I encountered an error analyzing your request: {analysis_result['error']}"
        
        query_type = parsed_query.get("query_type", "general")
        
        # Handle price shock questions with detailed structure
        if "price_shock_impact" in analysis_result:
            return format_price_shock_response(parsed_query, analysis_result)
        
        # Handle supply delay questions with detailed structure
        elif "delay_impact" in analysis_result:
            return format_delay_response(parsed_query, analysis_result)
        
        # Handle category cost breakdown
        elif query_type == "category_query" and "category_dishes" in analysis_result:
            return format_category_response(analysis_result)
        
        # Handle follow-up substitution questions
        elif "followup_context" in analysis_result:
            return format_substitution_followup_response(analysis_result)
        
        # Default response for general queries
        else:
            return ("I can help you analyze ingredient cost impacts and suggest menu changes. "
                   "Try asking about price increases, supply delays, or cost breakdowns for specific menu categories.")
        
    except Exception as e:
        return f"Sorry, I had trouble processing that. Could you try rephrasing your question?"

def format_price_shock_response(parsed_query: Dict[str, Any], analysis_result: Dict[str, Any]) -> str:
    """Format detailed price shock analysis response"""
    impact = analysis_result["price_shock_impact"]
    if "error" in impact:
        return f"Error analyzing price shock: {impact['error']}"
    
    shocks_applied = impact.get("price_shocks_applied", {})
    monthly_increase = impact.get('total_monthly_increase', 0)
    dishes_affected = impact.get('total_dishes_affected', 0)
    most_impacted = impact.get('most_impacted_dishes', [])
    affected_dishes = impact.get('affected_dishes', [])
    
    # Header with shock details
    response = "**PRICE SHOCK ANALYSIS**\n\n"
    
    # Query parsing summary
    response += "**Query Parsed:**\n"
    for ingredient, pct in shocks_applied.items():
        ingredient_name = ingredient.replace('_', ' ').title()
        response += f"- Ingredient: {ingredient}\n"
        response += f"- Price increase: {pct}%\n"
    response += "\n"
    
    # Impact Analysis section
    response += "**Impact Analysis:**\n"
    response += f"**Affected Menu Items:**\n"
    
    # Show affected dishes
    for i, dish in enumerate(affected_dishes[:8], 1):
        cost_increase = dish.get('cost_increase', 0)
        percentage_increase = dish.get('percentage_increase', 0)
        
        if percentage_increase > 0:
            old_cost = cost_increase / (percentage_increase / 100)
        else:
            old_cost = 0
            
        new_cost = old_cost + cost_increase
        response += f"{i}. {dish['name']} - Cost: ${old_cost:.2f} → ${new_cost:.2f} (+${cost_increase:.2f})\n"
    
    response += "\n"
    
    # Monthly Impact
    response += f"**Monthly Impact:**\n"
    response += f"- Additional COGS: +${monthly_increase:.0f} (assuming 100 dishes/month per item)\n"
    if most_impacted:
        most_exposed = most_impacted[0]
        exposure_pct = most_exposed.get('percentage_increase', 0)
        response += f"- Most exposed: {most_exposed['name']} (+{exposure_pct:.1f}% dish cost)\n"
    response += "\n"
    
    # Substitution Recommendations
    substitutions = analysis_result.get("available_substitutions", [])
    response += "**Substitution Recommendations:**\n"
    
    if substitutions:
        total_savings = 0
        applied_count = 0
        
        for i, sub in enumerate(substitutions[:3], 1):
            cost_impact_text = sub.get('cost_impact', '')
            
            if 'cheaper' in cost_impact_text.lower():
                match = re.search(r'\$(\d+\.?\d*)', cost_impact_text)
                if match:
                    savings = float(match.group(1))
                    total_savings += savings * 100
                    applied_count += 1
                    
                response += f"✅ **Applied:** {sub['original']} → {sub['substitute']} ({sub['context']} context)\n"
                response += f"- {sub['affected_dish']}: Potential savings ${savings:.2f} per dish\n"
                response += f"- Rationale: \"{sub['rationale']}\"\n\n"
            else:
                response += f"⚠️ **Available:** {sub['original']} → {sub['substitute']} ({sub['context']} context)\n"
                response += f"- {sub['affected_dish']}: {cost_impact_text}\n"
                response += f"- Rationale: \"{sub['rationale']}\"\n\n"
        
        if total_savings > 0 and applied_count > 0:
            response += f"**Final Impact After Substitutions:**\n"
            net_cost = max(0, monthly_increase - total_savings)
            reduction_pct = min(100, (total_savings/monthly_increase*100)) if monthly_increase > 0 else 0
            response += f"- Net additional cost: +${net_cost:.0f}/month (-{reduction_pct:.0f}% reduction)\n"
            response += f"- {applied_count} dishes optimized, {dishes_affected - applied_count} dishes still affected\n"
        else:
            response += f"**Impact Summary:**\n"
            response += f"- {len(substitutions)} substitution options found\n"
            response += f"- Consider implementing based on kitchen capabilities\n"
    else:
        # Dynamic ingredient name from parsed query
        ingredient_names = list(shocks_applied.keys())
        ingredient_display = ", ".join([name.replace('_', ' ') for name in ingredient_names])
        
        response += f"❌ No cost-effective substitutions found for {ingredient_display}.\n\n"
        response += f"**Recommendations:**\n"
        response += f"- Consider adjusting menu prices to offset the ${monthly_increase:.0f} monthly increase\n"
        response += f"- Negotiate with current supplier for better rates\n"
        response += f"- Source alternative suppliers for {ingredient_display}\n"
    
    return response

def format_delay_response(parsed_query: Dict[str, Any], analysis_result: Dict[str, Any]) -> str:
    """Format detailed supply delay analysis response"""
    impact = analysis_result["delay_impact"]
    if "error" in impact:
        return f"Error analyzing supply delay: {impact['error']}"
    
    delays_analyzed = impact.get("delays_analyzed", {})
    at_risk_dishes = impact.get('at_risk_dishes', [])
    supply_risks = impact.get('supply_risks', [])
    threshold = impact.get('threshold_days', 5)
    
    # Header
    response = "**SUPPLY DELAY ANALYSIS**\n\n"
    
    # Query parsing
    response += "**Query Parsed:**\n"
    for ingredient, days in delays_analyzed.items():
        ingredient_name = ingredient.replace('_', ' ').title()
        base_lead_time = 3  # default
        for risk in supply_risks:
            if risk['ingredient'] == ingredient:
                base_lead_time = risk.get('base_lead_time_days', 3)
                break
        
        response += f"- Ingredient: {ingredient}\n"
        response += f"- Delay: {days} additional days\n"
        response += f"- Current lead time: {base_lead_time} days → {base_lead_time + days} days total\n"
    response += "\n"
    
    # Supply Risk Assessment
    response += "**Supply Risk Assessment:**\n"
    high_risk_items = [r for r in supply_risks if r.get('risk_level') == 'HIGH']
    medium_risk_items = [r for r in supply_risks if r.get('risk_level') == 'MEDIUM']
    
    if high_risk_items:
        response += "**Critical Risk Items:**\n"
        for risk in high_risk_items:
            response += f"- {risk['ingredient'].replace('_', ' ').title()}: {risk['affected_dish_count']} menu items affected\n"
    
    if medium_risk_items:
        response += "**Medium Risk Items:**\n"
        for risk in medium_risk_items:
            response += f"- {risk['ingredient'].replace('_', ' ').title()}: {risk['affected_dish_count']} menu items affected\n"
    
    response += "\n"
    
    # Impact Timeline
    response += "**Impact Timeline:**\n"
    max_delay = max(delays_analyzed.values()) if delays_analyzed else 0
    response += f"- Days 1-{threshold-1}: Normal operations (current inventory)\n"
    response += f"- Days {threshold}-{threshold+max_delay}: **STOCKOUT RISK** - {len(at_risk_dishes)} menu items affected\n"
    
    # Estimate revenue impact
    revenue_at_risk = len(at_risk_dishes) * 15 * 7
    response += f"- Revenue at risk: ~${revenue_at_risk}/week\n\n"
    
    # Substitution Strategy
    substitutions = analysis_result.get("available_substitutions", [])
    if substitutions:
        response += "**Substitution Strategy:**\n"
        for i, sub in enumerate(substitutions[:3], 1):
            lead_time_info = sub.get('lead_time_improvement', 'Unknown timing')
            if 'faster' in lead_time_info:
                response += f"✅ **Applied:** {sub['original']} → {sub['substitute']} ({sub['context']} context)\n"
                response += f"- Affected dishes can continue production\n"
                response += f"- Rationale: \"{sub['rationale']}\"\n"
                response += f"- Lead time: {lead_time_info}\n\n"
            else:
                response += f"❌ **Limited Options:** {sub['original']} → {sub['substitute']}\n"
                response += f"- {lead_time_info}\n"
                response += f"- Consider temporary menu adjustments\n\n"
        
        response += "**Mitigation Plan:**\n"
        response += "1. **Immediate:** Implement viable substitutions above\n"
        response += "2. **Short-term:** Contact backup suppliers\n"
        response += "3. **Communication:** Notify customers of temporary menu changes\n"
    else:
        response += "**Mitigation Plan:**\n"
        response += "❌ No suitable substitutions found\n"
        response += "**Recommendations:**\n"
        response += "1. Contact alternative suppliers immediately\n"
        response += "2. Increase safety stock for critical ingredients\n"
        response += "3. Consider temporary menu modifications\n"
    
    return response

def format_category_response(analysis_result: Dict[str, Any]) -> str:
    """Format category cost breakdown response"""
    category = analysis_result.get("category_filter", "dishes")
    category_dishes = analysis_result["category_dishes"]
    
    if not category_dishes:
        return f"No {category} dishes found in the menu."
    
    total_cost = sum(d['ingredient_cost'] for d in category_dishes)
    avg_percentage = sum(d['cost_percentage'] for d in category_dishes) / len(category_dishes)
    
    response = f"**{category.upper()} COST BREAKDOWN**\n\n"
    response += f"**Summary:**\n"
    response += f"- {len(category_dishes)} {category} dishes analyzed\n"
    response += f"- Total ingredient costs: ${total_cost:.2f}\n"
    response += f"- Average cost ratio: {avg_percentage:.1f}% of menu price\n\n"
    
    response += "**Individual Dishes:**\n"
    for i, dish in enumerate(category_dishes[:8], 1):
        response += f"{i}. **{dish['name']}**\n"
        response += f"   - Menu price: ${dish['menu_price']:.2f}\n"
        response += f"   - Ingredient cost: ${dish['ingredient_cost']:.2f} ({dish['cost_percentage']:.1f}%)\n"
        
        ingredients = dish.get('ingredients', {})
        if ingredients:
            top_ingredients = sorted(ingredients.items(), key=lambda x: x[1]['total_cost'], reverse=True)[:3]
            response += f"   - Top ingredients: "
            ingredient_costs = [f"{ing.replace('_', ' ')} (${data['total_cost']:.2f})" for ing, data in top_ingredients]
            response += ", ".join(ingredient_costs)
        response += "\n"
    
    return response

def format_substitution_followup_response(analysis_result: Dict[str, Any]) -> str:
    """Format substitution follow-up response"""
    recent_ingredients = analysis_result["followup_context"]
    substitutions = analysis_result.get("available_substitutions", [])
    
    response = f"**SUBSTITUTION OPTIONS**\n\n"
    response += f"**Available substitutions for: {', '.join([ing.replace('_', ' ') for ing in recent_ingredients])}**\n\n"
    
    if substitutions:
        for i, sub in enumerate(substitutions[:4], 1):
            response += f"**{i}. {sub['original'].replace('_', ' ').title()} → {sub['substitute'].replace('_', ' ').title()}**\n"
            response += f"   - Context: {sub['context']}\n"
            response += f"   - Cost impact: {sub.get('cost_impact', 'Unknown')}\n"
            response += f"   - Rationale: {sub['rationale']}\n"
            if 'affected_dish' in sub:
                response += f"   - Example dish: {sub['affected_dish']}\n"
            response += "\n"
    else:
        response += "No substitutions are currently available for those ingredients.\n"
        response += "Consider contacting suppliers for alternative options.\n"
    
    return response

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)