"""Install dist/OpenMailMerge.oxt into a throwaway profile from inside LibreOffice, then check
the component loads and the menu entry is registered. Run by dev/run_installtest.sh."""

import json
import os
import traceback
from pathlib import Path

OXT = os.environ.get("MMM_OXT", "")
OUT = Path(os.environ.get("MMM_OUT", "/tmp"))


def _approving_env():
    import unohelper
    from com.sun.star.task import XInteractionHandler
    from com.sun.star.ucb import XCommandEnvironment

    class Handler(unohelper.Base, XInteractionHandler):
        def handle(self, request):
            import uno
            approve = uno.getTypeByName("com.sun.star.task.XInteractionApprove")
            for c in request.getContinuations():
                if c.queryInterface(approve):
                    c.select()
                    return

    class Env(unohelper.Base, XCommandEnvironment):
        def getInteractionHandler(self):
            return Handler()

        def getProgressHandler(self):
            return None

    return Env()


def run(*args):
    res = {}
    ctx = XSCRIPTCONTEXT.getComponentContext()  # noqa: F821
    desktop = XSCRIPTCONTEXT.getDesktop()  # noqa: F821
    try:
        import uno
        em = ctx.getValueByName("/singletons/com.sun.star.deployment.ExtensionManager")
        ext = em.addExtension(uno.systemPathToFileUrl(OXT), (), "user", None, _approving_env())
        res["installed"] = ext.getIdentifier().Value
        reg = ext.isRegistered(None, _approving_env())
        res["registered"] = bool(reg.IsPresent and reg.Value.Value)
        job = ctx.ServiceManager.createInstanceWithContext("io.github.mailmergemac.Job", ctx)
        res["job_loads"] = job is not None
        import sys
        res["job_type"] = repr(job)[:200]
        res["has_trigger"] = hasattr(job, "trigger")
        try:
            import pythonloader
            res["loaded_components"] = list(pythonloader.g_loadedComponents)
        except Exception as ex:
            res["loaded_components"] = repr(ex)
        res["sys_path_ext"] = [x for x in sys.path if "MailMerge" in x or "pythonpath" in x]
        os.environ["MAILMERGE_MAC_NO_MAIL"] = "1"
        log = OUT / "debug.log"
        os.environ["MAILMERGE_MAC_DEBUG_LOG"] = str(log)
        doc = desktop.loadComponentFromURL("private:factory/swriter", "_blank", 0, ())
        doc.Text.setString("Dear «First_Name»,")
        frame = doc.getCurrentController().getFrame()
        frame.activate()
        desktop.setActiveFrame(frame)
        res["current_is_doc"] = desktop.getCurrentComponent() is not None
        job.trigger("test:" + str(log))
        res["debug_log"] = log.read_text(encoding="utf-8").splitlines() if log.exists() else []
        dlg_mod = sys.modules.get("mailmerge_mac.dialog")
        res["dialog_module_loaded"] = dlg_mod is not None
        if dlg_mod:
            res["dialogs_open"] = len(dlg_mod._open)
            for d in list(dlg_mod._open.values()):
                res["dialog_title"] = d.model.Title
                res["dialog_visible"] = d.dlg.isVisible() if hasattr(d.dlg, "isVisible") else "n/a"
                d.close()
        doc.close(True)
        cp = ctx.ServiceManager.createInstanceWithContext("com.sun.star.configuration.ConfigurationProvider", ctx)
        from com.sun.star.beans import PropertyValue
        access = cp.createInstanceWithArguments(
            "com.sun.star.configuration.ConfigurationAccess",
            (PropertyValue(Name="nodepath", Value="/org.openoffice.Office.Addons/AddonUI/OfficeMenuBar"),))
        res["menus"] = list(access.getElementNames())
        res["ok"] = True
    except Exception as e:
        res["ok"] = False
        res["error"] = traceback.format_exc()
        cause, chain = getattr(e, "Cause", None), []
        for _ in range(5):
            if cause is None:
                break
            v = getattr(cause, "value", cause)
            chain.append(f"{type(v).__name__}: {getattr(v, 'Message', v)}")
            cause = getattr(v, "Cause", None)
        res["cause_chain"] = chain
    (OUT / "install.json").write_text(json.dumps(res, indent=2, default=str), encoding="utf-8")
    desktop.terminate()


g_exportedScripts = (run,)
