#!/usr/bin/env python3
from pathlib import Path
from filecmp import cmp

from calibre.library import db
from calibre.utils.config import config_dir
from calibre_plugins.worddumb.metadata import check_metadata
from calibre_plugins.worddumb.parse_job import do_job
from calibre_plugins.worddumb.database import get_ll_path

db = db().new_api
book_ids = db.all_book_ids()
plugin_path = Path(config_dir).joinpath('plugins/worddumb.zip')
do_job(db, book_ids, plugin_path, None, None, None)
(_, asin, book_path, _) = check_metadata(db, next(iter(book_ids)), False)

if asin != 'B003JTHWKU':
    print('Wrong ASIN: {}, should be B003JTHWKU.'.format(asin))

ll_path = get_ll_path(asin, book_path)
assert(cmp(ll_path, 'LanguageLayer.en.B003JTHWKU.kll') is True)
