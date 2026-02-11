# ruff: noqa
import os
import json
import logging
import warnings
import traceback
from typing import List, Dict, Any

import google.auth
from google.adk.agents import Agent
from google.adk.apps.app import App, EventsCompactionConfig, ResumabilityConfig
from google.genai import types as genai_types
from langchain_community.agent_toolkits import SQLDatabaseToolkit
from langchain_community.agent_toolkits.sql.base import create_sql_agent
from langchain_google_vertexai import ChatVertexAI

from .agent_instructions import AGENT_INSTRUCTION, SQL_SYSTEM_PROMPT
from .database import get_sql_db
from .hf_tools import (
    search_hf_models, search_hf_datasets, search_hf_spaces,
    get_hf_model_details, get_hf_dataset_details
)
from .app_utils.formatters import (
    sanitize_text_for_json, sanitize_dict_for_json, format_monetary_values_in_text
)
from .app_utils.viz_parser import analyze_visualization, generate_conclusion

# --- Configuration & Logging ---
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

warnings.filterwarnings("ignore", message=".*Invalid type NoneType for attribute.*")
logging.getLogger("opentelemetry.attributes").setLevel(logging.ERROR)

_, project_id = google.auth.default()
os.environ["GOOGLE_CLOUD_PROJECT"] = project_id
os.environ["GOOGLE_CLOUD_LOCATION"] = os.getenv("GOOGLE_CLOUD_LOCATION", "us-central1")
os.environ["GOOGLE_GENAI_USE_VERTEXAI"] = "True"

# --- SQL Agent Setup ---
_sql_agent = None

def get_sql_agent():
    """Lazy initialization of the SQL agent."""
    global _sql_agent
    if _sql_agent is None:
        db = get_sql_db()
        llm = ChatVertexAI(
            model="gemini-2.0-flash",
            project=project_id,
            location=os.getenv("GOOGLE_CLOUD_LOCATION", "us-central1"),
            temperature=0.0,
            max_output_tokens=1000,
            max_retries=2,
            request_timeout=30,
        )
        toolkit = SQLDatabaseToolkit(db=db, llm=llm)
        _sql_agent = create_sql_agent(
            llm=llm,
            toolkit=toolkit,
            agent_type="tool-calling",
            verbose=True,
            prefix=SQL_SYSTEM_PROMPT,
            return_intermediate_steps=True
        )
    return _sql_agent

# --- Database Tool ---

def query_database(question: str) -> str:
    """
    Query the PostgreSQL database using natural language.
    Returns structured JSON with data and visualization config.
    """
    try:
        logger.info(f"Executing query: {question[:100]}")
        
        sql_agent = get_sql_agent()
        result = sql_agent.invoke({"input": question})
        raw_output = result.get("output", "No result returned.")
        
        thinking_steps = _extract_thinking_steps(question, result.get("intermediate_steps", []))
        
        # Clean and format output
        clean_obs = sanitize_text_for_json(raw_output)
        formatted_output = format_monetary_values_in_text(clean_obs)
        
        # Determine if visualization is possible
        viz_config = analyze_visualization(formatted_output, question)
        is_visualizable = viz_config.get("visualizable", False)
        
        conclusion = generate_conclusion(viz_config.get("data"), question) if is_visualizable else formatted_output
        
        response = {
            "data": viz_config.get("data", {}),
            "visualizable": is_visualizable,
            "conclusion": conclusion,
            "visualization": viz_config if is_visualizable else {"type": "none"},
            "text": formatted_output,
            "thinking": thinking_steps,
            "totalRecords": viz_config.get("totalRecords", 0)
        }
        
        json_resp = json.dumps(sanitize_dict_for_json(response), ensure_ascii=True, separators=(',', ':'))
        return f"<<<GENERATIVE_BI_START>>>\n{json_resp}\n<<<GENERATIVE_BI_END>>>"
        
    except Exception as e:
        logger.error(f"Error in query_database: {e}")
        traceback.print_exc()
        return _format_error_response(str(e))

def _extract_thinking_steps(question: str, intermediate_steps: list) -> List[Dict]:
    """Parses LangChain intermediate steps into a clean thinking chain."""
    steps = [{"type": "query", "label": "Pregunta", "content": question}]
    
    for action, observation in intermediate_steps:
        tool_name = getattr(action, 'tool', '')
        if 'schema' in tool_name.lower() or 'list' in tool_name.lower():
            steps.append({"type": "schema", "label": "Explorando esquema", "content": "Consultando estructura de tablas..."})
        elif 'query' in tool_name.lower():
            sql = getattr(action, 'tool_input', {}).get('query', '')
            preview = str(observation)[:200] + "..." if len(str(observation)) > 200 else str(observation)
            steps.append({"type": "sql", "label": "Ejecutando SQL", "content": f"Resultados: {preview}", "sql": sql})
            
    steps.append({"type": "analyze", "label": "Analizando", "content": "Generando visualización..."})
    return steps

def _format_error_response(error_msg: str) -> str:
    err_body = {
        "data": {}, "visualizable": False, "conclusion": f"Error: {error_msg}",
        "visualization": {"type": "none"}, "text": f"Error: {error_msg}", "thinking": []
    }
    return f"<<<GENERATIVE_BI_START>>>\n{json.dumps(err_body)}\n<<<GENERATIVE_BI_END>>>"

# --- Agent & App Definition ---

root_agent = Agent(
    name="root_agent",
    model="gemini-2.0-flash",
    include_contents='default',
    instruction=AGENT_INSTRUCTION,
    tools=[
        query_database, search_hf_models, search_hf_datasets,
        search_hf_spaces, get_hf_model_details, get_hf_dataset_details
    ],
    generate_content_config=genai_types.GenerateContentConfig(
        temperature=0.1, max_output_tokens=2048, top_k=20
    )
)

app = App(
    root_agent=root_agent, 
    name="app",
    events_compaction_config=EventsCompactionConfig(compaction_interval=5, overlap_size=1),
    resumability_config=ResumabilityConfig(is_resumable=True)
)
