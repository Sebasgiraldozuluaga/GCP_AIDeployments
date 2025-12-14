# ruff: noqa
# Copyright 2025 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import datetime
from zoneinfo import ZoneInfo

from google.adk.agents import Agent
from google.adk.apps.app import App

import os
import google.auth

#_, project_id = google.auth.default()
#os.environ["GOOGLE_CLOUD_PROJECT"] = project_id
#os.environ["GOOGLE_CLOUD_LOCATION"] = "global"
#os.environ["GOOGLE_GENAI_USE_VERTEXAI"] = "True"

# The Inventory Database (Dictionary)
INVENTORY = {
    "brass lamp": {"price": 50, "cost": 30, "stock": 5},
    "silk scarf": {"price": 500, "cost": 300, "stock": 2},
    "sandalwood carving": {"price": 1000, "cost": 800, "stock": 1},
    "miniature taj mahal": {"price": 2000, "cost": 1500, "stock": 0} # Out of stock item
}

def check_inventory(item_name: str):
    """Checks if an item is in stock and returns price. Use this tool when asking for price of an item."""
    print(f"DEBUG: Checking inventory for {item_name}") # Good for debugging!
    item_lower = item_name.lower()

    # Simple partial match search
    for key in INVENTORY:
        if key in item_lower:
            data = INVENTORY[key]
            if data["stock"] > 0:
                return f"Yes! We have {key}. Price is {data['price']} coins."
            else:
                return f"Arre, sorry! {key} is currently out of stock."

    return "Sorry friend, I don't think we sell that."

def get_weather(query: str) -> str:
    """Simulates a web search. Use it get information on weather.

    Args:
        query: A string containing the location to get weather information for.

    Returns:
        A string with the simulated weather information for the queried location.
    """
    if "sf" in query.lower() or "san francisco" in query.lower():
        return "It's 60 degrees and foggy."
    return "It's 90 degrees and sunny."


def get_current_time(query: str) -> str:
    """Simulates getting the current time for a city.

    Args:
        city: The name of the city to get the current time for.

    Returns:
        A string with the current time information.
    """
    if "sf" in query.lower() or "san francisco" in query.lower():
        tz_identifier = "America/Los_Angeles"
    else:
        return f"Sorry, I don't have timezone information for query: {query}."

    tz = ZoneInfo(tz_identifier)
    now = datetime.datetime.now(tz)
    return f"The current time for query {query} is {now.strftime('%Y-%m-%d %H:%M:%S %Z%z')}"


root_agent = Agent(
    name="root_agent",
    model="gemini-2.0-flash-001",
    # We update the instruction to tell Raju to use the tool!
    instruction="""
    You are Raju, the owner of 'Raju's Royal Artifacts' in the Digital Bazaar.
    You speak in a mix of English and a little bit of Indian-English flair ("Hello my friend!", "Best price for you!").

    Your Goal: SELL. But do not sell cheap!

    IMPORTANT: You do NOT know what is in stock by memory.
    ALWAYS use your `check_inventory` tool to find out what items are available and their prices before answering the customer.

    If the customer asks for a discount, act shocked. "This is already best price!", "My children need to eat!".
    Only give a maximum 10% discount if they really insist.
    Be funny, charming, but shrewd.
    """,
    # We replace the old tools with our new one
    tools=[check_inventory],
)

app = App(root_agent=root_agent, name="app")
