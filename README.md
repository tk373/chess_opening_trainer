# Chess Opening Trainer

This is a chess opening trainer that supports 4 openings with 5 lines each. After completing the openings, Stockfish takes over and plays against you at an ELO of about 1300.

## Features
- Interactive chess board with drag-and-drop piece movement
- Opening training with multiple variations
- Stockfish integration for post-opening play
- Real-time position evaluation
- Opening and line selection interface

## Requirements
- Python 3.8 or higher
- Stockfish chess engine (you need to provide the path to your Stockfish binary in config.py)

## Setup

1. Create a Python virtual environment:
```bash
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
```

2. Install the required packages:
```bash
pip install -r requirements.txt
```

3. Edit `config.py` and set the path to your Stockfish binary:
```python
STOCKFISH_PATH = "/path/to/your/stockfish"
```

4. Run the program:
```bash
python main.py
```

## Controls
- Click and drag pieces to move them
- Use the dropdown menus to select different openings and lines
- Click "Reset Position" to start over

## System Requirements
- For Ubuntu: No additional system packages required
- For macOS: No additional system packages required
- For Windows: No additional system packages required

The program now uses PyQt5 for the interface, which provides better cross-platform compatibility and performance compared to the previous Pygame implementation. 