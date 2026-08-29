# Dubizzle Cars — Inventory-First AI Assistant

An AI-powered conversational car discovery assistant built with **FastAPI** and **Streamlit**. The application provides natural-language vehicle search grounded in the supplied Excel inventory, listing-specific follow-up questions, multi-turn conversational context, persistent user memory, saved favourites, lead qualification, and simulated viewing bookings.

The system is designed around an **inventory-first approach**: the supplied Excel dataset is the source of truth for vehicle information, while the language model is used for natural-language understanding and response generation rather than inventing vehicle facts.

---

## Quick Setup

### 1. Clone the Repository

```powershell
git clone https://github.com/Nysa44/Dubizzle-ai-Nysa.git
cd Dubizzle-ai-Nysa
2. Create and Activate the Virtual Environment

Using uv:

uv venv
.venv\Scripts\Activate.ps1

If uv is not installed, a standard Python virtual environment can also be used:

python -m venv .venv
.venv\Scripts\Activate.ps1
3. Install Dependencies

Using uv:

uv pip install -r requirements.txt --link-mode=copy

Alternatively:

python -m pip install -r requirements.txt
4. Configure the Gemini API Key

Create a .env file in the project root:

GEMINI_API_KEY=your_google_ai_studio_api_key
GEMINI_MODEL=gemini-3.7-flash

The API key is required for the language-model interpretation layer.

Running the Application

The application consists of a FastAPI backend and a Streamlit frontend.

Terminal 1 — Backend

Open PowerShell in the project directory and activate the environment:

.venv\Scripts\Activate.ps1

Start the FastAPI server:

uvicorn backend.main:app --reload

The backend runs at:

http://127.0.0.1:8000

You can also verify the backend through:

http://127.0.0.1:8000/docs

A successful startup should show:

INFO: Uvicorn running on http://127.0.0.1:8000
INFO: Application startup complete.
Terminal 2 — Frontend

Open a second PowerShell terminal in the same project directory:

.venv\Scripts\Activate.ps1

Start Streamlit:

streamlit run frontend/app.py

The interface will be available at:

http://localhost:8501

Open the displayed localhost URL in a browser.

Design Choices
Client — Streamlit

Streamlit was chosen instead of a Notebook because this project is designed around an interactive conversational experience. A chat-based interface makes it easy to demonstrate natural-language vehicle searches, follow-up questions, saved favourites, persistent memory, lead qualification, and viewing bookings. It also keeps the client lightweight while allowing the backend to remain independently testable through FastAPI.

The Streamlit application acts primarily as the presentation layer. It sends user messages to the FastAPI backend and renders the returned responses, vehicle information, memory state, and interaction controls. This separation also makes it possible to replace the Streamlit client with another interface in the future without rewriting the core backend logic.

Agent / Language Model

The backend uses the Google Gemini model through the google-genai package for natural-language interpretation and conversational responses. The model is not treated as the source of truth for vehicle information. Deterministic application logic handles inventory retrieval, listing selection, important vehicle facts, booking constraints, lead confirmation, and guardrails.

This approach keeps the LLM responsible for understanding natural user requests while the application remains responsible for validating and grounding factual vehicle information.

Search and Retrieval

The supplied Excel workbook is the primary vehicle source. The application loads the cleaned dataset sheet and uses structured fields such as:

Make
Model
Year
Trim
Title
Description
Photo URL

Additional information such as price, mileage, warranty, regional specification, body type, performance, and other vehicle attributes may appear inside listing titles or descriptions. The backend extracts these values from the listing text when they are explicitly present.

Retrieval uses deterministic filtering and keyword-based matching over the inventory rather than relying on an external vector database. This is appropriate for the supplied dataset size and provides predictable, explainable results.

The system also distinguishes between inventory-wide searches and focused follow-up questions. For example, after displaying several vehicles, a question such as:

What's the mileage of the second one?

is resolved against the active result set instead of starting an unrelated new search.

Memory — SQLite

SQLite is used for persistent application state because it requires no external database infrastructure and is lightweight enough for the project.

Short-term memory stores the current session's conversation state, including previous messages, active result listings, and pending booking or lead actions. This allows references such as:

the first one
the second one
that car
this car

to be resolved across multiple turns.

Long-term memory stores user information such as preferences, budgets, and favourites. This allows a returning user to start a completely new conversation while still having relevant preferences or saved vehicles recalled.

Implementation and Design Decisions

The backend is separated into modules responsible for configuration, inventory access, database operations, parsing, schema validation, language-model interaction, and agent behaviour. Vehicle facts are grounded in the Excel dataset and listing descriptions, while important operations such as booking and lead qualification are handled deterministically. This prevents unsupported vehicle information from being generated simply because a language model can produce a plausible answer.

The application also includes multi-turn context handling, persistent user memory, favourites, lead qualification with confirmation, CSV lead persistence, viewing-slot validation, and automotive-specific guardrails. Features outside the scope of this prototype could include real authentication, a production CRM integration, live dealership inventory synchronization, real appointment scheduling, payment processing, production-scale semantic/vector retrieval, analytics dashboards, and deployment infrastructure.

Project Architecture
## Project Architecture

```text
Dubizzle-ai-Nysa/
│
├── backend/
│   ├── __init__.py
│   ├── agent.py
│   ├── config.py
│   ├── db.py
│   ├── inventory.py
│   ├── llm.py
│   ├── main.py
│   ├── parser.py
│   └── schemas.py
│
├── data/
│   ├── cars_dataset.xlsx
│   ├── leads.csv
│   └── nysa.db
│
├── docs/
│   ├── data_notes.md
│   └── demo_transcript.md
│
├── frontend/
│   ├── api_client.py
│   └── app.py
│
├── screenshots/
│   ├── Booking-Carwise.png
│   ├── Booking.png
│   ├── Find Cars Between AED 20K and AED 40K.png
│   ├── Find Cars under AED 50K.png
│   ├── Front Page.png
│   ├── Guardrails.png
│   ├── Leads saved and Testing.png
│   ├── Long Term Memory-1.png
│   ├── Long Term Memory-2.png
│   ├── Requests Section.png
│   ├── Short Term Memory - Category.png
│   ├── Short Term Memory - Specific car.png
│   ├── Show me SUVS.png
│   └── SUVS Result.png
│
├── tests/
│   ├── test_api.py
│   ├── test_inventory.py
│   └── test_parser.py
│
├── .env.example
├── .gitignore
├── pyproject.toml
├── README.md
└── requirements.txt
Core Features
Inventory-Grounded Search

