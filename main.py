#!/usr/bin/env python3

from functools import partial

from calibre.gui2 import Dispatcher
from calibre.gui2.threaded_jobs import ThreadedJob

from .metadata import check_metadata
from .parse_job import do_job
from .send_file import SendFile, device_connected
from .utils import load_json_or_pickle, get_plugin_path
from .error_dialogs import job_failed


class ParseBook:
    def __init__(self, gui):
        self.gui = gui
        self.languages = load_json_or_pickle(get_plugin_path(), "data/languages.json")
        self.github_url = "https://github.com/xxyzz/WordDumb"

    def parse(self, create_ww=True, create_x=True):
        # get currently selected books
        rows = self.gui.library_view.selectionModel().selectedRows()
        if not rows or len(rows) == 0:
            return
        ids = map(self.gui.library_view.model().id, rows)
        show_job_pointer = False
        for data in filter(
            None,
            [
                check_metadata(self.gui.current_db.new_api, book_id, self.languages)
                for book_id in ids
            ],
        ):
            _, book_fmt, _, mi, lang = data
            if book_fmt == "EPUB":
                create_ww = False
            if not create_ww and not create_x:
                continue
            show_job_pointer = True
            if lang["wiki"] != "en":
                create_ww = False
            title = mi.get("title")
            notif = []
            if create_ww:
                notif.append("Word Wise")
            if create_x:
                notif.append("X-Ray")
            notif = " and ".join(notif)
            job = ThreadedJob(
                "WordDumb's dumb job",
                f"Generating {notif} for {title}",
                do_job,
                (data, create_ww, create_x),
                {},
                Dispatcher(partial(self.done, notif=f"{notif} generated for {title}")),
                killable=False,
            )
            self.gui.job_manager.run_threaded_job(job)

        if show_job_pointer:
            self.gui.jobs_pointer.start()

    def done(self, job, notif=None):
        if job_failed(job, self.gui):
            return

        book_id, _, _, mi, update_asin, book_fmt, _ = job.result
        if update_asin:
            self.gui.current_db.new_api.set_metadata(book_id, mi)

        # send files to device
        if connected := device_connected(self.gui, book_fmt):
            SendFile(self.gui, job.result, connected == "android", notif).send_files(
                None
            )
        else:
            self.gui.status_bar.show_message(notif)
