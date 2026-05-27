"""Monkey-patch OpenAI SDK to always send Mozilla User-Agent."""
import openai
import functools

# Get the real OpenAI class (not the proxy)
# In v1.x, the class is openai.OpenAI which inherits from openai._base_client.OpenAI
try:
    from openai import OpenAI as _RealOpenAI
except ImportError:
    _RealOpenAI = openai.OpenAI

# Store original __init__
_orig_init = _RealOpenAI.__init__

@functools.wraps(_orig_init)
def _patched_init(self, *args, **kwargs):
    # Ensure default_headers always has our Mozilla User-Agent
    dh = dict(kwargs.pop('default_headers', {}) or {})
    dh.setdefault('User-Agent', 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/148.0.0.0 Safari/537.36')
    kwargs['default_headers'] = dh
    return _orig_init(self, *args, **kwargs)

_RealOpenAI.__init__ = _patched_init
print("OpenAI User-Agent patch installed", flush=True)
