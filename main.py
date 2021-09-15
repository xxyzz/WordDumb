#!/usr/bin/env python3

from functools import partial

from calibre.gui2 import Dispatcher
from calibre.gui2.dialogs.message_box import JobError
from calibre.gui2.threaded_jobs import ThreadedJob
from calibre_plugins.worddumb.metadata import check_metadata
from calibre_plugins.worddumb.parse_job import do_job
from calibre_plugins.worddumb.send_file import SendFile, kindle_connected
from calibre_plugins.worddumb.unzip import load_json_or_pickle


class ParseBook:
    def __init__(self, gui):
        self.gui = gui
        self.languages = load_json_or_pickle('data/languages.json', True)

    def parse(self, create_ww=True, create_x=True):
        # get currently selected books
        rows = self.gui.library_view.selectionModel().selectedRows()
        if not rows or len(rows) == 0:
            return
        ids = map(self.gui.library_view.model().id, rows)
        show_job_pointer = False
        for data in filter(None, [check_metadata(
                self.gui.current_db.new_api,
                book_id, self.languages) for book_id in ids]):
            show_job_pointer = True
            if data[-1]['wiki'] != 'en':
                create_ww = False
            title = data[-2].get('title')
            notif = []
            if create_ww:
                notif.append('Word Wise')
            if create_x:
                notif.append('X-Ray')
            notif = ' and '.join(notif)
            job = ThreadedJob(
                "WordDumb's dumb job", f'Generating {notif} for {title}',
                do_job, (data, create_ww, create_x), {},
                Dispatcher(partial(self.done,
                                   notif=f'{notif} generated for {title}')))
            self.gui.job_manager.run_threaded_job(job)

        if show_job_pointer:
            self.gui.jobs_pointer.start()

    def done(self, job, notif=None):
        if self.job_failed(job):
            return

        book_id, _, _, mi, update_asin = job.result
        if update_asin:
            self.gui.current_db.new_api.set_metadata(book_id, mi)
        # send files to device
        if kindle_connected(self.gui):
            SendFile(self.gui, job.result, notif).send_files(None)
        else:
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
            elif 'ConnectionError' in job.details \
                 and 'wikipedia.org' in job.details:
                self.censorship_error('https://wikipedia.org', job.details)
            elif 'CalledProcessError' in job.details:
                self.subprocess_error(job)
            elif 'JointMOBI' in job.details:
                url = 'https://github.com/kevinhendricks/KindleUnpack'
                self.error_dialog(
                    'Joint MOBI',
                    f'''
                    Please use <a href='{url}'>KindleUnpack</a>'s '-s' option
                    to split the book.
                    ''', job.details)
            else:
                self.gui.job_exception(job, dialog_title='Eh!')
            return True
        return False

    def subprocess_error(self, job):
        exception = job.exception.stderr.decode('utf-8')
        if 'C++ Build Tools' in exception:
            self.error_dialog(
                'Seriously, 32bit?!',
                '''
                Install <a href='https://calibre-ebook.com/download_windows64'>
                64bit calibre</a>, 32bit calibre is not supported.
                ''',
                job.details + exception)
        elif 'No module named pip' in exception:
            self.error_dialog(
                'Missing pip module',
                '''
                Run the command "sudo apt install python3-pip" to install
                pip module if you are using Debian or Ubuntu based distro.
                <br><br>
                If you still have this error, make sure you installed calibre
                with the <a href="https://calibre-ebook.com/download_linux">
                binary install command</a> but not from Flathub or Snap Store.
                ''',
                job.details + exception)
        elif 'Timeout' in exception and 'github.com' in exception:
            self.censorship_error(
                'https://raw.githubusercontent.com', job.details + exception)
        else:
            dialog = JobError(self.gui)
            dialog.show_error(
                'Weak',
                'subprocess.run() failed',
                det_msg=job.details + exception)

    def error_dialog(self, title, message, error):
        dialog = JobError(self.gui)
        dialog.msg_label.setOpenExternalLinks(True)
        dialog.show_error(title, message, det_msg=error)

    def censorship_error(self, url, error):
        self.error_dialog(
            'It was a pleasure to burn',
            f'''
            Is <a href='{url}'>{url}</a> blocked in your country?
            You might need tools to bypass internet censorship.
            ''', error)
