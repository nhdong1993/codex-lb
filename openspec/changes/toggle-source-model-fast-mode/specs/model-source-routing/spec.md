## ADDED Requirements

### Requirement: Source model catalogs advertise declared service tiers

A source model MAY declare `service_tiers`, `additional_speed_tiers` and `default_service_tier` in its `raw_metadata_json`. Its Codex-native catalog entry, served at `/backend-api/codex/models` and the key-dashboard installer catalog `/api/key-dashboard/models`, MUST include the declared values unchanged. Its `/v1/models` entry MUST include them in `metadata`. A source model that declares none of these keys MUST NOT advertise any service tier.

A Responses request routed directly to a source model with `service_tier: "priority"` MUST reach the source with `service_tier: "priority"` on `/v1/responses`, `/backend-api/codex/responses` and their trailing-slash equivalents, unless `prohibitFastMode` is enabled.

#### Scenario: Declared Fast tier reaches every client catalog

- **GIVEN** a source model whose metadata declares a `service_tiers` entry with `id` `priority` and `additional_speed_tiers` `["fast"]`
- **WHEN** a client lists models from `/backend-api/codex/models`, `/api/key-dashboard/models` or `/v1/models`
- **THEN** the model's entry carries the same `service_tiers` and `additional_speed_tiers` values

#### Scenario: Undeclared source model advertises no tier

- **GIVEN** a source model without tier metadata
- **WHEN** a client lists models from `/backend-api/codex/models`
- **THEN** the model's entry has no `service_tiers` or `additional_speed_tiers` value

#### Scenario: Priority tier is forwarded to the source

- **GIVEN** a source model that declares the Fast tier and `prohibitFastMode` is disabled
- **WHEN** a client sends a Responses request for that model with `service_tier: "priority"`
- **THEN** the source receives `service_tier: "priority"`

### Requirement: Dashboard switches Fast mode per model

The source model editor SHALL show a Fast switch on every model row. A model advertises Fast when its metadata has a `service_tiers` object whose `id` is `fast` or `priority`, or an `additional_speed_tiers` string that is `fast` or `priority`, compared case-insensitively. The switch MUST be on for models that advertise Fast and off otherwise. New rows MUST start with it off.

Turning a row's switch on and saving MUST add `{"id": "priority", "name": "Fast", "description": "Priority processing"}` to `service_tiers` and MUST add `fast` to `additional_speed_tiers`. Turning it off MUST remove every entry advertising Fast from both lists, MUST remove a list left empty, and MUST remove `default_service_tier` when its value is `fast` or `priority`. Both changes MUST preserve every other metadata key, every other tier entry and every other row. Saving a row whose switch did not change MUST leave its tier metadata unchanged. Changing only this switch MUST send a models update.

#### Scenario: Turn on Fast for one model

- **WHEN** an operator turns on Fast on the `ch-relay/gpt-6-astra` row and saves
- **THEN** that model's metadata contains the priority `service_tiers` entry and `additional_speed_tiers: ["fast"]` alongside its existing keys
- **AND** the other models' metadata is unchanged

#### Scenario: Turn off Fast keeps other tiers

- **GIVEN** a model whose `service_tiers` lists `priority` and `flex`
- **WHEN** an operator turns off Fast on its row and saves
- **THEN** its `service_tiers` lists only `flex`
- **AND** its `additional_speed_tiers` no longer contains `fast`

#### Scenario: New rows do not advertise Fast

- **WHEN** an operator adds a model row and saves without touching its Fast switch
- **THEN** that model's metadata contains no service tier keys
