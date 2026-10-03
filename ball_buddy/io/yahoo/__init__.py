"""Yahoo I/O package: auth, client facade, snapshot model.

yfpy import is deferred to ``client.from_settings`` so the rest of the app
(and the headless tests) never pulls in Yahoo OAuth without needing it.
"""
