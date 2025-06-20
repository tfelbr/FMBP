from abc import abstractmethod, ABC

from fmbp.const import RUNTIME_CONFIG
from fmbp.context_source import ContextSource
from fmbp.model_interface import ModelInterface


class ConfigurationProvider(ABC):
    @abstractmethod
    def get_configuration(self) -> RUNTIME_CONFIG | None:
        pass


class StaticConfigurationProvider(ConfigurationProvider):
    def __init__(self, config: RUNTIME_CONFIG) -> None:
        self.__config = config

    def get_configuration(self) -> RUNTIME_CONFIG | None:
        return self.__config


class ContextConfigurationProvider(ConfigurationProvider):
    def __init__(
            self,
            context_source: ContextSource,
            model_interface: ModelInterface,
    ) -> None:
        self.__context_source = context_source
        self.__model_interface = model_interface

    def get_configuration(self) -> RUNTIME_CONFIG | None:
        return self.__model_interface.acquire_configuration(self.__context_source.get_data())


class CachingConfigurationProvider(ConfigurationProvider):
    def __init__(self, configuration_provider: ConfigurationProvider) -> None:
        self.__configuration_provider = configuration_provider
        self.__current_config: RUNTIME_CONFIG | None = None

    def get_configuration(self) -> RUNTIME_CONFIG | None:
        new_config = self.__configuration_provider.get_configuration()
        if new_config != self.__current_config:
            self.__current_config = new_config
            return new_config
        return None


class LoggingConfigurationProvider(ConfigurationProvider):
    def __init__(self, configuration_provider: ConfigurationProvider) -> None:
        self.__configuration_provider = configuration_provider

    def get_configuration(self) -> RUNTIME_CONFIG | None:
        new_config = self.__configuration_provider.get_configuration()
        if new_config is not None:
            print("### Reconfiguring ###")
        return new_config
