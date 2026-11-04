"""The directory ZIP: layout and the plugin-directory submission limits.

Limits are the OpenAI plugin-directory final-submission limits (the stricter
value where package validation and final submission differ) and the Claude
directory README rule. Every check reads the BUILT ZIP, so a manifest that
breaks a limit fails here even if the repository copy looks fine; the negative
tests rebuild the ZIP with one broken value and show each check can fail.
"""

from __future__ import annotations

import json
import re
import struct
import sys
import unicodedata
import zipfile
from pathlib import Path
from urllib.parse import urlparse

import pytest

from scripts import common, package

#: The plugin root, and only it, at the ZIP root.
EXPECTED_TOP_LEVEL = {
    "LICENSE",
    "LICENSE-CC-BY-4.0",
    "NOTICE",
    "README.md",
    "assets",
    "mcp.json",
    "plugin.json",
    "skills",
}

DESCRIPTION_MAX = 1024
DISPLAY_NAME_MAX = 30
SHORT_DESCRIPTION_MAX = 30
LONG_DESCRIPTION_MAX = 4000
DEVELOPER_NAME_MAX = 80
CAPABILITIES_MAX = 20
CAPABILITY_MAX = 120
URL_MAX = 1024
PROMPTS_MAX = 3
PROMPT_MAX = 128
ZIP_MAX_BYTES = 100 * 1000 * 1000
EXTRACTED_MAX_BYTES = 512 * 1024 * 1024
ENTRIES_MAX = 5000
IMAGE_MAX_BYTES = 5 * 1024 * 1024
IMAGE_MIN_PX, IMAGE_MAX_PX = 48, 4096
#: Listing links a remote-MCP submission requires, by their documented keys.
REQUIRED_URL_FIELDS = (
    "websiteURL",
    "supportURL",
    "privacyPolicyURL",
    "termsOfServiceURL",
)
CATEGORIES = frozenset(
    {
        "Productivity",
        "Creativity",
        "Developer Tools",
        "Business & Operations",
        "Data & Analytics",
        "Communication",
        "Education & Research",
        "Security",
        "Finance",
        "Healthcare",
        "Travel",
        "Entertainment",
        "Other",
    }
)
_PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
_S_IFMT, _S_IFLNK = 0o170000, 0o120000


def _single_line(value: object) -> bool:
    return isinstance(value, str) and value.strip() != "" and "\n" not in value


def _png_size(data: bytes) -> tuple[int, int] | None:
    if not data.startswith(_PNG_SIGNATURE) or data[12:16] != b"IHDR":
        return None
    return struct.unpack(">II", data[16:24])


def _urls(manifest: dict, interface: dict) -> dict[str, object]:
    found: dict[str, object] = {
        f"interface.{key}": value
        for key, value in interface.items()
        if key.endswith("URL")
    }
    for key in ("homepage", "repository"):
        if key in manifest:
            found[key] = manifest[key]
    if "url" in manifest.get("author", {}):
        found["author.url"] = manifest["author"]["url"]
    return found


