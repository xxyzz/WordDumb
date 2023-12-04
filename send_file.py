#!/usr/bin/env python3
import shutil
import subprocess
import traceback
from pathlib import Path
from typing import Any

from calibre.constants import ismacos
from calibre.gui2 import FunctionDispatcher
from calibre.gui2.dialogs.message_box import JobError

from .database import get_ll_path, get_x_ray_path, is_same_klld
from .error_dialogs import kindle_epub_dialog
from .parse_job import ParseJobData
from .utils import (
    get_plugin_path,
    get_wiktionary_klld_path,
    mac_bin_path,
    run_subprocess,
    use_kindle_ww_db,
)


class SendFile:
    def __init__(
        self, gui: Any, data: ParseJobData, package_name: str | bool, notif: Any
    ) -> None:
        self.gui = gui
        self.device_manager = gui.device_manager
        self.notif = notif
        self.job_data = data
        self.ll_path = get_ll_path(data.asin, data.book_path)
        self.x_ray_path = get_x_ray_path(data.asin, data.book_path)
        self.package_name = package_name
        if data.acr is None:
            self.job_data.acr = "_"

    # use some code from calibre.gui2.device:DeviceMixin.upload_books
    def send_files(self, job: Any) -> None:
        if isinstance(self.package_name, str):
            try:
                adb_path = which_adb()
                if adb_path is None:
                    return
                self.push_files_to_android(adb_path)
                self.gui.status_bar.show_message(self.notif)
            except subprocess.CalledProcessError as e:
                stderr = e.stderr.decode("utf-8")
                JobError(self.gui).show_error(
                    "adb failed", stderr, det_msg=traceback.format_exc() + stderr
                )
            return

        if job is not None:
            if job.failed:
                self.gui.job_exception(job, dialog_title="Upload book failed")
                return
            self.gui.books_uploaded(job)
            if self.job_data.book_fmt == "EPUB":
                self.gui.status_bar.show_message(self.notif)
                Path(self.job_data.book_path).unlink()
                return

        set_en_lang = False
        if (
            self.ll_path.exists()
            and self.job_data.book_fmt != "EPUB"
            and self.job_data.book_lang != "en"
        ):
            set_en_lang = True

        # https://github.com/kovidgoyal/calibre/blob/320fb96bbd08b99afbf3de560f7950367d21c093/src/calibre/gui2/device.py#L1772
        has_book, *_, paths = self.gui.book_on_device(self.job_data.book_id)
        if has_book and job is not None and self.job_data.book_fmt != "EPUB":
            self.move_files_to_kindle(self.gui.device_manager.device, Path(paths.pop()))
            library_book_path = Path(self.job_data.book_path)
            if library_book_path.stem.endswith("_en"):
                library_book_path.unlink()
            self.gui.status_bar.show_message(self.notif)
        elif job is None:
            # upload book and cover to device
            self.gui.update_thumbnail(self.job_data.mi)
            # without this the book language won't be English after uploading
            if set_en_lang and self.job_data.book_fmt == "KFX":
                self.job_data.mi.language = "eng"
            job = self.device_manager.upload_books(
                FunctionDispatcher(self.send_files),
                [self.job_data.book_path],
                [Path(self.job_data.book_path).name],
                on_card=None,
                metadata=[self.job_data.mi],
                titles=[i.title for i in [self.job_data.mi]],
                plugboards=self.gui.current_db.new_api.pref("plugboards", {}),
            )
            self.gui.upload_memory[job] = (
                [self.job_data.mi],
                None,
                None,
                [self.job_data.book_path],
            )

    def move_files_to_kindle(self, device_driver: Any, device_book_path: Path) -> None:
        use_mtp = is_mtp_device(device_driver)
        if not use_mtp:
            # _main_prefix: Kindle mount point, /Volumes/Kindle
            device_mount_point = Path(device_driver._main_prefix)
        if self.ll_path.exists():
            device_klld_path = Path("system/kll/kll.en.zh.klld")
            if not use_mtp:
                device_klld_path = device_mount_point.joinpath(device_klld_path)
            copy_klld_to_device(
                self.job_data.book_lang,
                device_klld_path,
                None,
                device_driver if use_mtp else None,
            )
        sidecar_folder = device_book_path.parent.joinpath(
            f"{device_book_path.stem}.sdr"
        )
        if use_mtp:
            for file_path in (self.ll_path, self.x_ray_path):
                dest_path = sidecar_folder.joinpath(file_path.name)
                upload_file_to_kindle_mtp(device_driver, file_path, dest_path)
        else:
            sidecar_folder = device_mount_point.joinpath(sidecar_folder)
            for file_path in (self.ll_path, self.x_ray_path):
                dest_path = sidecar_folder.joinpath(file_path.name)
                move_file_to_kindle_usbms(file_path, dest_path)

    def push_files_to_android(self, adb_path: str) -> None:
        device_book_folder = f"/sdcard/Android/data/{self.package_name}/files/"
        run_subprocess(
            [
                adb_path,
                "push",
                self.job_data.book_path,
                f"{device_book_folder}/{Path(self.job_data.book_path).name}",
            ]
        )
        if self.x_ray_path.exists():
            run_subprocess(
                [
                    adb_path,
                    "push",
                    self.x_ray_path,
                    f"{device_book_folder}/{self.job_data.asin}/XRAY."
                    f"{self.job_data.asin}.{self.job_data.acr}.db",
                ]
            )
            self.x_ray_path.unlink()
        if self.ll_path.exists():
            run_subprocess([adb_path, "root"])
            run_subprocess(
                [
                    adb_path,
                    "push",
                    self.ll_path,
                    f"/data/data/{self.package_name}/databases/WordWise.en."
                    f"{self.job_data.asin}.{self.job_data.acr.replace('!', '_')}.db",
                ]
            )
            self.ll_path.unlink()
            copy_klld_to_device(
                self.job_data.book_lang,
                Path(
                    f"/data/data/{self.package_name}"
                    "/databases/wordwise/WordWise.kll.en.zh.db"
                ),
                adb_path,
            )


