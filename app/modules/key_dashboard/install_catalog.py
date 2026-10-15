"""Standalone catalog setup programs embedded in exported client installers."""

UNIX_CATALOG_SETUP = r"""
import json
import re
import sys
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import HTTPRedirectHandler, Request, build_opener


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def toml_string(value):
    return json.dumps(value, ensure_ascii=False).replace("\x7f", "\\u007f")


codex_dir = Path(sys.argv[1]).resolve()
backup_dir = Path(sys.argv[2])
setup = json.loads((backup_dir / "setup.json").read_text(encoding="utf-8"))
auth = json.loads((backup_dir / "auth.new").read_text(encoding="utf-8"))
request = Request(
    setup["catalog_url"],
    headers={
        "Authorization": "Bearer " + auth["OPENAI_API_KEY"],
        "Accept": "application/json",
        "User-Agent": "codex-lb-installer/1.0",
    },
)
try:
    with build_opener(NoRedirect).open(request, timeout=30) as response:
        catalog = json.load(response)
except HTTPError as exc:
    if exc.code == 403:
        sys.exit("Catalog download forbidden (HTTP 403); check HTTPS and proxy or firewall rules. "
                 "Client files were not replaced.")
    sys.exit("Catalog download failed (HTTP %s); check the key and endpoint." % exc.code)
except (URLError, OSError, ValueError):
    sys.exit("Catalog download failed; check connectivity and the server's JSON catalog.")

if not isinstance(catalog, dict) or not isinstance(catalog.get("models"), list):
    sys.exit("Invalid native model catalog; client files were not replaced.")
models = []
slugs = set()
for entry in catalog["models"]:
    if (not isinstance(entry, dict) or not isinstance(entry.get("slug"), str)
            or not entry["slug"] or entry["slug"] in slugs
            or entry.get("visibility") not in ("list", "hide")
            or not isinstance(entry.get("supported_in_api"), bool)
            or not isinstance(entry.get("prefer_websockets"), bool)):
        sys.exit("Invalid native model entry; client files were not replaced.")
    slugs.add(entry["slug"])
    if entry["visibility"] == "list" and entry["supported_in_api"]:
        models.append(entry)
if not models:
    sys.exit("No usable Codex models for this key; ask the administrator to enable a streaming Responses model.")
listed = {entry["slug"] for entry in models}
model = models[0]["slug"]
skipped = []
for name in setup["preferred_models"]:
    if name in listed:
        model = name
        break
    skipped.append(name)
if skipped:
    print("Skipped models not in this key's catalog: " + ", ".join(json.dumps(name) for name in skipped)
          + "; using " + json.dumps(model) + ".", file=sys.stderr)

catalog_path = codex_dir / "codex-lb-models.json"
(backup_dir / "catalog.new").write_text(
    json.dumps({"models": models}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
)
config_path = backup_dir / "config.new"
config = (
    "model = " + toml_string(model) + "\n"
    + "model_catalog_json = " + toml_string(str(catalog_path)) + "\n"
    + config_path.read_text(encoding="utf-8")
)
if setup["keep_login"]:
    # Keep the client's credential store so its existing login stays visible to Codex.
    previous = backup_dir / "config.toml"
    for line in previous.read_text(encoding="utf-8", errors="replace").splitlines() if previous.is_file() else ():
        if line.lstrip().startswith("["):
            break
        store = re.fullmatch(r'\s*cli_auth_credentials_store\s*=\s*"(file|keyring|auto)"\s*(?:#.*)?', line)
        if store:
            config = 'cli_auth_credentials_store = "' + store.group(1) + '"\n' + config
            break
config_path.write_text(config, encoding="utf-8")
(backup_dir / "setup.json").unlink()
"""

WINDOWS_CATALOG_SETUP = r"""
$setup = $setupJson | ConvertFrom-Json
$credential = ($auth | ConvertFrom-Json).OPENAI_API_KEY
try {
    $catalogResponse = Invoke-WebRequest -UseBasicParsing -Uri $setup.catalog_url `
        -Headers @{ Authorization = ('Bearer ' + $credential); Accept = 'application/json' } `
        -UserAgent 'codex-lb-installer/1.0' `
        -MaximumRedirection 0 -TimeoutSec 30
    if ([int]$catalogResponse.StatusCode -ne 200) { throw 'Unexpected catalog status' }
    $catalog = $catalogResponse.Content | ConvertFrom-Json
} catch {
    if ($_.Exception.Response -and [int]$_.Exception.Response.StatusCode -eq 403) {
        throw ('Catalog download forbidden (HTTP 403); check HTTPS and proxy or firewall rules. ' +
            'Client files were not replaced.')
    }
    throw 'Catalog download failed; check the key, endpoint, and server JSON catalog. Client files were not replaced.'
}
if ($null -eq $catalog -or $catalog.models -isnot [Array]) {
    throw 'Invalid native model catalog; client files were not replaced.'
}
$models = @()
$slugs = [Collections.Generic.HashSet[string]]::new([StringComparer]::Ordinal)
foreach ($entry in $catalog.models) {
    if ($entry.slug -isnot [string] -or [string]::IsNullOrEmpty($entry.slug) -or -not $slugs.Add($entry.slug) `
        -or $entry.visibility -cnotin @('list', 'hide') -or $entry.supported_in_api -isnot [bool] `
        -or $entry.prefer_websockets -isnot [bool]) {
        throw 'Invalid native model entry; client files were not replaced.'
    }
    if ($entry.visibility -ceq 'list' -and $entry.supported_in_api) { $models += $entry }
}
if ($models.Count -eq 0) {
    throw 'No usable Codex models for this key; ask the administrator to enable a streaming Responses model.'
}
$listed = @($models | ForEach-Object { $_.slug })
$model = $models[0].slug
$skipped = @()
foreach ($name in @($setup.preferred_models | Where-Object { $_ -is [string] })) {
    if ($name -cin $listed) { $model = $name; break }
    $skipped += $name
}
if ($skipped.Count -gt 0) {
    $skippedJson = @($skipped | ForEach-Object { ConvertTo-Json -InputObject $_ -Compress }) -join ', '
    [Console]::Error.WriteLine("Skipped models not in this key's catalog: $skippedJson; using " +
        (ConvertTo-Json -InputObject $model -Compress) + '.')
}
$catalogPath = Join-Path $codexDir 'codex-lb-models.json'
$catalogJson = ConvertTo-Json -InputObject @{ models = @($models) } -Depth 100
# ConvertTo-Json safely quotes TOML basic strings, including Windows path separators.
$modelJson = ConvertTo-Json -InputObject $model -Compress
$pathJson = ConvertTo-Json -InputObject $catalogPath -Compress
$config = "model = $modelJson`nmodel_catalog_json = $pathJson`n" + $config
if ($setup.keep_login) {
    # Keep the client's credential store so its existing login stays visible to Codex.
    $previousConfig = Join-Path $backupDir 'config.toml'
    $previousLines = @()
    if (Test-Path -LiteralPath $previousConfig) { $previousLines = [IO.File]::ReadAllLines($previousConfig) }
    foreach ($line in $previousLines) {
        if ($line.TrimStart().StartsWith('[')) { break }
        if ($line -cmatch '\A\s*cli_auth_credentials_store\s*=\s*"(file|keyring|auto)"\s*(#.*)?\z') {
            $config = 'cli_auth_credentials_store = "' + $Matches[1] + '"' + "`n" + $config
            break
        }
    }
}
"""
