"""Bind this checkout's Python and Studio run configuration in PyCharm."""

from __future__ import annotations

import json
import logging
import os
import platform
import re
import sys
from pathlib import Path
from tempfile import NamedTemporaryFile
from uuid import uuid4
from xml.etree import ElementTree as ET

LOGGER = logging.getLogger("fpvs_studio.windows_setup")
SCRIPT = "$PROJECT_DIR$/src/fpvs_studio/app/main.py"
RUN_NAME = "FPVS Studio (Windows)"
PROFILE = re.compile(r"PyCharm(?:CE)?(\d{4})\.(\d+)(?:\.(\d+))?")


def _profile_version(name: str) -> tuple[int, ...]:
    match = PROFILE.fullmatch(name)
    return tuple(int(part or 0) for part in match.groups()) if match else ()


def find_profile() -> Path | None:
    override = os.environ.get("FPVS_PYCHARM_CONFIG")
    if override:
        path = Path(override).expanduser()
        if not path.is_absolute() or not path.is_dir():
            raise ValueError("FPVS_PYCHARM_CONFIG must name an existing PyCharm settings folder.")
        return path

    appdata = os.environ.get("APPDATA")
    if not appdata:
        return None
    profiles = Path(appdata) / "JetBrains"
    install_dirs = []
    if program_files := os.environ.get("ProgramFiles"):
        install_dirs.append(Path(program_files) / "JetBrains")
    if local := os.environ.get("LOCALAPPDATA"):
        install_dirs.extend(Path(local) / part for part in (
            "Programs", "Programs/JetBrains", "JetBrains/Toolbox/apps",
        ))

    installed = set()
    for directory in install_dirs:
        for info in directory.glob("PyCharm*/product-info.json"):
            product = json.loads(info.read_text(encoding="utf-8"))
            name = product.get("dataDirectoryName", "")
            if _profile_version(name):
                installed.add(name)
    names = installed or {path.name for path in profiles.glob("PyCharm*") if path.is_dir()}
    selected = max((name for name in names if _profile_version(name)),
                   key=lambda name: (_profile_version(name), name), default=None)
    return profiles / selected if selected else None


class SettingsFile:
    def __init__(self, path: Path, root: Path, tag: str, **attributes: str) -> None:
        if path.is_symlink() or not path.resolve().is_relative_to(root.resolve()):
            raise ValueError(f"Settings file must stay within {root}: {path}")
        self.path = path
        self.before = path.read_bytes() if path.exists() else None
        parser = ET.XMLParser(target=ET.TreeBuilder(insert_comments=True))
        self.tree = (ET.fromstring(self.before, parser) if self.before is not None
                     else ET.Element(tag, attributes))
        if self.tree.tag != tag:
            raise ValueError(f"Unrecognized PyCharm settings in {path}.")
        self.original_tree = ET.tostring(self.tree) if self.before is not None else None

    def save(self, backup_dir: Path) -> None:
        if ET.tostring(self.tree) == self.original_tree:
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        ET.indent(self.tree, space="  ")
        with NamedTemporaryFile(dir=self.path.parent, delete=False) as output:
            temporary = Path(output.name)
            output.write(ET.tostring(self.tree, encoding="utf-8", xml_declaration=True) + b"\n")
        try:
            if self.before is not None:
                backup_dir.mkdir(parents=True, exist_ok=True)
                (backup_dir / f"{self.path.name}.{uuid4().hex}.bak").write_bytes(self.before)
            current = self.path.read_bytes() if self.path.exists() else None
            if current != self.before:
                raise ValueError(f"PyCharm settings changed during setup: {self.path}")
            temporary.replace(self.path)
        finally:
            temporary.unlink(missing_ok=True)


def _component(tree: ET.Element, name: str, **attributes: str) -> ET.Element:
    component = tree.find(f"component[@name='{name}']")
    if component is None:
        component = ET.SubElement(tree, "component", {"name": name, **attributes})
    return component


def _register_sdk(table: ET.Element, root: Path, python: Path) -> str:
    entries = _component(table, "ProjectJdkTable")
    names = set()
    for sdk in entries.findall("jdk"):
        name_element = sdk.find("name")
        if name_element is None or not (label := name_element.get("value")):
            continue
        names.add(label)
        kind, home = sdk.find("type"), sdk.find("homePath")
        if kind is None or kind.get("value") != "Python SDK" or home is None:
            continue
        path = home.get("value", "").replace("$USER_HOME$", str(Path.home()))
        if Path(path) == python:
            return label

    base = f"Python 3.10 (FPVS Studio: {root.name})"
    name = base
    suffix = 2
    while name in names:
        name = f"{base} [{suffix}]"
        suffix += 1
    sdk = ET.SubElement(entries, "jdk", version="2")
    for tag, value in (("name", name), ("type", "Python SDK"),
                       ("version", f"Python {platform.python_version()}"),
                       ("homePath", python.as_posix())):
        ET.SubElement(sdk, tag, value=value)
    roots = ET.SubElement(sdk, "roots")
    for tag in ("classPath", "sourcePath"):
        ET.SubElement(ET.SubElement(roots, tag), "root", type="composite")
    ET.SubElement(sdk, "additional", ASSOCIATED_PROJECT_PATH=root.as_posix(), SDK_UUID=str(uuid4()))
    return name