Users can search the supplied inventory using natural language, for example:

Show me Mercedes cars
I'm looking for a 2024 Mercedes GLS
Show me cars under AED 50,000
Show me cars with a turbo engine

Results are grounded in the supplied Excel inventory.

Listing-Specific Questions

Users can ask questions about a selected vehicle, including:

What's the mileage?
What's the warranty?
Is it GCC spec?
What's the top speed?

If a requested fact is not stated in the listing, the system avoids inventing an answer.

Multi-Turn Context

The assistant maintains the current result set so follow-up references can be resolved:

Show me BMW cars
What's the mileage of the second one?
What about its warranty?
Persistent Memory

The system stores user preferences and favourites in SQLite.

A user can start a new conversation and still have previously stored information recalled.

Saved Favourites

Users can save a vehicle and retrieve their saved cars later.

Example:

I like the second one. Save it.

Then in a new conversation:

What cars have I saved?
Lead Qualification

The assistant can collect lead information such as:

Name
Phone number
Budget
Vehicle requirements
Preferences

The user is asked to confirm the enquiry before it is persisted.

Confirmed enquiries are written to:

data/leads.csv
Viewing Bookings

Users can request a viewing for a selected listing.

Viewing hours are restricted to:

Monday–Saturday
8:00 AM–8:00 PM

Bookings are simulated for the application and duplicate listing/time slots are prevented.

Grounding and Guardrails

The application includes deterministic handling for several important edge cases.

Price vs. Monthly Finance

The system distinguishes a vehicle's cash/asking price from monthly finance amounts so that a monthly payment is not incorrectly presented as the vehicle price.

Mileage vs. Performance

Values such as:

318 km/h

are treated as performance/top-speed information rather than mileage.

Missing Information

If a listing does not explicitly contain a requested fact, the assistant returns that the information is not stated/listed rather than generating a value.

