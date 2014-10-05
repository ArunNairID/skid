#!/usr/bin/env python

# gscholar - Get bibtex entries from Goolge Scholar
# Copyright (C) 2011  Bastian Venthur <venthur at debian org>
#
#   with some modifications by Tim Vieira.
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA.


"""Library to query Google Scholar.

Call the method query with a string which contains the full search string.
Query will return a list of bibtex items.
"""


import urllib2
import re
import hashlib
import random
import os
import subprocess
import logging
from htmlentitydefs import name2codepoint
from arsenal.fsutils import secure_filename


# fake google id (looks like it is a 16 elements hex)
google_id = hashlib.md5(str(random.random())).hexdigest()[:16]

GOOGLE_SCHOLAR_URL = "http://scholar.google.com"
# the cookie looks normally like:
#        'Cookie' : 'GSP=ID=%s:CF=4' % google_id }
# where CF is the format (e.g. bibtex). since we don't know the format yet, we
# have to append it later
HEADERS = {'User-Agent' : 'Mozilla/5.0',
        'Cookie' : 'GSP=ID=%s' % google_id }

FORMAT_BIBTEX = 4
FORMAT_ENDNOTE = 3
FORMAT_REFMAN = 2
FORMAT_WENXIANWANG = 5


def query(searchstr, outformat=FORMAT_BIBTEX, allresults=False):
    """Return a list of bibtex items."""
    logging.debug("Query: %s" % searchstr)
    searchstr = '/scholar?q='+urllib2.quote(searchstr)
    url = GOOGLE_SCHOLAR_URL + searchstr
    header = HEADERS
    header['Cookie'] = header['Cookie'] + ":CF=%d" % outformat
    request = urllib2.Request(url, headers=header)
    response = urllib2.urlopen(request)
    html = response.read()
    html.decode('ascii', 'ignore')
    # grab the links
    tmp = get_links(html, outformat)

    # follow the bibtex links to get the bibtex entries
    result = list()
    if allresults == False:
        tmp = tmp[:1]
    for link in tmp:
        url = GOOGLE_SCHOLAR_URL+link
        request = urllib2.Request(url, headers=header)
        response = urllib2.urlopen(request)
        bib = response.read()
        result.append(bib)
    return result


def get_links(html, outformat):
    """Return a list of reference links from the html."""
    if outformat == FORMAT_BIBTEX:
        refre = re.compile(r'<a href="(/scholar\.bib\?[^"]*)')
    elif outformat == FORMAT_ENDNOTE:
        refre = re.compile(r'<a href="(/scholar\.enw\?[^"]*)"')
    elif outformat == FORMAT_REFMAN:
        refre = re.compile(r'<a href="(/scholar\.ris\?[^"]*)"')
    elif outformat == FORMAT_WENXIANWANG:
        refre = re.compile(r'<a href="(/scholar\.ral\?[^"]*)"')
    reflist = refre.findall(html)
    # escape html enteties
    reflist = [re.sub('&(%s);' % '|'.join(name2codepoint), lambda m:
        unichr(name2codepoint[m.group(1)]), s) for s in reflist]
    return reflist


def convert_pdf_to_txt(pdf):
    """Convert a pdf file to txet and return the text.

    This method requires pdftotext to be installed.
    """
    stdout = subprocess.Popen(["pdftotext", "-q", pdf, "-"], stdout=subprocess.PIPE).communicate()[0]
    return stdout


def pdflookup(pdf, allresults, outformat):
    """Look a pdf up on google scholar and return bibtex items."""
    txt = convert_pdf_to_txt(pdf)
    # remove all non alphanumeric characters
    txt = re.sub("\W", " ", txt)
    words = txt.strip().split()[:20]
    gsquery = " ".join(words)
    bibtexlist = query(gsquery, outformat, allresults)
    return bibtexlist


def _get_bib_element(bibitem, element):
    """Return element from bibitem or None."""
    lst = [i.strip() for i in bibitem.split('\n')]
    for i in lst:
        if i.startswith(element):
            value = i.split("=", 1)[-1]
            value = value.strip()
            while value.endswith(','):
                value = value[:-1]
            while value.startswith('{') or value.startswith('"'):
                value = value[1:-1]
            return value
    return None


def rename_file(pdf, bibitem):
    """Attempt to rename pdf according to bibitem."""
    year = _get_bib_element(bibitem, "year")
    author = _get_bib_element(bibitem, "author")
    if author:
        author = author.split(",")[0].replace(' ','')
    title = _get_bib_element(bibitem, "title")

    # pick one word for the title
    title = title.strip().split()[0]

    filename = secure_filename('%s%s%s.pdf' % (author, year[-2:], title))
    newfile = pdf.replace(os.path.basename(pdf), filename)
    print
    print "Will rename:"
    print
    print "  %s" % pdf
    print
    print "to"
    print
    print "  %s" % newfile
    print
    print "Proceed? [y/N]"
    answer = raw_input()
    if answer == 'y':
        print "Renaming %s to %s" % (pdf, newfile)
        os.rename(pdf, newfile)
    else:
        print "Aborting."


def main():
    from argparse import ArgumentParser
    parser = ArgumentParser()
    parser.add_argument("-a", "--all", action="store_true",
                        help="show all bibtex results")
    parser.add_argument("-d", "--debug", action="store_true",
                        help="show debugging output")
    parser.add_argument("-r", "--rename", action="store_true",
                        help="rename file (asks before doing it)")
    parser.add_argument("-o", "--output",
                        choices=('bibtex','endnote','refman','wenxianwang'),
                        default="bibtex",
                        help="Output format. [default: %(default)s]")

    parser.add_argument('query', nargs='+')

    args = parser.parse_args()

    args.query = ' '.join(args.query)

    if args.debug:
        logging.basicConfig(level=logging.DEBUG)

    if args.output == 'bibtex':
        outformat = FORMAT_BIBTEX
    elif args.output == 'endnote':
        outformat = FORMAT_ENDNOTE
    elif args.output == 'refman':
        outformat = FORMAT_REFMAN
    elif args.output == 'wenxianwang':
        outformat = FORMAT_WENXIANWANG

    pdfmode = False
    if os.path.exists(args.query):
        logging.debug("File exist, assuming you want me to lookup the pdf: %r." % query)
        pdfmode = True
        biblist = pdflookup(args.query, all, outformat)
    else:
        logging.debug("Assuming you want me to lookup the query: %r." % query)
        biblist = query(args.query, outformat, args.all)

    if len(biblist) < 1:
        print "No results found, try again with a different query!"
        exit(1)

    if args.all:
        logging.debug("All results:")
        for i in biblist:
            print i
    else:
        logging.debug("First result:")
        print biblist[0]

    if args.rename:
        if not pdfmode:
            print "You asked me to rename the pdf but didn't tell me which file to rename, aborting."
            exit(1)
        else:
            rename_file(args.query, biblist[0])

if __name__ == "__main__":
    main()
