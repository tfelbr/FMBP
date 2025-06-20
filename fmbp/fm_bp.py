import logging
from json import JSONDecodeError
from typing import Callable, Optional, Any

from bppy import thread, BProgram, BProgramRunnerListener, BEvent

from fmbp.bp_model import BThreadFeature, EventAttribute
from fmbp.configuration_provider import ConfigurationProvider, StaticConfigurationProvider
from fmbp.consistency_checker import ConsistencyChecker, MissingEvent, IncorrectEvent, UnexpectedEvent, \
    MissingBThread, UnexpectedBThread, EventInconsistencyError, BThreadInconsistencyError
from fmbp.const import RUNTIME_CONFIG
from fmbp.model_watcher import UpdatingModelWatcher


class FMThread:
    def __init__(self, name: str, bp_wrapper: Any, *args: Any) -> None:
        self.name = name
        self.__bp_wrapper = bp_wrapper
        self.__args = args

    def get_generator(self) -> Any:
        return self.__bp_wrapper(*self.__args)


def fm_thread(name: str) -> Callable[[Callable, str], Callable[..., FMThread]]:
    def fm_thread0(func: Callable, mode: str = 'execution') -> Callable:
        def get_thread(*args) -> FMThread:
            wrapper = thread(func, mode)
            return FMThread(name, wrapper, *args)
        return get_thread
    return fm_thread0


class FMBProgram(BProgram):
    def __init__(
            self,
            bthreads: list[FMThread] | None = None,
            source_name=None,
            event_selection_strategy=None,
            listener: Optional["BPConfigurator"] = None,
    ) -> None:
        self.__listener = listener
        self.__name_to_thread = {}
        self.__thread_to_name = {}
        for b_thread in bthreads:
            name = b_thread.name
            gen = b_thread.get_generator()
            self.__name_to_thread[name] = gen
            self.__thread_to_name[gen] = name
        super().__init__(
            [],
            source_name,
            event_selection_strategy,
            listener
        )

    def enable_b_thread(self, name: str) -> bool:
        maybe_thread_function = self.__name_to_thread.get(name)
        if maybe_thread_function is None:
            return False
        ticket: dict[str, Any]
        for ticket in self.tickets:
            if ticket["bt"] is maybe_thread_function:
                return False
        self.add_bthread(maybe_thread_function)
        self.load_new_bthreads()
        return True

    def disable_b_thread(self, name: str) -> bool:
        maybe_thread_function = self.__name_to_thread.get(name)
        if maybe_thread_function is None:
            return False
        ticket_to_delete = None
        ticket: dict[str, Any]
        for ticket in self.tickets:
            if ticket["bt"] is maybe_thread_function:
                ticket_to_delete = ticket
                break
        if ticket_to_delete is not None:
            self.tickets.remove(ticket_to_delete)
            return True
        return False

    def get_generator(self, name: str) -> Any | None:
        return self.__name_to_thread.get(name)

    def get_name(self, gen: Any) -> str | None:
        return self.__thread_to_name.get(gen)

    def get_all_b_thread_names(self) -> tuple[str, ...]:
        return tuple(self.__name_to_thread.keys())


class SimpleBProgramRunnerListener(BProgramRunnerListener):

    def starting(self, b_program):
        pass

    def started(self, b_program):
        pass

    def super_step_done(self, b_program):
        pass

    def ended(self, b_program):
        pass

    def assertion_failed(self, b_program):
        pass

    def b_thread_added(self, b_program):
        pass

    def b_thread_removed(self, b_program):
        pass

    def b_thread_done(self, b_program):
        pass

    def event_selected(self, b_program, event):
        pass

    def halted(self, b_program):
        pass


