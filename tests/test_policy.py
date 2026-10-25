from nexus.openapi import extract_operations
from nexus.policy import assess_operation


def test_sensitive_write_requires_approval():
    doc = {'openapi': '3.0.3', 'servers': [{'url': 'https://example.com'}], 'paths': {'/admin/delete': {'delete': {'summary': 'Delete'}}}}
    assessment = assess_operation(extract_operations(doc)[0], doc)
    assert assessment['risk_level'] == 'high'
    assert 'state_changing_method' in assessment['risk_flags']
    assert assessment['executable'] is False


def test_private_ip_flagged():
    doc = {'openapi': '3.0.3', 'servers': [{'url': 'https://127.0.0.1'}], 'paths': {'/items': {'get': {}}}}
    assessment = assess_operation(extract_operations(doc)[0], doc)
    assert 'non_public_ip' in assessment['risk_flags']


def test_safe_read_still_not_executable():
    doc = {'openapi': '3.0.3', 'servers': [{'url': 'https://example.com'}], 'security': [{'apiKey': []}], 'paths': {'/items': {'get': {}}}}
    assessment = assess_operation(extract_operations(doc)[0], doc)
    assert assessment['risk_level'] == 'low'
    assert assessment['requires_explicit_approval']