def directory_violations(zip_path: Path) -> list[str]:
    """Every directory-limit violation in a built directory ZIP."""
    problems: list[str] = []
    if zip_path.stat().st_size > ZIP_MAX_BYTES:
        problems.append("zip exceeds 100 MB")
    with zipfile.ZipFile(zip_path) as archive:
        infos = archive.infolist()
        names = [info.filename for info in infos]
        if len(infos) > ENTRIES_MAX:
            problems.append("too many zip entries")
        if sum(info.file_size for info in infos) > EXTRACTED_MAX_BYTES:
            problems.append("extracted size exceeds 512 MiB")
        for info in infos:
            if (info.external_attr >> 16) & _S_IFMT == _S_IFLNK:
                problems.append(f"symlink entry: {info.filename}")
        top = {name.split("/", 1)[0] for name in names}
        if top != EXPECTED_TOP_LEVEL:
            problems.append(f"top-level entries {sorted(top)}")
        for name in names:
            parts = name.split("/")
            if parts[0] == "hooks" or parts[-1] in {"hooks.json", ".app.json"}:
                problems.append(f"hook or app file: {name}")
            if parts[0] == "apps":
                problems.append(f"app file: {name}")
        if "plugin.json" not in names:
            return [*problems, "no plugin.json at the zip root"]
        manifest = json.loads(archive.read("plugin.json"))
        files = {name: archive.read(name) for name in names}

    for key in ("hooks", "apps"):
        if key in manifest:
            problems.append(f"manifest declares {key}")
    description = manifest.get("description", "")
    if not 1 <= len(description) <= DESCRIPTION_MAX:
        problems.append("description length")

    interface = manifest.get("extensions", {}).get("com.openai", {}).get(
        "interface", {}
    )
    for key, limit in (
        ("displayName", DISPLAY_NAME_MAX),
        ("shortDescription", SHORT_DESCRIPTION_MAX),
        ("developerName", DEVELOPER_NAME_MAX),
    ):
        value = interface.get(key)
        if not _single_line(value) or len(str(value)) > limit:
            problems.append(f"interface.{key} must be one line of <= {limit}")
    long_description = interface.get("longDescription", "")
    if not isinstance(long_description, str) or len(long_description) > LONG_DESCRIPTION_MAX:
        problems.append("interface.longDescription length")
    if interface.get("category") not in CATEGORIES:
        problems.append(f"unsupported category {interface.get('category')!r}")
    capabilities = interface.get("capabilities", [])
    if len(capabilities) > CAPABILITIES_MAX or not all(
        _single_line(c) and len(c) <= CAPABILITY_MAX for c in capabilities
    ):
        problems.append("interface.capabilities")

    prompts = interface.get("defaultPrompt", [])
    normalized = {
        " ".join(unicodedata.normalize("NFKC", p).casefold().split())
        for p in prompts
        if isinstance(p, str)
    }
    if len(prompts) > PROMPTS_MAX or len(normalized) != len(prompts):
        problems.append("at most 3 unique starter prompts")
    for prompt in prompts:
        if not _single_line(prompt) or len(prompt) > PROMPT_MAX or "@" in prompt:
            problems.append(f"starter prompt: {prompt!r}")

    for field in REQUIRED_URL_FIELDS:
        if field not in interface:
            problems.append(f"missing interface.{field}")
    for key, url in _urls(manifest, interface).items():
        if not isinstance(url, str):
            problems.append(f"{key} must be a string")
            continue
        parsed = urlparse(url)
        if (
            parsed.scheme != "https"
            or not parsed.hostname
            or parsed.username
            or parsed.password
            or len(url) > URL_MAX
        ):
            problems.append(f"{key} must be an HTTPS URL of <= {URL_MAX}")

    for key in ("logo", "composerIcon"):
        path = interface.get(key)
        if not isinstance(path, str) or not path.startswith("./"):
            problems.append(f"interface.{key} must be a ./ path")
            continue
        data = files.get(path[2:])
        if data is None:
            problems.append(f"interface.{key} is not in the zip")
            continue
        size = _png_size(data) if path.endswith(".png") else None
        if len(data) > IMAGE_MAX_BYTES:
            problems.append(f"interface.{key} exceeds 5 MiB")
        if size is None:
            problems.append(f"interface.{key} is not a readable PNG")
        elif size[0] != size[1] or not IMAGE_MIN_PX <= size[0] <= IMAGE_MAX_PX:
            problems.append(f"interface.{key} must be square, 48-4096 px: {size}")
    return problems


@pytest.fixture(scope="module")
def directory_zip(tmp_path_factory) -> Path:
    archive, _ = package.build_release(
        common.REPO_ROOT, tmp_path_factory.mktemp("dist"), directory=True
    )
    return archive


def test_directory_zip_is_named_for_the_version(directory_zip):
    version = common.load_json(common.REPO_ROOT / common.PLUGIN_MANIFEST_REL)[
        "version"
    ]
    assert directory_zip.name == f"tara-{version}-directory.zip"


def test_directory_zip_has_the_plugin_root_at_its_root(directory_zip):
    with zipfile.ZipFile(directory_zip) as archive:
        names = archive.namelist()
    assert sorted(names) == sorted(
        rel[len(common.DIRECTORY_PREFIX) :] for rel in common.DIRECTORY_ALLOWLIST
    )
    assert not any(name.startswith("plugins/") for name in names)
    assert not any(name.startswith(".") for name in names)


def test_directory_zip_carries_the_repository_bytes(directory_zip):
    with zipfile.ZipFile(directory_zip) as archive:
        for rel in common.DIRECTORY_ALLOWLIST:
            name = rel[len(common.DIRECTORY_PREFIX) :]
            assert archive.read(name) == (common.REPO_ROOT / rel).read_bytes(), rel
        assert archive.read("LICENSE") == (common.REPO_ROOT / "LICENSE").read_bytes()


