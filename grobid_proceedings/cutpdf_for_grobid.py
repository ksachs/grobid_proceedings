"""
Helper function for grobid
Cut fulltext pdf file in pieces, store extracted parts in one directory
Input: pdf_filename - name of fulltext pdf
Input: page_filename - file with information on page-numbers of contributions
Creating: basename_for_grobid/basename_[pages].pdf - pdf files of contributions
          in same directory as fulltext pdf
"""
import os
import re
import sys
import getopt

USER = os.getlogin()
DIR_TMP = '/tmp/tmp_%s' % USER
if not os.path.isdir(DIR_TMP):
    os.system('mkdir %s' % DIR_TMP)

def byPage(a,b):
    """compare: if both fields are numeric or num-num sort numeric, alphabetic otherwise"""
    aa = re.sub('^ *(\d+) *- *\d+ *$',r'\1',a)
    bb = re.sub('^ *(\d+) *- *\d+ *$',r'\1',b)
    try:
        c = cmp(int(aa),int(bb))
    except:
        c = cmp(a,b)
    return c

def read_pages(page_filename):
    """Read from file
    article-ids should not contain spaces or underscores
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
    """
    page_offset = 0
    add_pages = True
    page_ranges = {}
    if not page_filename:
        return page_ranges, add_pages

    page_file = open(page_filename)
    for line in page_file.readlines():
        if line.startswith('#'):
            get_page_offset = re.search(r'^# *offset *= *(-?\d+)', line.lower())
            if get_page_offset:
                page_offset = int(get_page_offset.group(1))
            if re.search(r'# *nopage', line.lower()):
                add_pages = False
        else:
            line = re.sub(r' +', ' ', line)
            page_info = line.strip().split(' ', 1)
            cut_page = page_info[0]
            if cut_page.find('-') < 0:
                continue

            artid = cut_page
            if page_offset != 0:
                try:
                    cut_page = '-'.join([str(int(page) + page_offset)  for page in cut_page.split('-')])
                except:
                    cut_page = 'FAILED-%s' % cut_page
            if len(page_info) > 1:
                artid = page_info[1]
            page_ranges[artid] = cut_page
    page_file.close()
    return page_ranges, add_pages


def extract_pages(pdf_filename, cut_page, for_grobid, out_filename):
    """ replacement for pdftk """
    (first_page, last_page) = cut_page.split('-')

    command = 'pdfseparate -f %s -l %s %s %s/' % (first_page, last_page, pdf_filename, DIR_TMP) + 'extracted_%d.pdf'
    os.system(command)
    pages = range(int(first_page), int(last_page)+1)
    files = ['%s/extracted_%s.pdf' % (DIR_TMP, page) for page in pages]
    command = 'pdfunite %s %s/%s' % (' '.join(files) , for_grobid, out_filename)
    os.system(command)
    os.system('rm %s' % ' '.join(files))

def convert_version(pdf_filename):
    """ to avoid error from pdfunite, convert pdf to v1.4 if necessary """
    import pdfinfo
    pdf_info = pdfinfo.pdfinfo(pdf_filename)
    version = pdf_info['PDF version']
    if version and float(version) > 1.5:
        old_filename = pdf_filename.replace(".pdf", "_original.pdf")
        os.rename(pdf_filename, old_filename)
        command = "gs -sDEVICE=pdfwrite -dCompatibilityLevel=1.4 -o %s %s" % (pdf_filename, old_filename)
        os.system(command)
    
    
def cut_pdf(pdf_filename, page_filename, working_dir=None):
    """
    cut fulltext in contributions according to pdf_filename
    store pieces in working_dir, default is fname_for_grobid where fname is taken from pdf_filename
    """

    if not os.path.isfile(pdf_filename):
        print "Error: can't find fulltext pdf %s\n" % pdf_fulltext
        exit()

    convert_version(pdf_filename)
    
    basename = os.path.basename(pdf_filename)
    basename = re.sub('[-_]?fulltext', '', os.path.splitext(basename)[0])
    if not working_dir:
        for_grobid = os.path.join(os.path.dirname(pdf_filename), '%s_for_grobid' % basename)
    else:
        for_grobid = working_dir
    if not os.path.isdir(for_grobid):
        os.mkdir(for_grobid)

    cut_files = []
    page_ranges, nopages = read_pages(page_filename)
    artids = page_ranges.keys()
    artids.sort(byPage)
    for artid in artids:
        cut_page = page_ranges[artid]
        out_filename = '%s_%s.pdf' % (basename, artid)
        cut_files.append(out_filename)
        print 'split %s pages %s to %s/%s' % (pdf_filename, cut_page, for_grobid, out_filename)
        extract_pages(pdf_filename, cut_page, for_grobid, out_filename)

    print 'Extracted %s pdf files into directory\n%s\n' % (len(cut_files), for_grobid)

    spurious_files = []
    for gfile in os.listdir(for_grobid):
        if os.path.splitext(gfile)[1].lower() == '.pdf' and gfile not in cut_files:
            spurious_files.append(gfile)
    if spurious_files:
        print 'WARNING: additional file(s) in grobid directory:'
        print for_grobid
        for gfile in spurious_files:
            print gfile

def main(argv):
    "main function"
    helptext = "Usage: cutpdf_for_grobid.py -f pdf_filename -p page_filename\nBoth arguments needed"
    pdf_filename = ''
    page_filename = ''
    try:
        opts, args = getopt.getopt(argv, "f:p:", ["pdf_filename=", "page_filename="])
    except getopt.GetoptError:
        print(helptext)
        sys.exit(2)
    for opt, arg in opts:
        if opt in ("-f", "--pdf_filename"):
            pdf_filename = arg
        elif opt in ("-p", "--page_filename"):
            page_filename = arg

    if pdf_filename and page_filename:
        cut_pdf(pdf_filename, page_filename)
    else:
        print helptext


if __name__ == "__main__":
    main(sys.argv[1:])
