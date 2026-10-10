"""Config Flow: nur ein Klick, es gibt nichts einzustellen."""

from __future__ import annotations

from typing import Any

from homeassistant import config_entries

from .const import DOMAIN


class ESPHomeStudioConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None):
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")
        if user_input is not None:
            return self.async_create_entry(title="ESPHome Studio", data={})
        return self.async_show_form(step_id="user")
