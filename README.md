# Dubizzle Cars — Inventory-First AI Assistant

An AI-powered conversational car discovery assistant built with **FastAPI** and **Streamlit**.

The assistant allows users to search a supplied vehicle inventory using natural language, ask follow-up questions about specific listings, save favourite vehicles, maintain conversational context, recall user preferences across sessions, qualify leads, and simulate vehicle viewing bookings.

The system follows an **inventory-first approach**: the supplied Excel dataset is the source of truth for vehicle information. The language model is used for natural-language understanding and response generation, while vehicle retrieval, important vehicle facts, booking rules, and other critical operations are handled by deterministic application logic.

---

## Features

- Natural-language vehicle search
- Excel-grounded vehicle inventory
- Listing-specific questions
- Multi-turn conversational context
- References such as "the first one", "the second one", and "that car"
- Persistent user memory
- Saved vehicle favourites
- Lead qualification
- Lead confirmation before persistence
- Viewing booking simulation
- Booking conflict protection
- Vehicle attribute extraction from listing descriptions
- Price and mileage disambiguation
- Automotive-specific guardrails
- Source evidence for listing information
- Automated regression tests

---

# Quick Setup

## 1. Clone the Repository

```powershell
git clone https://github.com/Nysa44/Dubizzle-ai-Nysa.git
cd Dubizzle-ai-Nysa
```

## 2. Create and Activate the Virtual Environment

This project uses `uv` for environment and dependency management.

### Using uv

```powershell
uv venv
.venv\Scripts\Activate.ps1
```

### Without uv

A standard Python virtual environment can also be used:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
```

## 3. Install Dependencies

### Using uv

```powershell
uv pip install -r requirements.txt --link-mode=copy
```

### Using pip

```powershell
python -m pip install -r requirements.txt
```

## 4. Configure the Gemini API

Create a `.env` file in the project root.

```env
GEMINI_API_KEY=your_google_ai_studio_api_key
GEMINI_MODEL=gemini-3.7-flash
```

The API key is used by the language-model interpretation layer.

---

# Running the Application

The application consists of:

- **FastAPI** backend
- **Streamlit** frontend

Run them in two separate PowerShell terminals.

## Terminal 1 — Backend

From the project directory:

```powershell
.venv\Scripts\Activate.ps1
uvicorn backend.main:app --reload
```

The FastAPI backend will run at:

```text
http://127.0.0.1:8000
```

FastAPI documentation is also available at:

```text
http://127.0.0.1:8000/docs
```

A successful startup should show:

```text
INFO:     Uvicorn running on http://127.0.0.1:8000
INFO:     Application startup complete.
```

## Terminal 2 — Frontend

Open a second PowerShell terminal in the same project directory:

```powershell
.venv\Scripts\Activate.ps1
streamlit run frontend/app.py
```

The Streamlit interface will normally be available at:

```text
http://localhost:8501
```

Open the displayed URL in your browser.

---

# Project Architecture

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
│   └── demonstration screenshots
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
```

### Backend

- `main.py` — FastAPI application and API endpoints
- `agent.py` — conversational routing and agent behaviour
- `inventory.py` — inventory loading and retrieval
- `parser.py` — vehicle attribute and listing text extraction
- `llm.py` — Gemini language-model interaction
- `db.py` — SQLite persistence and memory operations
- `config.py` — application configuration
- `schemas.py` — request and response validation

### Frontend

- `app.py` — Streamlit conversational interface
- `api_client.py` — communication between Streamlit and the FastAPI backend

### Data

- `cars_dataset.xlsx` — supplied vehicle inventory
- `leads.csv` — confirmed lead records
- `nysa.db` — SQLite database containing application/session/user state

### Tests

The test suite covers API behaviour, inventory handling, parsing, extraction, routing, and memory-related functionality.

---

# Design Choices

## Client — Streamlit

Streamlit was chosen instead of a Notebook because the application is designed around an interactive conversational experience. A chat-based interface makes it easy to test natural-language vehicle searches, follow-up questions, favourites, memory, lead qualification, and viewing bookings. It also keeps the frontend lightweight while allowing the FastAPI backend to remain independently testable.

The frontend is intentionally separated from the backend. Streamlit is responsible for the user experience and presentation, while FastAPI handles the application logic and data operations. This separation makes the system easier to maintain and allows another client interface to be added later without replacing the backend.

## Agent and Language Model

The backend uses **Google Gemini** through the `google-genai` package for natural-language understanding and conversational response generation.

The language model is **not treated as the source of truth for vehicle facts**. Instead, deterministic application logic handles inventory retrieval, listing selection, important vehicle attributes, booking constraints, lead confirmation, and guardrails.

This design allows the LLM to understand flexible user requests while keeping factual vehicle information grounded in the supplied inventory.

## Search and Retrieval

The supplied Excel workbook is the primary vehicle source.

Structured fields are loaded from the cleaned dataset, including:

