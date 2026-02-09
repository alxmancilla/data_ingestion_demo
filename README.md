# Data Ingestion Demo

A Python project demonstrating data ingestion capabilities with data validation, generation, and processing.

## Features

- **Data Validation**: Using Pydantic for robust data validation and serialization
- **Synthetic Data Generation**: Faker integration for generating realistic test data
- **UUID v7 Support**: Time-ordered UUIDs for better database performance
- **Progress Tracking**: Visual progress bars with tqdm

## Requirements

- Python 3.8 or higher
- pip (Python package manager)

## Installation

1. Clone the repository:
```bash
git clone <repository-url>
cd data_ingestion_demo
```

2. Create a virtual environment:
```bash
python -m venv venv
```

3. Activate the virtual environment:
   - On macOS/Linux:
     ```bash
     source venv/bin/activate
     ```
   - On Windows:
     ```bash
     venv\Scripts\activate
     ```

4. Install dependencies:
```bash
pip install -r requirements.txt
```

5. For development, install dev dependencies:
```bash
pip install -r requirements-dev.txt
```

## Project Structure

```
data_ingestion_demo/
├── src/                    # Source code
│   └── __init__.py
├── tests/                  # Test files
│   └── __init__.py
├── requirements.txt        # Production dependencies
├── requirements-dev.txt    # Development dependencies
├── pyproject.toml         # Project configuration
├── .gitignore             # Git ignore rules
└── README.md              # This file
```

## Usage

```python
# Example usage will be added as the project develops
from src import __version__

print(f"Data Ingestion Demo v{__version__}")
```

## Development

### Running Tests

```bash
pytest
```

### Code Formatting

```bash
black src/ tests/
```

### Linting

```bash
flake8 src/ tests/
```

### Type Checking

```bash
mypy src/
```

## Dependencies

- **pydantic** (>=2.6.0): Data validation using Python type annotations
- **faker** (>=22.0.0): Generate fake data for testing
- **uuid7** (>=0.1.0): UUID version 7 implementation
- **tqdm** (>=4.66.0): Progress bar for loops and data processing

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add some amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Contact

For questions or feedback, please open an issue in the repository.