def test_directory_zip_meets_every_directory_limit(directory_zip):
    assert directory_violations(directory_zip) == []


def test_directory_zip_has_no_residue_and_a_matching_checksum(tmp_path):
    archive, checksum = package.build_release(
        common.REPO_ROOT, tmp_path, directory=True
    )
    assert common.scan_archive(archive, common.DIRECTORY_PREFIX) == []
    assert checksum.read_text().split() == [common.sha256_file(archive), archive.name]


def test_directory_zip_is_deterministic(tmp_path):
    first, _ = package.build_release(common.REPO_ROOT, tmp_path / "a", directory=True)
    second, _ = package.build_release(common.REPO_ROOT, tmp_path / "b", directory=True)
    assert first.read_bytes() == second.read_bytes()


def test_directory_build_leaves_the_marketplace_archive_layout_alone(tmp_path):
    archive, _ = package.build_release(common.REPO_ROOT, tmp_path)
    with zipfile.ZipFile(archive) as members:
        names = members.namelist()
    assert archive.name.endswith(".zip") and "directory" not in archive.name
    assert sorted(names) == sorted(common.ARCHIVE_ALLOWLIST)
    assert {name.split("/", 1)[0] for name in names} == {
        *common.LICENSE_PATHS,
        "plugins",
    }


# --- Each limit can fail: rebuild the ZIP with one broken value. -----------


def _rebuild(
    source: Path,
    target: Path,
    *,
    manifest_edit=None,
    extra: dict[str, bytes] | None = None,
    symlink: str | None = None,
    replace: dict[str, bytes] | None = None,
) -> Path:
    with zipfile.ZipFile(source) as archive:
        members = {name: archive.read(name) for name in archive.namelist()}
    if manifest_edit is not None:
        manifest = json.loads(members["plugin.json"])
        manifest_edit(manifest)
        members["plugin.json"] = json.dumps(manifest).encode()
    members.update(replace or {})
    members.update(extra or {})
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, data in members.items():
            archive.writestr(name, data)
        if symlink is not None:
            info = zipfile.ZipInfo(symlink)
            info.external_attr = (_S_IFLNK | 0o777) << 16
            archive.writestr(info, "plugin.json")
    return target


def _interface(manifest: dict) -> dict:
    return manifest["extensions"]["com.openai"]["interface"]


def _set(key: str, value):
    def edit(manifest: dict) -> None:
        _interface(manifest)[key] = value

    return edit


def _png(width: int, height: int) -> bytes:
    return _PNG_SIGNATURE + struct.pack(">I", 13) + b"IHDR" + struct.pack(
        ">II", width, height
    ) + b"\x08\x06\x00\x00\x00"


MANIFEST_BREAKS = {
    "description": lambda m: m.__setitem__("description", "x" * 1025),
    "displayName": _set("displayName", "x" * 31),
    "shortDescription": _set("shortDescription", "x" * 31),
    "shortDescription-multiline": _set("shortDescription", "Tahoe\ndata"),
    "longDescription": _set("longDescription", "x" * 4001),
    "developerName": _set("developerName", "x" * 81),
    "category": _set("category", "Research"),
    "capability": _set("capabilities", ["x" * 121]),
    "four-prompts": _set("defaultPrompt", ["a", "b", "c", "d"]),
    "duplicate-prompts": _set("defaultPrompt", ["Same prompt", "same  PROMPT"]),
    "long-prompt": _set("defaultPrompt", ["x" * 129]),
    "mention-prompt": _set("defaultPrompt", ["Ask @tahoe-public about MEK"]),
    "http-url": _set("websiteURL", "http://tara.tahoebio.io/"),
    "long-url": _set("supportURL", "https://tara.tahoebio.io/" + "x" * 1000),
    "credential-url": _set("privacyPolicyURL", "https://user:pw@tara.tahoebio.io/"),
    "missing-terms": lambda m: _interface(m).pop("termsOfServiceURL"),
    "http-homepage": lambda m: m.__setitem__("homepage", "http://tahoebio.ai"),
    "logo-path": _set("logo", "assets/tahoe-logo.png"),
    "logo-missing": _set("logo", "./assets/missing.png"),
    "hooks": lambda m: m.__setitem__("hooks", "./hooks/hooks.json"),
    "apps": lambda m: m.__setitem__("apps", "./.app.json"),
}


