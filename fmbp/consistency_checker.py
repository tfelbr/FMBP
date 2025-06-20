from abc import abstractmethod, ABC
from dataclasses import dataclass

from fmbp.bp_model import BThreadFeature, EventAttribute, b_threads_from_features
from fmbp.model_interface import ModelInterface


class FMInconsistencyError(Exception):
    pass


class BThreadInconsistencyError(FMInconsistencyError):
    pass


class EventInconsistencyError(FMInconsistencyError):
    pass


@dataclass(frozen=True)
class FMInconsistencyInfo:
    b_thread_name: str


@dataclass(frozen=True)
class BThreadInconsistencyInfo(FMInconsistencyInfo):
    pass


@dataclass(frozen=True)
class MissingBThread(BThreadInconsistencyInfo):
    pass


@dataclass(frozen=True)
class UnexpectedBThread(BThreadInconsistencyInfo):
    pass


@dataclass(frozen=True)
class EventInconsistencyInfo(FMInconsistencyInfo):
    pass


@dataclass(frozen=True)
class MissingEvent(EventInconsistencyInfo):
    event: EventAttribute


@dataclass(frozen=True)
class IncorrectEvent(EventInconsistencyInfo):
    model_event: EventAttribute
    runtime_event: EventAttribute


@dataclass(frozen=True)
class UnexpectedEvent(EventInconsistencyInfo):
    event: EventAttribute


class ConsistencyChecker(ABC):
    @abstractmethod
    def _get_model_info(self) -> dict[str, BThreadFeature]:
        pass

    def check_runtime_consistency(
            self,
            runtime_b_threads: tuple[BThreadFeature, ...]
    ) -> tuple[EventInconsistencyInfo, ...]:
        model_info = self._get_model_info()
        info: list[EventInconsistencyInfo] = []
        for runtime_b_thread in runtime_b_threads:
            model_b_thread = model_info.get(runtime_b_thread.name)
            if model_b_thread is None:
                raise ValueError(f"B-thread not in model: {runtime_b_thread.name}")
            for model_event in model_b_thread.events:
                found_event = False
                for runtime_event in runtime_b_thread.events:
                    if runtime_event.name == model_event.name:
                        found_event = True
                        if runtime_event != model_event:
                            info.append(IncorrectEvent(model_b_thread.name, model_event, runtime_event))
                if not found_event:
                    info.append(MissingEvent(model_b_thread.name, model_event))
            for runtime_event in runtime_b_thread.events:
                if not list(filter(lambda e: e.name == runtime_event.name, model_b_thread.events)):
                    info.append(UnexpectedEvent(runtime_b_thread.name, runtime_event))
        return tuple(info)

    def check_b_thread_set(
            self,
            b_threads: tuple[str, ...],
    ) -> tuple[BThreadInconsistencyInfo, ...]:
        consistency_info: list[BThreadInconsistencyInfo] = []
        model_info = self._get_model_info()
        unexpected = []
        missing = {k: v for k, v in model_info.items()}
        for b_thread in b_threads:
            if b_thread in model_info:
                missing.pop(b_thread)
            else:
                unexpected.append(b_thread)
        for missing_name in missing:
            consistency_info.append(MissingBThread(missing_name))
        for unexpected_b_thread in unexpected:
            consistency_info.append(UnexpectedBThread(unexpected_b_thread))
        return tuple(consistency_info)


class StaticConsistencyChecker(ConsistencyChecker):
    def __init__(self, model_info: dict[str, BThreadFeature]) -> None:
        self.__model_info = model_info

    def _get_model_info(self) -> dict[str, BThreadFeature]:
        return self.__model_info


class DynamicConsistencyChecker(ConsistencyChecker):
    def __init__(self, uvl_interface: ModelInterface) -> None:
        self.__uvl_interface = uvl_interface

    def _get_model_info(self) -> dict[str, BThreadFeature]:
        return b_threads_from_features(self.__uvl_interface.model_info)
