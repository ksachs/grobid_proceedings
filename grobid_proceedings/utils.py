# -*- coding: utf-8 -*-
#
# This file is part of INSPIRE.
# Copyright (C) 2015, 2016 CERN.
#
# INSPIRE is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License as
# published by the Free Software Foundation; either version 2 of the
# License, or (at your option) any later version.
#
# INSPIRE is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with INSPIRE; if not, write to the Free Software Foundation, Inc.,
# 59 Temple Place, Suite 330, Boston, MA 02111-1307, USA.

"""DoJSON related utilities."""

import six

import re

def encode_for_xml(text, wash=False, xml_version='1.0', quote=False):
    """Encode special characters in a text so that it would be XML-compliant.
    :param text: text to encode
    :return: an encoded text
    """
    text = text.replace('&', '&amp;')
    text = text.replace('<', '&lt;')
    if quote:
        text = text.replace('"', '&quot;')
    if wash:
        text = wash_for_xml(text, xml_version=xml_version)
    return text

try:
    unichr(0x100000)
    RE_ALLOWED_XML_1_0_CHARS = re.compile(
        u'[^\U00000009\U0000000A\U0000000D\U00000020-'
        u'\U0000D7FF\U0000E000-\U0000FFFD\U00010000-\U0010FFFF]')
    RE_ALLOWED_XML_1_1_CHARS = re.compile(
        u'[^\U00000001-\U0000D7FF\U0000E000-\U0000FFFD\U00010000-\U0010FFFF]')
except ValueError:
    # oops, we are running on a narrow UTF/UCS Python build,
    # so we have to limit the UTF/UCS char range:
    RE_ALLOWED_XML_1_0_CHARS = re.compile(
        u'[^\U00000009\U0000000A\U0000000D\U00000020-'
        u'\U0000D7FF\U0000E000-\U0000FFFD]')
    RE_ALLOWED_XML_1_1_CHARS = re.compile(
        u'[^\U00000001-\U0000D7FF\U0000E000-\U0000FFFD]')


def wash_for_xml(text, xml_version='1.0'):
    """Remove any character which isn't a allowed characters for XML.
    The allowed characters depends on the version
    of XML.
        - XML 1.0:
            <http://www.w3.org/TR/REC-xml/#charsets>
        - XML 1.1:
            <http://www.w3.org/TR/xml11/#charsets>
    :param text: input string to wash.
    :param xml_version: version of the XML for which we wash the
        input. Value for this parameter can be '1.0' or '1.1'
    """
    if xml_version == '1.0':
        return RE_ALLOWED_XML_1_0_CHARS.sub(
            '', unicode(text, 'utf-8')).encode('utf-8')
    else:
        return RE_ALLOWED_XML_1_1_CHARS.sub(
            '', unicode(text, 'utf-8')).encode('utf-8')


def legacy_export_as_marc(json, tabsize=4, no_empty_fields=True):
    """Create the MARCXML representation using the producer rules."""

    def encode_for_marcxml(value):
        #from invenio_utils.text import encode_for_xml  # FIXME: is this really needed? Investigate!
        if not value:
            value = ""
        if isinstance(value, unicode):
            value = value.encode('utf8')
        return encode_for_xml(str(value), wash=True)

    export = ['<record>\n']

    for key, value in sorted(six.iteritems(json)):
        if no_empty_fields and not value:
            continue
        if key.startswith('00') and len(key) == 3:
            # Controlfield
            if isinstance(value, list):
                value = value[0]
            export += ['\t<controlfield tag="%s">%s'
                       '</controlfield>\n'.expandtabs(tabsize)
                       % (key, encode_for_marcxml(value))]
        else:
            tag = key[:3]
            try:
                ind1 = key[3].replace("_", "")
            except:
                ind1 = ""
            try:
                ind2 = key[4].replace("_", "")
            except:
                ind2 = ""
            if isinstance(value, dict):
                value = [value]
            for field in value:
                export += ['\t<datafield tag="%s" ind1="%s" '
                           'ind2="%s">\n'.expandtabs(tabsize)
                           % (tag, ind1, ind2)]
                if field:
                    for code, subfieldvalue in six.iteritems(field):
                        if subfieldvalue or not no_empty_fields:
                            if isinstance(subfieldvalue, list):
                                for val in subfieldvalue:
                                    export += ['\t\t<subfield code="%s">%s'
                                               '</subfield>\n'.expandtabs(tabsize)
                                               % (code, encode_for_marcxml(val))]
                            else:
                                export += ['\t\t<subfield code="%s">%s'
                                           '</subfield>\n'.expandtabs(tabsize)
                                           % (code,
                                              encode_for_marcxml(subfieldvalue))]
                export += ['\t</datafield>\n'.expandtabs(tabsize)]
    export += ['</record>\n']
    return "".join(export)


def create_profile_url(profile_id):
    """Create HEP author profile link based on the profile_id."""
    base_url = 'http://inspirehep.net/record/'

    try:
        int(profile_id)
        return base_url + str(profile_id)
    except (TypeError, ValueError):
        return ''


def strip_empty_values(obj):
    """Recursively strips empty values."""
    if isinstance(obj, dict):
        for key, value in obj.items():
            value = strip_empty_values(value)
            if value or value is False or value == 0:
                obj[key] = value
            else:
                del obj[key]
        return obj
    elif isinstance(obj, (list, tuple, set)):
        new_obj = [strip_empty_values(v) for v in obj]
        new_obj = [v for v in new_obj if v or v is False or v == 0]
        return type(obj)(new_obj)
    else:
        return obj


def remove_duplicates_from_list(l):
    """Remove duplicates from a list preserving the order.

    We might be tempted to use the list(set(l)) idiom,
    but it doesn't preserve the order, which hinders
    testability."""
    result = []

    for el in l:
        if el not in result:
            result.append(el)

    return result


def remove_duplicates_from_list_of_dicts(ld):
    """Remove duplicates from a list of dictionaries preserving the order.

    We can't use the generic list helper because a dictionary isn't
    hashable. Taken from http://stackoverflow.com/a/9427216/374865."""
    result = []
    seen = set()

    for d in ld:
        t = tuple(d.items())
        if t not in seen:
            result.append(d)
            seen.add(t)

    return result

def has_numbers(text):
    """Detects if a string contains numbers"""
    return any(char.isdigit() for char in text)

def handle_initials(given_names):
    """Adds a dot after every initial."""
    split_names = given_names.split()
    if split_names > 1:
        initials = []
        split_names = [i.strip(".") for i in split_names]
        for name in split_names:
            if len(name) == 1:
                initials.append(name + ".")
            else:
                initials.append(name)
        return " ".join(initials)
    else:
        return given_names

def split_fullname(author, surname_first=True):
    """Split an author name to surname and given names.

    It accepts author strings with and without comma separation
    and surname can be first or last. Note that multi-part surnames are incorrectly
    detected in strings without comma separation.
    """
    if not author:
        return "", ""

    if "collaboration" in author.lower():
        return author, ""

    if has_numbers(author):
        # Remove artifacts from superscript commands
        author = "".join(
            [char for char in author if not char.isdigit() and char != "@"]
            ).replace("bullet", "")

    author = author.strip("' ")
    if not author:
        return "", ""

    if "," in author:
        fullname = [n.strip() for n in author.split(',')]
    else:
        fullname = [n.strip() for n in author.split()]

    if surname_first:
        surname = fullname[0]
        given_names = " ".join(fullname[1:])
    else:
        surname = fullname[-1]
        given_names = " ".join(fullname[:-1])

    given_names = handle_initials(given_names)


    return surname, given_names
