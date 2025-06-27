import json
import logging
import time
from pathlib import Path

from bppy import *

from fmbp.configuration_provider import ContextConfigurationProvider, CachingConfigurationProvider, \
    LoggingConfigurationProvider
from fmbp.consistency_checker import DynamicConsistencyChecker
from fmbp.context_source import ContextSource
from fmbp.fm import Feature, Attribute
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
        # We give the events an effect
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
    # The custom implementation for the water tank.
    # Returns a dictionary containing context information relevant for this scenario.
    # It returns the same names that can be found in the Env feature of the water tank model.
    def get_data(self) -> dict[str, str | int | float | bool]:
        return {
            "temp": TANK.water_temperature,
            "level": TANK.water_level,
        }

TANK = WaterTank()


# B-thread definition
# We define b-threads the same way it is done in BPpy.
# The only exception is the use of the fm_thread decorator to provide a name for the thread.
# The name should be the same as in the model.
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
    # We deactivate error logging to hide the ugly json decoding errors
    logging.basicConfig(level=logging.CRITICAL)

    # Paths to language server executable and model
    uvl_path = Path(__file__).parent / "water_tank.uvl"
    server_path = Path(json.loads((Path(__file__).parent.parent / "config.json").read_text())["uvls_path"])

    # Model interface instantiation
    interface = UVLLSPInterface(uvl_path, server_path)
    config_provider = LoggingConfigurationProvider( # logs if a configuration has been returned by the level below
        CachingConfigurationProvider(   # caches configurations and only returns new ones
            ContextConfigurationProvider(   # uses a ContextSource to gather context data and feeds them into the interface
                WaterTankContextSource(),
                interface,
            ),
        )
    )

    # We extract the initial context values from the provided model and set them in the runtime
    env_feature: Feature = list(filter(lambda feature: feature.name == "Env", interface.model_info))[0]
    initial_temp: Attribute = \
        list(filter(lambda attribute: attribute.name == "temp", env_feature.attributes))[0]
    initial_level: Attribute = \
        list(filter(lambda attribute: attribute.name == "level", env_feature.attributes))[0]
    TANK.water_temperature = initial_temp.value
    TANK.water_level = initial_level.value

    # Behavioral program initialization
    b_program = FMBProgram(
        bthreads=[add_hot(), add_cold(), remove_water(), finished()],   # we add all b-threads
        event_selection_strategy=PriorityBasedEventSelectionStrategy(), # we use priorities
        listener=BPConfigurator(    # to reconfigure the BP
            WaterTankListener(TANK),
            config_provider,
            DynamicConsistencyChecker(interface),   # checks consistency between model and runtime
            MTimeUpdatingModelWatcher(interface),   # checks the model for updates via modification time changes
        ),
    )
    b_program.run()
