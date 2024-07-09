from calibre.customize import InterfaceActionBase

VERSION = (3, 33, 0)


class WordDumbDumb(InterfaceActionBase):
    name = "WordDumb"
    description = (
        "Create Kindle Word Wise and X-Ray file and EPUB footnotes "
        "then send to e-reader."
    )
    supported_platforms = ["linux", "osx", "windows"]
    author = "xxyzz"
    version = VERSION
    minimum_calibre_version = (7, 1, 0)
    actual_plugin = "calibre_plugins.worddumb.ui:WordDumb"

    def is_customizable(self):
        return True

    def config_widget(self):
        from .config import ConfigWidget

        return ConfigWidget()

    def save_settings(self, config_widget):
        config_widget.save_settings()

    def cli_main(self, argv):
        import argparse

        from calibre.utils.logging import Log

        from .metadata import cli_check_metadata
        from .parse_job import ParseJobData, do_job

        parser = argparse.ArgumentParser(prog="calibre-debug -r WordDumb --")
        parser.add_argument("-w", help="Create Word Wise", action="store_true")
        parser.add_argument("-x", help="Create X-Ray", action="store_true")
        parser.add_argument(
            "-v", "--version", action="version", version=".".join(map(str, VERSION))
        )
        parser.add_argument("book_path", nargs="+")
        args = parser.parse_args(argv[1:])

        log = Log()
        create_w = args.w
        create_x = args.x
        if not create_w and not create_x:
            create_w = True
            create_x = True

        for file_path in args.book_path:
            md_result = cli_check_metadata(file_path, log)
            if md_result is None:
                continue
            if create_w and not md_result.support_ww_list[0]:
                create_w = False
                log.prints(
                    Log.WARNING,
                    "Book language is not supported for selected "
                    "Word Wise gloss language",
                )
            if create_x and not md_result.support_x_ray:
                create_x = False
                log.prints(
                    Log.WARNING,
                    "X-Ray doesn't support the book language",
                )
            if not create_w and not create_x:
                continue

            notif = []
            if create_w:
                notif.append("Word Wise")
            if create_x:
                notif.append("X-Ray")
            notif_str = " and ".join(notif)
            log.prints(
                Log.INFO,
                f"Creating {notif_str} file for book {md_result.mi.get('title')}",
            )
            job_data = ParseJobData(
                book_fmt=md_result.book_fmts[0],
                book_path=file_path,
                mi=md_result.mi,
                book_lang=md_result.book_lang,
                create_ww=create_w,
                create_x=create_x,
            )
            do_job(job_data)