Listing Selection

References such as:

the first one
the second one
that car
this car
it

are resolved against the active result set where possible.

Unsupported Requests

Non-automotive requests are handled through application guardrails instead of being answered as general-purpose questions.

Testing

The project includes automated regression tests covering the main backend and inventory functionality.

Activate the environment:

.venv\Scripts\Activate.ps1

Run the complete test suite:

python -m pytest -q

Expected result:

.......................................... [100%]

42 passed, 1 warning

The warning is an environment dependency deprecation warning and does not indicate a failing test.

The tests cover areas including:

Excel inventory loading
Inventory retrieval
Vehicle attribute extraction
Price extraction
Mileage extraction
Mercedes GLS information
Listing-specific follow-ups
Cheapest/most-expensive queries
Intent routing
Guardrails
Session behaviour
Long-term memory
API behaviour
Lead Verification

Confirmed leads can be inspected from PowerShell:

Import-Csv .\data\leads.csv | Format-Table -AutoSize

Example output:

lead_id        created_at           user_id   name   phone
-------        ----------           -------   ----   -----
LEAD-35CC864D  2026-08-29T15:34:33  nysaa     Nysa   0501234567

This verifies that confirmed enquiries are persisted to the CSV file.

Demonstration
1. Multi-Turn Inventory Conversation

A multi-turn conversation demonstrates that the assistant can maintain the active inventory result set.

Example:

User:
I'm interested in the 2024 Mercedes GLS.

Assistant:
2024 Mercedes-Benz Gls-Class · Listing #40
Spec: GCC
Warranty: stated

User:
What's the warranty?

Assistant:
Warranty: 5 Years Gargash Auto Warranty.
Regional specification: GCC

A screenshot demonstrating the multi-turn inventory conversation can be added here:

screenshots/multi_turn_inventory.png
2. Long-Term Memory Across a New Session

The application stores user preferences and favourites in SQLite.

Example:

Session 1

User:
My budget is AED 50,000 and I prefer BMW cars.

Assistant:
Preference saved.

A new conversation/session is then started using the same user.

Session 2

User:
What do you remember about me?

Assistant:
I remember your budget and vehicle preferences from previous conversations.

Screenshot:

screenshots/long_term_memory.png
3. Lead Qualification

Example:

User:
My name is Nysa and my phone number is 0501234567.

Assistant:
Here's the enquiry I can save...
Reply "confirm" and I'll record it.

User:
confirm

Assistant:
Done — your enquiry is saved.

The resulting lead can be verified with:

Import-Csv .\data\leads.csv | Format-Table -AutoSize

Screenshot:

screenshots/lead_verification.png
4. Guardrails

The application also demonstrates handling of requests outside the intended automotive scope.

Example:

User:
Write me Python code.

Assistant:
I can help with dubizzle Cars — searching the provided inventory,
comparing cars, remembering preferences, qualifying enquiries,
and booking viewing slots.

Screenshot:

screenshots/guardrails.png
Running the Full Application

Use two PowerShell terminals.

Terminal 1
cd Dubizzle-ai-Nysa
.venv\Scripts\Activate.ps1
uvicorn backend.main:app --reload
Terminal 2
cd Dubizzle-ai-Nysa
.venv\Scripts\Activate.ps1
streamlit run frontend/app.py

Then open:

http://localhost:8501
Project Scope

The current prototype focuses on:

Grounded vehicle discovery
Natural-language search
Listing-level information retrieval
Multi-turn context
Persistent user memory
Favourites
Lead qualification
Viewing bookings
Deterministic guardrails
Automated testing

Potential future extensions include:

Real user authentication
Production database infrastructure
Live inventory synchronization
Real dealership booking integration
CRM integration
Payment processing
Semantic/vector retrieval for much larger inventories
Multilingual support
Analytics and sales dashboards
Production deployment and monitoring
LLM provider fallback/routing

These features are outside the scope of the current prototype.

Tech Stack
Python
FastAPI — backend API
Streamlit — conversational frontend
Google Gemini — language-model interpretation
Pydantic — request/response validation
SQLite — persistent application and user memory
Pandas / OpenPyXL — Excel inventory loading
Pytest — automated testing
uv — Python environment and dependency management