"""Switches: notifications per watch; Checking (pause everything) per practice."""
from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import GpAvailabilityConfigEntry
from .coordinator import GpAvailabilityCoordinator
from .entity import GpAvailabilityWatchEntity, practice_device


async def async_setup_entry(
    hass: HomeAssistant,
    entry: GpAvailabilityConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    coordinator = entry.runtime_data
    async_add_entities(
        [CheckingSwitch(coordinator), *(NotifySwitch(coordinator, wid) for wid in coordinator.watches)]
    )


class NotifySwitch(GpAvailabilityWatchEntity, SwitchEntity):
    """State lives in the coordinator's Store, so it survives restarts."""

    def __init__(self, coordinator: GpAvailabilityCoordinator, watch_id: str) -> None:
        super().__init__(coordinator, watch_id, "notifications")

    @property
    def available(self) -> bool:
        return True  # a setting, usable even while the API is down

    @property
    def is_on(self) -> bool:
        return self.coordinator.get_notify(self.watch_id)

    async def async_turn_on(self, **kwargs: Any) -> None:
        self.coordinator.set_notify(self.watch_id, True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        self.coordinator.set_notify(self.watch_id, False)


class CheckingSwitch(CoordinatorEntity[GpAvailabilityCoordinator], SwitchEntity):
    """Off stops all checks (no requests at all) until it is turned on again."""

    _attr_has_entity_name = True
    _attr_translation_key = "checking"
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, coordinator: GpAvailabilityCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_checking"
        self._attr_device_info = practice_device(coordinator)

    @property
    def available(self) -> bool:
        return True  # a setting, usable even while checks fail

    @property
    def is_on(self) -> bool:
        return self.coordinator.polling

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self.coordinator.async_set_polling(True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self.coordinator.async_set_polling(False)
