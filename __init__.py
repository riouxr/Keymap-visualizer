bl_info = {
    "name": "Keymap Visualizer - Enhanced Layout",
    "author": "ChatGPT + User",
    "version": (1, 0, 1),
    "blender": (4, 2, 0),
    "location": "3D View > Sidebar > Keymap",
    "description": "Visualizes assigned hotkeys with enhanced keyboard layout, full hierarchy support",
    "category": "Interface",
}

import bpy
import platform

# ---------------------------------------------
# Editor map (space types and related scopes)
# ---------------------------------------------
editor_map = {
    'EMPTY': 'Window',
    'SCREEN': 'Screen',
    'VIEW_2D': 'View2D',
    'VIEW_2D_BUTTONS_LIST': 'View2D Buttons List',
    'USER_INTERFACE': 'User Interface',
    'VIEW_3D': '3D View',
    'GRAPH_EDITOR': 'Graph Editor',
    'DOPESHEET_EDITOR': 'Dopesheet',
    'NLA_EDITOR': 'NLA Editor',
    'IMAGE_EDITOR': 'Image',
    'UV': 'UV Editor',  # Added for Blender 4.5+
    'OUTLINER': 'Outliner',
    'NODE_EDITOR': 'Node Editor',
    'SEQUENCE_EDITOR': 'Video Sequence Editor',
    'FILE_BROWSER': 'File Browser',
    'INFO': 'Info',
    'PROPERTIES': 'Property Editor',
    'TEXT_EDITOR': 'Text',
    'CONSOLE': 'Console',
    'CLIP_EDITOR': 'Clip',
    'GREASE_PENCIL': 'Grease Pencil',
    'MASK_EDITOR': 'Mask Editing',
    'TIMELINE': 'Frames',
    'MARKER': 'Markers',
    'ANIMATION': 'Animation',
    'CHANNELS': 'Animation Channels'
}


# ---------------------------------------------
# Keyboard layouts to render
# ---------------------------------------------
qwerty_keys = [
    ['ESC', 'F1', 'F2', 'F3', 'F4', 'F5', 'F6', 'F7', 'F8', 'F9', 'F10', 'F11', 'F12'],
    ['`', '1', '2', '3', '4', '5', '6', '7', '8', '9', '0', '-', '=', 'DELETE'],
    ['TAB', 'Q', 'W', 'E', 'R', 'T', 'Y', 'U', 'I', 'O', 'P', '[', ']', '\\'],
    ['A', 'S', 'D', 'F', 'G', 'H', 'J', 'K', 'L', ';', "'", 'RETURN'],
    ['Z', 'X', 'C', 'V', 'B', 'N', 'M', ',', '.', '/'],
    ['SPACE', 'ENTER', 'BACK_SPACE'],
]

numpad_keys = [
    ['F16', 'F17', 'F18', 'F19'],
    [' ', '=', '/', '*'],
    ['7', '8', '9', '-'],
    ['4', '5', '6', '+'],
    ['1', '2', '3', ' '],
    [' ', '0', '.', 'ENTER'],
]

cursor_keys = [
    ['F13', 'F14', 'F15'],
    ['INSERT', 'HOME', 'PAGE_UP'],
    ['DELETE', 'END', 'PAGE_DOWN'],
    [' ', ' ', ' '],
    [' ', ' ', ' '],
    [' ', ' ', ' '],
    [' ', ' ', ' '],
    [' ', 'UP', ' '],
    ['DOWN', 'LEFT', 'RIGHT'],
]

# ---------------------------------------------
# Properties
# ---------------------------------------------
class KeymapCheckerPrefs(bpy.types.PropertyGroup):
    editor: bpy.props.EnumProperty(
        name="Editor",
        items=[(k, v, "") for k, v in editor_map.items()],
        default='VIEW_3D'
    )
    screen_always_on: bpy.props.BoolProperty(
        name="Screen Always ON",
        description="Also consider Screen/Window/UI keymaps with the chosen editor",
        default=True
    )
    # NEW: hide modal map results (Knife/Bevel/Transform modal, etc.)
    hide_modal: bpy.props.BoolProperty(
        name="Hide Model",
        description="Hide modal keymap results (Knife/Bevel/Transform modal maps, etc.)",
        default=True
    )
    ctrl: bpy.props.BoolProperty(name="Ctrl", default=False)
    shift: bpy.props.BoolProperty(name="Shift", default=False)
    alt: bpy.props.BoolProperty(name="Alt", default=False)
    cmd: bpy.props.BoolProperty(
        name="Cmd", default=False,
        description="Mac Command key"
    ) if platform.system() == 'Darwin' else bpy.props.BoolProperty(name="Cmd", default=False)
    selected_key: bpy.props.StringProperty(name="Selected Key", default="")

