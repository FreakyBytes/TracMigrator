#!/bin/usr/python3
"""
This script/library takes care of converting the
trac-wiki syntax into MarkDown
"""

import re


class WikiConverter(object):
    _re_code = re.compile(r'(?<!\\)`)(?P<code>.+)((?<!\\)`)', re.IGNORECASE | re.MULTILINE | re.UNICODE)
    _re_codeblock = re.compile(r'(?:(?<!\\)\{){3}([\r\n\s]*\#\!(?P<shebang>[ \w\=\"\']+)$)?(?P<code>.*?)(?:(?<!\\)\}){3}', re.IGNORECASE | re.MULTILINE | re.DOTALL | re.UNICODE)
    _re_text_style = re.compile(r'(?P<prefix>(?:(?:(?<!\\)\'){2,3}){1,2})(?P<bold>.*?)(?P=prefix)', re.IGNORECASE | re.MULTILINE | re.DOTALL | re.UNICODE)
    _re_headlines = re.compile(r'^(?P<level>((?<!\\)=)+)\s*(?P<title>[^=]+)\s*(?P=level)\s*$', re.IGNORECASE | re.MULTILINE | re.UNICODE)
    _re_marked_links = re.compile(r'(:P[^\!]|^)\[{1,2}(?:(?P<macro>\w+)\()?(?P<link>[^ |\[\]]+)(?(macro)\))(?:[ |](?P<name>[\s\w]+?))?\]{1,2}', re.IGNORECASE | re.MULTILINE | re.UNICODE)
    _re_inline_links = re.compile(r'(?:[^\!]|^)(?#target)(?:(?P<target>[a-zA-Z0-9-_]+):)??(?# target end / link type)(?:(?P<linktype>wiki|ticket|report|changeset):)?(?# type end / actual name w/ opt dbl quotes)(?P<quoting>\"?)(?P<name>(?(linktype)[a-zA-Z0-9-_#]+|(?:[A-Z#][a-z0-9-_#]+){2,}))+(?P=quoting)', re.IGNORECASE | re.MULTILINE | re.UNICODE)
    _re_break_line = re.compile(r'(?:[^\!]|^)(\\{2}|\[{2}br\]{2})', re.IGNORECASE | re.MULTILINE | re.UNICODE)
    

    def __init__(self, pages={}, prefixes={}):
        # map with names of all the other wiki pages
        self.pages = pages
        # map with names of other tracs as key
        # to remap inter-trac links
        self.prefixes = prefixes

    def convert(self, text):
        pass

    def _convert_inline_links(self, text):
        
        return self._re_inline_link.(self_callback_inline_links, text)

    def _callback_inline_links(self, match):
        
        return "{prefix}{link_type}/{link}".format(
                prefix=self.prefixes[match.group('target')] or '',
                link_type=match.group('type') or 'wiki',
                link=match.group('name') or '',
            )





