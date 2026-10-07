"""Time: the earliest and latest start time of a wanted slot."""
from __future__ import annotations

import datetime as dt

from homeassistant.components.time import TimeEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import GpAvailabilityConfigEntry
from .coordinator import GpAvailabilityCoordinator
from .entity import GpAvailabilityWatchEntity

# entity key -> Window field
_FIELDS = {"earliest_time": "earliest", "latest_time": "latest"}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: GpAvailabilityConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    coordinator = entry.runtime_data
    async_add_entities(
        WindowTime(coordinator, wid, key) for wid in coordinator.watches for key in _FIELDS
    )


class WindowTime(GpAvailabilityWatchEntity, TimeEntity):
    """Part of the preferred window, kept in the coordinator's Store."""

    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, coordinator: GpAvailabilityCoordinator, watch_id: str, key: str) -> None:
        super().__init__(coordinator, watch_id, key)
        self._field = _FIELDS[key]

    @property
    def available(self) -> bool:
        return True  # a setting, usable even while checks fail

    @property
    def native_value(self) -> dt.time:
        return getattr(self.coordinator.get_window(self.watch_id), self._field)

    async def async_set_value(self, value: dt.time) -> None:
        await self.coordinator.async_set_window(
            self.watch_id, **{self._field: value.replace(second=0, microsecond=0)}
        )
