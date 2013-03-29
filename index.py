"""
Index skid-marks to support efficient search over attributes including
full-text.
"""

import re, os
from datetime import datetime

from whoosh.index import create_in, open_dir
from whoosh.fields import Schema, TEXT, KEYWORD, ID, DATETIME
from whoosh.qparser import QueryParser, MultifieldParser
from whoosh.analysis import StandardAnalyzer, SimpleAnalyzer, KeywordAnalyzer, STOP_WORDS

from skid.config import ROOT, CACHE
from skid.add import Document

# globals
DIRECTORY = ROOT + '/index'
NAME = 'index'


def create():
    """ Create a new Whoosh index.. """
    print 'creating new index in directory %s' % DIRECTORY
    os.system('rm -rf %s' % DIRECTORY)
    os.mkdir(DIRECTORY)
    schema = Schema(source = ID(stored=True, unique=True),
                    cached = ID(stored=True, unique=True),
                    hash = ID(stored=True, unique=True),
                    title = TEXT(stored=True),
                    author = TEXT(stored=True),
                    year = TEXT(stored=True),
                    notes = TEXT(stored=True),
                    text = TEXT(stored=True),
                    tags = TEXT(stored=True, analyzer=KeywordAnalyzer()),
                    added = DATETIME(stored=True),
                    mtime = DATETIME(stored=True))
    create_in(DIRECTORY, schema, NAME)


def search(q, limit=10):
    q = unicode(q.decode('utf8'))
    ix = open_dir(DIRECTORY, NAME)
    with ix.searcher() as searcher:
        qp = MultifieldParser(fieldnames=['title', 'author', 'tags', 'notes', 'text'],
                              fieldboosts={'title': 5,
                                           'author': 5,
                                           'tags': 5,
                                           'notes': 2,
                                           'text': 1},
                              schema=ix.schema)

        # Whoosh chokes on queries with stop words, so remove them.
        q = re.sub(r'\b(%s)\b' % '|'.join(STOP_WORDS), '', q)

        q = qp.parse(q)
        for hit in searcher.search(q, limit=limit):
            yield hit


#def correct(qstr):
#    qstr = unicode(qstr.decode('utf8'))
#    ix = open_dir(DIRECTORY, NAME)
#    with ix.searcher() as searcher:
#        qp = QueryParser('text', schema=ix.schema)
#        q = qp.parse(qstr)
#        return searcher.correct_query(q, qstr, allfields=True)


def drop():
    "Drop existing index."
    assert DIRECTORY.exists()
    os.system('rm -rf ' + DIRECTORY)
    print 'dropped index', DIRECTORY


def delete(cached):
    "Remove file from index."
    try:
        ix = open_dir(DIRECTORY, NAME)
        with ix.searcher() as searcher, ix.writer() as w:
            qp = QueryParser(u'cached', ix.schema)
            q = qp.parse(unicode(cached))
            # should only get one hit.
            [hit] = searcher.search(q)
            w.delete_document(hit.docnum)
    except ValueError:
        print 'Cached file %r not found in index.' % cached


def update():
    "Rebuild index from scratch."

    # create index if it doesn't exist
    if not DIRECTORY.exists():
        create()

    # get handle to Whoosh index
    ix = open_dir(DIRECTORY, NAME)

    with ix.writer() as w, ix.searcher() as searcher:

        # sort cached files by mtime.
        files = [Document(f) for f in CACHE.files()]
        files.sort(key = (lambda x: x.modified), reverse=True)

        for d in files:

            # lookup document mtime in the index; don't add or extract info if
            # you don't need it.
            result = searcher.find('cached', unicode(d.cached))

            if not result:
                print '[INFO] new document', d.cached

            else:
                assert len(result) == 1, 'cached should be unique.'
                result = result[0]
                if d.modified <= result['mtime']:   # already up to date

                    # Since we've sorted files by mtime, we know that files
                    # after this one are older, and thus we're done.
                    return

                print '[INFO] update to existing document:', d.cached

            meta = d.parse_notes()

            # just a lint check
            assert meta['cached'] == d.cached, \
                'Cached field in notes (%s) ' \
                'does not match associated file (%s) ' \
                'in notes file %r' % (meta['cached'],
                                      d.cached,
                                      'file://' + d.d/'notes.org')

            w.update_document(source = meta['source'],
                              cached = unicode(d.cached),
                              hash = d.hash(),
                              title = meta['title'],
                              author = meta.get('author', u''),
                              year = meta.get('year', u''),
                              notes = meta['notes'],
                              text = d.text(),
                              mtime = d.modified,
                              added = d.added,
                              tags = meta['tags'])


def lexicon(field):
    """
    List lexicon entries from field. For example lexicon('tags') should return
    all know tags.
    """
    ix = open_dir(DIRECTORY, NAME)
    with ix.searcher() as s:
        return list(s.lexicon(field))