@pytest.mark.parametrize("case", sorted(MANIFEST_BREAKS))
def test_a_broken_manifest_limit_is_reported(case, directory_zip, tmp_path):
    broken = _rebuild(
        directory_zip, tmp_path / "broken.zip", manifest_edit=MANIFEST_BREAKS[case]
    )
    assert directory_violations(broken) != []


@pytest.mark.parametrize(
    "extra",
    [
        {"hooks/hooks.json": b"{}"},
        {".app.json": b"{}"},
        {"apps/app.json": b"{}"},
        {"stray.txt": b"x"},
        {"plugins/tara/plugin.json": b"{}"},
    ],
    ids=["hooks-dir", "app-json", "apps-dir", "sibling-file", "nested-root"],
)
def test_an_extra_entry_is_reported(extra, directory_zip, tmp_path):
    broken = _rebuild(directory_zip, tmp_path / "broken.zip", extra=extra)
    assert directory_violations(broken) != []


def test_a_symlink_entry_is_reported(directory_zip, tmp_path):
    broken = _rebuild(directory_zip, tmp_path / "broken.zip", symlink="skills/link")
    assert "symlink entry: skills/link" in directory_violations(broken)


@pytest.mark.parametrize(
    ("data", "fragment"),
    [
        (_png(1000, 900), "square"),
        (_png(32, 32), "square"),
        (_png(5000, 5000), "square"),
        (b"not a png", "readable PNG"),
        (_png(1000, 1000) + b"\x00" * (5 * 1024 * 1024), "5 MiB"),
    ],
    ids=["not-square", "too-small", "too-large", "not-png", "over-5-mib"],
)
def test_a_broken_logo_is_reported(data, fragment, directory_zip, tmp_path):
    broken = _rebuild(
        directory_zip,
        tmp_path / "broken.zip",
        replace={"assets/tahoe-logo.png": data},
    )
    assert any(fragment in problem for problem in directory_violations(broken))


def test_an_oversized_zip_is_reported(directory_zip, monkeypatch):
    # Lower the ceiling below the real archive rather than writing 100 MB.
    monkeypatch.setattr(
        sys.modules[__name__], "ZIP_MAX_BYTES", directory_zip.stat().st_size - 1
    )
    assert "zip exceeds 100 MB" in directory_violations(directory_zip)


def test_the_marketplace_adapter_declares_no_hooks_and_is_within_limits():
    # The Claude adapter is not in the directory ZIP, but the Claude directory
    # reads it from the repository; hold it to the same description limit.
    adapter = common.load_json(common.REPO_ROOT / common.CLAUDE_ADAPTER_REL)
    assert "hooks" not in adapter
    assert 1 <= len(adapter["description"]) <= DESCRIPTION_MAX
    assert adapter["author"]["name"] == "Tahoe Bio"


def test_no_plugin_file_is_a_symlink():
    for rel in common.DIRECTORY_ALLOWLIST + common.ARCHIVE_ALLOWLIST:
        assert not (common.REPO_ROOT / rel).is_symlink(), rel


# --- The plugin README: what both directories show as the listing. ---------


def _readme() -> str:
    return (common.REPO_ROOT / common.PLUGIN_README_REL).read_text(encoding="utf-8")


def test_readme_is_150_to_400_words_of_prose():
    prose = re.sub(r"```.*?```", "", _readme(), flags=re.DOTALL)
    words = len(re.findall(r"[A-Za-z0-9][\w'.@/:-]*", prose))
    assert 150 <= words <= 400, words


@pytest.mark.parametrize(
    "required",
    [
        "https://tara.tahoebio.io/install.md",
        "https://tara.tahoebio.io/mcp",
        "https://tara.tahoebio.io/privacy",
        "https://github.com/tahoebio/tahoe-public-plugins/issues",
        "tara@tahoebio.ai",
        "Tahoe account",
        "research use only",
        "read-only",
        "Apache-2.0",
        "CC BY 4.0",
        "CC0",
    ],
)
def test_readme_covers_each_listing_requirement(required):
    assert required in " ".join(_readme().split())


def test_readme_lists_the_manifest_starter_prompts():
    readme = " ".join(_readme().split())
    manifest = common.load_json(common.REPO_ROOT / common.PLUGIN_MANIFEST_REL)
    for prompt in _interface(manifest)["defaultPrompt"]:
        assert prompt in readme, prompt


def test_readme_does_not_promise_the_signatures_panel():
    assert "signature" not in _readme().lower()


def test_readme_names_the_launch_datasets():
    readme = _readme()
    assert "Tahoe-100M" in readme and "Emerald Bay" in readme
