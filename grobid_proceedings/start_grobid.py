# -*- coding: utf-8 -*-
"""
Start GROBID
"""

import os
import re
import sys
from cutpdf_for_grobid import cut_pdf
from execute_grobid import build_marc_xml
import pdf_upload_path

DIR_HOME = os.getcwd()
DIR_PDF = pdf_upload_path.dir_pdf(DIR_HOME)
DESYDOC = 'desydoc@desy.de'


def create_dummy_metadata(record_id, metadata_filename):
    """
    Create a sort of base record (MARC21), with info copied to all extracted records.
    """
    recid = int(record_id)
    if not os.path.isfile(metadata_filename):
        dummyfile = open(metadata_filename, mode='w')
        dummyfile.write('%09i 269__ $$c2021-01-01\n' % recid)
        dummyfile.write('%09i 773__ $$wC99-99-99.1\n' % recid)
        dummyfile.write('%09i 980__ $$aConferencePaper\n' % recid)
        dummyfile.write('%09i 980__ $$aHEP\n' % recid)
        dummyfile.close()


def main(argv):
    """Main function. Talk the user through the process."""
    helptext = """Usage:
Download of fulltext from INSPIRE is currently not possible.
Please download the fulltext manually to your working directory and rename it to [recid]_fulltext.pdf
You can delete the files when the records are in INSPIRE.

You need to write a page-file.

    3 exampes for page_file:
1st example:  e.g. pages 23-29 of the pdf will get 773__c:3-9

    #offset=20
    3-9
    11-14

-----------------------------------------
2nd example:  e.g. pages 21-33 of the pdf will get no 773__c subfield
    #nopages
    21-33
    35-51

-----------------------------------------
3rd example:  e.g. pages  5-17 of the pdf will get 773__c:qcd12
    5-17    qcd12
    21-29   susy-4

===========================================================================
There are 2 possibilities to call the program:
    python start_grobid.py <recid>.txt
    python start_grobid.py <recid> <page_filename>

    where

    <recid> is the record-ID of the Proceedings or Book record and
    <page_filename> is the name of a file holding info how to cut the pdf
    In the 1st example <recid>.txt is the page_filename.
    The resulting xml file will be written to your current directory.
    """

    recid = None
    page_filename = ''
    for arg in argv:
        if os.path.isfile(arg):
            page_filename = arg
        elif arg.isdigit():
            recid = arg
    if not recid:
        # try to get recid from the name of page_filename.
        basename = os.path.basename(page_filename).split('.')[0]
        if basename.isdigit():
            recid = basename

    if not recid or not os.path.isfile(page_filename):
        print helptext
        print ''
        if not recid:
            print "Please give recid of proceedings as argument"
        if not page_filename:
            print "Please give pages file as argument"
        if not os.path.isfile(page_filename):
            print "Can't read pages file", page_filename
        sys.exit(1)

    if not os.access(DIR_HOME, os.W_OK) or not os.access(DIR_PDF, os.W_OK) or not os.access(DIR_PDF, os.X_OK):
        print "You need write permission in the current directory and %s" % DIR_PDF
        answer = raw_input("Are you sure you want to continue? y/[n]\n")
        if not answer or answer[0].lower() == 'n':
            sys.exit(1)

    print 'Hi!\nYou are starting the process to extract contributions \
from an INSPIRE fulltext of record %s' % recid

    dir_for_grobid = os.path.join(DIR_PDF, '%s_for_grobid' % recid)
    if not os.path.isdir(dir_for_grobid):
        os.mkdir(dir_for_grobid)

    fulltext_filename = os.path.join(DIR_HOME, "%s_fulltext.pdf" % recid) 
    metadata_filename = os.path.join(dir_for_grobid, "%s_metadata.txt" % recid)
    metadata_linkname = os.path.join(DIR_HOME, "%s_metadata.txt" % recid)
    
    create_dummy_metadata(recid, metadata_filename)
    if os.path.isfile(metadata_linkname):
        os.unlink(metadata_linkname)
    os.symlink(metadata_filename, metadata_linkname)

# get fulltext and metadata from INSPIRE
    print '\nDownload of the fulltext from INSPIRE is currently not available'
    print 'Copy the fulltext manually to %s' % fulltext_filename
    print 'And update the metadata in %s now' % metadata_linkname
    print 'e.g. CNUM and date - which will be copied to the contributions'
    os.system('more %s' % metadata_linkname)
    print '\n#############################################'
    print ' you have to update %s before you continue!!!' % metadata_linkname
    print ' otherwise there will be wrong metadata in the records'
    print '#############################################'

# cut fulltext pdf in pieces
    answer = raw_input(
        "Do you want to cut the pdf? (possibly skip if it was already done)     [y]/n\nType q to exit\n")
    if not answer or answer[0].lower() == 'y':
        if not os.path.isfile(fulltext_filename):
            print '\n\nTHERE IS NO FULLTEXT ON'
            print fulltext_filename
            print 'Please download fulltext.'
            print 'Then run start_grobid.py again'
            exit()

        cut_pdf(fulltext_filename, page_filename, dir_for_grobid)
    elif answer[0].lower() == 'q':
        exit()
    
# extract metadata from pdf using grobid
    answer = raw_input('  Call GROBID now?    [y]/n/s\n  You can skip metadata extraction\n')
    if not answer or answer[0].lower() == 'y' or answer[0].lower() == 's':
        if answer and answer[0].lower() == 's':
            extract_metadata = False
        else:
            extract_metadata = True

        nrecs, xml_file = build_marc_xml(dir_for_grobid, DIR_HOME, page_filename, extract_metadata)

        if nrecs:
            basename = os.path.basename(xml_file)
            print "You should now check %s\n" % basename
            print "Then send it to the journal workflow:"
            print "> tar -cf grobid.tar %s" % (basename)
            print "> echo %s | mail -s Grobid -a grobid.tar %s" % (basename, DESYDOC)
        else:
            print "execute_grobid failed?"

# delete unnessesary files
    print "\nYou can delete some files now:\n rm %s %s\n" % (fulltext_filename,  metadata_linkname)
    print "Other files in %s can be deleted when the records are in INSPIRE\n" % dir_for_grobid

if __name__ == "__main__":
    main(sys.argv[1:])