# ---------------------------------------------
# Helpers
# ---------------------------------------------
def is_relevant_keymap(km, editor):
    """
    Return True only for keymaps that belong to the chosen editor.
    - Exact space_type match always counts.
    - UV Editor in Blender >= 4.5: accept by name too (some maps don't report space_type='UV').
    - For global scopes (SCREEN/EMPTY/USER_INTERFACE), accept broad/global names.
    """
    space = km.space_type or 'EMPTY'
    name = (km.name or "")

    # Exact space type match
    if space == editor:
        return True

    # Special handling for UV Editor in 4.5+
    if editor == 'UV':
        # Many UV maps have names like "UV Editor", "UV Sculpt", "UV Editor Tool..."
        if ('UV' in name) or ('UV Editor' in name):
            return True
        # Also accept legacy cases where UV lived under Image Editor
        if space == 'IMAGE_EDITOR' and ('UV' in name or 'UV Editor' in name):
            return True

    # Global scopes accept broad/global names
    if editor in {'SCREEN', 'EMPTY', 'USER_INTERFACE'}:
        global_keywords = ("Window", "Screen", "Global", "User Interface", "UI", "PME", "Pie Menu Editor")
        return any(k in name for k in global_keywords)

    # Otherwise, no fuzzy matching
    return False


def normalize_key_types(label: str):
    """
    Map UI label to Blender key types.
    Distinguish main number row from NUMPAD_* keys.
    """
    # F-keys passthrough
    if label.startswith("F") and label[1:].isdigit():
        return [label]

    # Arrow keys use *_ARROW
    if label in {"UP", "DOWN", "LEFT", "RIGHT"}:
        return [f"{label}_ARROW"]

    # Main keyboard specials
    special = {
        "TAB": ["TAB"],
        "ESC": ["ESC"],
        "SPACE": ["SPACE"],
        "BACK_SPACE": ["BACK_SPACE"],
        "RETURN": ["RET"],          # main return/enter
        "ENTER": ["RET"],
        "DELETE": ["DEL"],
        "INSERT": ["INSERT"],
        "HOME": ["HOME"],
        "END": ["END"],
        "PAGE_UP": ["PAGE_UP"],
        "PAGE_DOWN": ["PAGE_DOWN"],
    }
    if label in special:
        return special[label]

    # Main row numbers -> Blender uses word names for main row digits
    if label in {"0","1","2","3","4","5","6","7","8","9"}:
        num_map = {
            "0": "ZERO", "1": "ONE", "2": "TWO", "3": "THREE", "4": "FOUR",
            "5": "FIVE", "6": "SIX", "7": "SEVEN", "8": "EIGHT", "9": "NINE",
        }
        return [num_map[label]]

    # Main row punctuation (non-numpad)
    punct = {
        "`": ["ACCENT_GRAVE", "GRAVE"],
        "-": ["MINUS"],
        "=": ["EQUAL"],
        "[": ["LEFT_BRACKET"],
        "]": ["RIGHT_BRACKET"],
        "\\": ["BACK_SLASH"],
        ";": ["SEMI_COLON"],
        "'": ["QUOTE"],
        ",": ["COMMA"],
        ".": ["PERIOD"],
        "/": ["SLASH"],
        "+": ["PLUS"],
    }
    if label in punct:
        return punct[label]

    # NUMPAD_* already normalized (we pass explicit NUMPAD_* from numpad grid)
    if label.startswith("NUMPAD_"):
        return [label]

    # Default: letters and others pass through
    return [label]

def _iter_all_keyconfigs():
    """Yield all available keyconfigs (default, user, addon, active) without duplicates."""
    wm = bpy.context.window_manager
    kcs = []
    for kc in (
        getattr(wm.keyconfigs, "default", None),
        getattr(wm.keyconfigs, "user", None),
        getattr(wm.keyconfigs, "addon", None),
        getattr(wm.keyconfigs, "active", None),
    ):
        if kc and kc not in kcs:
            kcs.append(kc)
    try:
        for kc in wm.keyconfigs:
            if kc and kc not in kcs:
                kcs.append(kc)
    except Exception:
        pass
    for kc in kcs:
        yield kc