class BPConfigurator(SimpleBProgramRunnerListener):
    def __init__(
            self,
            listener: BProgramRunnerListener | None = None,
            configuration_provider: ConfigurationProvider | None = None,
            fm_consistency_checker: ConsistencyChecker | None = None,
            uvl_file_watcher: UpdatingModelWatcher | None = None,
    ) -> None:
        self.__listener = listener or SimpleBProgramRunnerListener()
        self.__configuration_provider = configuration_provider
        self.__consistency_checker = fm_consistency_checker
        self.__watcher = uvl_file_watcher

    def __maybe_get_new_config(self) -> dict[str, bool] | None:
        assert self.__configuration_provider is not None
        while True:
            try:
                new_config = self.__configuration_provider.get_configuration()
            except JSONDecodeError as e:
                logging.error("Cannot decode json configuration: " + str(e))
            else:
                return new_config

    def __assert_event_consistency(self, b_program: FMBProgram) -> None:
        if self.__consistency_checker is not None:
            runtime_b_threads = []
            ticket: dict[str, Any]
            for ticket in b_program.tickets:
                events = []
                request: BEvent | None = ticket.get("request")
                block: BEvent | None = ticket.get("block")
                wait_for: BEvent | None = ticket.get("waitFor")
                priority: int | None = ticket.get("priority")
                if request:
                    events.append(EventAttribute(request.name, requested=True, priority=priority or 0))
                if block:
                    events.append(EventAttribute(block.name, blocked=True, priority=priority or 0))
                if wait_for:
                    events.append(EventAttribute(wait_for.name, waited_for=True, priority=priority or 0))
                name = b_program.get_name(ticket["bt"])
                runtime_b_threads.append(BThreadFeature(name, tuple(events)))
            final_errors = []
            for result in self.__consistency_checker.check_runtime_consistency(tuple(runtime_b_threads)):
                match result:
                    case MissingEvent(b_thread_name, event):
                        final_errors.append(
                            f"Event detected in model of b-thread '{b_thread_name}' but missing in runtime\n"
                            f"{event}"
                        )
                    case IncorrectEvent(b_thread_name, model_event, runtime_event):
                        final_errors.append(
                            f"Runtime event of b-thread '{b_thread_name}' does not match model\n"
                            f"Runtime:  {runtime_event}\n"
                            f"Model:    {model_event}"
                        )
                    case UnexpectedEvent(b_thread_name, event):
                        final_errors.append(
                            f"Runtime event of b-thread '{b_thread_name}' not found in model\n"
                            f"{event}"
                        )
            if final_errors:
                raise EventInconsistencyError(
                    "Runtime and model have diverged:\n\n" + "\n\n".join(final_errors)
                )

    def __assert_b_thread_consistency(self, b_program: FMBProgram) -> None:
        if self.__consistency_checker is not None:
            final_errors = []
            for result in self.__consistency_checker.check_b_thread_set(b_program.get_all_b_thread_names())  :
                match result:
                    case MissingBThread(name):
                        final_errors.append(f"Missing b-thread: '{name}' found in model but not in runtime")
                    case UnexpectedBThread(name):
                        final_errors.append(f"Unexpected b-thread: '{name}' found in runtime but not in model")
            if final_errors:
                if final_errors:
                    raise BThreadInconsistencyError(
                        "Runtime and model have diverged:\n\n" + "\n".join(final_errors)
                    )


    def starting(self, b_program: BProgram):
        assert isinstance(b_program, FMBProgram)
        self.__assert_b_thread_consistency(b_program)
        self.__listener.starting(b_program)
        if self.__configuration_provider is None:
            self.__configuration_provider = StaticConfigurationProvider(
                {name: True for name in b_program.get_all_b_thread_names()}
            )
        maybe_new_config = self.__configuration_provider.get_configuration()
        if maybe_new_config is not None:
            self.__reconfigure_program(b_program, maybe_new_config)

    @staticmethod
    def __reconfigure_program(b_program: FMBProgram, config: RUNTIME_CONFIG) -> None:
        for b_thread, to_activate in config.items():
            if to_activate:
                b_program.enable_b_thread(b_thread)
            else:
                b_program.disable_b_thread(b_thread)

    def event_selected(self, b_program: BProgram, event: BEvent) -> bool | None:
        assert isinstance(b_program, FMBProgram)
        if self.__watcher:
            self.__watcher.check()
        self.__assert_b_thread_consistency(b_program)
        self.__assert_event_consistency(b_program)
        to_return = self.__listener.event_selected(b_program, event)
        if to_return:
            return to_return
        maybe_new_config = self.__maybe_get_new_config()
        if maybe_new_config is not None:
            self.__reconfigure_program(b_program, maybe_new_config)
        return None
