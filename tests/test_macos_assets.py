"""Cross-platform checks for the native app's checked-in release assets."""

import json
from pathlib import Path
import plistlib
import re
import struct
import subprocess
import tomllib

import pytest

from extract_chat import __version__


ROOT = Path(__file__).resolve().parents[1]
CATALOG = ROOT / "macos/ExtractChatApp/Assets.xcassets/AppIcon.appiconset"
SLOTS = [(size, scale) for size in (16, 32, 128, 256, 512) for scale in (1, 2)]


def test_lgpt_is_owned_without_taking_json_or_zip_defaults() -> None:
    info = plistlib.loads((ROOT / "macos/ExtractChatApp/Info.plist").read_bytes())
    declaration, = info["UTExportedTypeDeclarations"]
    identifier = "ai.unixwzrd.loggpt.archive"
    assert declaration["UTTypeIdentifier"] == identifier
    assert declaration["UTTypeDescription"] == "LogGPT Plus file for Extract Chat"
    assert declaration["UTTypeTagSpecification"] == {"public.filename-extension": ["lgpt"], "public.mime-type": "application/vnd.loggpt.archive"}
    assert "public.zip-archive" in declaration["UTTypeConformsTo"]
    custom = next(item for item in info["CFBundleDocumentTypes"] if identifier in item["LSItemContentTypes"])
    assert custom["LSHandlerRank"] == "Owner"
    assert custom["CFBundleTypeName"] == declaration["UTTypeDescription"]
    assert custom["CFBundleTypeRole"] == "Viewer" and not custom["LSTypeIsPackage"]
    for legacy in ("public.json", "public.zip-archive"):
        handler = next(item for item in info["CFBundleDocumentTypes"] if legacy in item["LSItemContentTypes"])
        assert handler["LSHandlerRank"] == "Alternate"
    acceptance = plistlib.loads((ROOT / "macos/Tests/GUIAcceptance-Info.plist").read_bytes())
    assert acceptance["UTImportedTypeDeclarations"][0]["UTTypeIdentifier"] == identifier
    assert all(item["LSHandlerRank"] == "Alternate" for item in acceptance["CFBundleDocumentTypes"])


def test_css_viewer_uses_a_build_generated_engine_stylesheet() -> None:
    builder = (ROOT / "scripts/build_macos_helper.sh").read_text(encoding="utf-8")
    spec = (ROOT / "macos/engine.spec.in").read_text(encoding="utf-8")
    checker = (ROOT / "scripts/check_xcode_engine.sh").read_text(encoding="utf-8")
    assert "get_default_css_content" in builder and '"$work_dir/default.css"' in builder
    assert 'Path(SPECPATH) / "default.css"' in spec
    assert 'Contents/Resources/default.css' in checker


def test_package_and_app_versions_agree() -> None:
    metadata = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    project = (ROOT / "macos/ExtractChatApp/ExtractChatApp.xcodeproj/project.pbxproj").read_text(encoding="utf-8")
    versions = re.findall(r"MARKETING_VERSION = ([^;]+);", project)
    assert metadata["project"]["version"] == __version__
    assert versions == [__version__, __version__], "Debug/Release must use the engine's version"


def test_app_signing_defaults_select_a_development_team() -> None:
    project = (ROOT / "macos/ExtractChatApp/ExtractChatApp.xcodeproj/project.pbxproj").read_text(encoding="utf-8")
    configurations = [block for block in re.findall(r"buildSettings\s*=\s*\{(.*?)\};", project, re.DOTALL) if "PRODUCT_BUNDLE_IDENTIFIER = ai.unixwzrd.ExtractChat;" in block]
    assert len(configurations) == 2
    for configuration in configurations:
        assert 'CODE_SIGN_IDENTITY = "Apple Development";' in configuration
        assert "CODE_SIGN_STYLE = Automatic;" in configuration
        assert re.search(r"DEVELOPMENT_TEAM = [A-Z0-9]+;", configuration)