def _modifiers_match(kmi, ctrl, shift, alt, cmd):
    """Strict modifier match:
       - exact equality for ctrl/shift/alt/oskey
       - if kmi.any is True, only match when no modifiers are selected in the UI
       - key_modifier is informational and does not affect matching
    """
    # If the keymap item allows ANY modifiers, only show it when the UI has none selected
    if getattr(kmi, "any", False):
        return not (ctrl or shift or alt or cmd)

    # Exact match for the four standard modifiers
    return (
        bool(kmi.ctrl)  == bool(ctrl)  and
        bool(kmi.shift) == bool(shift) and
        bool(kmi.alt)   == bool(alt)   and
        bool(kmi.oskey) == bool(cmd)
    )

def _global_editors_for_merge():
    return ('SCREEN', 'EMPTY', 'USER_INTERFACE')

# ---- de-dup signature helpers ------------------------------------------------
def _sig_for_kmi(km, kmi):
    """Signature identifying the *meaning* of a mapping across keyconfigs.
    Same id if same keymap name + operator + display name + value + key_modifier."""
    return (
        km.name or "",
        kmi.idname or "",
        kmi.name or "",
        getattr(kmi, "value", "PRESS"),
        getattr(kmi, "key_modifier", "NONE"),
    )

def _format_kmi_label(kc_names, km, kmi):
    """Build a single line label; kc_names is a joined string of sources after merging.
    Handles modal maps where idname/name can be empty by showing the modal event instead.
    """
    op = (getattr(kmi, "idname", "") or "").strip()
    disp = (getattr(kmi, "name", "") or "").strip()

    # Modal maps (e.g., "Knife Tool Modal Map") often have empty idname/name; show event instead
    if getattr(km, "is_modal", False) and not op:
        # Try common modal fields in order; fall back to key type
        event = (
            getattr(kmi, "propvalue", None)
            or getattr(kmi, "propvalue_str", None)
            or getattr(kmi, "modal", None)
            or getattr(kmi, "type", None)
            or "Modal Event"
        )
        # Nicely format event token
        event_str = str(event).replace("_", " ").title()
        label = f"{kc_names}: {km.name} > {event_str}"
    else:
        base = op if op else (disp if disp else "(Unknown)")
        label = f"{kc_names}: {km.name} > {base}"
        if disp and disp != op:
            label += f" ({disp})"

    # Extras/annotations
    extras = []
    if getattr(kmi, "any", False):
        extras.append("any-mod")
    kmv = getattr(kmi, "value", None)
    if kmv and kmv != 'PRESS':
        extras.append(f"value:{kmv}")
    key_mod = getattr(kmi, "key_modifier", 'NONE')
    if key_mod not in (None, 'NONE', 'UNKNOWN', ''):
        extras.append(f"key_mod:{key_mod}")
    if extras:
        label += " [" + ", ".join(extras) + "]"

    return label

# ---- core queries with merging ------------------------------------------------
def get_keymap_matches_in_editor(key_label, editor, ctrl, shift, alt, cmd, hide_modal=False):
    key_types = normalize_key_types(key_label)
    merged = {}  # sig -> (km, kmi, set(kc_names))
    order = []

    for kc in _iter_all_keyconfigs():
        kc_name = kc.name
        for km in kc.keymaps:
            if hide_modal and getattr(km, "is_modal", False):
                continue
            if not is_relevant_keymap(km, editor):
                continue
            for kmi in km.keymap_items:
                if not kmi.active:
                    continue
                if (kmi.type in key_types and _modifiers_match(kmi, ctrl, shift, alt, cmd)):
                    sig = _sig_for_kmi(km, kmi)
                    if sig not in merged:
                        merged[sig] = (km, kmi, {kc_name})
                        order.append(sig)
                    else:
                        merged[sig][2].add(kc_name)

    out = []
    for sig in order:
        km, kmi, kc_names = merged[sig]
        sources = ", ".join(sorted(kc_names))
        out.append(_format_kmi_label(sources, km, kmi))
    return out

