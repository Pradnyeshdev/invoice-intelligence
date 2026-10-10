# Invoice Intelligence

**A Python-based invoice processing and validation platform built with FastAPI and React.**

Invoice Intelligence helps users upload invoice documents, extract relevant information, validate financial fields, and review processed invoice records through a web dashboard.

## Features

* **Document upload:** Accepts supported PDF and image files.
* **Text extraction:** Extracts selectable PDF text and supports local OCR where implemented.
* **Invoice parsing:** Identifies common fields such as invoice number, date, vendor, subtotal, tax, total, and currency.
* **Data validation:** Checks extracted values and flags missing or inconsistent information.
* **Invoice history:** Stores processed records and supports viewing and deleting saved invoices.
* **REST API:** Provides backend endpoints through FastAPI.
* **Web interface:** React and TypeScript frontend for interacting with the application.
* **Automated tests:** Includes backend tests for core application behavior.

## Technology Stack

| Area                | Technologies                           |
| ------------------- | -------------------------------------- |
| Backend             | Python, FastAPI                        |
| Frontend            | React, TypeScript, Vite                |
| Document processing | PyMuPDF, Python parsing and validation |
| Local persistence   | SQLite                                 |
| Testing             | Pytest                                 |

## How It Works

1. Upload a supported invoice document.
2. Extract text from the document.
3. Parse the available invoice fields.
4. Validate the extracted information.
5. Review the results and saved invoice history.

## Run Locally

### Prerequisites

* Python installed
* Node.js and npm installed

### Backend

From the project root, open a terminal:

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload
```

The backend API should be available at `http://127.0.0.1:8000`.

Interactive API documentation is available at `http://127.0.0.1:8000/docs`.

### Frontend

Open a second terminal from the project root:

```powershell
cd frontend
npm install
npm run dev
```

Open the local URL printed by Vite in the terminal. Follow any additional environment configuration required by the current project setup.

## Project Structure

```text
invoice-intelligence/
├── backend/       # FastAPI application and invoice processing
├── frontend/      # React and TypeScript user interface
├── sample-data/   # Sample data, if included
├── .env.example   # Example environment configuration
└── README.md
```

## Testing

Run the backend test suite from the backend directory:

```powershell
python -m pytest
```

Build the frontend from its directory:

```powershell
npm run build
```

## Current Scope and Limitations

* Invoice extraction and validation use the implementations available in the current codebase; extracted results may require human review.
* AI/LLM-based evaluation and cloud OCR are not claimed as implemented features.
* A successful local run does not imply that a public deployment is available.
* Cloud persistence and deployment must be configured and tested separately before they can be considered operational.

## Privacy and Security

Use synthetic or non-sensitive sample invoices when demonstrating the project. Do not upload confidential financial documents to an unverified deployment.

Authentication, per-user access controls, and secure production storage must be verified before the application is exposed for real invoice data.

## Purpose

This project demonstrates practical skills in Python backend development, REST API design, document processing, data validation, database persistence, frontend integration, and automated testing.
