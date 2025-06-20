from dataclasses import dataclass


ATTRIBUTES_DICT = dict[str, str | dict[str , str | float | bool | list]]
FEATURE_DICT = dict[str, str | list[ATTRIBUTES_DICT]]


@dataclass
class Attribute:
    name: str
    value: str | float | bool | tuple["Attribute", ...]

    @classmethod
    def from_dict(cls, data: ATTRIBUTES_DICT) -> "Attribute":
        value = list(data["value"].values())[0]
        if isinstance(value, list):
            value = tuple(Attribute.from_dict(sub_data) for sub_data in value)
        return cls(
            data["name"],
            value,
        )


@dataclass
class Feature:
    name: str
    attributes: tuple[Attribute, ...]

    @classmethod
    def from_dict(cls, data: FEATURE_DICT) -> "Feature":
        return cls(
            data["name"],
            tuple(Attribute.from_dict(attribute_data) for attribute_data in data["attributes"]),
        )