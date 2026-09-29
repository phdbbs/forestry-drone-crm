"""统一的 SSRF 防护抓取入口：所有抓取外部 URL 的代码必须经过 safe_get。

防护点：仅 http/https；域名解析结果全部为公网地址（拦截内网/环回/保留段）；
禁止重定向（防校验后跳转绕过）；限制响应大小与超时。
"""
import ipaddress
import socket
from urllib.parse import urlparse

import requests

_UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
       "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")


class SafeFetchError(Exception):
    """抓取失败。security=True 表示 URL 安全校验未过（应回 400），
    否则为网络/远端故障（应回 502）。"""

    def __init__(self, msg, security=False):
        super().__init__(msg)
        self.security = security


def _assert_public_host(hostname):
    try:
        infos = socket.getaddrinfo(hostname, None)
    except OSError as e:
        raise SafeFetchError(f"域名无法解析: {hostname}", security=True) from e
    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if (ip.is_private or ip.is_loopback or ip.is_reserved
                or ip.is_link_local or ip.is_multicast or ip.is_unspecified):
            raise SafeFetchError("目标地址指向受限地址（内网/保留地址段），已拦截", security=True)


def safe_get(url, timeout=15, max_bytes=8 * 1024 * 1024, session=None, **kw):
    """SSRF 防护的 GET。返回 requests.Response；不安全或失败抛 SafeFetchError。

    session: 可传入 requests.Session（复用 UA/cookie），安全校验不变。
    """
    u = urlparse(url)
    if u.scheme not in ('http', 'https') or not u.hostname:
        raise SafeFetchError("URL 不合法（仅支持 http/https）", security=True)
    _assert_public_host(u.hostname)
    getter = session.get if session is not None else requests.get
    headers = kw.pop('headers', None)
    try:
        resp = getter(url, timeout=timeout, headers=headers,
                      allow_redirects=False, stream=True, **kw)
    except requests.RequestException as e:
        raise SafeFetchError(f"请求失败: {e}") from e
    # 重定向目标同样校验（逐跳跟随，每跳都过公网检查）
    hops = 0
    while getattr(resp, 'is_redirect', False) and hops < 3:
        loc = resp.headers.get('Location', '')
        u2 = urlparse(loc)
        if u2.scheme not in ('http', 'https') or not u2.hostname:
            raise SafeFetchError("重定向地址不合法", security=True)
        _assert_public_host(u2.hostname)
        try:
            resp = getter(loc, timeout=timeout, headers=headers,
                          allow_redirects=False, stream=True, **kw)
        except requests.RequestException as e:
            raise SafeFetchError(f"重定向请求失败: {e}") from e
        hops += 1
    if resp.status_code != 200:
        raise SafeFetchError(f"站点返回 HTTP {resp.status_code}")
    if not resp.encoding or resp.encoding.lower() == 'iso-8859-1':
        resp.encoding = resp.apparent_encoding or 'utf-8'
    resp._max_bytes = max_bytes
    return resp


def safe_text(resp, limit=800000):
    """读取响应文本（截断到 limit 字符）。"""
    return (resp.text or '')[:limit]
