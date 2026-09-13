# -*- coding: utf-8 -*-
"""Web 服务入口，使用 waitress 作为生产级 WSGI 服务器。"""

import os

from waitress import serve

from webapp import create_app

if __name__ == "__main__":
    app = create_app()
    host = os.environ.get("OM_HOST", "0.0.0.0")
    port = int(os.environ.get("OM_PORT", "8080"))
    print("Oracle Monitor Web 已启动: http://{}:{}".format(host, port))
    serve(app, host=host, port=port, threads=8)
