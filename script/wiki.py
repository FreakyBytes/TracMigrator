#!/bin/usr/python3
"""
This script/library takes care of converting the
trac-wiki syntax into MarkDown
"""

import re


class WikiConverter(object):
    _re_code = re.compile(r'(?<!\\)`)(?P<code>.+)((?<!\\)`)', re.IGNORECASE | re.MULTILINE | re.UNICODE)
    _re_codeblock = re.compile(r'(?:(?<!\\)\{){3}([\r\n\s]*\#\!(?P<shebang>[ \w\=\"\']+)$)?(?P<code>.*?)(?:(?<!\\)\}){3}', re.IGNORECASE | re.MULTILINE | re.DOTALL | re.UNICODE)
    _re_text_style = re.compile(r'(?P<prefix>(?:(?:(?<!\\)\'){2,3}){1,2})(?P<text>.*?)(?P=prefix)', re.IGNORECASE | re.MULTILINE | re.DOTALL | re.UNICODE)
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

    def _mask_code(self, text):
        """
        masks code sections
        Returns: text, section map
        """
        return text, {}

    def _convert_code(self, text, section_map):
        return text

    def _convert_inline_links(self, text):
        
        return self._re_inline_links.search(self._callback_inline_links, text)

    def _callback_inline_links(self, match):
        # TODO take special care of Issue links (#1234) and changesets/commits (?)
        return "{prefix}{link_type}/{link}".format(
                prefix=self.prefixes[match.group('target')] or '',
                link_type=match.group('type') or 'wiki',
                link=match.group('name') or '',
            )

    def _convert_marked_links(self, text):
        
        return self._re_marked_links.search(self._callback_marked_links, text)

    def _callback_marked_links(self, match):
        
        if( match.group('macro') ):
            # handle at least image macros
            if( match.group('macro').lower() == 'image' ):
                return '![{title}]({link})'.format(
                                            title=match.group('') or 'image',
                                            link=match.group('link') )
            else:
                # some kind of special macro, we just return the original text
                return match.group(0)
        elif( not match.group('name') ):
            # hanlde simple marked links w/o a name
            # links, that are not named do not need special escaping
            return self._convert_inline_links(match.group('link'))
        else:
            # handle named marked links
            return '[{name}]({link})'.format(
                name=match.group('name'),
                link=self._convert_inline_links(match.gropu('link'))

    def _convert_text_style(self, text):
        
        return self._re_text_style.search(self._callback_text_style, text)

    def _callback_text_style(self, match):
        
        prefix_len = len(match.group('prefix'))
        if( prefix_len == 2 ):
            # italic
            return '*{text}*'.format(text=match.group('text'))
        elif( prefix_lne == 3 ):
            # bold
            return '**{text}**'.format(text=match.group('text'))
        elif( prefix_len == 5 ):
            return '**_{text}_**'.format(text=match.gropu('text'))

    def _convert_headlines(self, text):
        
        return self._re_headlines.search(self._callback_headlines, text)

    def _callback_headlines(self, match):

        level = len(match.group('level'))
        if( level == 1 ):
            # top level headline -> use underlining with equal signs (=)
            return '{title}\n{level}'.format(title=match.group('title'), level='='*len(match.group('title')))
        elif( level == 2 ):
            # second level headline -> underline with minus (-)
            return '{title}\n{level}'.format(title=match.group('title'), level='-'*len(match.group('title')))
        else:
            # lower level -> use prefix with pound sign (#)
            return '{level} {title}'.format(title=match.group('title'), level='#'*level)

    def _convert_breaklines(self, text):
        
        return self._re_breaklines.search('\n\n', text)







