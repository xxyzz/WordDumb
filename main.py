#!/usr/bin/env python3

from functools import partial

from calibre.gui2 import Dispatcher
from calibre.gui2.dialogs.message_box import JobError
from calibre.gui2.threaded_jobs import ThreadedJob
from calibre_plugins.worddumb.metadata import check_metadata
from calibre_plugins.worddumb.parse_job import do_job
from calibre_plugins.worddumb.send_file import SendFile, kindle_connected
from calibre_plugins.worddumb.unzip import install_libs


class ParseBook():
    def __init__(self, gui):
        self.gui = gui
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

        if books == 1:
            self.create_jobs(install=True)
        else:
            job = ThreadedJob(
                "WordDumb's dumb job", 'Install dependencies',
                install_libs, (), {}, Dispatcher(self.create_jobs))
            self.gui.job_manager.run_threaded_job(job)

        self.gui.jobs_pointer.start()
        self.gui.status_bar.show_message(
            f'Generating Word Wise for {books} '
            f'{"books" if books > 1 else "book"}')

    def create_jobs(self, job=None, install=False):
        if self.job_failed(job):
            return

        for data in self.metadata_list:
            title = data[-1].get('title')
            job = ThreadedJob(
                "WordDumb's dumb job", f'Generating Word Wise for {title}',
                do_job, (data, install), {},
                Dispatcher(partial(self.done, data=data, title=title)))
            self.gui.job_manager.run_threaded_job(job)

    def done(self, job, data=None, title=None):
        if self.job_failed(job):
            return

        # send files to device
        if kindle_connected(self.gui):
            sf = SendFile(self.gui, data)
            sf.send_files(None)

        self.gui.status_bar.show_message(f'Word Wise generated for {title}')

    def job_failed(self, job):
        if job and job.failed:
            if 'FileNotFoundError' in job.details and \
               'subprocess.py' in job.details:
                self.error_dialog(
                    "Can't find Python",
                    '''
                    Please read the <a
                    href='https://github.com/xxyzz/WordDumb#how-to-use'>document</a>
                    of how to install Python.
                    ''', job.details)
            elif 'FileNotFoundError' in job.details and '.zip' in job.details:
                self.censorship_error(
                    'https://raw.githubusercontent.com',
                    'nltk.download() failed', job.details)
            elif 'URLError' in job.details and 'wikipedia' in job.details:
                self.censorship_error(
                    'https://en.wikipedia.org',
                    'It was a pleasure to burn', job.details)
            elif 'CalledProcessError' in job.details:
                dialog = JobError(self.gui)
                dialog.show_error(
                    'subprocess.run failed',
                    job.exception.stderr.decode('utf-8'),
                    det_msg=job.details)
            elif 'JointMOBI' in job.details:
                url = 'https://github.com/kevinhendricks/KindleUnpack'
                self.error_dialog(
                    'Joint MOBI',
                    f'''
                    Please use <a href='{url}'>KindleUnpack</a>
                    to split the book.
                    ''', job.details)
            else:
                self.gui.job_exception(job, dialog_title='Dumb error')
            return True
        return False

    def error_dialog(self, title, message, error):
        dialog = JobError(self.gui)
        dialog.msg_label.setOpenExternalLinks(True)
        dialog.show_error(title, message, det_msg=error)

    def censorship_error(self, url, title, error):
        self.error_dialog(
            title,
            f'''
            Is <a href='{url}'>{url}</a> blocked in your country?
            You might need tools to bypass internet censorship.
            ''', error)
