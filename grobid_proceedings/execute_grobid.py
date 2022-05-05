# -*- coding: utf-8 -*-
# Copyright (C) 2016 CERN.

"""
Python module to extract information from a set of pdf files in a directory.
PDF extraction uses Grobid, which runs as a service on https://grobid.inspirebeta.net
Conversion from Grobid output file formats to HEPRecord MARCXML (Inspire Invenio1) using
`grobid_proceedings/mapping`  and  `utils` derived from
`invenio_grobid.mapping`,
`inspirehep.dojson.utils`, and
`invenio_utils.text`.


How it works:

1. Input one directory for this script. This dir must be on AFS (unless just testing).

2. Go through every pdf file in that directory (`process_pdf_dir`).

3. For every file, open them as a raw string (`open_pdf`)
   and give the string to Grobid (`process_pdf_stream`). Grobid outputs TEI
   format XML files.

4. Take the TEI XML file and convert it to a record dictionary (`build_dicts`).

5. Take the dictionary and modify its key names to match with
   MARC21 HEPRecord. Finally convert (`utils.legacy_export_as_marc`)
   and print the dictionary to a MARCXML file (`build_marc_xml`)

6. Information about the page ranges can be provided in file page_filename

USAGE EXAMPLES:
$ python execute_grobid.py -i test/
$ python execute_grobid.py -i 12345_for_grobid/ -o my_grobid_results/ -p page_filename
"""

from __future__ import print_function
from __future__ import absolute_import

import sys
import getopt
import os
import re
import copy
import textwrap

import fnmatch
import json
import logging

import requests

from cutpdf_for_grobid import read_pages
import mapping, utils, pdf_upload_path

#input_dir = "test/"
#GROBID_HOST = "http://localhost:8080/"  # Local installation
#GROBID_HOST = "http://inspire-grobid.cern.ch:8080/"
#GROBID_HOST = "https://inspire-prod-grobid1.cern.ch/"
#GROBID_HOST = "https://grobid.qa.inspirebeta.net/api"
GROBID_HOST = "https://grobid.inspirebeta.net/api"
#GROBID_HOST = "https://grobid.inspirehep.net/api"

grobid_likes_not = []

def byPage(a,b):
    """compare: if both fields are numeric or num-num sort numeric, alphabetic otherwise"""
    aa = re.sub('^ *(\d+) *- *\d+ *$',r'\1',a)
    bb = re.sub('^ *(\d+) *- *\d+ *$',r'\1',b)
    try:
        c = cmp(int(aa),int(bb))
    except:
        c = cmp(a,b)
    return c


def parse_filename(pdf_file):
    """Get page numbers from pdf filename."""
    pages = os.path.splitext(pdf_file)[0].split('_')[-1]
    return pages


def open_pdf(pdf_file):
    """Open one pdf file as a raw string."""
    with open(pdf_file, "r") as pfile:
        pdf_string = pfile.read()
    return pdf_string


def process_pdf_stream(pdf_file):
    """Process a PDF file stream with Grobid, returning TEI XML results."""
    response = requests.post(
        url=os.path.join(GROBID_HOST, "processFulltextDocument"),
        files={'input': open_pdf(pdf_file)},
        verify=False,
        )

    if response.status_code == 200:
        return response.text
    else:
        print("Grobid server error, status code: %i. Problematic file: %s" % (response.status_code, pdf_file))
        grobid_likes_not.append(pdf_file)
        return None

def process_pdf_dir(input_dir, extract_metadata=True):
    """Process the entire directory, but take only pdf files.

    Return cnum, first page, and XML (parsed pdf) in Grobid TEI format.
    """
    paths = []
    pdf_files = []
    for root, dirnames, filenames in os.walk(input_dir):
        for filename in fnmatch.filter(filenames, '*.pdf'):
            paths.append(os.path.join(root, filename))
            pdf_files.append(filename)

    for filename, pdf_path in zip(pdf_files, paths):
        if extract_metadata:
            grobid_response = process_pdf_stream(pdf_path)
        else:
            grobid_response = None

        yield (
            os.path.abspath(pdf_path),
            parse_filename(filename),
            grobid_response,
            )