- Make
- Model
- Year
- Trim
- Title
- Description
- Photo URL

Additional vehicle information such as price, mileage, warranty, regional specification, performance, and features can appear inside listing titles and descriptions. The backend extracts these values when they are explicitly present.

Retrieval uses deterministic filtering and keyword-based matching over the supplied inventory rather than an external vector database. This provides predictable and explainable results for the current dataset size.

The system also separates inventory-wide searches from listing-specific follow-up questions.

For example:

```text
User: Show me Mercedes cars

Assistant: [Mercedes results]

User: What's the mileage of the second one?

Assistant: [Mileage from the second active listing]
```

The second question is resolved against the active result set instead of triggering an unrelated inventory search.

## Memory — SQLite

SQLite is used for persistent state because it is lightweight, local, requires no separate database server, and is sufficient for the scope of this application.

### Short-Term Memory

Short-term session memory stores information such as:

- Conversation messages
- Active result listings
- Selected listing context
- Pending booking actions
- Pending lead actions

This allows references such as:

```text
the first one
the second one
that car
this car
it
```

to be resolved across multiple turns.

### Long-Term Memory

Long-term memory stores user information such as:

- Preferences
- Budget information
- Saved vehicles
- User history

This allows a user to start a completely new conversation while still having relevant information recalled.

---

# Implementation

The application separates the main responsibilities of the system into independent backend components. Inventory loading, parsing, retrieval, database operations, LLM interaction, API handling, and conversational routing are handled by separate modules. Vehicle information is grounded in the Excel dataset and listing descriptions, while important operations such as vehicle selection, booking validation, lead confirmation, and guardrails use deterministic logic.

The system supports multi-turn context, persistent user memory, saved favourites, lead qualification, CSV lead persistence, and simulated viewing bookings. The application also handles important extraction edge cases, such as distinguishing vehicle mileage from performance values and distinguishing cash prices from monthly finance amounts. Information that is not explicitly available in a listing is not invented.

---

# Core Functionality

## Inventory-Grounded Search

Users can search the inventory using natural language.

Examples:

```text
Show me Mercedes cars
```

```text
I'm looking for a 2024 Mercedes GLS
```

```text
Show me cars under AED 50,000
```

```text
Show me cars with a turbo engine
```

Results are grounded in the supplied Excel inventory.

---

## Listing-Specific Questions

Users can ask questions about a vehicle currently being discussed.

Examples:

```text
What's the mileage?
```

```text
What's the warranty?
```

```text
Is it GCC spec?
```

```text
What's the top speed?
```

If a requested fact is not explicitly stated in the listing, the system avoids inventing an answer.

---

## Multi-Turn Context

The assistant maintains the active result set across turns.

Example:

```text
User: Show me BMW cars

Assistant: [BMW results]

User: What's the mileage of the second one?

Assistant: [Mileage of second BMW]

User: What about its warranty?

Assistant: [Warranty information for the same vehicle]
```

---

## Persistent Memory

User preferences and favourites are stored in SQLite.

Example:

```text
Session 1

User: My budget is AED 50,000 and I prefer BMW cars.

Assistant: Preference saved.
```

After starting a completely new conversation:

```text
Session 2

User: What do you remember about me?

Assistant: [Previously stored preferences/history]
```

---

## Saved Favourites

Users can save vehicles from the current result set.

Example:

```text
I like the second one. Save it.
```

Saved vehicles can later be retrieved with:

```text
What cars have I saved?
```

---

## Lead Qualification

The assistant can collect lead information such as:

- Name
- Phone number
- Budget
- Vehicle requirements
- Preferences

The user is asked to confirm the enquiry before it is persisted.

Confirmed leads are written to:

```text
data/leads.csv
```

---

## Viewing Bookings

Users can request a viewing for a selected vehicle.

Viewing slots are restricted to:

```text
Monday–Saturday
8:00 AM–8:00 PM
```

Bookings are simulated within the application and duplicate listing/time slots are prevented.

---

# Grounding and Guardrails

The application includes deterministic handling for important edge cases.

## Price vs. Monthly Finance

The system distinguishes between a vehicle's cash/asking price and monthly finance amounts.

This prevents a monthly payment from being incorrectly displayed as the vehicle's actual price.

## Mileage vs. Performance

Performance values such as:

```text
318 km/h
```

are treated as top-speed information rather than mileage.

## Missing Information

If a requested fact is not explicitly stated in the listing, the assistant does not generate an unsupported value.

Instead, the user is informed that the information is not stated in the listing.

## Listing Selection

References such as:

```text
the first one
the second one
that car
this car
it
```

are resolved against the current active result set where possible.

## Inventory-Wide vs. Focused Queries

The system distinguishes between:

- Searching across the inventory
- Asking about the currently selected vehicle
- Performing booking or lead actions

For example, a query such as:

```text
Which cars have 7 seats?
```

is treated as an inventory-wide search rather than a question about only the currently focused vehicle.

---

# Testing

