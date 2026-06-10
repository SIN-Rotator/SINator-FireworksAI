"""Monkey-patch OpenAI SDK for Hermes Survey Automation.

1. User-Agent Spoof: Mozilla/5.0 (Mac/Chrome) statt "OpenAI/Python"
2. max_retries=0: Retry wird vom Pool-Router übernommen, nicht vom SDK

Der Router (localhost:9998) failtovert automatisch bei 429/412/5xx
zu den 10 lokalen Proxys. SDK-Retry würde nur denselben Endpoint
wiederholen → sinnlos. Router-Retry → nächster Pool.

Docs: _ua_patch.doc.md
"""
import openai
import functools

# Get the real OpenAI class (not the proxy)
try:
    from openai import OpenAI as _RealOpenAI
except ImportError:
    _RealOpenAI = openai.OpenAI

# Store original __init__
_orig_init = _RealOpenAI.__init__

@functools.wraps(_orig_init)
def _patched_init(self, *args, **kwargs):
    # 1. User-Agent Spoof
    dh = dict(kwargs.pop('default_headers', {}) or {})
    dh.setdefault('User-Agent', 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/148.0.0.0 Safari/537.36')
    kwargs['default_headers'] = dh

    # 2. Disable SDK-level retries — Router handles failover across pools
    if 'max_retries' not in kwargs:
        kwargs['max_retries'] = 0

    return _orig_init(self, *args, **kwargs)

_RealOpenAI.__init__ = _patched_init
print("OpenAI UA-spoof + retry-disable patch installed", flush=True)
