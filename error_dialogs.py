from typing import TYPE_CHECKING, Any

GITHUB_URL = "https://github.com/xxyzz/WordDumb"
INSTALL_PYTHON_DOC = (
    "https://xxyzz.github.io/WordDumb/installation.html#install-python-3-11-and-pip"
)

load_translations()  # type: ignore
if TYPE_CHECKING:
    _: Any


def error_dialog(title: str, message: str, error: str, parent: Any) -> None:
    from calibre.gui2.dialogs.message_box import JobError

    dialog = JobError(parent)
    dialog.msg_label.setOpenExternalLinks(True)
    dialog.show_error(title, message, det_msg=error)


def job_failed(job: Any, parent: Any = None) -> bool:
    if job and job.failed:
        if "PythonNotFound" in job.details:
            error_dialog(
                "We want... a shrubbery!",
                _(
                    "Can't find Python. Please read the <a href='{}'>document</a> "
                    "of how to install Python."
                ).format(INSTALL_PYTHON_DOC),
                job.details,
                parent,
            )
        elif "OutdatedPython" in job.details:
            error_dialog(
                "Outdated Python",
                _(
                    "Your Python version is too old, please update to a newer version "
                    "and read the <a href='{}'>document</a> for more information."
                ).format(INSTALL_PYTHON_DOC),
                job.details,
                parent,
            )
        elif "UnsupportedPython" in job.details:
            error_dialog(
                "Unsupported Python",
                _(
                    "Please install an older version and put the Python binary file "
                    "path in the plugin's preferences window."
                ),
                job.details,
                parent,
            )
        elif "CalledProcessError" in job.details:
            subprocess_error(job, parent)
        elif "ModuleNotFoundError" in job.details:
            module_not_found_error(job.details, parent)
        elif "JointMOBI" in job.details:
            error_dialog(
                "Joint MOBI",
                _(
                    "Please use "
                    "<a href='https://github.com/kevinhendricks/KindleUnpack'>"
                    "KindleUnpack</a>'s '-s' option to split the book."
                ),
                job.details,
                parent,
            )
        elif "DLL load failed" in job.details:
            error_dialog(
                "Welcome to DLL Hell",
                _(
                    "Install <a href='https://support.microsoft.com/en-us/help/2977003/"
                    "the-latest-supported-visual-c-downloads'>"
                    "Visual C++ 2019 Redistributable</a>"
                ),
                job.datails,
                parent,
            )
        elif "DownloadFiled" in job.details:
            error_dialog(
                _("Download failed"),
                _("Download failed, please retry."),
                job.details,
                parent,
            )
        else:
            check_network_error(job.details, parent)
        return True
    return False


def subprocess_error(job: Any, parent: Any) -> None:
    exception = job.exception.stderr.decode("utf-8", "ignore")
    if "No module named pip" in exception:
        error_dialog(
            "Hello, my name is Philip, but everyone calls me Pip, "
            "because they hate me.",
            _(
                "<p>Please read the friendly <a href='{}'>manual</a> of how to install "
                "pip.</p><p>If you still have this error, make sure you installed "
                "calibre with the <a href='https://calibre-ebook.com/download_linux'>"
                "binary install command</a> but not from Flathub or Snap Store.</p>"
            ).format(INSTALL_PYTHON_DOC),
            job.details + exception,
            parent,
        )
    elif "ModuleNotFoundError" in exception:
        module_not_found_error(job.details + exception, parent)
    else:
        check_network_error(job.details + exception, parent)


def module_not_found_error(error: str, parent: Any) -> None:
    from .utils import get_plugin_path

    error_dialog(
        "Welcome to dependency hell",
        _("Please delete the '{}/worddumb-libs-py*' folder then try again.").format(
            str(get_plugin_path().parent)
        ),
        error,
        parent,
    )


def check_network_error(error: str, parent: Any) -> None:
    CALIBRE_PROXY_FAQ = (
        "https://manual.calibre-ebook.com/faq.html"
        "#how-do-i-get-calibre-to-use-my-http-proxy"
    )

    if "check_hostname requires server_hostname" in error or "SSLError" in error:
        error_dialog(
            "Cyberspace is not a place beyond the rule of law",
            _(
                "<p>Read <a href='{}'>calibre FAQ</a> first then check your proxy "
                "environment variables, they should be set by these commands:</p>"
                "<p><code>$ export HTTP_PROXY='http://host:port'</code></p>"
                "<p><code>$ export HTTPS_PROXY='http://host:port'</code></p>"
                "<p>If you're allergic to terminal, close your proxy and use a VPN.</p>"
            ).format(CALIBRE_PROXY_FAQ),
            error,
            parent,
        )
    elif "ConnectionError" in error or "Timeout" in error:
        error_dialog(
            "It was a pleasure to burn",
            _(
                "Is GitHub or Wikipedia blocked by your ISP? You might need to "
                "bypass Internet censorship. Please read <a href='{}'>calibre FAQ</a>."
            ).format(CALIBRE_PROXY_FAQ),
            error,
            parent,
        )
    else:
        error_dialog(
            "Tonnerre de Brest!",
            _(
                "An error occurred, please copy error message then report bug at "
                '<a href="{}/issues">GitHub</a>.'
            ).format(GITHUB_URL),
            error,
            parent,
        )


def warning_dialog(title: str, message: str, parent: Any = None) -> None:
    from calibre.gui2.dialogs.message_box import MessageBox

    MessageBox(MessageBox.WARNING, title, message, parent=parent).exec()


def unsupported_language_dialog(book_title: str) -> None:
    warning_dialog(
        _("Unsupported language"),
        _("The language of the book <i>{}</i> is not supported.").format(book_title),
    )


def unsupported_format_dialog() -> None:
    warning_dialog(_("Unsupported book format"), _("The book format is not supported."))


def device_not_found_dialog(parent: Any) -> None:
    warning_dialog(
        _("Device not found"),
        _(
            "Definition data will be added when Kindle or Android(requires adb) "
            "device is connected."
        ),
        parent,
    )


def ww_db_not_found_dialog(parent: Any) -> None:
    warning_dialog(
        _("Word Wise database not found"),
        _(
            "Can't find Word Wise database on your device, open a Word Wise enabled "
            "book to download this file."
        ),
        parent,
    )


def kindle_epub_dialog(parent: Any) -> None:
    warning_dialog(
        _("Kindle doesn't support EPUB"),
        _(
            "Kindle doesn't support EPUB format natively, please convert the book "
            "format then try again."
        ),
        parent,
    )


def unsupported_ww_lang_dialog() -> None:
    warning_dialog(
        _("Unsupported language"),
        _("Book language is not supported for the selected Word Wise gloss language."),
    )


def change_kindle_ww_lang_dialog(
    checked: bool, parent: Any = None, prefs: Any = None
) -> None:
    if checked and prefs["show_change_kindle_ww_lang_warning"]:
        warning_dialog(
            "",
            _(
                "Word Wise language must be set to Chinese on Kindle to display the "
                'correct definitions when the "Use Wiktionary definition" option is '
                "enabled."
            ),
            parent,
        )
        prefs["show_change_kindle_ww_lang_warning"] = False
