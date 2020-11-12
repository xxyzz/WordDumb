#!/usr/bin/env python3

from calibre.gui2 import FunctionDispatcher
from pathlib import Path
import shutil

class SendFile():
    def __init__(self, gui, book_id, book_path, ll_path, mi):
        self.gui = gui
        self.device_manager = self.gui.device_manager
        self.book_id = book_id
        self.book_path = book_path # string
        self.ll_path = ll_path     # path object
        self.mi = mi
        self.retry = False

    def send_to_device(self):
        if not self.device_manager.is_device_connected:
            return None
        device = self.device_manager.device
        if device.VENDOR_ID != [0x1949]: # Kindle device
            return None
        self.send_files(None)

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
        device_info = self.device_manager.get_current_device_information()
        device_path_prefix = device_info['info'][4]['main']['prefix'] # /Volumes/Kindle
        if has_book:
            device_book_path = Path(device_path_prefix)
            device_book_path = device_book_path.joinpath(next(iter(paths)))
            self.move_ll_to_device(device_book_path)
        elif not self.retry:
            # upload book and cover to device
            cover_path = Path(self.book_path).parent.joinpath('cover.jpg')
            self.mi.thumbnail = None, None, cover_path.read_bytes()
            book_name = Path(self.book_path).name
            titles = [i.title for i in [self.mi]]
            plugboards = self.gui.current_db.new_api.pref('plugboards', {})
            self.device_manager.upload_books(
                FunctionDispatcher(self.send_files), [self.book_path], [book_name],
                on_card=None, metadata=[self.mi], titles=titles, plugboards=plugboards)
            self.retry = True

    def move_ll_to_device(self, book_path):
        ll_folder = book_path.stem + '.sdr'
        device_ll_path = book_path.parent.joinpath(ll_folder)
        if not device_ll_path.is_dir():
            device_ll_path.mkdir()
        device_ll_path = device_ll_path.joinpath(self.ll_path.name)
        shutil.move(self.ll_path, device_ll_path)
