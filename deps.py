#!/usr/bin/env python3

import platform
import shutil
from pathlib import Path

from calibre.constants import is64bit, ismacos, iswindows
from calibre.utils.config import config_dir

from .utils import load_json_or_pickle, run_subprocess, homebrew_mac_bin_path


class InstallDeps:
    def __init__(self, model, plugin_path, book_fmt, notif):
        self.model = model
        self.model_v = "3.2.0"
        self.plugin_path = plugin_path
        self.notif = notif
        self.book_fmt = book_fmt
        self.machine = platform.machine()
        self.which_python()
        self.install_x_ray_deps()

    def which_python(self):
        self.py = "python3"
        self.py_v = ".".join(platform.python_version_tuple()[:2])
        if iswindows:
            self.py = "py" if shutil.which("py") else "python"
            r = run_subprocess(
                [self.py, "-c", "import sys; print(sys.maxsize > 2**32)"]
            )
            if r.stdout.strip() != "True":
                raise Exception("32BIT_PYTHON")
        elif ismacos:
            self.py = homebrew_mac_bin_path("python3")
            if not shutil.which(self.py):
                self.py = "/usr/bin/python3"  # Command Line Tools
                self.upgrade_mac_pip()
            r = run_subprocess(
                [
                    self.py,
                    "-c",
                    'import platform; print(".".join(platform.python_version_tuple()[:2]))',
                ]
            )
            self.py_v = r.stdout.strip()

        self.libs_path = Path(config_dir).joinpath(
            f"plugins/worddumb-libs-py{self.py_v}"
        )

    def install_x_ray_deps(self):
        if reinstall := False if self.libs_path.exists() else True:
            for old_path in self.libs_path.parent.glob("worddumb-libs-py*"):
                old_path.rename(self.libs_path)

        for pkg, value in load_json_or_pickle(
            self.plugin_path, "data/spacy.json"
        ).items():
            self.pip_install(
                pkg, value["version"], value["compiled"], reinstall=reinstall
            )
        url = "https://github.com/explosion/spacy-models/releases/download/"
        url += f"{self.model}-{self.model_v}/"
        url += f"{self.model}-{self.model_v}-py3-none-any.whl"
        self.pip_install(self.model, self.model_v, url=url)
        self.install_extra_deps()

    def pip_install(self, pkg, pkg_version, compiled=False, url=None, reinstall=False):
        pattern = f"{pkg.replace('-', '_')}-{pkg_version}*"
        if not any(self.libs_path.glob(pattern)) or (reinstall and compiled):
            if self.notif:
                self.notif.put((0, f"Installing {pkg}"))
            run_subprocess(self.pip_args(pkg, pkg_version, compiled, url))

    def pip_args(self, pkg, pkg_version, compiled, url):
        args = [
            self.py,
            "-m",
            "pip",
            "install",
            "-U",
            "-t",
            self.libs_path,
            "--no-deps",
            "--no-cache-dir",
        ]
        if compiled:
            args.extend(["--python-version", self.py_v])
            if not is64bit:
                raise Exception("32BIT_CALIBRE")
        if url:
            args.append(url)
        elif pkg_version:
            args.append(f"{pkg}=={pkg_version}")
        else:
            args.append(pkg)
        return args

    def install_extra_deps(self):
        # https://spacy.io/usage/models#languages
        data = load_json_or_pickle(self.plugin_path, "data/spacy_extra.json")
        if (lang := self.model[:2]) in data:
            for pkg, value in data[lang].items():
                self.pip_install(pkg, value["version"], value["compiled"])

        if ismacos:
            if self.book_fmt == "EPUB":
                for pkg, value in data["mac_epub"].items():
                    self.pip_install(pkg, value["version"], value["compiled"])
            if self.machine == "arm64":
                for pkg, value in data["mac_arm"].items():
                    self.pip_install(pkg, value["version"], value["compiled"])

    def upgrade_mac_pip(self):
        import re

        r = run_subprocess([self.py, "-m", "pip", "--version"])
        m = re.match(r"pip (\d+)\.", r.stdout)
        if m and int(m.group(1)) < 22:
            run_subprocess(
                [
                    self.py,
                    "-m",
                    "pip",
                    "install",
                    "--user",
                    "-U",
                    "--no-cache-dir",
                    "pip",
                ]
            )
