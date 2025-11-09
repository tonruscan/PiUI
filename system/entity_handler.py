# /system/entity_handler.py
import importlib
import showlog
from system import cc_registry
import unit_router

def handle_entity(entity_name: str, entity_type: str, switch_mode_fn):
    """
    Handle activation of an entity (device or module).
    Currently: fully initializes modules; devices still stubbed.
    """
    try:
        showlog.debug(f"[ENTITY_HANDLER] handle_entity → {entity_name} (type={entity_type})")

        # ───────────────────────────────
        # PLUGINS (formerly modules)
        # ───────────────────────────────
        if entity_type == "module":
            try:
                showlog.info(f"*[ENTITY_HANDLER] 🔄 Loading plugin: {entity_name}")
                
                # 1️⃣ Import the plugin dynamically
                mod = importlib.import_module(f"plugins.{entity_name}_plugin")
                showlog.info(f"*[ENTITY_HANDLER] ✅ Imported plugin module: {entity_name}_plugin")

                # 2️⃣ Load its CC registry (for dial mapping)
                try:
                    reg = getattr(mod, "REGISTRY", None)
                    if reg:
                        cc_registry.load_from_module(entity_name, reg)
                        showlog.info(f"*[ENTITY_HANDLER] ✅ CC registry loaded for plugin {entity_name}")
                    else:
                        showlog.warn(f"[ENTITY_HANDLER] No REGISTRY found in {entity_name}_plugin")
                except Exception as e:
                    showlog.error(f"[ENTITY_HANDLER] CC registry load failed for module {entity_name}: {e}")


                # 3️⃣ Initialize the page (same as old ui logic)
                if hasattr(mod, "init_page"):
                    showlog.info(f"*[ENTITY_HANDLER] 🔄 Calling {entity_name}.init_page()")
                    mod.init_page()
                    showlog.info(f"*[ENTITY_HANDLER] ✅ {entity_name} page initialized")
                else:
                    showlog.warn(f"*[ENTITY_HANDLER] ⚠️ {entity_name}_plugin has NO init_page() - this may be normal for some plugins")

                # 4️⃣ Route hardware dials to the module
                if hasattr(mod, "handle_hw_dial"):
                    unit_router.load_module(entity_name, mod.handle_hw_dial)
                    showlog.debug(f"[ENTITY_HANDLER] {entity_name} HW routing active")

                # 5️⃣ Switch UI mode
                showlog.debug(f"[ENTITY_HANDLER] About to call switch_mode_fn for {entity_name.lower()}")
                switch_mode_fn(entity_name.lower())
                showlog.debug(f"[ENTITY_HANDLER] UI switched to {entity_name.lower()}")

            except Exception as e:
                showlog.error(f"[ENTITY_HANDLER] Plugin activation failed for {entity_name}: {e}")

        # ───────────────────────────────
        # DEVICES (stub for future migration)
        # ───────────────────────────────
        elif entity_type == "device":
            showlog.debug(f"[ENTITY_HANDLER] {entity_name} is a device → (stub branch)")

        else:
            showlog.warn(f"[ENTITY_HANDLER] Unknown entity type '{entity_type}' for {entity_name}")

    except Exception as e:
        showlog.error(f"[ENTITY_HANDLER] Exception: {e}")
