import os
import logging
from datetime import datetime
from pathlib import Path
from pythonjsonlogger import jsonlogger

def setup_logging(log_path, logger_name, is_json_format=True):
    """
    Setups logging configuration.
    Args:
        log_path (str): The path to the log file.
        logger_name (str): The name of the logger.
        is_json_format (bool): Whether to use JSON format for logs.
    Returns:
        logging.Logger: Configured logger instance.
    """
    log_path = Path(log_path)
    log_path.parent.mkdir(parents=True, exist_ok=True)

    logger = logging.getLogger(logger_name)
    logger.setLevel(logging.INFO)

    log_file_name = f"{logger_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
    file_handler = logging.FileHandler(log_path / log_file_name)

    if is_json_format:
        formatter = jsonlogger.JsonFormatter('%(asctime)s %(levelname)s %(name)s %(module)s %(funcName)s %(lineno)d %(message)s')
    else:
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')

    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    # Add a stream handler to also print logs to console
    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)
    logger.addHandler(stream_handler)

    return logger
