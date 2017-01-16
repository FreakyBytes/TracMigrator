#!/usr/bin/python3
"""
module containing all bits and pieces to interact with the trac JSON-RPC api/interface
"""

import logging
import requests
import json
import urllib.parse as urlparse
from datetime import datetime
import base64
import re

# regex to match all environment links, shown in the trac base url
_re_env_list = re.compile(r'<a href=\"(?P<link>[\w\d\/\-_]+)\"(?:.*?)(?:title=\"(?P<title>[\w\d\-_ ]+)\")(?:.*?)>(?:\s*)(?P<text>.+?)(?:\s*)</a>', re.IGNORECASE | re.MULTILINE | re.DOTALL | re.UNICODE)

class TracError(Exception):
    
    def __init__(self, message, *args, **kwargs):
        super(Exception, self).__init__(message, *args, **kwargs)


def listTracEnvironments(base_url, timeout=15):
    
    r = requests.get(base_url, timeout=timeout, stream=True)

    if not r:
        raise TracError('HTTP response object is None')
    if r.status_code != 200:
        raise TracError('Unexpected HTTP status code {code}: {msg}'.format(code=r.status_code, msg=r.reason))

    try:
        for match in _re_env_list.finditer(r.text):
            yield {
                'trac_id': match.group('text'),
                'name': match.group('title') or None,
                'url': match.group('link'),
                'github_project': None,
                'git_repository': None,
                'enabled': True,
            }

        r.close()
    except BaseException as e:
        raise TracError('Exception while parsing environment list', e)


class Trac(object):
    
    def __init__(self, base_url, trac_id, user=None, password=None, timeout=5):
        self.base_url = base_url
        self.trac_id = trac_id
        self.trac_url = urlparse.urljoin(self.base_url, self.trac_id) + '/'
        self.user = user
        self.password = password
        self.rpc_url = urlparse.urljoin(self.trac_url, 'login/jsonrpc' if self.user else 'jsonrpc')
        self.timeout = timeout

        self.log = logging.getLogger('trac.{id}'.format(id=self.trac_id))

    def _call(self, endpoint, *args):
        """
        makes a JSON-RPC to trac
        """
        data = {
                'method': endpoint,
                'params': args,
            }
        
        self.log.debug("Query {endpoint}({args})".format(endpoint=endpoint, args=', '.join(str(args))))
        r = requests.post(
                    self.rpc_url,
                    json={
                        'method': endpoint,
                        'params': args if args else [],
                    },
                    headers={
                        'Content-Type': 'application/json',
                        'Accept': 'application/json'
                    },
                    auth=(self.user, self.password) if self.user else None,
                    allow_redirects=True,
                    stream=True,
                    timeout=self.timeout,
                )

        if not r:
            self.log.error('HTTP response object is None')
            raise TracError('HTTP response object is None')

        if r.status_code != 200:
            self.log.error('Unexpected HTTP status code {code}: {msg}'.format(code=r.status_code, msg=r.reason))
            raise TracError('Unexpected HTTP status code {code}: {msg}'.format(code=r.status_code, msg=r.reason))

        # normal JSON parsing - no binary result expected
        try:
            result = r.json()
            r.close()

            if result['error'] is not None:
                # error handling
                error_msg = 'Trac error, while calling {endpoint}({args}): {msg}'.format(endpoint=endpoint, args=', '.join(str(args)), msg=result['error']['message'])
                self.log.error(error_msg)
                raise TracError(error_msg)

            # everything ok
            self.log.debug('Query ok')
            return result['result']
        except ValueError as e:
            raise TracError("Result is no valid JSON", e)


    def convertClassHint(self, hint):
        if not isinstance(hint, dict):
            raise TracError('Class Hint is expected to be a map')

        if not '__jsonclass__' in hint:
            raise TracError('No Class Hint found')

        if hint['__jsonclass__'][0] == 'datetime':
            # let's parse datetime!
            return datetime.strptime(hint['__jsonclass__'][1], '%Y-%m-%dT%H:%M:%S')
        elif hint['__jsonclass__'][0] == 'binary':
            # let's decode BASE64!
            print(hint['__jsonclass__'][1])
            return base64.b64decode(hint['__jsonclass__'][1])

    def listWikiPages(self):
        return self._call('wiki.getAllPages')

    def getWikiPageText(self, pagename):
        return self._call('wiki.getPage', pagename)

    def listWikiAttachements(self, pagename):
        return self._call('wiki.listAttachments', pagename)

    def getWikiAttachement(self, path):
        return self.convertClassHint(self._call('wiki.getAttachment', path))

    def queryTickets(self, query):
        return self._call('ticket.query', query)

    def listTickets(self):
        ticket_list = self.queryTickets('max=0')
        if ticket_list and isinstance(ticket_list, (list, tuple)):
            ticket_list.sort()

        return ticket_list

    def getTicket(self, ticket_id):
        ticket = self._call('ticket.get', ticket_id)
        if not ticket or not isinstance(ticket, (list, tuple)):
            raise TracError('Got unexpected datatype back')
        
        # only return necessary information
        result = {
            'ticket_id': ticket[0],
            'time_created': self.convertClassHint(ticket[1]),
            'time_changed': self.convertClassHint(ticket[2]),
            'attributes': ticket[3],
        }
        if 'changetime' in result['attributes']:
            result['attributes']['changetime'] = self.convertClassHint(result['attributes']['changetime'])
        if 'time' in result['attributes']:
            result['attributes']['time'] = self.convertClassHint(result['attributes']['time'])

        return result

    def getTicketChangeLog(self, ticket_id):
        change_log = self._call('ticket.changeLog', ticket_id)

        # convert dates into datetime objects and the single entries into a map
        result = []
        for log_entry in change_log:
            result.append({
                'time': self.convertClassHint(log_entry[0]),
                'author': log_entry[1],
                'field': log_entry[2],
                'old_value': log_entry[3],
                'new_value': log_entry[4],
                'permanent': True if log_entry[5] == 1 else False,
            })

        return result

