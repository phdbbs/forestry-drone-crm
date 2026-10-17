"""统一的 SSRF 防护抓取入口：所有抓取外部 URL 的代码必须经过 safe_get。

防护点：
- 仅 http/https；
- 域名解析结果全部为公网地址（拦截内网/环回/保留段）；
- 把建连固定到**已校验的那个 IP**：校验与建连之间还要再解析一次，
  这次答案完全可以和上次不同（DNS rebinding），旧实现正是栽在这一刀；
- 禁止自动重定向（防校验后跳转绕过），逐跳跟随时每一跳重新校验；
- 真正按字节上限分块读取：旧实现只把上限记在响应对象上没人用，
  调用方取 .text 时照样能把远端整站拖进内存。

编码判定见 `resolve_encoding`：中文站几乎都不在 HTTP 头里写 charset，
交给 chardet 猜会把 UTF-8 的中文猜成 ptcp154 这类西里尔编码，公告全文整篇变乱码。
"""
import ipaddress
import re
import socket
import threading
from contextlib import contextmanager
from urllib.parse import urljoin, urlparse

import requests

_CHUNK = 64 * 1024
_MAX_HOPS = 3
_META_CHARSET_RE = re.compile(rb'charset\s*=\s*["\']?\s*([A-Za-z0-9][A-Za-z0-9_.:\-]*)', re.I)
# gb2312/gbk 收字太少，公告里的生僻字与少数民族地名会解码失败，一律升到 gb18030
_CHARSET_ALIAS = {'gb2312': 'gb18030', 'gbk': 'gb18030', 'windows-936': 'gb18030',
                  'iso-8859-1': '', 'ascii': 'utf-8', 'x-utf-8': 'utf-8', 'utf8': 'utf-8'}

# 线程内的「域名 → 已校验 IP」映射。requests/urllib3 建连时走 socket.getaddrinfo，
# 我们只替换当前线程已登记域名的答案，其它线程与其它域名不受影响。
_local = threading.local()
_orig_getaddrinfo = socket.getaddrinfo


def _pinned_getaddrinfo(host, port, *args, **kwargs):
    pins = getattr(_local, 'pins', None)
    if pins and isinstance(host, str) and host in pins:
        host = pins[host]
    return _orig_getaddrinfo(host, port, *args, **kwargs)


socket.getaddrinfo = _pinned_getaddrinfo


class SafeFetchError(Exception):
    """抓取失败。security=True 表示 URL 安全校验未过（应回 400），
    否则为网络/远端故障（应回 502）。"""

    def __init__(self, msg, security=False):
        super().__init__(msg)
        self.security = security


def _is_restricted(ip_str):
    ip = ipaddress.ip_address(ip_str)
    return (ip.is_private or ip.is_loopback or ip.is_reserved
            or ip.is_link_local or ip.is_multicast or ip.is_unspecified)


def _resolve_public_ip(hostname):
    """解析域名：任一答案落在受限网段就整体拒绝，否则返回用于固定的答案。

    用当前生效的 socket.getaddrinfo（即本模块装上的固定版），保证同一主机
    在一轮抓取里的多次解析都拿到同一个答案。
    """
    try:
        infos = socket.getaddrinfo(hostname, None, socket.AF_UNSPEC, socket.SOCK_STREAM)
    except OSError as e:
        raise SafeFetchError(f"域名无法解析: {hostname}", security=True) from e
    if not infos:
        raise SafeFetchError(f"域名无法解析: {hostname}", security=True)
    for info in infos:
        if _is_restricted(info[4][0]):
            raise SafeFetchError("目标地址指向受限地址（内网/保留地址段），已拦截", security=True)
    return infos[0][4][0]


@contextmanager
def _pinned(hostname, ip):
    pins = _local.__dict__.setdefault('pins', {})
    had_previous = hostname in pins
    previous = pins.get(hostname)
    pins[hostname] = ip
    try:
        yield
    finally:
        if had_previous:
            pins[hostname] = previous
        else:
            pins.pop(hostname, None)


def _check_url(url):
    u = urlparse(url)
    if u.scheme not in ('http', 'https') or not u.hostname:
        raise SafeFetchError("URL 不合法（仅支持 http/https）", security=True)
    return u


