"""
Base class for code analyzers.
"""

from abc import ABC, abstractmethod
from typing import List, Dict

class BaseAnalyzer(ABC):
    @abstractmethod
    def analyze(self, file_path: str) -> List[Dict]:
        pass

    @abstractmethod
    def get_supported_extensions(self) -> List[str]:
        pass
