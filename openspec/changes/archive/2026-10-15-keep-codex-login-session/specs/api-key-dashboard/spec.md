## ADDED Requirements

### Requirement: Installer can keep the Codex login session

`GET /api/key-dashboard/install-script` SHALL accept `keep_login=true`. Such an installer MUST configure the `codex-lb` provider with `requires_openai_auth = true` and `http_headers` sending the exported key as `x-codex-lb-api-key`, MUST carry over only a top-level `cli_auth_credentials_store` value of `file`, `keyring` or `auto` from the previous configuration and otherwise leave it unset, and MUST neither create nor replace `auth.json`, while still downloading the catalog with the exported key and writing configuration and catalog with existing backup and protection. It MUST state that `auth.json` was not changed without printing the key. A first install recorded by a keep-login installer MUST mark `auth.json` as unmanaged so the offline uninstaller neither restores nor deletes it; a later installer that replaces `auth.json` MUST make that run's pre-replacement copy (or its absence) the restore point. Installers exported without the option MUST keep the API-key `auth.json` behavior.

The Install tab SHALL offer a "keep login session" checkbox checked by default. While checked it MUST show a visually highlighted Vietnamese warning that Codex sends its login access token to the codex-lb server on every request, MUST export installers and commands with `keep_login=true`, and MUST require confirming a Vietnamese warning dialog before copying the command or script or downloading the script. Unchecking MUST export the API-key installer without the dialog.

#### Scenario: Keep an existing ChatGPT login

- **GIVEN** a Codex home whose `auth.json` holds a ChatGPT login
- **WHEN** a `keep_login` installer runs successfully
- **THEN** `auth.json` is byte-for-byte unchanged
- **AND** the provider sends the API key in `x-codex-lb-api-key`

#### Scenario: No login yet

- **GIVEN** a Codex home without `auth.json`
- **WHEN** a `keep_login` installer runs
- **THEN** no `auth.json` is created and the user is told to sign in to Codex

#### Scenario: Uninstall keeps the client login

- **GIVEN** a keep-login install after which the user signed in or Codex renewed its login
- **WHEN** the offline uninstaller runs
- **THEN** `auth.json` keeps the current login while configuration and catalog are restored

#### Scenario: Confirm before exporting a keep-login installer

- **WHEN** a user copies the command or script, or downloads the script, with the checkbox checked
- **THEN** a Vietnamese warning dialog appears and the export happens only after confirmation
