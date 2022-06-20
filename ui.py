#!/usr/bin/env python3

from functools import partial

from calibre.gui2 import Dispatcher
from calibre.gui2.actions import InterfaceAction
from calibre.gui2.threaded_jobs import ThreadedJob
from PyQt5.QtGui import QIcon

from .error_dialogs import job_failed
from .metadata import check_metadata
from .parse_job import do_job
from .send_file import SendFile, device_connected
from .utils import donate


class WordDumb(InterfaceAction):
    name = "WordDumb"
    action_spec = ("WordDumb", None, "Good morning Krusty Crew!", None)
    action_type = "current"
    action_add_menu = True
    action_menu_clone_qaction = "Create Word Wise and X-Ray"

    def genesis(self):
        icon = get_icons("starfish.svg")
        self.qaction.setIcon(icon)
        self.menu = self.qaction.menu()

        self.qaction.triggered.connect(partial(run, self.gui, True, True))
        self.create_menu_action(
            self.menu,
            "Word Wise",
            "Create Word Wise",
            triggered=partial(run, self.gui, True, False),
        )
        self.create_menu_action(
            self.menu,
            "X-Ray",
            "Create X-Ray",
            triggered=partial(run, self.gui, False, True),
        )

        self.menu.addSeparator()
        self.create_menu_action(
            self.menu,
            "Preferences",
            "Preferences",
            icon=QIcon(I("config.png")),
            triggered=self.config,
        )
        self.menu.addSeparator()
        self.create_menu_action(
            self.menu,
            "Donate",
            "Donate",
            icon=QIcon(I("donate.png")),
            description="I need about tree-fiddy.",
            triggered=donate,
        )
        self.qaction.setMenu(self.menu)

    def config(self):
        self.interface_action_base_plugin.do_user_config(self.gui)


def run(gui, create_ww, create_x):
    for book_id, book_fmts, book_paths, mi, lang in filter(
        None,
        [
            check_metadata(gui.current_db.new_api, book_id)
            for book_id in map(
                gui.library_view.model().id,
                gui.library_view.selectionModel().selectedRows(),
            )
        ],
    ):
        for book_fmt, book_path in zip(book_fmts, book_paths):
            if book_fmt == "EPUB" or lang["wiki"] != "en":
                create_ww = False
            if not create_ww and not create_x:
                continue
            title = (
                f'{mi.get("title")}({book_fmt})'
                if len(book_fmts) > 1
                else mi.get("title")
            )
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
                ((book_id, book_fmt, book_path, mi, lang), create_ww, create_x),
                {},
                Dispatcher(
                    partial(done, gui=gui, notif=f"{notif} generated for {title}")
                ),
                killable=False,
            )
            gui.job_manager.run_threaded_job(job)


def done(job, gui=None, notif=None):
    if job_failed(job, gui):
        return
    book_id, _, _, mi, update_asin, book_fmt, _ = job.result
    if update_asin:
        gui.current_db.new_api.set_metadata(book_id, mi)

    if package_name := device_connected(gui, book_fmt):
        SendFile(gui, job.result, package_name, notif).send_files(None)
    else:
        gui.status_bar.show_message(notif)