The project includes automated regression tests covering the backend, inventory, parsing, extraction, routing, API behaviour, and memory functionality.

Activate the virtual environment:

```powershell
.venv\Scripts\Activate.ps1
```

Run the complete test suite:

```powershell
python -m pytest -q
```

Current test result:

```text
.......................................... [100%]

42 passed, 1 warning
```

The warning is a dependency deprecation warning from the test environment and does not indicate a failing test.

The tests cover areas including:

- Excel inventory loading
- Inventory retrieval
- Vehicle attribute extraction
- Price extraction
- Mileage extraction
- Listing-specific follow-up questions
- Cheapest/most-expensive queries
- Intent routing
- Guardrails
- Session behaviour
- Long-term memory
- API behaviour

---

# Lead Verification

Confirmed leads can be inspected from PowerShell using:

```powershell
Import-Csv .\data\leads.csv | Format-Table -AutoSize
```

Example:

```text
lead_id        created_at           user_id   name   phone
-------        ----------           -------   ----   -----
LEAD-XXXXXXXX  2026-08-29T15:34:33  nysaa     Nysa   0501234567
```

This verifies that confirmed enquiries are persisted as lead records.

---

# Demonstrations

Screenshots demonstrating the application's functionality are stored in the `screenshots/` directory.

## 1. Multi-Turn Inventory Exploration

The application can maintain the active inventory result set and answer follow-up questions about a selected listing.

Example:

```text
User: Show me Mercedes cars

Assistant: [Mercedes listings]

User: What's the top speed of the second one?

Assistant: [Top speed from the selected listing]

User: What's the mileage of the second one?

Assistant: [Mileage from the same listing]
```

**Screenshot:**

```text
screenshots/Short Term Memory - Category.png
screenshots/Short Term Memory - Specific car.png
```

## 2. Long-Term Memory Across a New Session

The application stores user preferences and favourites in SQLite.

Example:

```text
Session 1

User: My budget is AED 50,000 and I prefer BMW cars.

Assistant: Preference saved.
```

A completely new conversation can then retrieve the stored information.

**Screenshots:**

```text
screenshots/Long Term Memory-1.png
screenshots/Long Term Memory-2.png
```

## 3. Lead Qualification and Persistence

A user can provide contact information, review the enquiry, and confirm it before it is saved.

**Screenshot:**

```text
screenshots/Leads saved and Testing.png
```

The resulting lead can also be verified using:

```powershell
Import-Csv .\data\leads.csv | Format-Table -AutoSize
```

## 4. Guardrails

The assistant restricts requests outside its intended automotive functionality.

**Screenshot:**

```text
screenshots/Guardrails.png
```

## 5. Viewing Booking

The application supports simulated viewing requests with booking validation.

**Screenshots:**

```text
screenshots/Booking.png
screenshots/Booking-Carwise.png
```

---

# Running the Full Application

Use two PowerShell terminals.

### Terminal 1 — Backend

```powershell
cd Dubizzle-ai-Nysa
.venv\Scripts\Activate.ps1
uvicorn backend.main:app --reload
```

### Terminal 2 — Frontend

```powershell
cd Dubizzle-ai-Nysa
.venv\Scripts\Activate.ps1
streamlit run frontend/app.py
```

Then open:

```text
http://localhost:8501
```

---

# Project Scope

The current implementation focuses on:

- Grounded vehicle discovery
- Natural-language search
- Listing-level information retrieval
- Multi-turn conversational context
- Persistent user memory
- Saved favourites
- Lead qualification
- Viewing bookings
- Deterministic guardrails
- Automated testing

Potential future extensions include:

- Production user authentication
- Production database infrastructure
- Live inventory synchronization
- Real dealership booking integration
- CRM integration
- Payment processing
- Semantic/vector retrieval for substantially larger inventories
- Multilingual support
- Analytics and sales dashboards
- Production deployment and monitoring
- LLM provider fallback/routing

These features are outside the scope of the current prototype.

---

# Tech Stack

| Technology | Purpose |
|---|---|
| Python | Application development |
| FastAPI | Backend API |
| Streamlit | Conversational frontend |
| Google Gemini | Natural-language interpretation |
| google-genai | Gemini API integration |
| Pydantic | Request/response validation |
| SQLite | Persistent memory and application state |
| Pandas / OpenPyXL | Excel inventory loading |
| Pytest | Automated testing |
| uv | Environment and dependency management |

---

# Repository Structure

```text
backend/       Backend API, agent logic, inventory, parsing and database
frontend/      Streamlit interface and API client
data/          Vehicle dataset and application data
docs/          Supporting documentation and demo notes
screenshots/   Application demonstration screenshots
tests/         Automated regression tests
```

---

# Notes

The `.env` file is intentionally excluded from version control. Use `.env.example` as the template for configuring the Gemini API key.

Generated application state such as the SQLite database and lead CSV can be excluded from Git when appropriate using the project's `.gitignore`.
