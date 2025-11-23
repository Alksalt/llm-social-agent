# src/tools/file_tools.py

"""
File-related helper functions.

These functions handle:
- Reading text from files (e.g. diary.txt, x_threads.txt),
- Returning clean strings for the orchestrator.

We keep them small and focused so file I/O is not mixed with
database logic or LLM logic.
"""
from pathlib import Path
def read_text_file(path_str: str) -> str:
    """
    Read a UTF-8 text file and return its contents as a string.

    Args:
        path_str:
            File path as a string (e.g. 'data/diary.txt').

    Returns:
        The file contents as a string.
        If the file does not exist, it returns an empty string.
    """
    path = Path(path_str)

    if not path.exists():
        return ""
    with path.open("r", encoding="utf-8") as f:
        content = f.read()
    
    return content
