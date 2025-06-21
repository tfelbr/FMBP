import json
import time
from pathlib import Path

from bppy import *

from fmbp.configuration_provider import ContextConfigurationProvider, CachingConfigurationProvider, \
    LoggingConfigurationProvider
from fmbp.consistency_checker import DynamicConsistencyChecker
from fmbp.context_source import ContextSource
from fmbp.fm_bp import fm_thread, FMBProgram, BPConfigurator, SimpleBProgramRunnerListener
from fmbp.model_interface import UVLLSPInterface
from fmbp.model_watcher import MTimeUpdatingModelWatcher


class WaterTank:
    def __init__(self) -> None:
        self.water_level = 0
        self.water_temperature = 0

    def add_water(self, amount: int, temperature: int) -> None:
        if amount == 0:
            return
        new_temperature = (self.water_level * self.water_temperature + amount * temperature) / \
                          (self.water_level + amount)
        self.water_level += amount
        self.water_temperature = int(new_temperature)

    def remove_water(self, amount: int) -> None:
        if self.water_level >= amount:
            self.water_level -= amount


class WaterTankListener(SimpleBProgramRunnerListener):
    def __init__(self, water_tank: WaterTank) -> None:
        self.__water_tank = water_tank
        self.__has_finished = False

    def event_selected(self, b_program: BProgram, event: BEvent):
        if event == BEvent("FINISHED"):
            if not self.__has_finished:
                print("Finished")
                self.__has_finished = True
            time.sleep(1)
        else:
            self.__has_finished = False
            if event == BEvent("HOT"):
                self.__water_tank.add_water(1, 80)
            elif event == BEvent("COLD"):
                self.__water_tank.add_water(1, 0)
            elif event == BEvent("DRAIN"):
                self.__water_tank.remove_water(1)
            print(f"{event} {self.__water_tank.water_level} L, {self.__water_tank.water_temperature} °C", {event.name})


class WaterTankContextSource(ContextSource):

    def get_data(self) -> dict[str, str | int | float | bool]:
        return {
            "temp": TANK.water_temperature,
            "level": TANK.water_level,
        }

TANK = WaterTank()


@fm_thread("AddHot")
def add_hot():
    while True:
        yield sync(request=BEvent("HOT"), priority=1)


@fm_thread("AddCold")
def add_cold():
    while True:
        yield sync(request=BEvent("COLD"), priority=1)


@fm_thread("RemoveWater")
def remove_water():
    while True:
        yield sync(request=BEvent("DRAIN"), priority=2)


@fm_thread("Finished")
def finished():
    while True:
        yield sync(request=BEvent("FINISHED"), priority=1)


if __name__ == "__main__":
    uvl_path = Path(__file__).parent / "water_tank.uvl"
    server_path = Path(json.loads((Path(__file__).parent.parent / "config.json").read_text())["uvls_path"])
    interface = UVLLSPInterface(uvl_path, server_path)
    config_provider = LoggingConfigurationProvider(
        CachingConfigurationProvider(
            ContextConfigurationProvider(
                WaterTankContextSource(),
                interface,
            ),
        )
    )
    b_program = FMBProgram(
        bthreads=[add_hot(), add_cold(), remove_water(), finished()],
        event_selection_strategy=PriorityBasedEventSelectionStrategy(),
        listener=BPConfigurator(
            WaterTankListener(TANK),
            config_provider,
            DynamicConsistencyChecker(interface),
            MTimeUpdatingModelWatcher(interface),
        ),
    )
    b_program.run()
