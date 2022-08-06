#!/usr/bin/env python3

GITHUB_URL = "https://github.com/xxyzz/WordDumb"


def error_dialog(title, message, error, parent):
    from calibre.gui2.dialogs.message_box import JobError

    dialog = JobError(parent)
    dialog.msg_label.setOpenExternalLinks(True)
    dialog.show_error(title, message, det_msg=error)


def job_failed(job, parent=None):
    if job and job.failed:
        if "FileNotFoundError" in job.details and "subprocess.py" in job.details:
            error_dialog(
                "We want... a shrubbery!",
                f"Please read the friendly <a href='{GITHUB_URL}#how-to-use'>manual</a> of how to install Python.",
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
                "Please use <a href='https://github.com/kevinhendricks/KindleUnpack'>KindleUnpack</a>'s '-s' option to split the book.",
                job.details,
                parent,
            )
        elif "DLL load failed" in job.details:
            error_dialog(
                "Welcome to DLL Hell",
                "Install <a href='https://support.microsoft.com/en-us/help/2977003/the-latest-supported-visual-c-downloads'>Visual C++ 2019 redistributable</a>",
                job.datails,
                parent,
            )
        elif "32BIT_PYTHON" in job.details:
            error_dialog(
                "The wrist game!",
                "You're using 32bit Python, please install the 64bit version.",
                job.details,
                parent,
            )
        else:
            check_network_error(job.details, parent)
        return True
    return False


def subprocess_error(job, parent):
    exception = job.exception.stderr
    if "No module named pip" in exception:
        error_dialog(
            "Hello, my name is Philip, but everyone calls me Pip, because they hate me.",
            f"""
            Please read the friendly <a href='{GITHUB_URL}#how-to-use'>manual</a> of how to install pip.
            <br><br>
            If you still have this error, make sure you installed calibre
            with the <a href="https://calibre-ebook.com/download_linux">
            binary install command</a> but not from Flathub or Snap Store.
            """,
            job.details + exception,
            parent,
        )
    elif "ModuleNotFoundError" in exception:
        module_not_found_error(job.details + exception, parent)
    else:
        check_network_error(job.details + exception, parent)


def module_not_found_error(error, parent):
    import re

    broken_pkg = re.search(r"No module named '(.*)'", error)
    broken_pkg = broken_pkg.group(1).split(".")[0]

    error_dialog(
        "Welcome to dependency hell",
        f"Please delete the '{broken_pkg}*' folder from the 'worddumb-libs-py*' folder and try again.",
        error,
        parent,
    )


def check_network_error(error, parent):
    CALIBRE_PROXY_FAQ = "https://manual.calibre-ebook.com/faq.html#how-do-i-get-calibre-to-use-my-http-proxy"

    if "check_hostname requires server_hostname" in error:
        error_dialog(
            "Cyberspace is not a place beyond the rule of law",
            f"""
            Read <a href="{CALIBRE_PROXY_FAQ}">calibre FAQ</a> first then
            check your proxy environment variables,
            they should be set by these commands:<br>
            <code>$ export HTTP_PROXY="http://host:port"</code><br>
            <code>$ export HTTPS_PROXY="http://host:port"</code><br>
            <br>
            If you're allergic to terminal, close your proxy and use a VPN.
            """,
            error,
            parent,
        )
    elif "ConnectionError" in error or "Timeout" in error:
        error_dialog(
            "It was a pleasure to burn",
            f"Is GitHub/Wikipedia/Fandom blocked by your ISP? You might need tools to bypass Internet censorship. Please read <a href='{CALIBRE_PROXY_FAQ}'>calibre FAQ</a>.",
            error,
            parent,
        )
    else:
        error_dialog(
            "Tonnerre de Brest!",
            f'An error occurred, please copy error message then report bug at <a href="{GITHUB_URL}/issues">GitHub</a>.',
            error,
            parent,
        )


def warning_dialog(title, message, parent=None):
    from calibre.gui2.dialogs.message_box import MessageBox

    MessageBox(MessageBox.WARNING, title, message, parent=parent).exec()


def unsupported_language_dialog(book_title):
    warning_dialog(
        "Unsupported language",
        f"The language of the book <i>{book_title}</i> is not supported.",
    )


def non_english_book_dialog():
    warning_dialog(
        "Non-English book",
        "For Kindle format books, Word Wise is only available in books in English.",
    )


def unsupported_format_dialog():
    warning_dialog("Unsupported book format", "The book format is not supported.")


def device_not_found_dialog(parent):
    warning_dialog(
        "Device not found",
        "Please connect your Kindle or Android(requires adb) device then try again.",
        parent,
    )