def device_connected(gui: Any, book_fmt: str) -> str | bool:
    if gui.device_manager.is_device_present:
        is_kindle = False
        device = gui.device_manager.device
        if hasattr(device, "VENDOR_NAME"):
            # Normal USB mass storage Kindle
            is_kindle = device.VENDOR_NAME == "KINDLE"
        elif hasattr(device, "current_vid"):
            # Kindle Scribe, MTP vendor id is Amazon
            # https://github.com/kovidgoyal/calibre/blob/475b0d3d2e6678dc4fd5441619f71a048c3806ea/src/calibre/devices/mtp/driver.py#L145
            is_kindle = device.current_vid == 0x1949

        if book_fmt == "EPUB":
            if is_kindle:
                kindle_epub_dialog(gui)
            else:
                return True
        elif is_kindle:
            return True
    if book_fmt == "KFX":
        adb_path = which_adb()
        if adb_path and adb_connected(adb_path):
            package_name = get_package_name(adb_path)
            return package_name if package_name else False
    return False


def is_mtp_device(device_driver: Any) -> bool:
    # https://github.com/kovidgoyal/calibre/blob/475b0d3d2e6678dc4fd5441619f71a048c3806ea/src/calibre/devices/mtp/driver.py#L49
    if hasattr(device_driver, "DEVICE_PLUGBOARD_NAME"):
        return device_driver.DEVICE_PLUGBOARD_NAME == "MTP_DEVICE"
    return False


def adb_connected(adb_path: str) -> bool:
    r = run_subprocess([adb_path, "devices"])
    return r.stdout.decode().strip().endswith("device") if r else False


def which_adb() -> str | None:
    return shutil.which(mac_bin_path("adb") if ismacos else "adb")


def get_package_name(adb_path: str) -> str | None:
    r = run_subprocess(
        [adb_path, "shell", "pm", "list", "packages", "com.amazon.kindle"]
    )
    result = r.stdout.decode().strip()
    if len(result.split(":")) > 1:
        return result.split(":")[1]  # China version: com.amazon.kindlefc
    return None


def copy_klld_from_android(package_name: str, dest_path: Path) -> None:
    adb_path = which_adb()
    run_subprocess([adb_path, "root"])
    run_subprocess(
        [
            adb_path,
            "pull",
            f"/data/data/{package_name}/databases/wordwise",
            dest_path,
        ]
    )
    for path in dest_path.joinpath("wordwise").iterdir():
        shutil.move(path, dest_path)
    dest_path.joinpath("wordwise").rmdir()


def copy_klld_from_kindle(gui: Any, dest_path: Path) -> None:
    for klld_path in Path(f"{gui.device_manager.device._main_prefix}/system/kll").glob(
        "*.en.klld"
    ):
        shutil.copy(klld_path, dest_path)


def copy_klld_to_device(
    book_lang: str, device_klld_path: Path, adb_path: str | None, mtp_driver: Any = None
) -> None:
    from .config import prefs

    plugin_path = get_plugin_path()
    if use_kindle_ww_db(book_lang, prefs):
        return
    local_klld_path = get_wiktionary_klld_path(
        plugin_path, book_lang, prefs["kindle_gloss_lang"]
    )

    if adb_path is not None:
        run_subprocess([adb_path, "push", str(local_klld_path), str(device_klld_path)])
    elif mtp_driver is not None:
        upload_file_to_kindle_mtp(mtp_driver, local_klld_path, device_klld_path)
    else:
        copy = False
        if not device_klld_path.exists():
            copy = True
        elif not is_same_klld(local_klld_path, device_klld_path):
            copy = True

        if copy:
            shutil.copy(local_klld_path, device_klld_path)


def upload_file_to_kindle_mtp(driver: Any, source_path: Path, dest_path: Path) -> None:
    # https://github.com/kovidgoyal/calibre/blob/52ebc7809506e19beb135f53419a8bb9571c24e3/src/calibre/devices/mtp/driver.py#L417
    if not source_path.exists():
        return
    storage = driver.filesystem_cache.storage(driver._main_id)
    parent = driver.ensure_parent(storage, dest_path.parts)
    with source_path.open("rb") as f:
        driver.put_file(
            parent, dest_path.parts[-1], f, source_path.stat().st_size, replace=True
        )
    source_path.unlink()


def move_file_to_kindle_usbms(source_path: Path, dest_path: Path) -> None:
    if not source_path.is_file():
        return
    if not dest_path.parent.is_dir():
        dest_path.parent.mkdir()
    if dest_path.is_file():
        dest_path.unlink()
    shutil.move(source_path, dest_path, shutil.copy)
