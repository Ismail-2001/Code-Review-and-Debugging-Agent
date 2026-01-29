import logging
import re
from rich.logging import RichHandler

class SecretMasker(logging.Filter):
    """Filter to mask sensitive data in logs."""
    def filter(self, record):
        if isinstance(record.msg, str):
            # Mask common API key patterns
            record.msg = re.sub(r'(sk-)[a-zA-Z0-9]{32,}', r'\1********', record.msg)
            record.msg = re.sub(r'(key=)[a-zA-Z0-9-_]{20,}', r'\1********', record.msg)
            # Add more patterns as needed
        return True

def setup_logger(name: str):
    """Setup a rich-based logger with masking."""
    logging.basicConfig(
        level="INFO",
        format="%(message)s",
        datefmt="[%X]",
        handlers=[RichHandler(rich_tracebacks=True)]
    )
    logger = logging.getLogger(name)
    logger.addFilter(SecretMasker())
    return logger
