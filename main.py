#!/usr/bin/env python3

from functools import partial
from pathlib import Path

from calibre.gui2 import Dispatcher
from calibre.gui2.dialogs.message_box import JobError
from calibre.gui2.threaded_jobs import ThreadedJob
from calibre.utils.config import config_dir

from .metadata import check_metadata
from .parse_job import do_job
from .send_file import SendFile, device_connected
from .utils import load_json_or_pickle


class ParseBook:
    def __init__(self, gui):
        self.gui = gui
        plugin_path = Path(config_dir).joinpath("plugins/WordDumb.zip")
        self.languages = load_json_or_pickle(plugin_path, "data/languages.json")
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
        if self.job_failed(job):
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

    def job_failed(self, job):
        if job and job.failed:
            if "FileNotFoundError" in job.details and "subprocess.py" in job.details:
                self.error_dialog(
                    "We want... a shrubbery!",
                    f"Please read the friendly <a href='{self.github_url}#how-to-use'>manual</a> of how to install Python.",
                    job.details,
                )
            elif "CalledProcessError" in job.details:
                self.subprocess_error(job)
            elif "JointMOBI" in job.details:
                self.error_dialog(
                    "Joint MOBI",
                    "Please use <a href='https://github.com/kevinhendricks/KindleUnpack'>KindleUnpack</a>'s '-s' option to split the book.",
                    job.details,
                )
            elif "DLL load failed" in job.details:
                self.error_dialog(
                    "Welcome to DLL Hell",
                    "Install <a href='https://support.microsoft.com/en-us/help/2977003/the-latest-supported-visual-c-downloads'>Visual C++ 2019 redistributable</a>",
                    job.datails,
                )
            elif "32BIT_CALIBRE" in job.details or "32BIT_PYTHON" in job.details:
                program = "calibre" if "32BIT_CALIBRE" in job.details else "Python"
                self.error_dialog(
                    "The wrist game!",
                    f"You're using 32bit {program}, please install the 64bit version.",
                    job.details,
                )
            else:
                self.check_network_error(job.details)
            return True
        return False

    def subprocess_error(self, job):
        exception = job.exception.stderr
        if "No module named pip" in exception:
            self.error_dialog(
                "Hello, my name is Philip, but everyone calls me Pip, because they hate me.",
                """
                Run the command "sudo apt install python3-pip" to install
                pip module if you are using Debian based distro.
                <br><br>
                If you still have this error, make sure you installed calibre
                with the <a href="https://calibre-ebook.com/download_linux">
                binary install command</a> but not from Flathub or Snap Store.
                """,
                job.details + exception,
            )
        else:
            self.check_network_error(job.details + exception)

    def error_dialog(self, title, message, error):
        dialog = JobError(self.gui)
        dialog.msg_label.setOpenExternalLinks(True)
        dialog.show_error(title, message, det_msg=error)

    def check_network_error(self, error):
        if "check_hostname requires server_hostname" in error:
            self.error_dialog(
                "Cyberspace is not a place beyond the rule of law",
                """
                Check your proxy configuration environment variables,
                they should be set by these commands:<br>
                <code>$ export HTTP_PROXY="http://host:port"</code><br>
                <code>$ export HTTPS_PROXY="http://host:port"</code><br>
                <br>
                If you're allergic to terminal, close your proxy and use a VPN.
                """,
                error,
            )
        elif "ConnectionError" in error or "Timeout" in error:
            self.error_dialog(
                "It was a pleasure to burn",
                "Is GitHub/Wikipedia/Fandom blocked by your ISP? You might need tools to bypass internet censorship.",
                error,
            )
        else:
            self.error_dialog(
                "Tonnerre de Brest!",
                f'An error occurred, please copy error message then report bug at <a href="{self.github_url}/issues">GitHub</a>.',
                error,
            )
