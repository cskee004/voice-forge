"""4-step HA config flow for VoiceForge."""

from __future__ import annotations

import logging

import voluptuous as vol
from homeassistant import config_entries

from .const import (
    CONF_ACTIVE_CHARACTER,
    CONF_API_KEY,
    CONF_ENDPOINT,
    CONF_HOUSEHOLD_MEMBERS,
    CONF_MODEL,
    CONF_PARENT_NOTIFY_ENTITY,
    CONF_SCHOOL_SCHEDULE,
    CONF_WAKE_TIME,
    DEFAULT_API_KEY,
    DEFAULT_ENDPOINT,
    DEFAULT_MODEL,
    DOMAIN,
)
from .llm_client import LLMClient

_LOGGER = logging.getLogger(__name__)

_STEP1_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_ENDPOINT, default=DEFAULT_ENDPOINT): str,
        vol.Required(CONF_MODEL, default=DEFAULT_MODEL): str,
        vol.Optional(CONF_API_KEY, default=DEFAULT_API_KEY): str,
    }
)

_STEP2_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_ACTIVE_CHARACTER, default="aria"): str,
    }
)

_STEP3_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_HOUSEHOLD_MEMBERS, default=""): str,
        vol.Optional(CONF_WAKE_TIME, default="07:00"): str,
        vol.Optional(CONF_SCHOOL_SCHEDULE, default="08:00-15:00"): str,
        vol.Optional(CONF_PARENT_NOTIFY_ENTITY, default=""): str,
    }
)


class VoiceForgeConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    def __init__(self) -> None:
        self._data: dict = {}

    async def async_step_user(self, user_input=None):
        errors = {}
        if user_input is not None:
            try:
                client = LLMClient(
                    endpoint=user_input[CONF_ENDPOINT],
                    model=user_input[CONF_MODEL],
                    api_key=user_input.get(CONF_API_KEY, DEFAULT_API_KEY),
                )
                response = await client.complete([{"role": "user", "content": "Hello"}])
                if not response:
                    raise ConnectionError("Empty response from LLM endpoint")
            except Exception:
                errors["base"] = "cannot_connect"
            else:
                self._data.update(user_input)
                return await self.async_step_character()

        return self.async_show_form(
            step_id="user",
            data_schema=_STEP1_SCHEMA,
            errors=errors,
        )

    async def async_step_character(self, user_input=None):
        if user_input is not None:
            self._data.update(user_input)
            return await self.async_step_home_context()

        return self.async_show_form(
            step_id="character",
            data_schema=_STEP2_SCHEMA,
        )

    async def async_step_home_context(self, user_input=None):
        if user_input is not None:
            self._data.update(user_input)
            return await self.async_step_pipeline()

        return self.async_show_form(
            step_id="home_context",
            data_schema=_STEP3_SCHEMA,
        )

    async def async_step_pipeline(self, user_input=None):
        if user_input is None:
            return self.async_show_form(
                step_id="pipeline",
                data_schema=vol.Schema({}),
            )

        return self.async_create_entry(title="VoiceForge", data=self._data)