def read_book_dict(input_dir):
    """Read info from Proceedings / Book record from file."""
    basename = re.sub('_for_grobid', '', os.path.basename(input_dir))
    data_file = open(os.path.join(input_dir, '%s_metadata.txt' % basename), 'r')
    re_marc_line = re.compile(r'^ *(\d+)  *(.....)  *(.*) *$')
    book_dict = {}
    recid = None
    repno = None
    isbn = None
    cnum = None
    pyear = None
    art_type = None
    for line in data_file.readlines():
        marc_line = re_marc_line.search(line)
        if marc_line:
            recid = int(marc_line.group(1))
            key = marc_line.group(2).rstrip('_')
            values = marc_line.group(3).split('$$')[1:]
            if key == '980':
                if 'aProceedings' in values:
                    art_type = 'ConferencePaper'
                elif 'aBook' in values:
                    art_type = 'BookChapter'
            elif key == '037':
                if '9arXiv' in values:
                    for value in values:
                        if value[0] == 'a':
                            repno = value[1:]
            elif key == '773':
                for value in values:
                    if value[0] == 'w':
                        cnum = value[1:]
                        art_type = 'ConferencePaper'
                    if value[0] == 'y':
                        pyear = value[1:]
            elif key == '020':
                for value in values:
                    if value[0] == 'a':
                        isbn = value[1:]
            else:
                subfield = {}
                for value in values:
                    code = value[0]
                    if code in subfield.keys():
                        subfield[code].append(value[1:])
                    else:
                        subfield[code] = [value[1:], ]
                if key in book_dict.keys():
                    book_dict[key].append(subfield)
                else:
                    book_dict[key] = [subfield, ]
        elif line:
            print('Cant read:', line)
        data_file.close()

    book_dict['980'] = [{'a':'HEP'}, ]
    if art_type:
        book_dict['980'].append({'a':art_type})

    pbn = {}
    if recid:
        pbn['0'] = recid
    if cnum:
        pbn['w'] = cnum
    if repno:
        pbn['r'] = repno
    if pyear:
        pbn['y'] = pyear
    if isbn:
        pbn['z'] = isbn
    book_dict['773'] = [pbn, ]
    return book_dict

def build_dicts(input_dir, extract_metadata=True):
    """Create dictionaries from the TEI XML data."""
    for processed_pdf in process_pdf_dir(input_dir, extract_metadata):
        rec_dict = {}
        pdf_path, pages, tei = processed_pdf
        if tei:
            rec_dict = mapping.tei_to_dict(tei)  # NOTE: this includes some empty elements, which is not cool
        # NOTE: create a record even if pdf could not be grobided
        rec_dict["pdf_path"] = pdf_path
        rec_dict["pages"] = pages
        yield rec_dict

def get_authors(aut):
    """Get author name and affiliation. Format: 'lastname, firstname'."""
    author_name = ''
    surname = ''
    surname, given_names = utils.split_fullname(aut.get("name"), surname_first=False)
    if surname and "collaboration" in surname.lower():
        author_name = surname
    if surname and given_names:
        if len(given_names) == 1:  # Handle initials
            given_names += "."
        given_names = re.sub('\. +', '.', given_names)
        #author_name = u"{}, {}".format(surname, given_names)  # NOTE: this doesn't work with python 2.6
        author_name = surname + ", " + given_names
    elif surname:
        author_name = surname
    affiliations = []
    aff_raws = aut.get("affiliations")
    if aff_raws:
        for aff in aff_raws:
            affiliations.append(aff.get("value").strip("()"))

    return author_name, affiliations

def number_of_pages(pages):
    """Given a page range return number of pages as string"""
    p1_p2 = pages.split('-')
    if len(p1_p2) == 2 and p1_p2[0].isdigit() and p1_p2[1].isdigit():
        np = int(p1_p2[1]) - int(p1_p2[0]) + 1
        return "%s" % np
    else:
        return None

def build_marc_xml(input_dir, output_dir, page_filename, extract_metadata=True):
    """Build a MARCXML file from the HEPRecord dictionary."""
    all_records = {}

    user = os.getlogin()
    page_ranges, add_pages = read_pages(page_filename)
    basename = re.sub('_for_grobid', '', os.path.basename(input_dir))

    book_dict = read_book_dict(input_dir)
    counter = {"authors": 0, "title": 0, "abstract": 0}
    for dic in build_dicts(input_dir, extract_metadata):
        marcdict = copy.deepcopy(book_dict)

        if "pages" in dic.keys():
            pages = dic.get("pages")
        else:
            pages = 'No pages'

        numpages = number_of_pages(pages)

        if not numpages:
            if pages in page_ranges.keys():
                numpages = number_of_pages(page_ranges[pages])
        if numpages:
            marcdict["300"] = {"a": numpages}

        if add_pages:
            pbn_pages = pages
        else:
            pbn_pages = 'VVPP'  ## FIXME: DESY workflow needs something in this field
        if '773' in marcdict.keys():
            marcdict['773'][0]['c'] = pbn_pages
        else:
            marcdict['773'] = [{'c': pbn_pages}, ]

        if extract_metadata:
            marcdict["595"] = {"a": "From Grobid by %s: title, authors, affiliations, abstract" % user}
        else:
            marcdict["595"] = {"a": "From Grobid by %s: PBN only" % user}

        authors_raw = dic.get("authors")
        authors = []
        if authors_raw:
            # delete authors which have empty values:
            for author in authors_raw:
                author_not_empty = dict((k, v) for k, v in author.iteritems() if v)
                if author_not_empty:
                    authors.append(author_not_empty)
        if authors:
            counter["authors"] += 1
            marcdict["100"] = []
            marcdict["110"] = []
            marcdict["700"] = []
            # Only the first author should be put in the 100 field, others to 700
            marcfield = "100"
            for aut in authors:
                author_name, affiliations = get_authors(aut)
                if not author_name:
                    # "If you have a separate field for the affiliation it should always be 110 and no subfield $$a."
                    marcdict["110"].append({"v":affiliations})
                else:
                    author_name, affiliations = get_authors(aut)
                    marcdict[marcfield].append({"a": author_name, "v": affiliations})
                    marcfield = "700"
        elif extract_metadata:
            marcdict["100"] = [{"a": ""}, ]

        title = dic.get("title")
        if title:
            marcdict["245"] = {"a": title}
            counter["title"] += 1
        elif extract_metadata:
            marcdict["245"] = {"a": ""}

        abstract =  dic.get("abstract")
        if abstract:
            abstract =  textwrap.fill(abstract, 80) + '\n'
            marcdict["520"] = {"a": abstract, "9": "Grobid"}
            counter["abstract"] += 1

        upload_path = pdf_upload_path.pdf_url(dic["pdf_path"])
        
        marcdict["FFT"] = {
            "a": upload_path,
            "d": "Fulltext",
            "t": "INSPIRE-PUBLIC",
            }

        # NOTE: we don't need the references at this point
        #marcdict["999C5"] = []
        #for ref in dic["references"]:
            #authors = ", ".join([aut["name"] for aut in ref["authors"]])
            #title = ref["journal_pubnote"].get("journal_title", "")
            #volume = ref["journal_pubnote"].get("journal_volume", "")
            #pages = ref["journal_pubnote"].get("page_range", "")
            #year = ref["journal_pubnote"].get("year", "")
            #pubnote = u"{},{},{}".format(title, volume, pages)
            #marcdict["999C5"].append({"s":pubnote, "y":year})

        all_records[pages] = marcdict

    all_records_marc = ''
    all_pages = all_records.keys()
    all_pages.sort(byPage)
    for pages in all_pages:
        marcdict = all_records[pages]
        all_records_marc += utils.legacy_export_as_marc(marcdict, no_empty_fields=False)

