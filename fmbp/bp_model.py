from dataclasses import dataclass

from fmbp.fm import Attribute, Feature


@dataclass(frozen=True, eq=True)
class EventAttribute:
    name: str
    requested: bool = False
    blocked: bool = False
    waited_for: bool = False
    priority: int = 0


@dataclass(frozen=True, eq=True)
class BThreadFeature:
    name: str
    events: tuple[EventAttribute, ...]


def events_from_attributes(attributes: tuple[Attribute, ...]) -> tuple[EventAttribute, ...]:
    events = []
    for attribute in attributes:
        if isinstance(attribute.value, tuple):
            filtered_len = len(list(filter(
                lambda sub_attr: sub_attr.name == "type" and sub_attr.value == "BEvent",
                attribute.value
            )))
            if filtered_len == 0:
                continue
            sub_attribute: Attribute
            requested = False
            blocked = False
            waited_for = False
            priority = 0
            for sub_attribute in attribute.value:
                match sub_attribute:
                    case Attribute(name="requested", value=1.0):
                        requested = True
                    case Attribute(name="blocked", value=1.0):
                        blocked = True
                    case Attribute(name="waited_for", value=1.0):
                        waited_for = True
                    case Attribute(name="priority", value=value):
                        assert isinstance(value, float), value
                        priority = value
            events.append(EventAttribute(attribute.name, requested, blocked, waited_for, priority))

    return tuple(events)


def b_threads_from_features(features: tuple[Feature, ...]) -> dict[str, BThreadFeature]:
    b_threads = {}
    for feature in features:
        # look for b-threads
        for attribute in feature.attributes:
            if attribute.name == "type" and attribute.value == "BThread":
                b_threads[feature.name] = BThreadFeature(feature.name, events_from_attributes(feature.attributes))
                break
    return b_threads
