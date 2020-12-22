#!/usr/bin/env python3
import re

from calibre.gui2 import Dispatcher, error_dialog, warning_dialog
from calibre.gui2.threaded_jobs import ThreadedJob
from calibre_plugins.worddumb.metadata import check_metadata
from calibre_plugins.worddumb.parse_job import do_job
from calibre_plugins.worddumb.send_file import send


class ParseBook():
    def __init__(self, gui, plugin_path):
        self.gui = gui
        self.books = []
        self.plugin_path = plugin_path

    def parse(self):
        # get currently selected books
        rows = self.gui.library_view.selectionModel().selectedRows()
        if not rows or len(rows) == 0:
            return
        self.ids = list(map(self.gui.library_view.model().id, rows))
        if len(self.ids) == 0:
            return

        job = ThreadedJob('Generating Word Wise', 'Generating Word Wise',
                          do_job, (self.gui, self.ids, self.plugin_path), {},
                          Dispatcher(self.done))

        self.gui.job_manager.run_threaded_job(job)
        self.gui.status_bar.show_message("Generating Word Wise")

    def done(self, job):
        if job.result:
            # Problems during word wise generation
            # jobs.results is a list - the first entry is the intended
            # title for the dialog
            # Subsequent strings are error messages
            dialog_title = job.result.pop(0)
            if re.search('warning', job.result[0].lower()):
                msg = "Word Wise generation complete, with warnings."
                warning_dialog(self.gui, dialog_title, msg,
                               det_msg='\n'.join(job.result), show=True)
            else:
                job.result.append("Word Wise generation terminated.")
                error_dialog(self.gui, dialog_title,
                             '\n'.join(job.result), show=True)
                return
        if job.failed:
            self.gui.job_exception(job)
            return

        # send files to device
        for book_id in self.ids:
            data = check_metadata(self.gui.current_db.new_api,
                                  book_id, False)
            if data is None:
                continue
            send(self.gui, (book_id, ) + data)

        self.gui.status_bar.show_message("Word Wise generated.")
