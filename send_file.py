#!/usr/bin/env python3

from pathlib import Path
import shutil

def send_to_device(gui, book_id, ll_file):
    device_manager = gui.device_manager
    if not device_manager.is_device_connected:
        return None
    device = device_manager.device
    if device.VENDOR_ID != [0x1949]: # Kindle device
        return None

    [has_book, _, _, _, paths] = gui.book_on_device(book_id)
    device_info = device_manager.get_current_device_information()
    device_path_prefix = device_info['info'][4]['main']['prefix'] # /Volumes/Kindle
    if has_book:
        book_path = Path(device_path_prefix)
        book_path = book_path.joinpath(next(iter(paths)))
        move_ll_to_device(book_path, ll_file)

def move_ll_to_device(book_path, ll_file):
    ll_folder = book_path.stem + '.sdr'
    ll_path = book_path.parent.joinpath(ll_folder)
    if not ll_path.is_dir():
        ll_path.mkdir()
    ll_path = ll_path.joinpath(ll_file.name)
    shutil.move(ll_file, ll_path)
