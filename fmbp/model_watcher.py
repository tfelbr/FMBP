import os
from abc import ABC, abstractmethod

from fmbp.model_interface import ModelInterface, FileBasedModelInterface


class ModelWatcher(ABC):
    @abstractmethod
    def check(self) -> None:
        pass


class UpdatingModelWatcher(ModelWatcher, ABC):
    """
    Watches the underlying feature model and notifies the ModelInterface to update itself on changes.
    """
    def __init__(self, model_interface: ModelInterface) -> None:
        self.__interface = model_interface

    @abstractmethod
    def _file_modified(self) -> bool:
        """
        :return: If the watched file has been modified
        """
        pass

    def check(self) -> None:
        if self._file_modified():
            self.__interface.update()


class MTimeUpdatingModelWatcher(UpdatingModelWatcher):
    """
    Uses the modification time stamp of files to check if a feature model has been updated.
    """
    def __init__(self, model_interface: FileBasedModelInterface) -> None:
        super().__init__(model_interface)
        self.__interface = model_interface
        self.__mod_time = os.path.getmtime(self.__interface.model)

    def _file_modified(self) -> bool:
        new_mod_time = os.path.getmtime(self.__interface.model)
        if new_mod_time > self.__mod_time:
            self.__mod_time = new_mod_time
            return True
        return False
