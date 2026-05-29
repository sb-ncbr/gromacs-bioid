"""Logging utilities for BAT3 pipeline runs."""

import logging
import os
from typing import List, Tuple


class FlushFileHandler(logging.FileHandler):
    """FileHandler that flushes after every record to ensure immediate writes."""
    
    def emit(self, record):
        super().emit(record)
        try:
            self.flush()
        except Exception:
            pass


def setup_run_log_handlers(run_dir: str) -> List[Tuple[logging.Handler, str]]:
    """
    Attach FileHandlers for a specific run.
    
    Args:
        run_dir: Path to the run directory (e.g., runs/<run_id>/).
    
    Returns:
        List of (handler, logger_name) tuples so caller can clean up.
        Logger name is empty string for root logger.
    """
    normal_log_path = os.path.join(run_dir, "results.log")
    debug_log_path = os.path.join(run_dir, "results.debug.log")
    
    # Create formatters
    formatter = logging.Formatter("[%(asctime)s] %(levelname)s %(name)s: %(message)s")
    
    # Create normal handler (INFO level)
    normal_handler = FlushFileHandler(
        normal_log_path, mode='a', encoding='utf-8'
    )
    normal_handler.setLevel(logging.INFO)
    normal_handler.setFormatter(formatter)
    
    # Create debug handler (DEBUG level)
    debug_handler = FlushFileHandler(
        debug_log_path, mode='a', encoding='utf-8'
    )
    debug_handler.setLevel(logging.DEBUG)
    debug_handler.setFormatter(formatter)
    
    # Add handlers to root logger so all modules propagate to them
    root = logging.getLogger()
    root.setLevel(logging.DEBUG)
    root.addHandler(normal_handler)
    root.addHandler(debug_handler)
    
    # Set named logger levels to DEBUG for redundancy (no duplicates since handlers are only on root)
    for name in ["base", "signature", "identifier", "verification"]:
        logging.getLogger(name).setLevel(logging.DEBUG)
    
    # Return handlers with empty string logger name (root)
    return [(normal_handler, ""), (debug_handler, "")]


def teardown_run_log_handlers(handlers: List[Tuple[logging.Handler, str]]) -> None:
    """
    Remove and close all handlers added by setup_run_log_handlers.
    
    Args:
        handlers: List of (handler, logger_name) tuples returned by setup_run_log_handlers.
    """
    for handler, logger_name in handlers:
        logger = logging.getLogger(logger_name)
        try:
            logger.removeHandler(handler)
        except Exception:
            pass  # Logger may no longer exist
        
        try:
            handler.close()
        except Exception:
            pass  # Handler may already be closed
