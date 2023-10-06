#!/usr/bin/env python3

import json
import random
import re
import string
from pathlib import Path
from typing import TYPE_CHECKING, Any, BinaryIO, TypedDict

if TYPE_CHECKING:
    from .parse_job import ParseJobData


def check_metadata(
    gui: Any, book_id: int, custom_x_ray: bool
) -> tuple[int, list[str], list[str], Any, str] | None:
    from .config import prefs
    from .error_dialogs import unsupported_format_dialog, unsupported_language_dialog
    from .utils import get_plugin_path, load_plugin_json

    db = gui.current_db.new_api
    lang_dict = load_plugin_json(get_plugin_path(), "data/languages.json")
    supported_languages = {v["639-2"]: k for k, v in lang_dict.items()}
    mi = db.get_metadata(book_id, get_cover=True)
    # https://en.wikipedia.org/wiki/List_of_ISO_639-1_codes
    book_language = mi.get("language")
    if book_language not in supported_languages:
        unsupported_language_dialog(mi.get("title"))
        return None

    book_fmts = db.formats(book_id)
    supported_fmts = [f for f in prefs["preferred_formats"] if f in book_fmts]
    if not supported_fmts:
        unsupported_format_dialog()
        return None
    if len(supported_fmts) > 1 and prefs["choose_format_manually"] and not custom_x_ray:
        from .config import ChooseFormatDialog

        choose_format_dlg = ChooseFormatDialog(supported_fmts)
        if choose_format_dlg.exec():
            supported_fmts = [choose_format_dlg.chosen_format]
        else:
            return None
    if not prefs["use_all_formats"]:
        supported_fmts = [supported_fmts[0]]

    return (
        book_id,
        supported_fmts,
        [db.format_abspath(book_id, fmt) for fmt in supported_fmts],
        mi,
        supported_languages[book_language],
    )


def cli_check_metadata(book_path_str: str, log: Any) -> tuple[str, Any, str] | None:
    from .utils import get_plugin_path, load_plugin_json

    lang_dict = load_plugin_json(get_plugin_path(), "data/languages.json")
    supported_languages = {v["639-2"]: k for k, v in lang_dict.items()}
    book_path = Path(book_path_str)
    book_fmt = book_path.suffix.upper()[1:]
    mi = None
    if book_fmt == "KFX":
        from calibre.ebooks.metadata.book.base import Metadata
        from calibre.utils.localization import canonicalize_lang
        from calibre_plugins.kfx_input.kfxlib import YJ_Book

        yj_book = YJ_Book(str(book_path))
        yj_md = yj_book.get_metadata()
        title = getattr(yj_md, "title", None)
        language = getattr(yj_md, "language", None)
        mi = Metadata(title)
        mi.language = canonicalize_lang(language)
    elif book_fmt == "EPUB":
        from calibre.ebooks.metadata.epub import get_metadata

        with book_path.open("rb") as f:
            mi = get_metadata(f, False)
    elif book_fmt in ["AZW3", "AZW", "MOBI"]:
        from calibre.ebooks.metadata.mobi import get_metadata

        with book_path.open("rb") as f:
            mi = get_metadata(f)

    if mi:
        book_language = mi.get("language")
        if book_language not in supported_languages:
            log.prints(
                log.WARN,
                f"The language of the book {mi.get('title')} is not supported.",
            )
            return None
        return book_fmt, mi, supported_languages[book_language]

    log.prints(log.WARN, "The book format is not supported.")
    return None


def random_asin() -> str:
    "return an invalid ASIN"
    asin = "BB"
    asin += "".join(random.choices(string.ascii_uppercase + string.digits, k=8))
    return asin


def validate_asin(asin: str | None, mi: Any) -> tuple[str, bool]:
    # check ASIN, create a random one if doesn't exist
    update_asin = False
    if asin is None or re.fullmatch(r"B[0-9A-Z]{9}", asin) is None:
        asin = random_asin()
        mi.set_identifier("mobi-asin", asin)
        update_asin = True
    return asin, update_asin


class KFXJson(TypedDict):
    position: int
    content: str
    type: int