def is_key_assigned_in_editor(key_label, editor, ctrl, shift, alt, cmd, hide_modal=False):
    """Return True if key is assigned in the given editor (optionally skipping modal maps)."""
    key_types = normalize_key_types(key_label)
    for kc in _iter_all_keyconfigs():
        for km in kc.keymaps:
            if hide_modal and getattr(km, "is_modal", False):
                continue
            if not is_relevant_keymap(km, editor):
                continue
            for kmi in km.keymap_items:
                if not kmi.active:
                    continue
                if (kmi.type in key_types and _modifiers_match(kmi, ctrl, shift, alt, cmd)):
                    return True
    return False

def is_key_assigned(key_label, editor, ctrl, shift, alt, cmd, screen_always_on=False, hide_modal=False):
    if is_key_assigned_in_editor(key_label, editor, ctrl, shift, alt, cmd, hide_modal=hide_modal):
        return True
    if screen_always_on:
        for ed in _global_editors_for_merge():
            if is_key_assigned_in_editor(key_label, ed, ctrl, shift, alt, cmd, hide_modal=hide_modal):
                return True
    return False

def get_keymap_matches(key_label, editor, ctrl, shift, alt, cmd, screen_always_on=False, hide_modal=False):
    out = get_keymap_matches_in_editor(key_label, editor, ctrl, shift, alt, cmd, hide_modal=hide_modal)
    if screen_always_on:
        for ed in _global_editors_for_merge():
            extra = get_keymap_matches_in_editor(key_label, ed, ctrl, shift, alt, cmd, hide_modal=hide_modal)
            seen = set(out)
            for r in extra:
                if r not in seen:
                    out.append(r); seen.add(r)
    return out

def get_keymap_conflicts(key_label, current_editor, ctrl, shift, alt, cmd, hide_modal=False):
    key_types = normalize_key_types(key_label)
    merged = {}  # sig -> (km, kmi, set(kc_names))
    order = []

    for kc in _iter_all_keyconfigs():
        kc_name = kc.name
        for km in kc.keymaps:
            if hide_modal and getattr(km, "is_modal", False):
                continue
            if is_relevant_keymap(km, current_editor):
                continue
            for kmi in km.keymap_items:
                if not kmi.active:
                    continue
                if (kmi.type in key_types and _modifiers_match(kmi, ctrl, shift, alt, cmd)):
                    sig = _sig_for_kmi(km, kmi)
                    if sig not in merged:
                        merged[sig] = (km, kmi, {kc_name})
                        order.append(sig)
                    else:
                        merged[sig][2].add(kc_name)

    out = []
    for sig in order:
        km, kmi, kc_names = merged[sig]
        sources = ", ".join(sorted(kc_names))
        out.append(_format_kmi_label(sources, km, kmi))
    return out

# ---------------------------------------------
# Operators
# ---------------------------------------------
class WM_OT_SelectKey(bpy.types.Operator):
    bl_idname = "wm.select_keymap_key"
    bl_label = "Select Key"
    key: bpy.props.StringProperty()

    def execute(self, context):
        prefs = context.scene.keymap_checker
        assigned = is_key_assigned(
            self.key, prefs.editor, prefs.ctrl, prefs.shift, prefs.alt, prefs.cmd,
            screen_always_on=prefs.screen_always_on, hide_modal=prefs.hide_modal
        )
        if assigned:
            prefs.selected_key = self.key

        for area in context.screen.areas:
            if area.type == 'VIEW_3D':
                for region in area.regions:
                    if region.type == 'UI':
                        region.tag_redraw()
        return {'FINISHED'}

