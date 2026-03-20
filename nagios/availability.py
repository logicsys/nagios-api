#!/usr/bin/env python3

'''Nagios availability report fetcher.

Fetches availability data from Nagios CGI (avail.cgi) and parses the
HTML response into structured data.
'''

import logging
import threading
import time

import requests
from bs4 import BeautifulSoup
from lxml import etree

log = logging.getLogger('nagios-api')

_cache = {}
_CACHE_LOCK = threading.Lock()
_CACHE_TTL = 60
_CACHE_MAX = 500


def _cache_key(cgi_url, host, service, start_ts, end_ts):
    return (cgi_url, host, service, int(start_ts), int(end_ts))


def _cache_get(key):
    with _CACHE_LOCK:
        entry = _cache.get(key)
        if entry and (time.time() - entry[1]) < _CACHE_TTL:
            return entry[0]
    return None


def _cache_put(key, value):
    with _CACHE_LOCK:
        if len(_cache) >= _CACHE_MAX:
            oldest_key = min(_cache, key=lambda k: _cache[k][1])
            del _cache[oldest_key]
        _cache[key] = (value, time.time())


def fetch_availability(cgi_url, user, password, hostname, service,
                       start_ts, end_ts, verify_ssl=False):
    '''Fetch availability data from Nagios avail.cgi.

    Returns a dict with 'breakdown' and 'log' keys, or raises on error.
    '''
    cache_k = _cache_key(cgi_url, hostname, service, start_ts, end_ts)
    cached = _cache_get(cache_k)
    if cached is not None:
        return cached

    url = (
        '{base}/avail.cgi?t1={t1}&t2={t2}'
        '&show_log_entries=&host={host}&service={service}'
        '&assumeinitialstates=yes&assumestateretention=yes'
        '&assumestatesduringnotrunning=yes&includesoftstates=no'
        '&initialassumedhoststate=0&initialassumedservicestate=0'
        '&timeperiod=&backtrack=4'
    ).format(
        base=cgi_url.rstrip('/'),
        t1=int(start_ts),
        t2=int(end_ts),
        host=hostname,
        service=service or '',
    )

    resp = requests.get(url, auth=(user, password), verify=verify_ssl,
                        timeout=30)
    resp.raise_for_status()

    result = _parse_avail_html(resp.text)
    _cache_put(cache_k, result)
    return result


def _parse_avail_html(html):
    '''Parse the avail.cgi HTML response into structured data.'''
    soup = BeautifulSoup(html, features='lxml')
    dom = etree.HTML(str(soup))

    breakdown = _parse_breakdown_table(dom)
    service_log = _parse_service_log_table(dom)

    return {
        'breakdown': breakdown,
        'log': service_log,
    }


def _parse_breakdown_table(dom):
    '''Parse the state breakdown table from avail.cgi output.'''
    breakdown_table = dom.xpath('/html/body/div[3]/table')
    if not breakdown_table:
        return {}

    rows = breakdown_table[0].xpath('tr')
    breakdown = {}
    state = ''

    for row in rows:
        cols = row.xpath('td')
        if len(cols) <= 1:
            continue

        idx = 0
        first_text = (cols[0].text or '').strip()

        if first_text in ('OK', 'WARNING', 'CRITICAL', 'UNKNOWN',
                          'Undetermined'):
            state = first_text
            idx += 1
        elif not first_text and state:
            # Continuation row with empty state cell
            idx += 1

        type_reason = cols[idx].text or ''
        idx += 1

        time_val = cols[idx].text or ''
        idx += 1

        total_pct = cols[idx].text or ''
        idx += 1

        known_pct = None
        if state != 'Undetermined' and idx < len(cols):
            known_pct = cols[idx].text
            idx += 1

        if state not in breakdown:
            breakdown[state] = {}

        entry = {
            'time': time_val,
            'total_pct': total_pct,
        }
        if known_pct is not None:
            entry['known_pct'] = known_pct

        breakdown[state][type_reason] = entry

    return breakdown


def _parse_service_log_table(dom):
    '''Parse the service log table from avail.cgi output.'''
    log_table = dom.xpath('/html/body/div[6]/table')
    if not log_table:
        return []

    rows = log_table[0].xpath('tr')
    entries = []

    for row in rows:
        cols = row.xpath('td')
        if len(cols) <= 1:
            continue

        entries.append({
            'start': cols[0].text or '',
            'end': cols[1].text or '',
            'duration': cols[2].text if cols[2].text else 'Ongoing',
            'state_type': cols[3].text or '',
            'info': cols[4].text or '',
        })

    return entries
