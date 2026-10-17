"""SSRF 防护（netutil）回归。

防护是否成立只看三件事：受限地址进不来、校验过的 IP 不会被第二次解析换掉、
字节上限真的截断。全部用可编排的假 DNS 与真实 requests.Response，不触网。
"""
import ipaddress
import re
import socket
import threading

import pytest

from app.services import netutil
from app.services.netutil import SafeFetchError, safe_get
from crm_test_utils import fake_stream

PUBLIC = '93.184.216.34'
PRIVATE = '10.0.0.1'
OTHER = '192.0.2.1'


def _answers(ip, port=None):
    return [(socket.AF_INET, socket.SOCK_STREAM, 6, '', (ip, port or 0))]


def _is_literal(host):
    try:
        ipaddress.ip_address(host)
        return True
    except ValueError:
        return False


@pytest.fixture()
def dns(monkeypatch):
    """假 DNS：替换固定器委托的那一层，可按用例改写答案。"""
    state = {'ip': PUBLIC, 'hosts': []}

    def fake(host, port=None, *args, **kwargs):
        state['hosts'].append(host)
        # 数字地址直接返回：这正是「把连接固定到已校验 IP」后的形态
        return _answers(host if _is_literal(host) else state['ip'], port)

    monkeypatch.setattr(netutil, '_orig_getaddrinfo', fake)
    return state


class _StubSession:
    """按脚本顺序返回响应；也可注入自定义 getter。"""

    def __init__(self, responses=(), get=None):
        self._responses = list(responses)
        self._get = get
        self.requested = []

    def get(self, url, **kw):
        self.requested.append(url)
        if self._get is not None:
            return self._get(url, **kw)
        assert self._responses, '脚本里的响应用完了'
        return self._responses.pop(0)


class TestAddressChecks:
    def test_rejects_non_http_scheme(self, dns):
        with pytest.raises(SafeFetchError) as e:
            safe_get('file:///etc/passwd')
        assert e.value.security is True

    def test_rejects_url_without_host(self, dns):
        with pytest.raises(SafeFetchError):
            safe_get('example.com/x.html')

    def test_rejects_loopback(self, dns):
        dns['ip'] = '127.0.0.1'
        with pytest.raises(SafeFetchError) as e:
            safe_get('http://internal.example/x')
        assert '受限' in str(e.value) and e.value.security

    def test_rejects_private_range(self, dns):
        dns['ip'] = PRIVATE
        with pytest.raises(SafeFetchError) as e:
            safe_get('http://internal.example/x')
        assert e.value.security is True

    def test_rejects_literal_ip_metadata_address(self, dns):
        with pytest.raises(SafeFetchError) as e:
            safe_get('http://169.254.169.254/latest/meta-data/')
        assert e.value.security is True

    def test_rejects_when_any_answer_is_restricted(self, monkeypatch, dns):
        # 多条解析记录里只要有一条指内网就整体拒绝
        monkeypatch.setattr(netutil, '_orig_getaddrinfo',
                            lambda host, port=None, *a, **k: _answers(PUBLIC, port) + _answers(PRIVATE, port))
        with pytest.raises(SafeFetchError) as e:
            safe_get('http://split.example/x', session=_StubSession())
        assert e.value.security is True

    def test_accepts_public_host(self, dns):
        session = _StubSession([fake_stream(chunks=[b'<html>ok</html>'])])
        resp = safe_get('https://example.com/a.htm', session=session)
        assert resp.status_code == 200 and resp.content == b'<html>ok</html>'


