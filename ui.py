#!/usr/bin/env python3

from functools import partial

from calibre.gui2.actions import InterfaceAction

from .main import ParseBook
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
            self.menu, "Preferences", "Preferences", triggered=self.config
        )
        self.menu.addSeparator()
        self.create_menu_action(
            self.menu,
            "Donate",
            "Donate",
            description="I need about tree-fiddy.",
            triggered=donate,
        )
        self.qaction.setMenu(self.menu)

    def config(self):
        self.interface_action_base_plugin.do_user_config(self.gui)


def run(gui, create_ww, create_x):
    ParseBook(gui).parse(create_ww, create_x)