def test_entitlements_navigator_reference_matches_the_signing_input() -> None:
    app = ROOT / "macos/ExtractChatApp"
    project = (app / "ExtractChatApp.xcodeproj/project.pbxproj").read_text(encoding="utf-8")
    reference = re.search(r"/\* ExtractChatApp\.entitlements \*/\s*=\s*\{([^}]+)\}", project)
    assert reference is not None
    assert "sourceTree = SOURCE_ROOT;" in reference.group(1), "The entitlements file is at the project root, not under Sources/ExtractChatApp"
    assert "path = ExtractChatApp.entitlements;" in reference.group(1)
    assert project.count("CODE_SIGN_ENTITLEMENTS = ExtractChatApp.entitlements;") == 2
    permissions = plistlib.loads((app / "ExtractChatApp.entitlements").read_bytes())
    assert permissions["com.apple.security.app-sandbox"] is True
    assert permissions["com.apple.security.files.downloads.read-write"] is True


def test_app_deployment_minimum_and_reviewed_build_settings() -> None:
    app = ROOT / "macos/ExtractChatApp"
    project = (app / "ExtractChatApp.xcodeproj/project.pbxproj").read_text(encoding="utf-8")
    assert re.findall(r"MACOSX_DEPLOYMENT_TARGET = ([^;]+);", project) == ["14.0"] * 4
    info = plistlib.loads((app / "Info.plist").read_bytes())
    assert info["LSMinimumSystemVersion"] == "$(MACOSX_DEPLOYMENT_TARGET)"
    assert "platforms: [.macOS(.v14)]" in (app / "Package.swift").read_text(encoding="utf-8")
    for setting in ["DEAD_CODE_STRIPPING", "ENABLE_USER_SCRIPT_SANDBOXING", "CLANG_ENABLE_OBJC_WEAK", "CLANG_WARN_INFINITE_RECURSION", "LOCALIZATION_PREFERS_STRING_CATALOGS", "STRING_CATALOG_GENERATE_SYMBOLS"]:
        assert project.count(f"{setting} = YES;") == 2, f"Enable {setting} for Debug and Release"
    acceptance = plistlib.loads((ROOT / "macos/Tests/GUIAcceptance-Info.plist").read_bytes())
    assert acceptance["LSMinimumSystemVersion"] == "14.0"
    assert "arm64-apple-macos14.0" in (ROOT / "scripts/build_macos_gui_acceptance.sh").read_text(encoding="utf-8")


def test_initial_native_release_explicitly_targets_apple_silicon() -> None:
    project = (ROOT / "macos/ExtractChatApp/ExtractChatApp.xcodeproj/project.pbxproj").read_text(encoding="utf-8")
    configurations = [block for block in re.findall(r"buildSettings\s*=\s*\{(.*?)\};", project, re.DOTALL) if "PRODUCT_BUNDLE_IDENTIFIER = ai.unixwzrd.ExtractChat;" in block]
    assert len(configurations) == 2
    for configuration in configurations:
        assert 'ARCHS = "$(ARCHS_STANDARD)";' in configuration
        assert '"EXCLUDED_ARCHS[sdk=macosx*]" = x86_64;' in configuration, "Debug and Release must exclude Intel to match the initial arm64-only engine, even if ARCHS is reset to Standard"
    checker = (ROOT / "scripts/check_xcode_engine.sh").read_text(encoding="utf-8")
    assert 'for architecture in ${ARCHS:?' in checker
    assert '-verify_arch "$architecture"' in checker, "Retain native engine architecture checks for future universal builds"


def test_mac_icon_catalog_has_every_standard_and_retina_slot() -> None:
    catalog = json.loads((CATALOG / "Contents.json").read_text(encoding="utf-8"))
    images = catalog["images"]
    assert len(images) == 10
    assert {(entry["size"], entry["scale"], entry["idiom"]) for entry in images} == {
        (f"{size}x{size}", f"{scale}x", "mac") for size, scale in SLOTS
    }
    assert len({entry["filename"] for entry in images}) == 10