class TestByteCap:
    def test_stops_reading_at_max_bytes(self, dns):
        resp = safe_get('https://example.com/big',
                        session=_StubSession([fake_stream(chunks=[b'x' * 1024] * 20)]),
                        max_bytes=3 * 1024)
        assert len(resp.content) == 3 * 1024
        assert resp._crm_truncated is True

    def test_releases_connection_after_cap(self, dns):
        streamed = fake_stream(chunks=[b'x' * 1024] * 20)
        safe_get('https://example.com/big', session=_StubSession([streamed]), max_bytes=1024)
        assert streamed.raw.closed == 1, '提前中断必须归还连接'

    def test_short_body_not_marked_truncated(self, dns):
        resp = safe_get('https://example.com/small',
                        session=_StubSession([fake_stream(chunks=[b'abc'])]), max_bytes=1024)
        assert resp.content == b'abc' and resp._crm_truncated is False

    def test_safe_text_respects_char_limit(self, dns):
        resp = safe_get('https://example.com/txt', session=_StubSession([fake_stream(chunks=[b'y' * 5000])]))
        assert len(netutil.safe_text(resp, limit=100)) == 100


class TestDnsRebinding:
    def test_connection_uses_the_validated_ip(self, monkeypatch, dns):
        """经典 rebinding：第一次解析公网，之后改成内网。

        建连时的第二次解析必须仍拿到已校验的公网 IP，否则校验形同虚设。
        """
        calls = {'n': 0}
        seen = {}

        def alternating(host, port=None, *a, **k):
            if host == 'rebind.example':
                calls['n'] += 1
                return _answers(PUBLIC if calls['n'] == 1 else PRIVATE, port)
            return _answers(host, port)

        def getter(url, **kw):
            # 模拟 urllib3 建连时自己再解析一次
            seen['ip'] = socket.getaddrinfo('rebind.example', 443)[0][4][0]
            return fake_stream(chunks=[b'ok'])

        monkeypatch.setattr(netutil, '_orig_getaddrinfo', alternating)
        resp = safe_get('http://rebind.example/x', session=_StubSession(get=getter))
        assert seen['ip'] == PUBLIC, '固定失效：建连拿到了第二次解析出的内网答案'
        assert resp.content == b'ok'

    def test_pin_is_thread_local(self, dns):
        dns['ip'] = OTHER
        with netutil._pinned('pinned.example', PUBLIC):
            holder = {}

            def worker():
                holder['ip'] = socket.getaddrinfo('pinned.example', 443)[0][4][0]

            t = threading.Thread(target=worker)
            t.start()
            t.join(5)
            assert socket.getaddrinfo('pinned.example', 443)[0][4][0] == PUBLIC
            assert holder['ip'] == OTHER, '固定泄漏到了别的线程'
        assert socket.getaddrinfo('pinned.example', 443)[0][4][0] == OTHER


class TestRedirects:
    def test_follows_relative_location(self, dns):
        session = _StubSession([
            fake_stream(status=302, headers={'Location': '/next.htm'}),
            fake_stream(chunks=[b'final']),
        ])
        resp = safe_get('https://example.com/a', session=session)
        assert resp.content == b'final'
        assert session.requested == ['https://example.com/a', 'https://example.com/next.htm']

    def test_each_hop_is_validated(self, dns):
        session = _StubSession([fake_stream(status=302, headers={'Location': 'http://127.0.0.1/y'})])
        with pytest.raises(SafeFetchError) as e:
            safe_get('https://example.com/a', session=session)
        assert e.value.security is True

    def test_hop_limit(self, dns):
        session = _StubSession([fake_stream(status=302, headers={'Location': f'/p{i}'})
                                for i in range(6)])
        with pytest.raises(SafeFetchError) as e:
            safe_get('https://example.com/p0', session=session)
        assert '重定向次数' in str(e.value)

    def test_non_200_is_a_remote_fault_not_a_security_block(self, dns):
        with pytest.raises(SafeFetchError) as e:
            safe_get('https://example.com/boom', session=_StubSession([fake_stream(status=500)]))
        assert e.value.security is False and 'HTTP 500' in str(e.value)


