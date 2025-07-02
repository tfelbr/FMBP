from abc import ABC, abstractmethod

from fmbp.const import CONTEXT_DATA


class ContextSource(ABC):
    """
    Gathers context information.
    Returns them in standardized format.
    """
    @abstractmethod
    def get_data(self) -> CONTEXT_DATA:
        pass
