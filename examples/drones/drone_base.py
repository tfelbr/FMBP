import json
from dataclasses import dataclass
from multiprocessing import Queue
from threading import Thread, Lock

from bppy import sync, BEvent, BProgram
from flask import Flask

from fmbp.const import CONTEXT_DATA
from fmbp.context_source import ContextSource
from fmbp.fm import Feature, Attribute
from fmbp.fm_bp import fm_thread, SimpleBProgramRunnerListener
from fmbp.model_interface import ModelInterface


@dataclass
class Target:
    id: str
    distance: float
    direction: tuple[float, float]
    position: tuple[float, float]
    visited: bool


TARGETS: dict[str, Target] = {}


def update_targets(distances: dict[str, float], directions: dict[str, list[float]]) -> None:
    for key in distances:
        if key in TARGETS:
            TARGETS[key].distance = distances[key]
            TARGETS[key].direction = (directions[key][0], directions[key][1])
            TARGETS[key].position = (directions[key][0] + DroneEnv.POSITION[0], directions[key][1] + DroneEnv.POSITION[1])
        else:
            TARGETS[key] = Target(
                    id=key,
                    distance=distances[key],
                    direction=(directions[key][0], directions[key][1]),
                    position=(directions[key][0] + DroneEnv.POSITION[0], directions[key][1] + DroneEnv.POSITION[1]),
                    visited=False,
            )


class DroneEnv:
    CURRENT_TARGET: Target | None = None
    POSITION = (0.0, 0.0)
    CHARGE = 100


class DroneListener(SimpleBProgramRunnerListener):
    def __init__(self, port: int, queue: Queue) -> None:
        self.__queue = queue
        self.__flask_app = Flask(f"drone-{port}")
        self.__flask_task = Thread(target=self.__flask_app.run, kwargs={"port": port, "threaded": True})

        self.__flask_app.route("/get")(self.__get)
        self.__flask_app.route("/update/<distances>/<directions>/<own_position>/<charge_value>")(self.__update)

        self.__next_target = (0.0, 0.0)

        self.__initial_lock = Lock()
        self.__initial_lock.acquire()
        self.__initialized = False

    def __get(self) -> str:
        return json.dumps({"target": self.__next_target})

    def __update(self, distances: str, directions: str, own_position: str, charge_value: str) -> str:
        distances = json.loads(distances)
        directions = json.loads(directions)
        own_position_split = own_position.split(",")
        own_position = (float(own_position_split[0]), float(own_position_split[1]))
        DroneEnv.CHARGE = float(charge_value)
        DroneEnv.POSITION = own_position
        if not self.__initialized:
            update_targets(distances, directions)
            if TARGETS:
                self.__initialized = True
                self.__initial_lock.release()
        else:
            update_targets(distances, directions)
        return ""

    def starting(self, b_program):
        self.__flask_task.start()
        self.__initial_lock.acquire()
        self.__initial_lock.release()

    def event_selected(self, b_program: BProgram, event: BEvent):
        self.__queue.put(f"Charge: {round(DroneEnv.CHARGE, 4):.2f} --- Event: {event.name}")
        if event.name in ["PATROL", "CHARGE", "FOLLOW"]:
            target: tuple[float, float] = event.data["target"]
            self.__next_target = target


class DroneContextSource(ContextSource):
    def __init__(self) -> None:
        self.__drone_last_charge = DroneEnv.CHARGE

    def get_data(self) -> CONTEXT_DATA:
        is_charging = 0
        if DroneEnv.POSITION == (0.0, 0.0):
            is_charging = 1
        self.__drone_last_charge = DroneEnv.CHARGE
        return {
            "charge": DroneEnv.CHARGE,
            "is_charging": is_charging,
        }


def reset_targets(targets: tuple[str, ...]) -> None:
    for target in targets:
        if target in TARGETS:
            TARGETS[target].visited = False


def target_visited(target_id: str) -> None:
    if target_id in TARGETS:
        TARGETS[target_id].visited = True


def find_min_distance(targets: tuple[str, ...]) -> Target | None:
    for target in targets:
        if target not in TARGETS:
           return None
    if DroneEnv.CURRENT_TARGET is not None and DroneEnv.CURRENT_TARGET.position == DroneEnv.POSITION:
        target_visited(DroneEnv.CURRENT_TARGET.id)
        DroneEnv.CURRENT_TARGET = None
    elif DroneEnv.CURRENT_TARGET is not None:
        return DroneEnv.CURRENT_TARGET
    nearest = None
    for _, target in TARGETS.items():
        if target.id in targets and not target.visited:
            if nearest is None:
                nearest = target
            elif nearest.distance > target.distance:
                nearest = target
    if nearest is None:
        reset_targets(targets)
        return find_min_distance(targets)
    DroneEnv.CURRENT_TARGET = nearest
    return DroneEnv.CURRENT_TARGET


def follow_at_distance(target_id: str, distance: float) -> tuple[float, float] | None:
    target = TARGETS.get(target_id)
    if target is None:
        return None
    return target.direction[0] + DroneEnv.POSITION[0] - distance, target.direction[1] + DroneEnv.POSITION[1] - distance


@fm_thread("Patrol")
def patrol(interface: ModelInterface):
    while True:
        config_feature: Feature = list(filter(lambda feature: feature.name == "Config", interface.model_info))[0]
        patrol_targets: Attribute = \
            list(filter(lambda attribute: attribute.name == "patrol_targets", config_feature.attributes))[0]
        parsed_patrol_targets: tuple[str, ...] = tuple(patrol_targets.value.split(","))
        maybe_nearest = find_min_distance(parsed_patrol_targets)
        if maybe_nearest is not None:
            yield sync(request=BEvent("PATROL", {"target": maybe_nearest.position}))


@fm_thread("Follow")
def follow(interface: ModelInterface):
    while True:
        config_feature: Feature = list(filter(lambda feature: feature.name == "Config", interface.model_info))[0]
        follow_target: Attribute = \
            list(filter(lambda attribute: attribute.name == "leader_to_follow", config_feature.attributes))[0]
        follow_distance: Attribute = \
            list(filter(lambda attribute: attribute.name == "follow_distance", config_feature.attributes))[0]
        maybe_target = follow_at_distance(follow_target.value, follow_distance.value)
        if maybe_target is not None:
            yield sync(request=BEvent("FOLLOW", {"target": maybe_target}))


@fm_thread("Charge")
def charge():
    while True:
        yield sync(request=BEvent("CHARGE", {"target": (0.0, 0.0)}), priority=1)