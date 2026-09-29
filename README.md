# Hermes 

![Hermes Icon](https://github.com/jabaldoo/Hermes/blob/main/hermes.png)

Nie będę robił w konia Hermes to...

## Installation

### Prerequisites

- Python 3.10 or higher
- pip (Python package installer)

### Setup

1. **Clone the repository:**
   ```bash
   git clone https://github.com/your-username/Hermes.git
   cd Hermes
   ```

2. **Create a virtual environment (recommended):**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows use `venv\Scripts\activate`
   ```

3. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

## Getting Started

To launch the Hermes application, run:

```bash
python main.py
```

The server will typically be available at `http://127.0.0.1:8000`.

## Project Structure

- `main.py`: Entry point of the application.
- `db.py`: Database management and connectivity.
- `edge_ai.py`: Edge AI logic and processing.
- `anonymizer.py`: Data anonymization tools for privacy compliance.
- `data/`: Directory containing system data and resources.
- `static/` & `templates/`: Frontend assets and HTML templates.

## Testing

Run the test suite to ensure everything is working correctly:

```bash
pytest tests/
```
