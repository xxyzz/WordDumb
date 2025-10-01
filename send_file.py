import shutil
from pathlib import Path
from typing import Any

from calibre.gui2 import FunctionDispatcher

from .database import get_ll_path, get_x_ray_path, is_same_klld
from .error_dialogs import kindle_epub_dialog
from .parse_job import ParseJobData
from .utils import (
    get_kindle_klld_path,
    get_plugin_path,
    get_wiktionary_klld_path,
    use_kindle_ww_db,
)


class SendFile:
    def __init__(self, gui: Any, data: ParseJobData, notif: Any) -> None:
        self.gui = gui
        self.device_manager = gui.device_manager
        self.is_mtp = is_mtp_device(self.device_manager.device)
        self.notif = notif
        self.job_data = data
        self.ll_path = get_ll_path(data.asin, data.book_path)
        self.x_ray_path = get_x_ray_path(data.asin, data.book_path)
        if data.acr is None:
            self.job_data.acr = "_"

    # use some code from calibre.gui2.device:DeviceMixin.upload_books
    def send_files(self, job: Any) -> None:
        if job is not None:
            if job.failed:
                self.gui.job_exception(job, dialog_title="Upload book failed")
                return
            self.gui.books_uploaded(job)
            if self.job_data.book_fmt == "EPUB":
                self.gui.status_bar.show_message(self.notif)
                Path(self.job_data.book_path).unlink()
                return
            if self.is_mtp:
                # https://github.com/kovidgoyal/calibre/blob/3eb69966563caf877d0e1f2819ddbf6599c35622/src/calibre/devices/mtp/driver.py#L462
                # https://github.com/kovidgoyal/calibre/blob/3eb69966563caf877d0e1f2819ddbf6599c35622/src/calibre/devices/mtp/filesystem_cache.py#L37
                mtp_device_filename = job.result[0][0].name

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
            device_book_path = Path(paths.pop())
            if self.is_mtp:
                # `book_on_device` returns lower case path for MTP devices
                device_book_path = device_book_path.with_name(mtp_device_filename)
            self.move_files_to_kindle(self.gui.device_manager, device_book_path)
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

    def move_files_to_kindle(self, device_manager: Any, device_book_path: Path) -> None:
        if not self.is_mtp:
            # _main_prefix: Kindle mount point, /Volumes/Kindle
            device_mount_point = Path(device_manager.device._main_prefix)
        if self.ll_path.exists():
            device_klld_path = Path("system/kll/kll.en.zh.klld")
            if not self.is_mtp:
                device_klld_path = device_mount_point.joinpath(device_klld_path)
            copy_klld_to_device(
                self.job_data.book_lang,
                device_klld_path,
                device_manager if self.is_mtp else None,
            )
        sidecar_folder = device_book_path.with_suffix(".sdr")
        if self.is_mtp:
            for file_path in (self.ll_path, self.x_ray_path):
                dest_path = sidecar_folder / file_path.name
                upload_file_to_mtp(device_manager, file_path, dest_path)
        else:
            sidecar_folder = device_mount_point / sidecar_folder
            for file_path in (self.ll_path, self.x_ray_path):
                dest_path = sidecar_folder / file_path.name
                move_file_to_kindle_usbms(file_path, dest_path)


def device_connected(gui: Any, book_fmt: str) -> bool:
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
    return False


def is_mtp_device(device_driver: Any) -> bool:
    # https://github.com/kovidgoyal/calibre/blob/475b0d3d2e6678dc4fd5441619f71a048c3806ea/src/calibre/devices/mtp/driver.py#L49
    if hasattr(device_driver, "DEVICE_PLUGBOARD_NAME"):
        return device_driver.DEVICE_PLUGBOARD_NAME == "MTP_DEVICE"
    return False


def copy_klld_from_kindle(device_manager: Any, dest_path: Path) -> None:
    if is_mtp_device(device_manager.device):
        download_file_from_mtp(
            device_manager, Path("system/kll/kll.en.en.klld"), dest_path
        )
        download_file_from_mtp(
            device_manager, Path("system/kll/kll.en.zh.klld"), dest_path
        )
    else:
        for klld_path in Path(f"{device_manager.device._main_prefix}/system/kll").glob(
            "*.klld"
        ):
            shutil.copy(klld_path, dest_path)


def copy_klld_to_device(
    book_lang: str, device_klld_path: Path, device_manager: Any = None
) -> None:
    from .config import prefs

    plugin_path = get_plugin_path()
    if use_kindle_ww_db(book_lang, prefs):
        if prefs["gloss_lang"] in ("zh", "zh_cn"):  # restore origin ww db
            local_klld_path = get_kindle_klld_path(plugin_path, True)
            if local_klld_path is None:
                return
        else:
            return
    else:
        local_klld_path = get_wiktionary_klld_path(plugin_path, book_lang, prefs)

    if device_manager is not None:
        upload_file_to_mtp(device_manager, local_klld_path, device_klld_path)
    else:
        copy = False
        if not device_klld_path.exists():
            copy = True
        elif not is_same_klld(local_klld_path, device_klld_path):
            copy = True

        if copy:
            shutil.copy(local_klld_path, device_klld_path)


def upload_file_to_mtp(device_manager: Any, source_path: Path, dest_path: Path) -> None:
    if not source_path.exists():
        return
    device_manager.create_job(
        mtp_upload_job,
        None,
        f"MTP uploading '{dest_path}'",
        args=[device_manager.device, source_path, dest_path],
    )


def mtp_upload_job(driver: Any, source_path: Path, dest_path: Path) -> None:
    # https://github.com/kovidgoyal/calibre/blob/52ebc7809506e19beb135f53419a8bb9571c24e3/src/calibre/devices/mtp/driver.py#L417
    storage = driver.filesystem_cache.storage(driver._main_id)
    parent = driver.ensure_parent(storage, dest_path.parts)
    with source_path.open("rb") as f:
        driver.put_file(
            parent, dest_path.parts[-1], f, source_path.stat().st_size, replace=True
        )
    source_path.unlink()


def download_file_from_mtp(device_manager: Any, source_path: Path, dest_path: Path):
    device_manager.create_job(
        mtp_download_job,
        None,
        f"MTP downloading '{source_path}'",
        args=[device_manager.device, source_path, dest_path],
    )


def mtp_download_job(driver: Any, source_path: Path, dest_path: Path) -> None:
    # https://github.com/kovidgoyal/calibre/blob/a1d86860ac83146e06fc398ed8c6d5422f8749ca/src/calibre/devices/mtp/driver.py#L171
    storage = driver.filesystem_cache.storage(driver._main_id)
    path = storage.find_path(source_path.parts)
    if path is not None:
        stream = driver.get_mtp_file(path)
        with dest_path.open("wb") as dest_f:
            shutil.copyfileobj(stream, dest_f)


def move_file_to_kindle_usbms(source_path: Path, dest_path: Path) -> None:
    if not source_path.is_file():
        return
    if not dest_path.parent.is_dir():
        dest_path.parent.mkdir()
    if dest_path.is_file():
        dest_path.unlink()
    shutil.move(source_path, dest_path, shutil.copy)
