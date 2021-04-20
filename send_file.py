#!/usr/bin/env python3
import shutil
from pathlib import Path

from calibre.gui2 import FunctionDispatcher
from calibre_plugins.worddumb.config import prefs
from calibre_plugins.worddumb.database import get_ll_path, get_x_ray_path


class SendFile():
    def __init__(self, gui, data):
        self.gui = gui
        self.device_manager = self.gui.device_manager
        (self.book_id, _, self.asin, self.book_path, self.mi) = data
        self.ll_path = get_ll_path(self.asin, self.book_path)
        self.x_ray_path = get_x_ray_path(self.asin, self.book_path)
        self.retry = False

    # use some code from calibre.gui2.device:DeviceMixin.upload_books
    def send_files(self, job):
        if job is not None:
            self.device_manager.add_books_to_metadata(
                job.result, [self.mi], self.gui.booklists())
            if not self.gui.set_books_in_library(
                    self.gui.booklists(), reset=True,
                    add_as_step_to_job=job, do_device_sync=False):
                self.gui.upload_booklists(job)
            self.gui.refresh_ondevice()
            view = self.gui.memory_view
            view.model().resort(reset=False)
            view.model().research()

        [has_book, _, _, _, paths] = self.gui.book_on_device(self.book_id)
        # /Volumes/Kindle
        device_prefix = self.device_manager.device._main_prefix
        if has_book:
            device_book_path = Path(device_prefix).joinpath(next(iter(paths)))
            self.move_file_to_device(self.ll_path, device_book_path)
            if prefs['x-ray']:
                self.move_file_to_device(self.x_ray_path, device_book_path)
        elif not self.retry:
            # upload book and cover to device
            cover_path = Path(self.book_path).parent.joinpath('cover.jpg')
            self.mi.thumbnail = None, None, cover_path.read_bytes()
            book_name = Path(self.book_path).name
            titles = [i.title for i in [self.mi]]
            plugboards = self.gui.current_db.new_api.pref('plugboards', {})
            self.device_manager.upload_books(
                FunctionDispatcher(self.send_files), [self.book_path],
                [book_name], on_card=None, metadata=[self.mi],
                titles=titles, plugboards=plugboards)
            self.retry = True

    def move_file_to_device(self, file_path, device_book_path):
        sidecar_folder = device_book_path.parent.joinpath(
            f'{device_book_path.stem}.sdr')
        if not sidecar_folder.is_dir():
            sidecar_folder.mkdir()
        dst_path = sidecar_folder.joinpath(file_path.name)
        if dst_path.is_file():
            dst_path.unlink()
        # Python 3.9 accepts path-like object, calibre uses 3.8
        shutil.move(str(file_path), str(dst_path))


def kindle_connected(gui):
    if not gui.device_manager.is_device_present:
        return False
    if gui.device_manager.device.VENDOR_NAME != 'KINDLE':
        return False
    return True
