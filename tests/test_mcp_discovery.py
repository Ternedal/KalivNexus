import json
import pytest
from nexus.mcp_discovery import discover_tools

class Transport:
    def __init__(self, pages):
        self.pages = pages
        self.requests = []
    def exchange(self, payload):
        request = json.loads(payload)
        self.requests.append(request)
        response = self.pages[len(self.requests)-1]
        return 200, 'application/json', json.dumps({'jsonrpc':'2.0','id':request['id'],'result':response}).encode()

def test_one_page():
    t = Transport([{'tools':[{'name':'weather','inputSchema':{'type':'object'}}]}])
    result = discover_tools(t)
    assert result['count'] == 1 and result['pages'] == 1
    assert not result['executable'] and not result['approved']
    assert t.requests[0]['method'] == 'tools/list'

def test_paginated():
    t = Transport([{'tools':[{'name':'a'}], 'nextCursor':'next'}, {'tools':[{'name':'b'}]}])
    assert discover_tools(t)['count'] == 2
    assert t.requests[1]['params']['cursor'] == 'next'

def test_duplicate_rejected():
    t = Transport([{'tools':[{'name':'a'}], 'nextCursor':'next'}, {'tools':[{'name':'a'}]}])
    with pytest.raises(ValueError, match='Duplicate'):
        discover_tools(t)

def test_cursor_cycle_rejected():
    t = Transport([{'tools':[], 'nextCursor':'x'}, {'tools':[], 'nextCursor':'x'}])
    with pytest.raises(ValueError, match='cursor'):
        discover_tools(t)

def test_page_limit_rejected():
    t = Transport([{'tools':[], 'nextCursor':'x'}])
    with pytest.raises(ValueError, match='page limit'):
        discover_tools(t, max_pages=1)

def test_invalid_page_limit():
    with pytest.raises(ValueError):
        discover_tools(Transport([]), max_pages=0)

def test_invalid_schema():
    with pytest.raises(ValueError):
        discover_tools(Transport([{'tools':[{'name':'x','inputSchema':{'type':'string'}}]}]))
