"""
Logging utility module.

This sets up a singleton logger named "MyLogger" that:
- Outputs logs both to the terminal and to a file ("logs.log").
- Prevents multiple handler attachments (safe for reuse across modules).
- Provides a simple `log_and_print()` function to log messages at INFO level.

Usage:
    from helper.helper import log_and_print
    log_and_print("This will appear in the console and in logs.log")
"""
import logging
import sys

# Setup logger only once
logger = logging.getLogger("MyLogger")
logger.setLevel(logging.INFO)

# Prevent multiple handlers if script is imported or run multiple times
if not logger.handlers:
    # File handler (logs saved to file)
    file_handler = logging.FileHandler("logs.log")
    file_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))

    # Console handler (logs shown in terminal)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(logging.Formatter('%(message)s'))

    # Add both handlers to the logger
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

def log_and_print(message: str):
    """Logs the message to both console and file."""
    logger.info(message)
