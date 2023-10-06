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
from .metadata import get_asin_etc
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
        [has_book, _, _, _, paths] = self.gui.book_on_device(self.job_data.book_id)
        if has_book and self.job_data.book_fmt != "EPUB":
            # _main_prefix: Kindle mount point, /Volumes/Kindle
            device_mount_point = Path(self.device_manager.device._main_prefix)
            device_book_path = device_mount_point.joinpath(paths.pop())
            if job is None:
                # update device book ASIN if it doesn't have the same ASIN
                get_asin_etc(self.job_data, device_book_path, set_en_lang)
                if self.job_data.update_asin:  # Re-upload book cover
                    self.gui.update_thumbnail(self.job_data.mi)
                    self.device_manager.device.upload_kindle_thumbnail(
                        self.job_data.mi, self.job_data.book_path
                    )

            self.move_files_to_kindle(device_mount_point, device_book_path)
            library_book_path = Path(self.job_data.book_path)
            if library_book_path.stem.endswith("_en"):
                library_book_path.unlink()
            self.gui.status_bar.show_message(self.notif)
        elif job is None or self.job_data.book_fmt == "EPUB":
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

    def move_files_to_kindle(
        self, device_mount_point: Path, device_book_path: Path
    ) -> None:
        if self.ll_path.exists():
            copy_klld_to_device(
                self.job_data.book_lang,
                device_mount_point.joinpath("system/kll/kll.en.zh.klld"),
                None,
            )
            self.move_file_to_kindle(self.ll_path, device_book_path)
        self.move_file_to_kindle(self.x_ray_path, device_book_path)

    def move_file_to_kindle(self, file_path: Path, device_book_path: Path) -> None:
        if not file_path.is_file():
            return
        sidecar_folder = device_book_path.parent.joinpath(
            f"{device_book_path.stem}.sdr"
        )
        if not sidecar_folder.is_dir():
            sidecar_folder.mkdir()
        dst_path = sidecar_folder.joinpath(file_path.name)
        if dst_path.is_file():
            dst_path.unlink()
        shutil.move(file_path, dst_path, shutil.copy)

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
        is_kindle = getattr(gui.device_manager.device, "VENDOR_NAME", None) == "KINDLE"
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
    book_lang: str, device_klld_path: Path, adb_path: str | None
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
    else:
        copy = False
        if not device_klld_path.exists():
            copy = True
        elif not is_same_klld(local_klld_path, device_klld_path):
            copy = True

        if copy:
            shutil.copy(local_klld_path, device_klld_path)
