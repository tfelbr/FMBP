import json
import logging
from pathlib import Path

from bppy import PriorityBasedEventSelectionStrategy

from fmbp.configuration_provider import LoggingConfigurationProvider, \
    CachingConfigurationProvider, ContextConfigurationProvider
from fmbp.consistency_checker import DynamicConsistencyChecker
from fmbp.fm_bp import FMBProgram, BPConfigurator
from fmbp.model_interface import UVLLSPInterface
from fmbp.model_watcher import MTimeUpdatingModelWatcher
from examples.drones.drone_base import DroneContextSource, patrol, charge, DroneListener, follow

if __name__ == "__main__":
    log = logging.getLogger('werkzeug')
    log.setLevel(logging.ERROR)
    uvl_path = Path(__file__).parent / "drone_1.uvl"
    server_path = Path(json.loads((Path(__file__).parent.parent / "config.json").read_text())["uvls_path"])
    interface = UVLLSPInterface(uvl_path, server_path)
    config_provider = LoggingConfigurationProvider(
        CachingConfigurationProvider(
            ContextConfigurationProvider(
                DroneContextSource(),
                interface,
            ),
        )
    )
    b_program = FMBProgram(
        bthreads=[patrol(interface), follow(interface), charge()],
        event_selection_strategy=PriorityBasedEventSelectionStrategy(),
        listener=BPConfigurator(
            DroneListener(8001),
            config_provider,
            DynamicConsistencyChecker(interface),
            MTimeUpdatingModelWatcher(interface),
        ),
    )
    b_program.run()