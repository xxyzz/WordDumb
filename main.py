#!/usr/bin/env python3

from functools import partial

from calibre.gui2 import Dispatcher
from calibre.gui2.threaded_jobs import ThreadedJob
from calibre_plugins.worddumb.metadata import check_metadata
from calibre_plugins.worddumb.parse_job import do_job
from calibre_plugins.worddumb.send_file import kindle_connected, send


class ParseBook():
    def __init__(self, gui):
        self.gui = gui

    def parse(self):
        # get currently selected books
        rows = self.gui.library_view.selectionModel().selectedRows()
        if not rows or len(rows) == 0:
            return
        ids = list(map(self.gui.library_view.model().id, rows))
        if len(ids) == 0:
            return

        books = 0
        for book_id in ids:
            if (data := check_metadata(self.gui.current_db.new_api,
                                       book_id)) is None:
                continue
            title = data[-1].get('title')
            books += 1
            desc = f'Generating Word Wise for {title}'
            job = ThreadedJob(
                "WordDumb's dumb job", desc, do_job, (data, ), {},
                Dispatcher(partial(self.done, data=data, title=title)))
            self.gui.job_manager.run_threaded_job(job)

        if books > 0:
            self.gui.jobs_pointer.start()
            self.gui.status_bar.show_message(
                f'Generating Word Wise for {books} books')

    def done(self, job, data=None, title=None):
        if job.failed:
            self.gui.job_exception(job)
            return

        # send files to device
        if kindle_connected(self.gui):
            send(self.gui, data)

        self.gui.status_bar.show_message(f'Word Wise generated for {title}')