def _read_capped(resp, max_bytes):
    """分块读到 max_bytes 就断开；正文缓存在响应对象上，后续 .text 不再碰 socket。"""
    chunks = []
    total = 0
    truncated = False
    try:
        for chunk in resp.iter_content(chunk_size=_CHUNK):
            if not chunk:
                continue
            chunks.append(chunk)
            total += len(chunk)
            if total >= max_bytes:
                truncated = True
                break
    except requests.RequestException as e:
        raise SafeFetchError(f"读取响应失败: {e}") from e
    finally:
        # 提前中断必须归还连接，否则半开连接会一直占着句柄和连接池
        resp.close()
    body = b''.join(chunks)
    if truncated:
        body = body[:max_bytes]
    resp._content = body
    resp._content_consumed = True
    resp._crm_truncated = truncated
    return resp


def _get_once(getter, url, timeout, headers, kw):
    """单个 URL 的一次校验 + 固定 IP 建连。返回的响应可能仍是重定向。"""
    u = _check_url(url)
    ip = _resolve_public_ip(u.hostname)
    with _pinned(u.hostname, ip):
        try:
            return getter(url, timeout=timeout, headers=headers,
                          allow_redirects=False, stream=True, **kw)
        except requests.RequestException as e:
            raise SafeFetchError(f"请求失败: {e}") from e


def _norm_charset(name):
    """归一化编码名；无法识别或等于 requests 的默认 latin 猜测时返回 ''。"""
    enc = (name or '').strip().lower().replace('_', '-')
    if not enc:
        return ''
    enc = _CHARSET_ALIAS.get(enc, enc)
    if not enc:
        return ''
    # 校验编码名真的存在，避免把 'gb-2312-80' 之类怪写法交给 codecs 抛异常
    try:
        ''.encode(enc)
    except (LookupError, ValueError):
        return ''
    return enc


def sniff_charset(body):
    """从 HTML 前 4KB 里读 `<meta charset>` / `Content-Type" content="...charset=x`。"""
    m = _META_CHARSET_RE.search((body or b'')[:4096])
    return _norm_charset(m.group(1).decode('ascii', 'ignore')) if m else ''


def _is_utf8(body):
    try:
        body.decode('utf-8')
        return True
    except UnicodeDecodeError:
        return False


def _header_charset(resp):
    ct = resp.headers.get('Content-Type') or ''
    return _norm_charset(ct.split('charset=', 1)[1]) if 'charset=' in ct.lower() else ''


def resolve_encoding(resp):
    """确定响应正文编码：HTTP 头 → 页面 meta 声明 → UTF-8 严格试探 → chardet 兜底。

    requests 在 `Content-Type: text/html` 没有 charset 时把 encoding 设成 iso-8859-1，
    旧实现因此直接改用 apparent_encoding，而 chardet 面对成段中文经常猜出 ptcp1251/ptcp154
    这类西里尔编码：字节数对得上、每个字节都能解出字符，于是「解码成功」地把公告全文
    变成 «д»Ӣдј‘…» 存进库。页面自己声明的 charset 才是权威，先信它。
    """
    body = resp.content or b''
    return (_header_charset(resp)
            or sniff_charset(body)
            or ('utf-8' if _is_utf8(body) else '')
            or _norm_charset(resp.apparent_encoding)
            or 'utf-8')


def safe_get(url, timeout=15, max_bytes=8 * 1024 * 1024, session=None, **kw):
    """SSRF 防护的 GET。返回 requests.Response；不安全或失败抛 SafeFetchError。

    session: 可传入 requests.Session（复用 UA/cookie），安全校验不变。
    """
    headers = kw.pop('headers', None)
    getter = session.get if session is not None else requests.get
    resp = _get_once(getter, url, timeout, headers, kw)
    hops = 0
    current = url
    while resp.is_redirect:
        if hops >= _MAX_HOPS:
            resp.close()
            raise SafeFetchError(f"重定向次数超过 {_MAX_HOPS} 次上限", security=True)
        # Location 允许是相对路径，按当前 URL 归一化后再校验，避免绕开检查
        current = urljoin(current, resp.headers.get('Location', ''))
        resp.close()
        resp = _get_once(getter, current, timeout, headers, kw)
        hops += 1
    if resp.status_code != 200:
        code = resp.status_code
        resp.close()
        raise SafeFetchError(f"站点返回 HTTP {code}")
    resp = _read_capped(resp, max_bytes)
    resp.encoding = resolve_encoding(resp)
    return resp


def safe_text(resp, limit=800000):
    """读取响应文本（截断到 limit 字符）。"""
    return (resp.text or '')[:limit]
