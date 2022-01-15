#!/usr/bin/env python3

import platform
import shutil
import subprocess
from pathlib import Path

from calibre.constants import is64bit, ismacos, iswindows
from calibre.utils.config import config_dir
from calibre_plugins.worddumb.unzip import load_json_or_pickle


class InstallDeps:
    def __init__(self, model, plugin_path, notif):
        self.model = model
        self.model_v = '3.2.0'
        self.plugin_path = plugin_path
        self.notif = notif
        self.machine = platform.machine()
        self.which_python()
        self.install_x_ray_deps()

    def which_python(self):
        py = 'python3'
        self.py_v = '.'.join(platform.python_version_tuple()[:2])
        if iswindows:
            py = 'py' if shutil.which('py') else 'python'
        elif ismacos:
            # stupid macOS loses PATH when calibre is not launched in terminal
            if self.machine == 'arm64':
                py = '/opt/homebrew/bin/python3'
            else:
                py = '/usr/local/bin/python3'
            if not shutil.which(py):
                py = '/usr/bin/python3'  # Command Line Tools
            command = 'import platform;' \
                'print(".".join(platform.python_version_tuple()[:2]))'
            r = subprocess.run([py, '-c', command], check=True,
                               capture_output=True, text=True)
            self.py_v = r.stdout.strip()

        self.py = py
        self.libs_path = Path(config_dir).joinpath(
            f"plugins/worddumb-libs-py{self.py_v}")

    def install_x_ray_deps(self):
        if (reinstall := False if self.libs_path.exists() else True):
            for old_path in self.libs_path.parent.glob('worddumb-libs-py*'):
                old_path.rename(self.libs_path)

        for pkg, value in load_json_or_pickle(
                self.plugin_path, 'data/spacy.json').items():
            self.pip_install(pkg, value['version'], value['compiled'],
                             reinstall=reinstall)
        url = 'https://github.com/explosion/spacy-models/releases/download/'
        url += f'{self.model}-{self.model_v}/'
        url += f'{self.model}-{self.model_v}-py3-none-any.whl'
        self.pip_install(self.model, self.model_v, url=url)
        self.install_extra_deps()

    def pip_install(self, pkg, pkg_version, compiled=False, url=None,
                    reinstall=False):
        pattern = f"{pkg.replace('-', '_')}-{pkg_version}*"
        if not any(self.libs_path.glob(pattern)) or (reinstall and compiled):
            if self.notif:
                self.notif.put((0, f'Installing {pkg}'))
            args = self.pip_args(pkg, pkg_version, compiled, url)
            if iswindows:
                subprocess.run(
                    args, check=True, capture_output=True, text=True,
                    creationflags=subprocess.CREATE_NO_WINDOW)
            else:
                subprocess.run(
                    args, check=True, capture_output=True, text=True)

    def pip_args(self, pkg, pkg_version, compiled, url):
        args = [self.py, '-m', 'pip', 'install', '-U', '-t',
                self.libs_path, '--no-deps']
        if compiled:
            args.extend(['--python-version', self.py_v])
            if iswindows:
                args.append('--platform')
                if is64bit:  # in case someone installed 32bit python
                    args.append('win_amd64')
                else:
                    raise Exception('32BIT_CALIBRE')
            elif ismacos and self.machine == 'x86_64':
                # prevent command line tool's pip from compiling package
                args.extend(['--platform', 'macosx_10_9_x86_64'])
        if url:
            args.append(url)
        elif pkg_version:
            args.append(f'{pkg}=={pkg_version}')
        else:
            args.append(pkg)
        return args

    def install_extra_deps(self):
        # https://spacy.io/usage/models#languages
        data = load_json_or_pickle(self.plugin_path, 'data/spacy_extra.json')
        if (lang := self.model[:2]) in data:
            for pkg, value in data[lang].items():
                self.pip_install(pkg, value['version'], value['compiled'])

        if ismacos and self.machine == 'arm64':
            for pkg, value in data['apple'].items():
                self.pip_install(pkg, value['version'], value['compiled'])
