#!/usr/bin/env python3

from functools import partial

from calibre.gui2 import Dispatcher
from calibre.gui2.dialogs.message_box import JobError
from calibre.gui2.threaded_jobs import ThreadedJob
from calibre_plugins.worddumb.metadata import check_metadata
from calibre_plugins.worddumb.parse_job import do_job
from calibre_plugins.worddumb.send_file import SendFile, kindle_connected


class ParseBook:
    def __init__(self, gui):
        self.gui = gui
        self.metadata_list = []

    def parse(self, create_ww=True, create_x=True):
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

        if len(self.metadata_list) == 0:
            return

        for data in self.metadata_list:
            if data[-1]['wiki'] != 'en':
                create_ww = False
            title = data[-3].get('title')
            notif = []
            if create_ww:
                notif.append('Word Wise')
            if create_x:
                notif.append('X-Ray')
            notif = ' and '.join(notif)

            job = ThreadedJob(
                "WordDumb's dumb job", f'Generating {notif} for {title}',
                do_job, (data, create_ww, create_x), {},
                Dispatcher(partial(self.done, data=data,
                                   notif=f'{notif} generated for {title}')))
            self.gui.job_manager.run_threaded_job(job)

        self.gui.jobs_pointer.start()

    def done(self, job, data=None, notif=None):
        if self.job_failed(job):
            return

        # send files to device
        if kindle_connected(self.gui):
            SendFile(self.gui, data).send_files(None)

        self.gui.status_bar.show_message(notif)

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
            elif 'ConnectionError' in job.details \
                 and 'wikipedia.org' in job.details:
                self.censorship_error(
                    'https://wikipedia.org',
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
                    Please use <a href='{url}'>KindleUnpack</a>'s '-s' option
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
