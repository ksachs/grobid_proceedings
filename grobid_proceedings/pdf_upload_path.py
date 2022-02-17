# -*- coding: utf-8 -*-import re
#
# Files for grobid are stored under afs/eos
# Upload to INSPIRE via URL
# Here you can define which path should be used and what is the corresponding URL

import os
import re

THISLAB = os.uname()[1].split('.')[1].lower()

def dir_pdf(dir_home):
    """
    Directory hosting personal web-page, default is dir_home
    CERN: /eos/home-s/sachs/www/for_grobid/
    DESY: /afs/desy.de/user/s/sachs/www/for_grobid/
    """
    user = os.getlogin()
    if THISLAB == 'cern':
        grobid_dir = '/eos/home-%s/%s/www/for_grobid/' % (user[0], user)
    elif THISLAB == 'desy':
        grobid_dir = '/afs/desy.de/user/%s/%s/www/for_grobid/' % (user[0], user)
    else:
        grobid_dir = dir_home
    return grobid_dir
    
def pdf_url(pdf_path):  
    """ Return URL for path. Keep path as default """
    
    if THISLAB == 'cern':
        url = re.sub(r'^/eos/home-./([a-z]+)/www/', r'https://\1.web.cern.ch/', pdf_path)        
    elif THISLAB == 'desy':
        url = re.sub(r'^/afs/desy.de/user/./([a-z]+)/www/',r'https://www.desy.de/~\1/', pdf_path)        
    else:
        url = pdf_path
    return url