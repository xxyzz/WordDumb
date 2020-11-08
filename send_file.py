#!/usr/bin/env python3

from pathlib import Path
import shutil

class SendFile():
    def __init__(self, gui, book_id, book_path, ll_path, mi):
        self.gui = gui
        self.book_id = book_id
        self.book_path = book_path # string
        self.ll_path = ll_path     # path object
        self.mi = mi
        self.device = None

    def send_to_device(self):
        if not self.gui.device_manager.is_device_connected:
            return None
        self.device = self.gui.device_manager.device
        if self.device.VENDOR_ID != [0x1949]: # Kindle device
            return None
        self.send_files()

    def send_files(self):
        [has_book, _, _, _, paths] = self.gui.book_on_device(self.book_id)
        device_info = self.gui.device_manager.get_current_device_information()
        device_path_prefix = device_info['info'][4]['main']['prefix'] # /Volumes/Kindle
        if has_book:
            device_book_path = Path(device_path_prefix)
            device_book_path = device_book_path.joinpath(next(iter(paths)))
            self.move_ll_to_device(device_book_path)
        elif self.book_path is not None:
            book_name = Path(self.book_path).name
            results = self.device.upload_books(
                [self.book_path], [book_name], metadata=[self.mi])
            self.device.add_books_to_metadata(results, [self.mi], self.gui.booklists())
            self.gui.refresh_ondevice()
            self.book_path = None
            self.send_files()

    def move_ll_to_device(self, book_path):
        ll_folder = book_path.stem + '.sdr'
        device_ll_path = book_path.parent.joinpath(ll_folder)
        if not device_ll_path.is_dir():
            device_ll_path.mkdir()
        device_ll_path = device_ll_path.joinpath(self.ll_path.name)
        shutil.move(self.ll_path, device_ll_path)
