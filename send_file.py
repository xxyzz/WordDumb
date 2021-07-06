#!/usr/bin/env python3
import shutil
from pathlib import Path

from calibre.gui2 import FunctionDispatcher
from calibre_plugins.worddumb.database import get_ll_path, get_x_ray_path


class SendFile():
    def __init__(self, gui, data):
        self.gui = gui
        self.device_manager = self.gui.device_manager
        (self.book_id, _, self.asin, self.book_path, self.mi, _) = data
        self.ll_path = get_ll_path(self.asin, self.book_path)
        self.x_ray_path = get_x_ray_path(self.asin, self.book_path)
        self.retry = False

    # use some code from calibre.gui2.device:DeviceMixin.upload_books
    def send_files(self, job):
        if job is not None:
            self.gui.books_uploaded(job)

        [has_book, _, _, _, paths] = self.gui.book_on_device(self.book_id)
        # /Volumes/Kindle
        device_prefix = self.device_manager.device._main_prefix
        if has_book:
            device_book_path = Path(device_prefix).joinpath(next(iter(paths)))
            self.move_file_to_device(self.ll_path, device_book_path)
            self.move_file_to_device(self.x_ray_path, device_book_path)
        elif not self.retry:
            # upload book and cover to device
            self.gui.update_thumbnail(self.mi)
            job = self.device_manager.upload_books(
                FunctionDispatcher(self.send_files), [self.book_path],
                [Path(self.book_path).name], on_card=None, metadata=[self.mi],
                titles=[i.title for i in [self.mi]],
                plugboards=self.gui.current_db.new_api.pref('plugboards', {}))
            self.gui.upload_memory[job] = (
                [self.mi], None, None, [self.book_path])
            self.retry = True

    def move_file_to_device(self, file_path, device_book_path):
        if not file_path.is_file():
            return
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
