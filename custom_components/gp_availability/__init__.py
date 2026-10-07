"""GP availability for Home Assistant.

Watches a practice's online booking page (HotDoc, EasyVisit) for open
appointments with chosen doctors and notifies when one opens up before a
cutoff date.
"""
from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryError
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import CONF_PROVIDER, DOMAIN
from .coordinator import GpAvailabilityCoordinator
from .entity import practice_device
from .providers import PROVIDERS

PLATFORMS = [
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.DATE,
    Platform.NUMBER,
    Platform.SELECT,
    Platform.SENSOR,
    Platform.SWITCH,
    Platform.TIME,
]

type GpAvailabilityConfigEntry = ConfigEntry[GpAvailabilityCoordinator]


async def async_setup_entry(hass: HomeAssistant, entry: GpAvailabilityConfigEntry) -> bool:
    """Set up a practice from a config entry."""
    provider_cls = PROVIDERS.get(entry.data.get(CONF_PROVIDER))
    if provider_cls is None:
        raise ConfigEntryError(f"Unknown booking provider {entry.data.get(CONF_PROVIDER)!r}")
    provider = provider_cls(async_get_clientsession(hass))
    coordinator = GpAvailabilityCoordinator(hass, entry, provider)
    await coordinator.async_load()
    # Paused (the Checking switch is off): no request at all until it is turned on.
    if coordinator.polling:
        await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator

    # Doctor devices hang off the practice device, so it must exist first.
    registry = dr.async_get(hass)
    coordinator.practice_device_id = registry.async_get_or_create(
        config_entry_id=entry.entry_id, **practice_device(coordinator)
    ).id

    # Drop devices for doctors no longer watched (removed in the options flow).
    wanted = {(DOMAIN, entry.entry_id)} | {
        (DOMAIN, f"{entry.entry_id}_{wid}") for wid in coordinator.watches
    }
    for device in dr.async_entries_for_config_entry(registry, entry.entry_id):
        if not device.identifiers & wanted:
            registry.async_update_device(device.id, remove_config_entry_id=entry.entry_id)

    entry.async_on_unload(entry.add_update_listener(_async_reload))
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def _async_reload(hass: HomeAssistant, entry: GpAvailabilityConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: GpAvailabilityConfigEntry) -> bool:
    """Unload a config entry."""
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        await entry.runtime_data.async_save_now()
    return unloaded