def _project_module(root: Path, modules: SettingsFile) -> SettingsFile | None:
    if modules.before is None:
        relative = ".idea/fpvs-studio.iml"
        manager = _component(modules.tree, "ProjectModuleManager")
        ET.SubElement(ET.SubElement(manager, "modules"), "module", {
            "fileurl": f"file://$PROJECT_DIR$/{relative}", "filepath": f"$PROJECT_DIR$/{relative}",
        })
        module = SettingsFile(root / relative, root, "module", type="PYTHON_MODULE", version="4")
        if module.before is None:
            manager = _component(module.tree, "NewModuleRootManager")
            content = ET.SubElement(manager, "content", url="file://$MODULE_DIR$")
            ET.SubElement(
                content, "sourceFolder", url="file://$MODULE_DIR$/src", isTestSource="false",
            )
            ET.SubElement(manager, "orderEntry", type="inheritedJdk")
            ET.SubElement(manager, "orderEntry", type="sourceFolder", forTests="false")
        return module

    paths = []
    for entry in modules.tree.findall("component[@name='ProjectModuleManager']/modules/module"):
        path = Path(entry.get("filepath", "").replace("$PROJECT_DIR$", str(root)))
        if path.suffix == ".iml" and path.is_file() and path.resolve().is_relative_to(root):
            paths.append(path)
    primary = next((path for path in paths if path.stem in ("fpvs-studio", root.name)), None)
    if primary is None and len(paths) == 1:
        primary = paths[0]
    return SettingsFile(primary, root, "module") if primary else None


def configure(root: Path, python: Path, profile: Path | None) -> None:
    idea = root / ".idea"
    backups = idea / "fpvs-setup-backups"
    if not backups.resolve().is_relative_to(root):
        raise ValueError("PyCharm settings and backups must stay inside the checkout.")

    run = SettingsFile(idea / "runConfigurations/FPVS_Studio_Windows.xml", root, "component",
                       name="ProjectRunConfigurationManager")
    configuration = run.tree.find("configuration")
    if configuration is None:
        configuration = ET.SubElement(run.tree, "configuration", default="false", name=RUN_NAME,
                                      type="PythonConfigurationType", factoryName="Python")
        ET.SubElement(configuration, "method", v="2")
    elif (configuration.get("name") != RUN_NAME
          or configuration.get("type") != "PythonConfigurationType"):
        raise ValueError(f"Rename the custom run configuration at {run.path} and rerun setup.")

    options = {
        "SDK_HOME": f"$PROJECT_DIR$/{python.relative_to(root).as_posix()}",
        "IS_MODULE_SDK": "false",
        "WORKING_DIRECTORY": "$PROJECT_DIR$",
        "SCRIPT_NAME": SCRIPT,
        "MODULE_MODE": "false",
    }
    if profile is not None:
        table = SettingsFile(profile / "options/jdk.table.xml", profile, "application")
        misc = SettingsFile(idea / "misc.xml", root, "project", version="4")
        modules = SettingsFile(idea / "modules.xml", root, "project", version="4")
        module = _project_module(root, modules)
        sdk = _register_sdk(table.tree, root, python)
        manager = _component(misc.tree, "ProjectRootManager", version="2")
        manager.set("project-jdk-name", sdk)
        manager.set("project-jdk-type", "Python SDK")
        if module is not None:
            sdk_entry = module.tree.find(".//orderEntry[@type='jdk'][@jdkType='Python SDK']")
            if sdk_entry is not None:
                sdk_entry.set("jdkName", sdk)
            selection = configuration.find("module")
            if selection is None:
                selection = ET.SubElement(configuration, "module")
            selection.set("name", module.path.stem)

        options["SDK_NAME"] = sdk
        # PyCharm can serialize a newer interpreter field that takes priority over SDK_NAME.
        if (interpreter := configuration.find("option[@name='INTERPRETER']")) is not None:
            configuration.remove(interpreter)
        for settings in (table, misc, module, modules):
            if settings is not None:
                settings.save(backups)

    for key, value in options.items():
        option = configuration.find(f"option[@name='{key}']")
        if option is None:
            option = ET.SubElement(configuration, "option", name=key)
        option.set("value", value)
    run.save(backups)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    checkout = Path(__file__).resolve().parents[1]
    interpreter = Path(sys.executable)
    try:
        profile = find_profile()
        configure(checkout, interpreter, profile)
    except (OSError, ValueError, ET.ParseError) as error:
        LOGGER.error("Could not configure PyCharm: %s", error)
        raise SystemExit(1) from error
    if profile is None:
        LOGGER.info("Run configuration created. Rerun setup after installing PyCharm.")
    else:
        LOGGER.info("PyCharm interpreter and %s run configuration prepared.", RUN_NAME)
