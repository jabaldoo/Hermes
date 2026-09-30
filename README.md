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

2. **Run start.bat**
   ```bash
   It ill install every dependency, and automatically run the HERMES system.
   ```

## Getting Started

To launch the Hermes application, run:

```
start.bat from the Hermes folder
```

The server will typically be available at `http://127.0.0.1:8000`.

## Project Structure

- `start.bat`: Installs every dependency, run on every boot, it wont download anything else besides the dependencies.
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
