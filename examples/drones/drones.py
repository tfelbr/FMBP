import json
import logging
import sys
import time
from multiprocessing import Process, Queue
from pathlib import Path

from bppy import PriorityBasedEventSelectionStrategy

from examples.drones.drone_base import DroneContextSource, patrol, charge, DroneListener, follow
from fmbp.configuration_provider import CachingConfigurationProvider, ContextConfigurationProvider
from fmbp.consistency_checker import DynamicConsistencyChecker
from fmbp.fm_bp import FMBProgram, BPConfigurator
from fmbp.model_interface import UVLLSPInterface
from fmbp.model_watcher import MTimeUpdatingModelWatcher


class DroneProcess(Process):
    def __init__(self, bp: FMBProgram) -> None:
        super().__init__()
        self.__bp = bp

    def run(self):
        self.__bp.run()


if __name__ == "__main__":
    log = logging.getLogger('werkzeug')
    log.setLevel(logging.ERROR)
    logging.basicConfig(level=logging.CRITICAL)

    # The 4 drones are controlled in their own processes.
    # We use Python's multiprocessing to achieve that.
    # All processes get a queue where they put there state in which gets collected here and printed.
    queues: list[Queue] = []
    for i in range(4):
        queue = Queue()
        queues.append(queue)

        # Very similar setup as with the water tank.
        uvl_path = Path(__file__).parent / f"drone_{i}.uvl"
        server_path = Path(json.loads((Path(__file__).parent.parent / "config.json").read_text())["uvls_path"])
        interface = UVLLSPInterface(uvl_path, server_path)
        config_provider = CachingConfigurationProvider(
            ContextConfigurationProvider(
                DroneContextSource(),
                interface,
            ),
        )
        b_program = FMBProgram(
            bthreads=[patrol(interface), follow(interface), charge()],
            event_selection_strategy=PriorityBasedEventSelectionStrategy(),
            listener=BPConfigurator(
                DroneListener(8000 + i, queue),
                config_provider,
                DynamicConsistencyChecker(interface),
                MTimeUpdatingModelWatcher(interface),
            ),
        )
        process = DroneProcess(b_program)
        process.daemon = True
        process.start()

    time.sleep(1)
    print("\nReady", end="\n\n")

    # Printing the drones' states.
    while True:
        for index, queue in enumerate(queues):
            content = queue.get()
            while queue.qsize() > 0:
                content = queue.get()
            print(f"Drone-{index}: {content}{' '*10}")
        print(f'\033[{len(queues)}A', end="\r")
        sys.stdout.flush()

