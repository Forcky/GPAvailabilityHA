"""Select: which days of the week a slot may fall on."""
from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import GpAvailabilityConfigEntry
from .coordinator import GpAvailabilityCoordinator
from .entity import GpAvailabilityWatchEntity
from .slots import DAY_PRESETS


async def async_setup_entry(
    hass: HomeAssistant,
    entry: GpAvailabilityConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    coordinator = entry.runtime_data
    async_add_entities(PreferredDays(coordinator, wid) for wid in coordinator.watches)


class PreferredDays(GpAvailabilityWatchEntity, SelectEntity):
    """Part of the preferred window, kept in the coordinator's Store."""

    _attr_entity_category = EntityCategory.CONFIG
    _attr_options = list(DAY_PRESETS)

    def __init__(self, coordinator: GpAvailabilityCoordinator, watch_id: str) -> None:
        super().__init__(coordinator, watch_id, "preferred_days")

    @property
    def available(self) -> bool:
        return True  # a setting, usable even while checks fail

    @property
    def current_option(self) -> str:
        return self.coordinator.get_window(self.watch_id).days

    async def async_select_option(self, option: str) -> None:
        await self.coordinator.async_set_window(self.watch_id, days=option)
