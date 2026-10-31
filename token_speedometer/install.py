"""User-level, manifest-scoped installation. Never alters an inference engine."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from .config import OWNER, data_dir

NAME = "Etincelles Token Meter"
EXE = "EtincellesTokenMeter.exe"

def installed_root():
    if os.name == "nt":
        return Path.home() / ".etincelles-token-meter"
    return Path.home() / ".local/share/etincelles-token-meter"

def shortcut_paths():
    if os.name == "nt":
        from .windows_paths import known_folder
        desktop = known_folder("desktop")
        menu = known_folder("roaming") / "Microsoft/Windows/Start Menu/Programs"
        return [desktop / (NAME + ".lnk"), menu / (NAME + ".lnk"),
                menu / ("Uninstall " + NAME + ".lnk"), menu / "Startup" / (NAME + ".lnk")]
    apps = Path.home() / ".local/share/applications"
    paths = [apps / "etincelles-token-meter.desktop", apps / "uninstall-etincelles-token-meter.desktop"]
    desktop = Path.home() / "Desktop"
    if desktop.is_dir():
        paths += [desktop / (NAME + ".desktop"), desktop / ("Uninstall " + NAME + ".desktop")]
    return paths + [Path.home() / ".config/autostart/etincelles-token-meter.desktop"]

def command(root=None):
    root = root or installed_root()
    if (root / EXE).exists():
        return str(root / EXE), ""
    return sys.executable, '"' + str(root / "launcher.py") + '"'

def ps_quote(value):
    return "'" + str(value).replace("'", "''") + "'"

def shortcut_owned(path, root=None):
    if not path.exists():
        return False
    target, arguments = command(root)
    if os.name == "nt":
        code = "$s=(New-Object -ComObject WScript.Shell).CreateShortcut(" + ps_quote(path) + ");"
        code += "if($s.TargetPath -eq " + ps_quote(target) + " -and $s.Arguments.StartsWith(" + ps_quote(arguments) + ")){exit 0}else{exit 1}"
        return subprocess.run(["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", code],
                              creationflags=subprocess.CREATE_NO_WINDOW).returncode == 0
    return ("X-Etincelles-Owner=" + OWNER) in path.read_text(encoding="utf-8")

def write_shortcut(path, uninstall=False):
    root = installed_root()
    if path.exists() and not shortcut_owned(path, root):
        raise RuntimeError("A shortcut with this name already exists and belongs to another application.")
    path.parent.mkdir(parents=True, exist_ok=True)
    target, arguments = command(root)
    if uninstall:
        arguments += " --uninstall"
    if os.name == "nt":
        code = "$s=(New-Object -ComObject WScript.Shell).CreateShortcut(" + ps_quote(path) + ");"
        code += "$s.TargetPath=" + ps_quote(target) + ";$s.Arguments=" + ps_quote(arguments) + ";"
        code += "$s.WorkingDirectory=" + ps_quote(root) + ";$s.Description=" + ps_quote(NAME) + ";$s.Save()"
        subprocess.run(["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", code],
                       check=True, creationflags=subprocess.CREATE_NO_WINDOW)
    else:
        path.write_text("[Desktop Entry]\nType=Application\nName=" + ("Uninstall " if uninstall else "") + NAME
                        + "\nExec=\"" + target + "\" " + arguments + "\nIcon=" + str(root / "token_speedometer/assets/etincelles-128.png") + "\nTerminal=false\nX-Etincelles-Owner=" + OWNER + "\n",
                        encoding="utf-8")
        path.chmod(0o755)

def set_startup(enabled):
    path = shortcut_paths()[-1]
    if enabled:
        if not (installed_root() / "install.json").is_file():
            raise RuntimeError("Install the widget before enabling start at login.")
        write_shortcut(path)
    elif path.exists():
        if not shortcut_owned(path):
            raise RuntimeError("The startup entry belongs to another application.")
        path.unlink()

def owned_root(root):
    root = Path(root)
    if root.is_symlink() or not (root / ".owner").is_file() or (root / ".owner").read_text().strip() != OWNER:
        raise RuntimeError("Refusing to change an unowned installation.")
    return root.resolve()

def manifest_files(root, manifest):
    root = owned_root(root)
    result = []
    for relative in manifest["files"]:
        path = root / relative
        if path.is_symlink() or not path.resolve().is_relative_to(root) or not relative or Path(relative).is_absolute():
            raise RuntimeError("Invalid installation manifest path.")
        result.append(path)
    return result

def install():
    root = installed_root()
    if root.exists() and any(root.iterdir()):
        owned_root(root)
    root.mkdir(parents=True, exist_ok=True)
    (root / ".owner").write_text(OWNER, encoding="utf-8")
    files = [".owner", "install.json"]
    if getattr(sys, "frozen", False):
        target = root / EXE
        if Path(sys.executable).resolve() != target.resolve():
            shutil.copy2(sys.executable, target)
        files.append(EXE)
    else:
        source = Path(__file__).parent
        package = root / "token_speedometer"
        package.mkdir(exist_ok=True)
        for item in source.glob("*.py"):
            shutil.copy2(item, package / item.name)
            files.append("token_speedometer/" + item.name)
        asset_folder = package / "assets"
        asset_folder.mkdir(exist_ok=True)
        for item in (source / "assets").iterdir():
            if item.is_file() and item.suffix in (".png", ".ico"):
                shutil.copy2(item, asset_folder / item.name)
                files.append("token_speedometer/assets/" + item.name)
        (root / "launcher.py").write_text("import sys\nsys.dont_write_bytecode=True\nfrom token_speedometer.cli import main\nmain()\n", encoding="utf-8")
        files.append("launcher.py")
    # Only this fixed application-settings file is included, never an entire folder tree.
    if data_dir().resolve() == root.resolve():
        files += ["config.json", "config.tmp"]
    manifest = {"owner": OWNER, "files": sorted(set(files)), "version": 1}
    (root / "install.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    paths = shortcut_paths()
    for index, path in enumerate(paths[:-1]):
        write_shortcut(path, uninstall=path.name.lower().startswith("uninstall"))
    return str(root)

def remove_files(root, manifest):
    """Delete exact owned files; unknown files and nonempty directories survive."""
    paths = manifest_files(root, manifest)
    for path in paths:
        if path.is_file():
            path.unlink()
    directories = {p.parent for p in paths}
    for path in sorted(directories, key=lambda p: len(p.parts), reverse=True):
        if path == root or path.is_relative_to(root):
            try:
                path.rmdir()
            except OSError:
                pass

def uninstall():
    root = owned_root(installed_root())
    manifest = json.loads((root / "install.json").read_text(encoding="utf-8"))
    if manifest.get("owner") != OWNER:
        raise RuntimeError("Invalid installation manifest owner.")
    files = manifest_files(root, manifest)
    shortcuts = list(shortcut_paths())
    if os.name == "nt" and getattr(sys, "frozen", False):
        # A separate helper waits for this executable to exit before removing it.
        import tempfile
        helper = Path(tempfile.gettempdir()) / ("etincelles-meter-uninstall-" + str(os.getpid()) + ".ps1")
        lines = ["Start-Sleep -Milliseconds 700", "Wait-Process -Id " + str(os.getpid()) + " -Timeout 20 -ErrorAction SilentlyContinue",
                 "$ErrorActionPreference='Stop'"]
        target, arguments = command(root)
        lines.append("$shell=New-Object -ComObject WScript.Shell")
        for path in shortcuts:
            lines.append("if(Test-Path -LiteralPath " + ps_quote(path) + "){ $link=$shell.CreateShortcut(" + ps_quote(path) + "); if($link.TargetPath -eq " + ps_quote(target) + " -and $link.Arguments.StartsWith(" + ps_quote(arguments) + ")) { Remove-Item -LiteralPath " + ps_quote(path) + " -Force } }")
        lines += ["Remove-Item -LiteralPath " + ps_quote(p) + " -Force -ErrorAction SilentlyContinue" for p in files]
        directories = sorted({p.parent for p in files} | {root}, key=lambda p: len(p.parts), reverse=True)
        lines += ["try { [System.IO.Directory]::Delete(" + ps_quote(p) + ",$false) } catch {}" for p in directories]
        lines += ["Remove-Item -LiteralPath $PSCommandPath -Force"]
        helper.write_text("\n".join(lines), encoding="utf-8-sig")
        subprocess.Popen(["powershell.exe", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-File", str(helper)],
                         creationflags=subprocess.CREATE_NO_WINDOW)
    else:
        for path in shortcuts:
            if shortcut_owned(path, root):
                path.unlink()
        remove_files(root, manifest)
    if data_dir().resolve() != root:
        settings = data_dir()
        if (settings / ".owner").is_file() and (settings / ".owner").read_text().strip() == OWNER:
            for name in ["config.json", "config.tmp", ".owner"]:
                path = settings / name
                if path.is_file() and not path.is_symlink():
                    path.unlink()
            try:
                settings.rmdir()
            except OSError:
                pass
    return "Etincelles Token Meter removed. Inference engines and unrelated files are preserved."