# ---------------------------------------------
# Panel
# ---------------------------------------------
class VIEW3D_PT_KeymapChecker(bpy.types.Panel):
    bl_label = "KeymapVisualizer"
    bl_idname = "VIEW3D_PT_keymap_visualizer"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'Keymap'


    def draw(self, context):
        layout = self.layout
        prefs = context.scene.keymap_checker

        # Editor + Screen Always ON + Hide Modal
        row = layout.row(align=True)
        row.prop(prefs, "editor")
        row.prop(prefs, "screen_always_on", text="Screen Always ON", toggle=True)
        row.prop(prefs, "hide_modal", text="Hide Modal", toggle=True)

        # Modifiers
        row = layout.row(align=True)
        row.prop(prefs, "ctrl", toggle=True)
        row.prop(prefs, "shift", toggle=True)
        row.prop(prefs, "alt", toggle=True)
        if platform.system() == 'Darwin':
            row.prop(prefs, "cmd", toggle=True)
        layout.separator()

        def key_used_here_or_screen(key_label: str) -> bool:
            return is_key_assigned(
                key_label, prefs.editor, prefs.ctrl, prefs.shift, prefs.alt, prefs.cmd,
                screen_always_on=prefs.screen_always_on, hide_modal=prefs.hide_modal
            )

        # Keyboard
        box = layout.box()
        box.label(text="Keyboard:")
        for row_keys in qwerty_keys:
            row = box.row(align=True)
            for k in row_keys:
                col = row.column(); col.scale_x = 1.0
                is_used = key_used_here_or_screen(k)
                props = col.operator("wm.select_keymap_key", text=k, depress=(prefs.selected_key == k), emboss=is_used)
                props.key = k
        layout.separator()

        # Cursor / Numpad
        split = layout.split(factor=0.5)

        col_left = split.column()
        box_left = col_left.box()
        box_left.label(text="Cursor and Navigation Keys:")
        for row_keys in cursor_keys:
            row = box_left.row(align=True)
            for k in row_keys:
                col = row.column(); col.scale_x = 1.0 if k != ' ' else 0.5
                if k != ' ':
                    is_used = key_used_here_or_screen(k)
                    props = col.operator("wm.select_keymap_key", text=k, depress=(prefs.selected_key == k), emboss=is_used)
                    props.key = k

        col_right = split.column()
        box_right = col_right.box()
        box_right.label(text="Numpad:")
        for row_keys in numpad_keys:
            row = box_right.row(align=True)
            for k in row_keys:
                col = row.column(); col.scale_x = 1.0
                if k == ' ':
                    col.label(text=""); continue
                if k in '0123456789':
                    key_id = f"NUMPAD_{k}"
                elif k == '.': key_id = "NUMPAD_PERIOD"
                elif k == '/': key_id = "NUMPAD_SLASH"
                elif k == '*': key_id = "NUMPAD_ASTERIX"
                elif k == '-': key_id = "NUMPAD_MINUS"
                elif k == '+': key_id = "NUMPAD_PLUS"
                elif k == 'ENTER': key_id = "NUMPAD_ENTER"
                elif k == '=': key_id = "NUMPAD_EQUALS"
                else: key_id = k
                is_used = key_used_here_or_screen(key_id)
                props = col.operator("wm.select_keymap_key", text=k, depress=(prefs.selected_key == key_id), emboss=is_used)
                props.key = key_id
        layout.separator()

        # Assignment Details
        layout.label(text="Assignment Details:")
        if prefs.selected_key:
            mods = []
            if prefs.ctrl: mods.append("Ctrl")
            if prefs.shift: mods.append("Shift")
            if prefs.alt: mods.append("Alt")
            if prefs.cmd and platform.system() == 'Darwin': mods.append("Cmd")
            layout.label(text=f"Selected: {prefs.selected_key} with modifiers: {'+'.join(mods) if mods else 'None'}")

            # First list: only current editor
            matches = get_keymap_matches_in_editor(
                prefs.selected_key,
                prefs.editor,
                prefs.ctrl,
                prefs.shift,
                prefs.alt,
                prefs.cmd,
                hide_modal=prefs.hide_modal
            )

            # Intra-editor conflict = more than one match
            intra_conflict = len(matches) > 1

            if matches:
                for m in matches:
                    if intra_conflict:
                        layout.label(text=m, icon='ERROR')  # red warning icon
                    else:
                        layout.label(text=m)
            else:
                layout.label(text="No assignment found for current scope.")

            # Other editors
            conflicts = get_keymap_conflicts(
                prefs.selected_key, prefs.editor, prefs.ctrl, prefs.shift, prefs.alt, prefs.cmd,
                hide_modal=prefs.hide_modal
            )
            if conflicts:
                layout.separator()
                layout.label(text="Also used in:")
                for c in conflicts:
                    layout.label(text=c)
        else:
            layout.label(text="(Click an assigned key to view its assignment)")


# ---------------------------------------------
# Registration
# ---------------------------------------------
classes = [
    KeymapCheckerPrefs,
    WM_OT_SelectKey,
    VIEW3D_PT_KeymapChecker,
]

def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.Scene.keymap_checker = bpy.props.PointerProperty(type=KeymapCheckerPrefs)

def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
    del bpy.types.Scene.keymap_checker

if __name__ == "__main__":
    register()