def get_asin_etc(
    data: "ParseJobData", device_book_path: str | None = None, set_en_lang: bool = False
) -> None:
    if data.book_fmt == "KFX":
        from calibre_plugins.kfx_input.kfxlib import YJ_Book

        yj_book = YJ_Book(
            str(device_book_path) if device_book_path is not None else data.book_path
        )
        yj_md = yj_book.get_metadata()
        book_asin = getattr(yj_md, "asin", "")
        data.acr = getattr(yj_md, "asset_id", "")
        book_lang = getattr(yj_md, "language", "en")
        if device_book_path is None:
            data.asin, data.update_asin = validate_asin(book_asin, data.mi)
        elif book_asin != data.asin:
            data.update_asin = True
        update_lang = False
        if set_en_lang and book_lang != "en":
            update_lang = True
            book_lang = "en"
        if data.update_asin or update_lang:
            update_kfx_metedata(
                str(device_book_path)
                if device_book_path is not None
                else data.book_path,
                data.asin,
                book_lang,
            )
        if device_book_path is None:
            data.kfx_json = json.loads(yj_book.convert_to_json_content())["data"]
    elif data.book_fmt != "EPUB":
        from calibre.ebooks.metadata.mobi import MetadataUpdater

        with open(device_book_path or data.book_path, "r+b") as f:
            data.acr = f.read(32).rstrip(b"\x00").decode("utf-8")  # Palm db name
            data.revision = get_mobi_revision(f)
            f.seek(0)
            mu = MetadataUpdater(f)
            data.mobi_codec = mu.codec
            asin_bytes = mu.original_exth_records.get(
                113
            ) or mu.original_exth_records.get(504)
            book_asin = asin_bytes.decode(mu.codec) if asin_bytes is not None else None
            if device_book_path is None:
                data.asin, data.update_asin = validate_asin(book_asin, data.mi)
            elif book_asin != data.asin:
                data.update_asin = True
            locale = mu.record0[0x5C:0x60]  # MOBI header locale
            mi_lang = data.mi.language
            update_lang = False
            if set_en_lang and locale[2:] != (9).to_bytes(2, "big"):
                update_lang = True
                locale = (9).to_bytes(4, "big")
                mi_lang = "eng"
            if data.update_asin or update_lang:
                data.mi.language = mi_lang
                mu.record0[0x5C:0x60] = locale
                mu.update(data.mi, asin=data.asin)
        if device_book_path is None:
            data.mobi_html = extract_mobi(data.book_path)


def get_mobi_revision(f: BinaryIO) -> str:
    # modified from calibre.ebooks.mobi.reader.headers:MetadataHeader.header
    f.seek(78)
    f.seek(int.from_bytes(f.read(4), "big") + 32)
    return f.read(4).hex()  # Unique-ID MOBI header


def extract_mobi(book_path: str) -> bytes:
    # use code from calibre.ebooks.mobi.reader.mobi8:Mobi8Reader.__call__
    # and calibre.ebook.conversion.plugins.mobi_input:MOBIInput.convert
    # https://github.com/kevinhendricks/KindleUnpack/blob/master/lib/mobi_k8proc.py#L216
    from calibre.ebooks.mobi.reader.mobi6 import MobiReader
    from calibre.ebooks.mobi.reader.mobi8 import Mobi8Reader

    with open(book_path, "rb") as f:
        mr = MobiReader(f)
        if mr.kf8_type == "joint":
            raise Exception("JointMOBI")
        mr.check_for_drm()
        mr.extract_text()
        html = mr.mobi_html
        if mr.kf8_type == "standalone":
            m8r = Mobi8Reader(mr, mr.log)
            m8r.kf8_sections = mr.sections
            m8r.read_indices()
            m8r.build_parts()
            html = b"".join(m8r.parts)  # KindleUnpack
        return html


def update_kfx_metedata(book_path: str, asin: str, lang: str):
    from calibre_plugins.kfx_input.kfxlib import YJ_Book, YJ_Metadata

    yj_book = YJ_Book(book_path)
    yj_md = YJ_Metadata()
    yj_md.asin = asin
    yj_md.language = lang
    yj_md.content_type = "EBOK"
    yj_book.decode_book(set_metadata=yj_md)
    with open(book_path, "wb") as f:
        f.write(yj_book.convert_to_single_kfx())


def check_word_wise_language(book_lang: str, is_kindle: bool) -> tuple[bool, str]:
    from .config import prefs
    from .utils import get_plugin_path, load_languages_data

    supported_languages = load_languages_data(get_plugin_path())
    gloss_lang = prefs["kindle_gloss_lang" if is_kindle else "wiktionary_gloss_lang"]
    return book_lang in supported_languages[gloss_lang]["lemma_languages"], gloss_lang
