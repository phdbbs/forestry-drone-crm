"""接口错误的唯一出口：所有失败响应统一为 {error, code[, detail]}。

- error：面向用户的中文文案，前端可直接展示，不含堆栈、SQL 或内部字段名；
- code：面向程序的稳定标识（snake_case）。前端分支、采集日志归类、测试断言都靠它，
  改文案不会破坏调用方，这也是它相对纯文案响应的唯一价值所在；
- detail：可选的排查补充（原始异常摘要），只在有助于定位且不含敏感信息时才带。

状态码 → 默认 code 的映射让 abort(400, description=...) 这类间接错误也自动补齐 code，
所以「形状统一」是由本模块 + 全局 errorhandler 共同保证的，不依赖每个路由记得传 code。
"""
from flask import jsonify

STATUS_CODE = {
    400: 'bad_request',
    401: 'unauthorized',
    403: 'forbidden',
    404: 'not_found',
    405: 'method_not_allowed',
    409: 'conflict',
    415: 'unsupported_media_type',
    429: 'too_many_requests',
    500: 'server_error',
    502: 'bad_gateway',
    503: 'service_unavailable',
}

# 面向用户的中文兜底文案：werkzeug 自带的默认描述是英文，直接透出会显得像报错页
STATUS_TEXT = {
    400: '请求参数有误',
    404: '请求的资源不存在',
    405: '请求方法不被允许',
    415: '请求体必须为 JSON 格式',
}


def fail(error, status=400, code=None, detail=None):
    """构造统一错误响应，直接 return 给路由。"""
    body = {"error": error, "code": code or STATUS_CODE.get(status, f'http_{status}')}
    if detail:
        body["detail"] = detail
    return jsonify(body), status


def http_error(exc):
    """把 werkzeug 的 HTTPException（含 abort(...)）转成统一形状。

    Werkzeug 的类默认 description 是英文，命中时改用 STATUS_TEXT 的中文兜底；
    abort(400, description='业务提示') 这类自定义描述原样透出。
    """
    desc = getattr(exc, 'description', None)
    if desc and desc == getattr(type(exc), 'description', None):
        desc = None
    return fail(desc or STATUS_TEXT.get(exc.code, '请求错误'), exc.code)
