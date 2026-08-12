import subprocess
from datetime import datetime
from pathlib import Path
import json

import spack.environment as ev

from .config import selected_project_config, update
from .preconditions import State, activate_development_environment, preconditions
from .spack_compat import tty
from .util import bold, cyan, gray

SUBCOMMAND = "install"
ALIASES = ["i"]


def setup_subparser(subparsers):
    subparsers.add_parser(
        SUBCOMMAND,
        description="install (and build if necessary) repositories",
        aliases=ALIASES,
        help="install built repositories",
    )


def process(args):
    preconditions(State.INITIALIZED, State.SELECTED_PROJECT, State.PACKAGES_TO_DEVELOP)

    project_config = selected_project_config()
    activate_development_environment(project_config["local"])
    project_name = project_config["name"]
    file_dir = Path(__file__).resolve().parent
    stdout = None if args.verbose else subprocess.DEVNULL

    packages = [p for p in project_config["packages"]]

    presets = {}
    source_path = Path(project_config["source"])
    with open((source_path / "CMakePresets.json").absolute(), "r") as f:
        presets = json.load(f)
    preset_obj = presets["configurePresets"][0]["cacheVariables"]

    # sanity check: make sure all packages have been built
    for pkg in packages:
        if not Path(project_config["build"] + "/" + pkg + "/cmake_install.cmake").exists():
            tty.error(f"Package {pkg} has not been built yet. Please run 'spack mpd build' first.")
            return

    # Make sure install directories are created so add-to-database doesn't complain
    for pkg in packages:
        if preset_obj[pkg + "_HASH"] is not None:
            all_arguments = ["spack", "python", "ensure-install-directory.py", project_name, preset_obj[pkg + "_HASH"]]
            subprocess.run(all_arguments, stdout=stdout, cwd = file_dir)

    for pkg in packages:
        all_arguments = ["cmake", "--install", project_config["build"] + "/" + pkg]
        if preset_obj[pkg + "_INSTALL_PREFIX"] is not None:
            all_arguments.append("--prefix")
            all_arguments.append(preset_obj[pkg + "_INSTALL_PREFIX"])
        all_arguments_str = " ".join(all_arguments)

        print()
        tty.msg(f"Installing {pkg} with command:\n\n" + cyan(all_arguments_str) + "\n")

        subprocess.run(all_arguments, stdout=stdout)

        if preset_obj[pkg + "_HASH"] is not None:
            all_arguments = ["spack", "python", "add-to-database.py", project_name, preset_obj[pkg + "_HASH"]]
            subprocess.run(all_arguments, stdout=stdout, cwd = file_dir)

    tty.msg(gray("Installing environment"))
    # Now install the environment
    env = ev.read(project_name)
    with env, env.write_transaction():
        env.install_all()
        env.write()

    update(project_config, installed_at=datetime.now().replace(microsecond=0).isoformat(" "))
    print()
    tty.msg(f"The {bold(project_name)} environment has been installed.\n")
