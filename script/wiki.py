#!/bin/usr/python3
"""
This script/library takes care of converting the
trac-wiki syntax into MarkDown
"""

import re
import hashlib

def hash(text):
    algo = hashlib.sha256()
    algo.update(bytes(text, 'utf-8'))
    return algo.hexdigest()


class WikiConverter(object):
    _re_code = re.compile(r'((?<!\\)`)(?P<code>.+)((?<!\\)`)', re.IGNORECASE | re.MULTILINE | re.UNICODE)
    _re_codeblock = re.compile(r'(?:(?<!\\)\{){3}([\r\n\s]*\#\!(?P<shebang>[ \w\=\"\']+)$)?(?P<code>.*?)(?:(?<!\\)\}){3}', re.IGNORECASE | re.MULTILINE | re.DOTALL | re.UNICODE)
    _re_text_style = re.compile(r'(?P<prefix>(?:(?:(?<!\\)\'){2,3}){1,2})(?P<text>.*?)(?P=prefix)', re.IGNORECASE | re.MULTILINE | re.DOTALL | re.UNICODE)
    _re_headlines = re.compile(r'^(?P<level>((?<!\\)=)+)\s*(?P<title>[^=]+)\s*(?P=level)\s*$', re.IGNORECASE | re.MULTILINE | re.UNICODE)
    _re_marked_links = re.compile(r'(?=[^\!]|^)\[{1,2}(?:(?P<macro>\w+)\()?(?P<link>[^ |\[\]]+)(?(macro)\))(?:[ |](?P<name>[\s\w]+?))?\]{1,2}', re.IGNORECASE | re.MULTILINE | re.UNICODE)
    _re_inline_links = re.compile(r'(?:(?<![\!\(\[])|^)(?#target)(?:(?P<target>[a-zA-Z0-9\-_]+):)??(?# target end / link type)(?:(?P<linktype>wiki|ticket|report|changeset|source):)?(?# type end / actual name w/ opt dbl quotes)(?P<quoting>\"?)(?P<name>(?(linktype)[a-zA-Z0-9\-_#\/]+|(?:[A-Z#][a-z0-9\-_#\/]+){2,}))+(?P=quoting)', re.MULTILINE | re.UNICODE)
    _re_breaklines = re.compile(r'(?:[^\!]|^)(\\{2}|\[{2}br\]{2})', re.IGNORECASE | re.MULTILINE | re.UNICODE)
    _re_code_placeholder = re.compile(r'%%%%%%%%{(?P<hash>[a-f0-9]+)}%%%%%%%%', re.IGNORECASE | re.MULTILINE | re.UNICODE)


    def __init__(self, pages={}, prefixes={}):
        # map with names of all the other wiki pages
        self.pages = pages
        # map with names of other tracs as key
        # to remap inter-trac links
        self.prefixes = prefixes

        # map to store code blocks in, so they are not altered by the other commands
        self.mask_map = {}

    def convert(self, text):

        text = self._mask_code(text)
        text = self._convert_marked_links(text)
        text = self._convert_inline_links(text)
        text = self._convert_text_style(text)
        text = self._convert_headlines(text)
        text = self._convert_breaklines(text)
        text = self._convert_code(text)

        return text

    def _mask_code(self, text):
        """
        masks code sections
        Returns: text
        """

        text = self._re_codeblock.sub(self._callback_mask_code, text)
        return self._re_code.sub(self._callback_mask_code, text)

    def _callback_mask_code(self, match):
        try:
            shebang = match.group('shebang')
        except:
            shebang = None

        code = match.group('code')
        code_id = hash(code)
        while( code_id in self.mask_map ):
            # recalc a new code_id
            code_id = hash(code_id + '_')

        # store orginal code in map
        self.mask_map[code_id] = {
                'code': code,
                'shebang': shebang,
            }

        # return palceholder
        return '%%%%%%%%{{{hash}}}%%%%%%%%'.format(hash=code_id)

    def _convert_code(self, text):

        return self._re_code_placeholder.sub(self._callback_convert_code, text)

    def _callback_convert_code(self, match):

        if match.group('hash') not in self.mask_map:
            return match.group('0')

        code = self.mask_map[match.group('hash')]
        if not code['shebang']:
            # "normal" code block
            return '```{code}```'.format(code=code['code'])
        else:
            # code block w/ shebang
            return '```{shebang}\n{code}\n```'.format(code=code['code'], shebang=code['shebang'])

    def _convert_inline_links(self, text):

        return self._re_inline_links.sub(self._callback_inline_links, text)

    def _callback_inline_links(self, match):
        # TODO take special care of Issue links (#1234) and changesets/commits (?)
        groups = match.groupdict()
        if 'escape' in groups and groups['escape']:
            # link is escaped, return it just without the leading '!'
            return match.group(0)[len(groups['escape']):]
        else:
            return "{prefix}{link_type}/{link}".format(
                    prefix=self.prefixes.get(groups.get('target', None), ''),
                    link_type=groups.get('type', ''),
                    link=groups.get('name', ''),
                )

    def _convert_marked_links(self, text):

        return self._re_marked_links.sub(self._callback_marked_links, text)

    def _callback_marked_links(self, match):
        groups = match.groupdict()
        if 'macro' in groups and groups['macro']:
            # handle at least image macros
            if groups['macro'].lower() == 'image':
                return '![{title}]({link})'.format(
                                            title=groups.get('name', 'image'),
                                            link=groups['link'] )
            else:
                # some kind of special macro, we just return the original text
                return match.group(0)
        elif 'name' not in groups:
            # hanlde simple marked links w/o a name
            # links, that are not named do not need special escaping
            return self._convert_inline_links(groups['link'])
        else:
            # handle named marked links
            return '[{name}]({link})'.format(
                name=groups.get('name', groups['link']),
                link=self._convert_inline_links(groups['link']))

    def _convert_text_style(self, text):

        return self._re_text_style.sub(self._callback_text_style, text)

    def _callback_text_style(self, match):

        prefix_len = len(match.group('prefix'))
        if prefix_len == 2:
            # italic
            return '*{text}*'.format(text=match.group('text'))
        elif prefix_len == 3:
            # bold
            return '**{text}**'.format(text=match.group('text'))
        elif prefix_len == 5:
            return '**_{text}_**'.format(text=match.group('text'))

    def _convert_headlines(self, text):

        return self._re_headlines.sub(self._callback_headlines, text)

    def _callback_headlines(self, match):

        level = len(match.group('level'))
        if level == 1:
            # top level headline -> use underlining with equal signs (=)
            return '{title}\n{level}'.format(title=match.group('title'), level='='*len(match.group('title')))
        elif level == 2:
            # second level headline -> underline with minus (-)
            return '{title}\n{level}'.format(title=match.group('title'), level='-'*len(match.group('title')))
        else:
            # lower level -> use prefix with pound sign (#)
            return '{level} {title}'.format(title=match.group('title'), level='#'*level)

    def _convert_breaklines(self, text):

        return self._re_breaklines.sub('\n\n', text)


if __name__ == '__main__':
    # called as standalone script
    converter = WikiConverter()

    # read piped text from stdin
    import sys
    import time

    if len(sys.argv) >= 2:
        with open(sys.argv[1], 'r') as fs:
            wiki_text = fs.read()
    else:
        buff = sys.stdin.readlines()
        wiki_text = ''.join(buff)

    sys.stdout.write(wiki_text)
    sys.stdout.write('\n\n -------- \n\n')
    sys.stdout.write(converter.convert(wiki_text))

