# infrastructure/cli/importers.py
import csv
from pathlib import Path
from typing import List

def load_sentences(file_path: str, csv_column: str = "sentence") -> List[str]:
    """
    Detects file type and loads sentences.
    """
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")
        
    if path.suffix == ".csv":
        return _load_from_csv(path, csv_column)
    elif path.suffix == ".txt":
        return _load_from_text(path)
    else:
        raise ValueError(f"Unsupported file type: {path.suffix}. Use .txt or .csv")

def _load_from_csv(path: Path, column: str) -> List[str]:
    """Loads sentences from a CSV file column."""
    sentences = []
    with open(path, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        if column not in reader.fieldnames:
            raise ValueError(f"Column '{column}' not found in {path}. Found: {reader.fieldnames}")
            
        for row in reader:
            sentence = row[column].strip()
            if sentence:
                sentences.append(sentence)
    return sentences

def _load_from_text(path: Path) -> List[str]:
    """
    Loads sentences from a plain text file.
    Handles both one-sentence-per-line and article formats.
    """
    with open(path, 'r', encoding='utf-8') as f:
        content = f.read()

    # Simple check: if content has many newlines, assume one-per-line
    lines = content.split('\n')
    if len(lines) > (len(content) / 100): # Heuristic: >1 newline per 100 chars
        return [line.strip() for line in lines if line.strip()]

    # Otherwise, assume article and split by sentence
    # This is a basic sentence splitter
    import re
    # Split on periods, question marks, exclamation marks followed by space or newline
    sentences = re.split(r'[.?!]\s+', content)
    
    return [s.strip() for s in sentences if s.strip()]
