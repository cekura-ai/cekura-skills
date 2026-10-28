"""Loaded by every interpreter in the instrumented backend image.

With CEKURA_METERING=1, refuses any Modal sandbox not created through the metered
generator path. Real provider keys never enter these processes, so an unpatched path
could not spend inference money either; this closes the infrastructure route too.
"""
import os

if os.environ.get("CEKURA_METERING") == "1":
    import importlib.util
    import sys
    spec = importlib.util.spec_from_file_location("app.cekura_metering", "/app/app/cekura_metering.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules["app.cekura_metering"] = module
    spec.loader.exec_module(module)
    module.guard_sandbox_creation()