# Write one big file for the whole directory
    basename = 'grobid_' + os.path.basename(input_dir).replace('_for_grobid', '')
    if '773' in book_dict.keys():
        master_repno = None
        master_recid = None
        for field in book_dict['773']:
             for code, value in field.items():
                 if code == 'r':
                     master_repno = value
                 if code == '0':
                     master_recid = value
        if master_repno:
            basename = master_repno
        elif master_recid:
            basename = master_recid
    basename = '%s' % basename
    basename = re.sub('[^\w.-]','_', basename)

    print("\v\vFinished processing...")
    filename = "grobid.split_%s.xml" % basename
    path_filename = os.path.join(output_dir, filename)
    outfile = open(path_filename, "w")
    outfile.write("<collection>\n")
    outfile.write(all_records_marc)
    outfile.write("</collection>\n")
    outfile.close()
    print("Wrote %s records to %s" % (len(all_records.keys()), path_filename))
    if extract_metadata:
        print("%5d records with authors" % (counter["authors"]))
        print("%5d records with titles" % (counter["title"]))
        print("%5d records with abstracts\n" % (counter["abstract"]))
    else:
        print("Metadata extraction skipped\n")

    if grobid_likes_not:
        print("Following pdfs were not processed: " + ", ".join(grobid_likes_not))

    return len(all_records.keys()), path_filename

def main(argv):
    """Main function."""
    input_dir = ''
    pubdate = ''
    helptext = ("\v* Usage: python execute_grobid.py -i <input_dir> -o <output_dir> -p <page_file>\n\v"
        "* <input_dir> is the directory where the conference files are, e.g.\n"
        "  `./1776837_for_grobid`\n"
        "* <page_file> is a file with page information\n"
        "* There should be a file <base_dir>_metadata.txt (i.e. 1776837_metadata.txt)\n"
        "  that contains information from the Book or Proceedings record in text marc,\n"
        "* -s: Skip extraction of metadata from pdf.\n"
        "* Output MARCXML record will be written to <output_dir>, default is '.'\n "
        )
    input_dir = ''
    output_dir = '.'

    try:
        opts, args = getopt.getopt(argv, "hsi:o:p:", ["idir=", "odir=", "pfile=" ])
    except getopt.GetoptError:
        print(helptext)
        sys.exit(2)

    page_filename = ""
    extract_metadata = True
    for opt, arg in opts:
        if opt == '-h':
            print(helptext)
            sys.exit()
        elif opt == '-s':
            extract_metadata = False
        elif opt in ("-i", "--idir"):
            input_dir = arg
        elif opt in ("-o", "--odir"):
            output_dir = arg
        elif opt in ("-p", "--pfile"):
            page_filename = arg
    if not output_dir:
        output_dir = input_dir
    if os.path.isdir(input_dir) and os.path.isdir(output_dir):
        print('Processing directory:', input_dir )
        build_marc_xml(input_dir, output_dir, page_filename, extract_metadata)
    else:
        print(helptext)
        print(opts)

if __name__ == "__main__":
    main(sys.argv[1:])
