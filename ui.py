import json
from functools import partial
from pathlib import Path
from typing import TYPE_CHECKING, Any, Iterator

from calibre.gui2 import Dispatcher
from calibre.gui2.actions import InterfaceAction
from calibre.gui2.threaded_jobs import ThreadedJob
from PyQt6.QtGui import QIcon

from .custom_x_ray import CustomXRayDialog
from .error_dialogs import job_failed, unsupported_ww_lang_dialog
from .metadata import MetaDataResult, check_metadata
from .parse_job import ParseJobData, do_job
from .send_file import SendFile, device_connected
from .utils import donate, get_book_settings_path

load_translations()  # type: ignore
if TYPE_CHECKING:
    _: Any


class WordDumb(InterfaceAction):
    name = "WordDumb"
    action_spec = ("WordDumb", None, "Good morning Krusty Crew!", None)
    action_type = "current"
    action_add_menu = True
    action_menu_clone_qaction = _("Create Word Wise and X-Ray")

    def genesis(self):
        self.qaction.setIcon(get_icons("starfish.svg", "WordDumb"))  # type: ignore
        self.menu = self.qaction.menu()

        self.qaction.triggered.connect(partial(run, self.gui, True, True))
        self.create_menu_action(
            self.menu,
            "Word Wise",
            _("Create Word Wise"),
            triggered=partial(run, self.gui, True, False),
        )
        self.create_menu_action(
            self.menu,
            "X-Ray",
            _("Create X-Ray"),
            triggered=partial(run, self.gui, False, True),
        )

        self.menu.addSeparator()
        self.create_menu_action(
            self.menu,
            "Customize X-Ray",
            _("Customize X-Ray"),
            icon=QIcon.ic("polish.png"),
            triggered=self.open_custom_x_ray_dialog,
        )
        self.create_menu_action(
            self.menu,
            "Book settings",
            _("Book settings"),
            icon=QIcon.ic("polish.png"),
            triggered=partial(open_book_settings_dialog, self.gui),
        )
        self.create_menu_action(
            self.menu,
            "Preferences",
            _("Preferences"),
            icon=QIcon.ic("config.png"),
            triggered=self.config,
        )

        self.menu.addSeparator()
        self.create_menu_action(
            self.menu,
            "Donate",
            _("Donate"),
            icon=QIcon.ic("donate.png"),
            description="I need about tree-fiddy.",
            triggered=donate,
        )
        self.qaction.setMenu(self.menu)

    def config(self):
        self.interface_action_base_plugin.do_user_config(self.gui)

    def open_custom_x_ray_dialog(self) -> None:
        for md_result in get_metadata_of_selected_books(self.gui, False):
            custom_x_dlg = CustomXRayDialog(
                md_result.book_paths[0], md_result.mi.get("title"), self.gui
            )
            if custom_x_dlg.exec():
                custom_x_dlg.x_ray_model.save_data()


def get_metadata_of_selected_books(
    gui: Any, choose_format: bool
) -> Iterator[MetaDataResult]:
    return filter(
        None,
        [
            check_metadata(gui, book_id, choose_format)
            for book_id in map(
                gui.library_view.model().id,
                gui.library_view.selectionModel().selectedRows(),
            )
        ],
    )


def run(gui: Any, create_ww: bool, create_x: bool) -> None:
    from .config import prefs

    if not create_ww and not create_x:
        return
    for md_result in get_metadata_of_selected_books(gui, True):
        for book_fmt, book_path, support_ww in zip(
            md_result.book_fmts, md_result.book_paths, md_result.support_ww_list
        ):
            if create_ww and not support_ww:
                create_ww = False
                unsupported_ww_lang_dialog()
            if create_x and not md_result.support_x_ray:
                create_x = False
            if not create_ww and not create_x:
                continue

            title = (
                f"{md_result.mi.get('title')}({md_result.book_fmt})"
                if len(md_result.book_fmts) > 1
                else md_result.mi.get("title")
            )
            notif = []
            book_settings = {}
            if create_ww:
                notif.append(_("Word Wise"))
            if create_x:
                notif.append("X-Ray")
                config_path = get_book_settings_path(Path(book_path))
                if not config_path.is_file() and not prefs["custom_entity_only"]:
                    open_book_settings_dialog(gui)
                if config_path.is_file():
                    with config_path.open() as f:
                        book_settings = json.load(f)

            notif = _(" and ").join(notif)
            job_data = ParseJobData(
                book_id=md_result.book_id,
                book_path=book_path,
                mi=md_result.mi,
                book_fmt=book_fmt,
                book_lang=md_result.book_lang,
                create_ww=create_ww,
                create_x=create_x,
                book_settings=book_settings,
            )
            job = ThreadedJob(
                "WordDumb's dumb job",
                _("Generating {} for {}").format(notif, title),
                do_job,
                (job_data,),
                {},
                Dispatcher(
                    partial(
                        done,
                        gui=gui,
                        notif=_("{} generated for {}").format(notif, title),
                    )
                ),
                killable=False,
            )
            gui.job_manager.run_threaded_job(job)


def done(job, gui=None, notif=None):
    if job_failed(job, gui):
        return

    if device_connected(gui, job.result.book_fmt):
        SendFile(gui, job.result, notif).send_files(None)
    else:
        gui.status_bar.show_message(notif)


def open_book_settings_dialog(gui):
    from pathlib import Path

    from .config import BookSettingsDialog

    for md_result in get_metadata_of_selected_books(gui, False):
        settings_dlg = BookSettingsDialog(
            gui, get_book_settings_path(Path(md_result.book_paths[0]))
        )
        if settings_dlg.exec():
            settings_dlg.save()
