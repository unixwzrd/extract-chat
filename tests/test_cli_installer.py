"""The installed app owns CLI dispatch and explicit folder authorization."""

from pathlib import Path
import plistlib
import subprocess


ROOT = Path(__file__).resolve().parents[1]


def test_app_and_inherited_engine_keep_their_sandbox_entitlements() -> None:
    def read(name: str) -> dict:
        return plistlib.loads((ROOT / "macos" / name).read_bytes())
    assert read("Helper.entitlements") == {"com.apple.security.app-sandbox": True, "com.apple.security.inherit": True}
    app = read("ExtractChatApp/ExtractChatApp.entitlements")
    assert app["com.apple.security.app-sandbox"] is True
    assert app["com.apple.security.files.user-selected.read-write"] is True
    assert app["com.apple.security.files.user-selected.executable"] is True
    assert app["com.apple.security.files.downloads.read-write"] is True
    assert app["com.apple.security.temporary-exception.files.home-relative-path.read-write"] == ["/Documents/"]
    assert "com.apple.security.temporary-exception.files.absolute-path.read-write" not in app
    assert "com.apple.security.inherit" not in app


def test_only_the_existing_engine_is_built_and_embedded() -> None:
    project = (ROOT / "macos/ExtractChatApp/ExtractChatApp.xcodeproj/project.pbxproj").read_text(encoding="utf-8")
    assert "ExtractChatEngine.app in Embed" in project  # Xcode may normalize the phase's display name.
    assert "ExtractChatCLI.app" not in project
    assert "CLIInstaller.swift in Sources" in project
    assert "CLIRunner.swift in Sources" in project
    spec = (ROOT / "macos/engine.spec.in").read_text(encoding="utf-8")
    assert 'entitlements_file=str(root / "macos/Helper.entitlements")' in spec
    assert 'name="ExtractChatEngine.app"' in spec
    assert "ExtractChatCLI.app" not in spec
    builder = (ROOT / "scripts/build_macos_helper.sh").read_text(encoding="utf-8")
    assert "EXTRACT_CHAT_RUNTIME_KIND" not in builder
    assert "ExtractChatCLI.app" not in builder


def test_cli_installer_is_in_the_command_group_without_requiring_input_files() -> None:
    view = (ROOT / "macos/ExtractChatApp/Sources/ExtractChatApp/ExportView.swift").read_text(encoding="utf-8")
    group = view.split('Text("Equivalent command(s)")', 1)[1].split("Text(model.commands)", 1)[0]
    assert 'Button("Install CLI…", action: model.installCLI).disabled(model.isRunning)' in group
    assert 'Button("Copy", action: model.copyCommands)' in group


def test_runtime_builder_rejects_removed_companion_mode() -> None:
    builder = ROOT / "scripts/build_macos_helper.sh"
    for arguments in [["--unknown"], ["--terminal"], ["--terminal", "--unexpected"]]:
        result = subprocess.run(["bash", str(builder), *arguments], capture_output=True, text=True)
        assert result.returncode == 2 and "Usage:" in result.stderr


def test_app_routes_cli_before_creating_the_gui_and_installer_saves_own_launcher() -> None:
    sources = ROOT / "macos/ExtractChatApp/Sources/ExtractChatApp"
    entry = (sources / "ExtractChatApp.swift").read_text(encoding="utf-8")
    assert entry.index("CLIRunner.run") < entry.index("NSApplication.shared")
    installer = (sources / "CLIInstaller.swift").read_text(encoding="utf-8")
    assert 'exec "$tool" --cli "$@"' in installer
    model = (sources / "ExportModel.swift").read_text(encoding="utf-8")
    install = model.split("func installCLI()", 1)[1].split("var validation:", 1)[0]
    assert "Bundle.main.executableURL" in install and "NSSavePanel()" in install
    assert "companion" not in install and '"extract-chat"' in install


def test_permission_setup_is_explicit_and_independent_of_output_preferences() -> None:
    sources = ROOT / "macos/ExtractChatApp/Sources/ExtractChatApp"
    runner = (sources / "CLIRunner.swift").read_text(encoding="utf-8")
    assert 'arguments.first == "--grant-access"' in runner
    assert 'arguments.first == "--list-access"' in runner
    assert 'arguments.first == "--forget-access"' in runner
    assert "restoreRememberedAccess()" in runner
    assert "ExportSettings" not in runner and "ExportModel" not in runner
    permissions = (sources / "ConversionPermissions.swift").read_text(encoding="utf-8")
    authorize = permissions.split("func authorizeFolders", 1)[1].split("private func contains", 1)[0]
    assert "NSOpenPanel()" in authorize and "try remember(folder)" in authorize
    assert "withoutUI" in permissions and "bookmarkDataIsStale" in permissions


def test_native_locations_do_not_force_a_custom_startup_or_install_picker() -> None:
    sources = ROOT / "macos/ExtractChatApp/Sources/ExtractChatApp"
    entry = (sources / "ExtractChatApp.swift").read_text(encoding="utf-8")
    assert "offerWorkingFolderSetup" not in entry
    assert 'withTitle: "Authorize Working Folders…"' in entry
    model = (sources / "ExportModel.swift").read_text(encoding="utf-8")
    assert "offerWorkingFolderSetup" not in model
    assert "try permissions.authorizeFolders()" in model
    assert "Open System Settings" in (sources / "ExportView.swift").read_text(encoding="utf-8")
    runner = (sources / "CLIRunner.swift").read_text(encoding="utf-8")
    assert "isReadableFile(atPath: directory.path)" not in runner
    assert 'environment["EXTRACT_CHAT_CALLER_DIRECTORY"] = callerDirectory.path' in runner


def test_product_and_acceptance_describe_system_folder_usage() -> None:
    for name in ("ExtractChatApp/Info.plist", "Tests/GUIAcceptance-Info.plist"):
        info = plistlib.loads((ROOT / "macos" / name).read_bytes())
        assert info["NSDocumentsFolderUsageDescription"]
        assert info["NSDownloadsFolderUsageDescription"]
