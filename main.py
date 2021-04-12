#!/usr/bin/env python3

from functools import partial

from calibre.gui2 import Dispatcher
from calibre.gui2.threaded_jobs import ThreadedJob
from calibre_plugins.worddumb.metadata import check_metadata
from calibre_plugins.worddumb.parse_job import do_job
from calibre_plugins.worddumb.send_file import kindle_connected, send
from calibre_plugins.worddumb.unzip import install_libs, load_json


class ParseBook():
    def __init__(self, gui):
        self.gui = gui
        self.lemmas = None
        self.metadata_list = []

    def parse(self):
        # get currently selected books
        rows = self.gui.library_view.selectionModel().selectedRows()
        if not rows or len(rows) == 0:
            return
        ids = list(map(self.gui.library_view.model().id, rows))
        if len(ids) == 0:
            return

        for book_id in ids:
            if (data := check_metadata(self.gui.current_db.new_api,
                                       book_id)) is None:
                continue
            self.metadata_list.append(data)

        if (books := len(self.metadata_list)) == 0:
            return

        self.lemmas = load_json('data/lemmas.json')
        if books == 1:
            self.create_jobs(install=True)
        else:
            job = ThreadedJob(
                "WordDumb's dumb job", 'Install dependencies',
                install_libs, (), {}, Dispatcher(self.create_jobs))
            self.gui.job_manager.run_threaded_job(job)

        self.gui.jobs_pointer.start()
        self.gui.status_bar.show_message(
            f'Generating Word Wise for {books} books')

    def create_jobs(self, job=None, install=False):
        if job and job.failed:
            self.gui.job_exception(job)
            return

        for data in self.metadata_list:
            title = data[-1].get('title')
            job = ThreadedJob(
                "WordDumb's dumb job", f'Generating Word Wise for {title}',
                do_job, (data, self.lemmas, install), {},
                Dispatcher(partial(self.done, data=data, title=title)))
            self.gui.job_manager.run_threaded_job(job)

    def done(self, job, data=None, title=None):
        if job.failed:
            self.gui.job_exception(job)
            return

        # send files to device
        if kindle_connected(self.gui):
            send(self.gui, data)

        self.gui.status_bar.show_message(f'Word Wise generated for {title}')
