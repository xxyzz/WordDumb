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
        elif "32BIT_CALIBRE" in job.details or "32BIT_PYTHON" in job.details:
            program = "calibre" if "32BIT_CALIBRE" in job.details else "Python"
            error_dialog(
                "The wrist game!",
                f"You're using 32bit {program}, please install the 64bit version.",
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
    else:
        check_network_error(job.details + exception, parent)


def check_network_error(error, parent):
    if "check_hostname requires server_hostname" in error:
        error_dialog(
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
            parent,
        )
    elif "ConnectionError" in error or "Timeout" in error:
        error_dialog(
            "It was a pleasure to burn",
            "Is GitHub/Wikipedia/Fandom blocked by your ISP? You might need tools to bypass internet censorship.",
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


def unsupported_language_dialog(title, parent):
    error_dialog(
        "Unsupported language",
        f"The language of the book <i>{title}</i> is not supported.",
        None,
        parent,
    )


def non_english_book_dialog(parent):
    error_dialog(
        "Non-English book",
        "Word Wise is only available in English books on Kindle.",
        None,
        parent,
    )


def unsupported_format_dialog(parent):
    error_dialog(
        "Unsupported book format",
        "The book format is not supported.",
        None,
        parent,
    )
