import sys
import types
import inspect
import asyncio
from urllib.parse import urlparse, parse_qs

import pandas as pd


pyarrow_stub = types.ModuleType("pyarrow")


class _Table:
    @staticmethod
    def from_pandas(df, preserve_index=False):
        return df


pyarrow_stub.Table = _Table


parquet_stub = types.ModuleType("pyarrow.parquet")


def _write_table(table, handle, compression="snappy"):
    # No-op for tests; serialization is validated by downstream patches.
    return None


def _write_to_dataset(*args, **kwargs):
    # No-op placeholder for dataset writing in tests.
    return None


def _read_table(handle):
    # Return an empty DataFrame for tests that rely on patched IO.
    return types.SimpleNamespace(to_pandas=lambda: pd.DataFrame())


parquet_stub.write_table = _write_table
parquet_stub.write_to_dataset = _write_to_dataset
parquet_stub.read_table = _read_table

sys.modules.setdefault("pyarrow", pyarrow_stub)
sys.modules.setdefault("pyarrow.parquet", parquet_stub)


def _install_fastapi_stub() -> None:
    try:
        import fastapi  # noqa: F401
        return
    except Exception:
        pass

    fastapi_stub = types.ModuleType("fastapi")

    class HTTPException(Exception):
        def __init__(self, status_code: int, detail: str | None = None):
            super().__init__(detail or "")
            self.status_code = status_code
            self.detail = detail or ""

    class _Query:
        def __init__(self, default=None, alias=None, **_):
            self.default = default
            self.alias = alias

    def Query(default=None, **kwargs):
        return _Query(default=default, **kwargs)

    class FastAPI:
        def __init__(self, *_, **__):
            self.routes = {"GET": {}, "POST": {}}

        def add_middleware(self, *_, **__):
            return None

        def get(self, path, **_):
            def decorator(fn):
                self.routes["GET"][path] = fn
                return fn
            return decorator

        def post(self, path, **_):
            def decorator(fn):
                self.routes["POST"][path] = fn
                return fn
            return decorator

    # middleware.cors submodule
    middleware_mod = types.ModuleType("fastapi.middleware")
    cors_mod = types.ModuleType("fastapi.middleware.cors")

    class CORSMiddleware:
        def __init__(self, *_, **__):
            return None

    cors_mod.CORSMiddleware = CORSMiddleware
    middleware_mod.cors = cors_mod

    # testclient submodule
    testclient_mod = types.ModuleType("fastapi.testclient")

    class _Response:
        def __init__(self, status_code: int, payload):
            self.status_code = status_code
            self._payload = payload

        def json(self):
            return self._payload

    def _jsonify(obj):
        if isinstance(obj, list):
            return [_jsonify(item) for item in obj]
        if hasattr(obj, "model_dump"):
            return obj.model_dump()
        if hasattr(obj, "dict"):
            return obj.dict()
        if isinstance(obj, dict):
            return {k: _jsonify(v) for k, v in obj.items()}
        return obj

    class TestClient:
        def __init__(self, app):
            self.app = app

        def get(self, url: str):
            return self._request("GET", url)

        def post(self, url: str, json=None):
            return self._request("POST", url, body=json)

        def _request(self, method: str, url: str, body=None):
            parsed = urlparse(url)
            path = parsed.path
            handler = self.app.routes.get(method, {}).get(path)
            if handler is None:
                return _Response(404, {"detail": "Not Found"})
            params = {}
            query = parse_qs(parsed.query)
            sig = inspect.signature(handler)
            for name, param in sig.parameters.items():
                default = param.default
                alias = None
                if isinstance(default, _Query):
                    alias = default.alias
                    default = default.default
                key = alias or name
                if key in query:
                    params[name] = query[key][0]
                elif default is not inspect._empty:
                    params[name] = default
            try:
                if inspect.iscoroutinefunction(handler):
                    result = asyncio.run(handler(**params))
                else:
                    result = handler(**params)
            except HTTPException as exc:
                return _Response(exc.status_code, {"detail": exc.detail})
            return _Response(200, _jsonify(result))

    TestClient.__test__ = False

    fastapi_stub.FastAPI = FastAPI
    fastapi_stub.HTTPException = HTTPException
    fastapi_stub.Query = Query
    fastapi_stub.middleware = middleware_mod
    testclient_mod.TestClient = TestClient

    sys.modules["fastapi"] = fastapi_stub
    sys.modules["fastapi.middleware"] = middleware_mod
    sys.modules["fastapi.middleware.cors"] = cors_mod
    sys.modules["fastapi.testclient"] = testclient_mod


_install_fastapi_stub()


def _install_yfinance_stub() -> None:
    try:
        import yfinance  # noqa: F401
        return
    except Exception:
        pass

    yfinance_stub = types.ModuleType("yfinance")

    class _Ticker:
        def __init__(self, *_args, **_kwargs):
            self.sustainability = pd.DataFrame()

        def history(self, *_, **__):
            return pd.DataFrame()

    def download(*_args, **_kwargs):
        return pd.DataFrame()

    yfinance_stub.Ticker = _Ticker
    yfinance_stub.download = download

    sys.modules["yfinance"] = yfinance_stub


_install_yfinance_stub()