@pytest.mark.parametrize(("size", "scale"), SLOTS)
def test_mac_icon_png_dimensions(size: int, scale: int) -> None:
    suffix = "@2x" if scale == 2 else ""
    filename = CATALOG / f"icon_{size}x{size}{suffix}.png"
    with filename.open("rb") as source:
        header = source.read(24)
    assert header[:8] == b"\x89PNG\r\n\x1a\n"
    assert header[12:16] == b"IHDR"
    assert struct.unpack(">II", header[16:24]) == (size * scale, size * scale)


def test_native_dialogs_and_acceptance_host_use_the_product_icon() -> None:
    sources = ROOT / "macos/ExtractChatApp/Sources/ExtractChatApp"
    assert "explanation.icon = NSApp.applicationIconImage" in (sources / "ConversionPermissions.swift").read_text(encoding="utf-8")
    assert "alert.icon = NSApp.applicationIconImage" in (sources / "ExtractChatApp.swift").read_text(encoding="utf-8")
    assert "Image(nsImage: NSApp.applicationIconImage)" in (sources / "ExportView.swift").read_text(encoding="utf-8")
    acceptance = plistlib.loads((ROOT / "macos/Tests/GUIAcceptance-Info.plist").read_bytes())
    assert acceptance["CFBundleIconFile"] == "AppIcon"
    builder = (ROOT / "scripts/build_macos_gui_acceptance.sh").read_text(encoding="utf-8")
    assert "xcrun actool" in builder and 'test -f "$app/Contents/Resources/AppIcon.icns"' in builder
    assert 'app="$staging_dir/Extract Chat GUI Acceptance.app"' in builder
    assert builder.index('codesign --verify --deep --strict "$app"') < builder.index('mv "$app" "$destination_app"'), "Verify a fresh bundle before publishing it at the stable path"


def test_gitignore_excludes_generated_state_but_keeps_release_sources(tmp_path: Path) -> None:
    (tmp_path / ".gitignore").write_text((ROOT / ".gitignore").read_text(encoding="utf-8"), encoding="utf-8")
    subprocess.run(["git", "init", "--quiet", str(tmp_path)], check=True)
    ignored = [".project-planning", ".ruff_cache/entry", ".pytest_cache/entry", "build/runtime", "macos/ExtractChatApp/.build/product", "macos/ExtractChatApp/.swiftpm/xcode/package.xcworkspace/contents.xcworkspacedata", "macos/ExtractChatApp/DerivedData/product", "macos/ExtractChatApp/ExtractChatApp.xcodeproj/project.xcworkspace/xcuserdata/test.xcuserdatad/UserInterfaceState.xcuserstate", "result.xcresult/Info.plist", "archive.xcarchive/Info.plist"]
    ignored += ["private-fixtures/conversation.json", "local-artifacts/image.png", "backup/old.py", "validation/results.json", "build.xcactivitylog", "session.trace/data"]
    sources = ["macos/ExtractChatApp/Assets.xcassets/AppIcon.appiconset/icon_16x16.png", "macos/ExtractChatApp/Sources/ExtractChatApp/ExportView.swift", "macos/ExtractChatApp/ExtractChatApp.xcodeproj/xcshareddata/xcschemes/ExtractChatApp.xcscheme", "macos/ExtractChatApp/ExtractChatApp.xcodeproj/project.pbxproj", "macos/ExtractChatApp/Package.resolved", "macos/engine.spec.in", "tests/fixtures/packaging-smoke.json"]
    result = subprocess.run(["git", "-C", str(tmp_path), "check-ignore", "--stdin"], input="\n".join(ignored + sources) + "\n", capture_output=True, text=True, check=True)
    assert set(result.stdout.splitlines()) == set(ignored)


def test_package_discovery_excludes_deprecated_local_utilities() -> None:
    config = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    discovery = config["tool"]["setuptools"]["packages"]["find"]
    assert discovery["include"] == ["extract_chat*"]
    assert {"extract_chat.utils", "extract_chat.utils.*"} <= set(discovery["exclude"])
    manifest = (ROOT / "MANIFEST.in").read_text(encoding="utf-8").splitlines()
    assert {"graft macos", "graft tests", "prune src/extract_chat/utils", "prune macos/ExtractChatApp/.build"} <= set(manifest)