class TestFetchGoesThroughGuard:
    def test_outbound_gets_use_safe_get(self):
        """新增抓取必须走 safe_get：裸 requests.get 一律算回归。"""
        import pathlib
        import re

        root = pathlib.Path(__file__).resolve().parents[1] / 'app'
        offenders = []
        for py in root.rglob('*.py'):
            if py.name == 'netutil.py':
                continue
            for lineno, line in enumerate(py.read_text().splitlines(), 1):
                if line.lstrip().startswith('#'):
                    continue
                if re.search(r'\brequests\.get\s*\(', line):
                    offenders.append(f'{py.name}:{lineno}')
        assert offenders == [], f'绕过 SSRF 防护的抓取: {offenders}'


class TestEncodingResolution:
    """公告全文乱码的根因：Content-Type 不带 charset 时不能让 chardet 猜中文页。

    ccgp 只回 `Content-Type: text/html`，requests 于是把 encoding 设成 iso-8859-1；
    旧实现直接换成 apparent_encoding，而 chardet 把成段 UTF-8 中文猜成了西里尔编码
    ptcp154 —— 每个字节都能解出字符，结果整篇 «д»Ӣдј‘…» 存进库。
    """

    def _fetch(self, dns, body, headers=None):
        resp = safe_get('https://example.com/a.htm',
                        session=_StubSession([fake_stream(chunks=[body], headers=headers)]))
        return resp

    def test_m026_001_meta_utf8_beats_cyrillic_guess(self, dns):
        body = ('<html><head><meta charset="utf-8"></head><body>介休市林业局 2026 年'
                '中央财政林草有害生物防治项目采购结果公告</body></html>').encode('utf-8')
        resp = self._fetch(dns, body)
        assert resp.encoding == 'utf-8'
        assert '介休市林业局' in resp.text
        assert not re.search(r'[\u0400-\u04FF]', resp.text)

    def test_m026_002_valid_utf8_without_any_declaration(self, dns):
        """没声明也不能交给猜测：UTF-8 严格解得通就用 UTF-8。"""
        body = ('<html><body>' + '云南省普洱市中央财政林草有害生物防治项目' * 12 + '</body></html>').encode()
        resp = self._fetch(dns, body)
        assert resp.encoding == 'utf-8' and '普洱市' in resp.text

    def test_m026_003_header_charset_wins(self, dns):
        body = '<html><body>轮台县林业和草原局</body></html>'.encode('gbk')
        resp = self._fetch(dns, body, headers={'Content-Type': 'text/html; charset=GBK'})
        assert resp.encoding == 'gb18030' and '轮台县' in resp.text

    def test_m026_004_gb2312_upgraded_to_gb18030(self, dns):
        """声明 gb2312 的页面常有生僻字，落到 gb18030 才不会解成 ?"""
        body = b'<html><head><meta http-equiv="Content-Type" content="text/html; charset=gb2312">' \
               b'</head><body>\xb8\xd5\xb9\xab\xb8\xe6</body></html>'
        resp = self._fetch(dns, body)
        assert resp.encoding == 'gb18030'
        assert '公告' in resp.text

    def test_m026_005_non_utf8_still_uses_guess(self, dns):
        """真·非 UTF-8 的老页面仍要有兜底，否则只能得到一串替换符。"""
        body = ('<html><body>' + 'X' * 200 + '</body></html>').encode('utf-16')
        resp = self._fetch(dns, body)
        assert resp.encoding != 'utf-8'

    def test_m026_006_meta_beyond_sniff_window_ignored(self, dns):
        body = b'<' + b'z' * 5000 + b'><meta charset="utf-16">'
        assert netutil.sniff_charset(body) == ''
        assert netutil.sniff_charset(b'<meta charset="UTF-8">ok') == 'utf-8'

    def test_m026_007_unknown_charset_name_is_dropped(self, dns):
        assert netutil._norm_charset('not-a-codec') == ''
        assert netutil._norm_charset('GBK_2000') == ''
        assert netutil._norm_charset('utf_8') == 'utf-8'
