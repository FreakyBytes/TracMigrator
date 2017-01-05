#!/usr/bin/python3
"""
module containing all bits and pieces to interact with the trac JSON-RPC api/interface
"""

import logging
import requests
import json
import urllib.parse as urlparse

class TracError(Exception):
    
    def __init__(self, message, *args, **kwargs):
        super(Exception, self).__init__(message, *args, **kwargs):


class Trac(object):
    
    def __init__(self, base_url, trac_id, user=None, password=None, timeout=5):
        self.base_url = base_url
        self.trac_id = trac_id
        self.trac_url = urlparse.urljoin(self.base_url, self.trac_id)
        self.user = user
        self.password = password
        self.rpc_url = urlparse.urljoin(self.trac_url, 'login/jsonrpc' if self.user else 'jsonrpc')
        self.timeout = timeout

        self.log = logging.getLogger('trac.{id}'.format(id=self.trac_id)

    def _call(self, endpoint, *args):
        """
        makes a JSON-RPC to trac
        """
        data = {
                'method': endpoint,
                'params': args,
            }
        
        self.log.debug("Query {endpoint}({args})".format(endpoint=endpoint, args=', '.join(args))
        r = requests.post(
                    self.rpc_url,
                    json={
                        'method': endpoint,
                        'params': args if args else [],
                    },
                    headers={'Content-Type': 'application/json'},
                    auth=(self.user, self.password) if self.user else None,
                    allow_redirects=True,
                    timeout=self.timeout,
                )

        if not r:
            self.log.error('HTTP response object is None'
            raise TracError('HTTP response object is None')

        if r.status_code != 200:
            self.log.error('Unexpected HTTP status code {code}: {msg}'.format(code=r.status_code, msg=r.reason)
            raise TracError('Unexpected HTTP status code {code}: {msg}'.format(code=r.status_code, msg=r.reason)

        try:
            result = r.json()
            if result['error'] not None:
                # error handling
                error_msg = 'Trac error, while calling {endpoint}({args}): {msg}'.format(endpoint=endpoint, args=', '.join(args), msg=result['error']['message']
                self.log.error(error_msg)
                raise TracError(error_msg)

            # everything ok
            self.log.debug('Query ok')
            return result['result']
        except ValueError as e:
            raise TracError("Result is no valid JSON", e)

    def listWikiPages(self):
        return self._call('wiki.getAllPages')

    def getWikiPageText(self, pagename):
        return self._call('wiki.getPage', pagename)

    def listWikiAttachements(self, pagename):
        return self._call('wiki.listAttachments', pagename)

    def getWikiAttachement(self, path):
        return self._call('wiki.getAttachment', path)

        

