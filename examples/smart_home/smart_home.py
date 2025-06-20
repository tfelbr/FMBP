import json
import time
from pathlib import Path

from bppy import *

from fmbp.configuration_provider import ContextConfigurationProvider, LoggingConfigurationProvider, \
    CachingConfigurationProvider
from fmbp.consistency_checker import DynamicConsistencyChecker
from fmbp.context_source import ContextSource
from fmbp.fm_bp import fm_thread, FMBProgram, BPConfigurator, SimpleBProgramRunnerListener
from fmbp.model_interface import UVLLSPInterface
from fmbp.model_watcher import MTimeUpdatingModelWatcher


class SmartHome:
    def __init__(self) -> None:
        self.temp = 20
        self.windows_open = 0


class SmartHomeListener(SimpleBProgramRunnerListener):
    def __init__(self, smart_home: SmartHome) -> None:
        self.__smart_home = smart_home
        self.__idle_printed = false

    def event_selected(self, b_program: BProgram, event: BEvent) -> bool | None:
        if event == BEvent("IDLE"):
            if not self.__idle_printed:
                print("IDLE")
                self.__idle_printed = True
        else:
            self.__idle_printed = False
            match event.name:
                case "HEAT":
                    self.__smart_home.temp += 1
                    print(f"Heated to {self.__smart_home.temp}°C with {event.data['type']}")
                case "COOL":
                    self.__smart_home.temp -= 1
                    print(f"Cooled to {self.__smart_home.temp}°C with {event.data['type']}")
                case "OPEN_WINDOWS":
                    self.__smart_home.windows_open = 1
                    print("Windows Opened")
                case "CLOSE_WINDOWS":
                    self.__smart_home.windows_open = 0
                    print("Windows Closed")
        time.sleep(0.5)


Home = SmartHome()


class SmartHomeContextSource(ContextSource):

    def get_data(self) -> dict[str, str | int | float | bool]:
        return {
            "internal_temp": Home.temp,
            "windows_open": Home.windows_open,
        }


@fm_thread("WindowOpen")
def window_open():
    while True:
        yield sync(request=BEvent("OPEN_WINDOWS"), priority=1)


@fm_thread("WindowClose")
def window_close():
    while True:
        yield sync(request=BEvent("CLOSE_WINDOWS"), priority=1)


@fm_thread("Idle")
def idle():
    while True:
        yield sync(request=BEvent("IDLE"), waitFor=BEvent("CLOSE_WINDOWS"))


@fm_thread("HeatFromAir")
def heat_from_air():
    while True:
        yield sync(request=BEvent("HEAT", {"type": "Outside Air"}), waitFor=BEvent("OPEN_WINDOWS"))


@fm_thread("CoolFromAir")
def cool_from_air():
    while True:
        yield sync(request=BEvent("COOL", {"type": "Outside Air"}), waitFor=BEvent("OPEN_WINDOWS"))


@fm_thread("Heater")
def heater():
    while True:
        yield sync(request=BEvent("HEAT", {"type": "Heater"}), waitFor=BEvent("CLOSE_WINDOWS"))


@fm_thread("AirConditioner")
def air_conditioner():
    while True:
        yield sync(request=BEvent("COOL", {"type": "AirConditioner"}), waitFor=BEvent("CLOSE_WINDOWS"))


@fm_thread("SolarPower")
def solar_power():
    print("Using Solar Power")
    yield sync()


@fm_thread("GridPower")
def grid_power():
    print("Using Grid Power")
    yield sync()


if __name__ == "__main__":
    uvl_path = Path(__file__).parent / "smart_home.uvl"
    server_path = Path(json.loads((Path(__file__).parent.parent / "config.json").read_text())["uvls_path"])
    interface = UVLLSPInterface(uvl_path, server_path)
    config_provider = LoggingConfigurationProvider(
        CachingConfigurationProvider(
            ContextConfigurationProvider(
                SmartHomeContextSource(),
                interface,
            ),
        )
    )
    b_program = FMBProgram(
        bthreads=[
            window_open(),
            window_close(),
            idle(),
            heat_from_air(),
            cool_from_air(),
            heater(),
            air_conditioner(),
            solar_power(),
            grid_power(),
        ],
        event_selection_strategy=PriorityBasedEventSelectionStrategy(),
        listener=BPConfigurator(
            SmartHomeListener(Home),
            config_provider,
            DynamicConsistencyChecker(interface),
            MTimeUpdatingModelWatcher(interface),
        ),
    )
    b_program.run()
