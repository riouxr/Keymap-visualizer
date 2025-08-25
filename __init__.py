
import bpy
import platform
from bpy.app.handlers import persistent

# ---------------------------------------------
# Debug Control
# ---------------------------------------------
DEBUG_KEYMAPS = False  # Set to True to enable debug prints, False to disable
_LAST_DEBUG_SIG = None  # for throttled debug prints

def _debug_print(*args, **kwargs):
    if DEBUG_KEYMAPS:
        print(*args, **kwargs)

# ---------------------------------------------
# Editor map (space types and related scopes)
# ---------------------------------------------
editor_map = {
    'VIEW_3D': '3D Viewport',
    'IMAGE_EDITOR': 'Image / UV',
    'GRAPH_EDITOR': 'Graph Editor',
    'DOPESHEET_EDITOR': 'Dope Sheet',
    'NLA_EDITOR': 'NLA Editor',
    'SEQUENCE_EDITOR': 'Video Sequence',
    'NODE_EDITOR': 'Node Editor',
    'OUTLINER': 'Outliner',
    'TEXT_EDITOR': 'Text Editor',
    'PROPERTIES': 'Properties',
    'CONSOLE': 'Console',
    'PREFERENCES': 'Preferences',
    'CLIP_EDITOR': 'Movie Clip',
    'EMPTY': 'Window',
    'SCREEN': 'Screen',
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
        name="System Keymaps",
        description="Include a separate informational section for system-wide keymaps (Screen + Window)",
        default=True
    )
    hide_modal: bpy.props.BoolProperty(
        name="Hide Modal",
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

def _full_binding_sig(km, kmi):
    """Exact binding identity: key + mods + value + key_modifier + operator scope."""
    return (
        km.name or "",
        kmi.idname or "",
        getattr(kmi, "type", None),
        bool(getattr(kmi, "ctrl", False)),
        bool(getattr(kmi, "shift", False)),
        bool(getattr(kmi, "alt", False)),
        bool(getattr(kmi, "oskey", False)),
        bool(getattr(kmi, "any", False)),
        getattr(kmi, "value", "PRESS"),
        getattr(kmi, "key_modifier", "NONE"),
    )

def _collect_disabled_binding_sigs():
    """
    Disabled binding mask from user/active keyconfigs keyed by FULL binding (not just operator/name).
    Prevents 'disabled in User' from leaking in via Add-on, but only for the exact binding.
    """
    disabled = set()
    wm = bpy.context.window_manager
    for kc in (getattr(wm.keyconfigs, "user", None), getattr(wm.keyconfigs, "active", None)):
        if not kc:
            continue
        for km in kc.keymaps:
            for kmi in km.keymap_items:
                if not getattr(kmi, "active", True):
                    disabled.add(_full_binding_sig(km, kmi))
    return disabled

# ============================================================
# HIGHLIGHT CACHE — ASSIGNED CONTEXT (filtered) OR RAW GLOBALS
# ============================================================

keymap_cache = {}
last_keyconfig_fingerprint = None

def _compute_keyconfig_fingerprint():
    try:
        wm = bpy.context.window_manager
        parts = []
        for kc_name in ("default", "user", "addon", "active"):
            kc = getattr(wm.keyconfigs, kc_name, None)
            if not kc:
                parts.append((kc_name, 0))
                continue
            cnt = 0
            for km in kc.keymaps:
                cnt += len(km.keymap_items)
            parts.append((kc_name, cnt))
        return tuple(parts)
    except Exception:
        return None

def clear_keymap_cache():
    keymap_cache.clear()

def is_cache_valid(_context):
    global last_keyconfig_fingerprint
    fp = _compute_keyconfig_fingerprint()
    if fp != last_keyconfig_fingerprint:
        last_keyconfig_fingerprint = fp
        return False
    return True

def get_cache_key(editor, ctrl, shift, alt, cmd, screen_always_on, hide_modal, mode_str):
    return (editor, bool(ctrl), bool(shift), bool(alt), bool(cmd),
            bool(screen_always_on), bool(hide_modal), mode_str)

# ---- helpers (match panel) ----
def _compact_rows(rows):
    merged, order = {}, []
    for label_txt, sig, kc_names in rows:
        k = (sig[1], sig[3], sig[4])  # (idname, value, key_mod)
        if k not in merged:
            merged[k] = (label_txt, sig, list(kc_names))
            order.append(k)
        else:
            prev_label, prev_sig, prev_kc = merged[k]
            merged[k] = (prev_label, prev_sig, sorted(set(prev_kc) | set(kc_names)))
    return [merged[k] for k in order]

def _only_press(rows):
    return [r for r in rows if r[1][3] == 'PRESS']

def _allow_global_for_editor(opid_lc, editor_id, mode_str):
    if editor_id == 'VIEW_3D':
        allowed_by_mode = {
            'OBJECT':       ('object.', 'mesh.', 'view3d.', 'pose.', 'armature.', 'wm.pme_user_pie_menu_call'),
            'EDIT_MESH':    ('mesh.', 'view3d.', 'uv.', 'curve.', 'curves.', 'wm.pme_user_pie_menu_call'),
            'EDIT_CURVE':   ('curve.', 'curves.', 'view3d.', 'wm.pme_user_pie_menu_call'),
            'EDIT_SURFACE': ('curve.', 'view3d.', 'wm.pme_user_pie_menu_call'),
            'SCULPT':       ('sculpt.', 'view3d.', 'wm.pme_user_pie_menu_call'),
            'PAINT_VERTEX': ('paint.', 'view3d.', 'wm.pme_user_pie_menu_call'),
            'PAINT_WEIGHT': ('paint.', 'view3d.', 'wm.pme_user_pie_menu_call'),
            'PAINT_TEXTURE':('paint.', 'view3d.', 'wm.pme_user_pie_menu_call'),
            'SCULPT_CURVES':('curves.', 'view3d.', 'wm.pme_user_pie_menu_call'),
            'PARTICLE_EDIT':('particle.', 'view3d.', 'wm.pme_user_pie_menu_call'),
            'POSE':         ('pose.', 'armature.', 'object.', 'view3d.', 'wm.pme_user_pie_menu_call'),
            'EDIT_ARMATURE':('armature.', 'view3d.', 'wm.pme_user_pie_menu_call'),
        }
        allowed = allowed_by_mode.get(mode_str, ('view3d.', 'object.', 'mesh.', 'wm.pme_user_pie_menu_call'))
        return opid_lc.startswith(allowed) or (opid_lc == 'wm.pme_user_pie_menu_call')
    if editor_id == 'UV':
        return opid_lc.startswith(('uv.', 'image.', 'wm.pme_user_pie_menu_call'))
    if editor_id == 'IMAGE_EDITOR':
        return opid_lc.startswith(('image.', 'mask.', 'uv.', 'wm.pme_user_pie_menu_call'))
    family = {
        'GRAPH_EDITOR': ('graph.', 'anim.', 'wm.pme_user_pie_menu_call'),
        'DOPESHEET_EDITOR': ('anim.', 'action.', 'wm.pme_user_pie_menu_call'),
        'NLA_EDITOR': ('nla.', 'wm.pme_user_pie_menu_call'),
        'SEQUENCE_EDITOR': ('sequencer.', 'wm.pme_user_pie_menu_call'),
        'NODE_EDITOR': ('node.', 'wm.pme_user_pie_menu_call'),
        'CLIP_EDITOR': ('clip.', 'wm.pme_user_pie_menu_call'),
        'OUTLINER': ('outliner.', 'wm.pme_user_pie_menu_call'),
        'TEXT_EDITOR': ('text.', 'wm.pme_user_pie_menu_call'),
        'FILE_BROWSER': ('file.', 'wm.pme_user_pie_menu_call'),
    }.get(editor_id, ('wm.pme_user_pie_menu_call',))
    return opid_lc.startswith(family) or (opid_lc == 'wm.pme_user_pie_menu_call')

def _filter_global_rows_for_context(rows, editor_id, mode_str):
    out = []
    for label_txt, sig, kc_names in rows:
        opid_lc = (sig[1] or '').lower()
        if _allow_global_for_editor(opid_lc, editor_id, mode_str):
            out.append((label_txt, sig, kc_names))
    return out

# Rows for the merged "Assigned in current context" (editor PRESS + filtered global PRESS)
def _rows_for_assigned_context(context, key_label):
    prefs = context.scene.keymap_checker
    mode_str = getattr(context, "mode", "OBJECT") or "OBJECT"

    ed = _only_press(get_keymap_matches_in_editor(
        key_label, prefs.editor, prefs.ctrl, prefs.shift, prefs.alt, prefs.cmd, hide_modal=prefs.hide_modal
    ))
    ed = _compact_rows(ed)

    merged = list(ed)
    if prefs.screen_always_on:
        gl = _only_press(get_global_matches(
            key_label, prefs.ctrl, prefs.shift, prefs.alt, prefs.cmd, hide_modal=prefs.hide_modal
        ))
        gl = _compact_rows(gl)
        gl = _filter_global_rows_for_context(gl, prefs.editor, mode_str)  # keep merged view clean
        merged.extend(gl)
        merged = _compact_rows(merged)
    return merged

# Rows for the visible "In global scopes" section — RAW globals (PRESS only), NO editor/mode filter
def _rows_for_global_scopes_section(context, key_label):
    prefs = context.scene.keymap_checker
    if not prefs.screen_always_on:
        return []
    gl = _only_press(get_global_matches(
        key_label, prefs.ctrl, prefs.shift, prefs.alt, prefs.cmd, hide_modal=prefs.hide_modal
    ))
    gl = _compact_rows(gl)
    return gl

def populate_keymap_cache(context):
    global keymap_cache
    prefs = context.scene.keymap_checker
    mode_str = getattr(context, "mode", "OBJECT") or "OBJECT"
    cache_key = get_cache_key(
        prefs.editor, prefs.ctrl, prefs.shift, prefs.alt, prefs.cmd,
        prefs.screen_always_on, prefs.hide_modal, mode_str
    )
    if cache_key in keymap_cache:
        return keymap_cache[cache_key]

    cache = {}

    def _highlight_for(label):
        # Highlight if either list the user can see has rows.
        if _rows_for_assigned_context(context, label):
            return True
        if _rows_for_global_scopes_section(context, label):
            return True
        return False

    # QWERTY
    for row_keys in qwerty_keys:
        for k in row_keys:
            cache[k] = _highlight_for(k)

    # Cursor/navigation
    for row_keys in cursor_keys:
        for k in row_keys:
            if k != ' ':
                cache[k] = _highlight_for(k)

    # Numpad
    for row_keys in numpad_keys:
        for k in row_keys:
            if k == ' ':
                continue
            key_id = (
                f"NUMPAD_{k}" if k in '0123456789' else
                "NUMPAD_PERIOD" if k == '.' else
                "NUMPAD_SLASH"  if k == '/' else
                "NUMPAD_ASTERIX" if k == '*' else
                "NUMPAD_MINUS"  if k == '-' else
                "NUMPAD_PLUS"   if k == '+' else
                "NUMPAD_ENTER"  if k == 'ENTER' else
                "NUMPAD_EQUALS" if k == '=' else k
            )
            cache[key_id] = _highlight_for(key_id)

    keymap_cache[cache_key] = cache
    return cache

def is_key_used_cached(context, key_label):
    if not is_cache_valid(context):
        clear_keymap_cache()
    prefs = context.scene.keymap_checker
    mode_str = getattr(context, "mode", "OBJECT") or "OBJECT"
    cache_key = get_cache_key(
        prefs.editor, prefs.ctrl, prefs.shift, prefs.alt, prefs.cmd,
        prefs.screen_always_on, prefs.hide_modal, mode_str
    )
    cache = keymap_cache.get(cache_key)
    if cache is None:
        cache = populate_keymap_cache(context)
    return cache.get(key_label, False)


# --- Original Helper Functions (mostly unchanged) ---

def is_relevant_keymap(km, editor):
    """
    Return True only for keymaps relevant to the chosen editor.
    Rules:
      • Exact space_type match counts (except UV special case below).
      • UV Editor: only IMAGE_EDITOR keymaps that are UV-specific (by name).
      • Non‑UV editors: block UV‑named maps.
      • Global scopes (SCREEN/EMPTY) are not treated as 'current editor'.
    """
    space = km.space_type or 'EMPTY'
    name = (km.name or "").lower()

    # UV Editor special case:
    #   Accept ONLY IMAGE_EDITOR keymaps whose name mentions 'uv'
    if editor == 'UV':
        return (space == 'IMAGE_EDITOR') and ('uv' in name)

    # For any non‑UV editor, block UV‑named maps
    if 'uv' in name and editor != 'UV':
        return False

    # Editor must match by space_type (never treat SCREEN/EMPTY as editor)
    if space == editor:
        return True

    # Otherwise not relevant for the current editor
    return False

def _collect_disabled_sigs():
    disabled = set()
    wm = bpy.context.window_manager
    for kc in (getattr(wm.keyconfigs, "user", None),
               getattr(wm.keyconfigs, "active", None)):
        if not kc:
            continue
        for km in kc.keymaps:
            for kmi in km.keymap_items:
                if not getattr(kmi, "active", True):
                    disabled.add(_sig_for_kmi(km, kmi))
    return disabled


def normalize_key_types(label: str):
    if label.startswith("F") and label[1:].isdigit():
        return [label]
    if label in {"UP", "DOWN", "LEFT", "RIGHT"}:
        return [f"{label}_ARROW"]
    special = {
        "TAB": ["TAB"],
        "ESC": ["ESC"],
        "SPACE": ["SPACE"],
        "BACK_SPACE": ["BACK_SPACE"],
        "RETURN": ["RET"],
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
    if label in {"0","1","2","3","4","5","6","7","8","9"}:
        num_map = {
            "0": "ZERO", "1": "ONE", "2": "TWO", "3": "THREE", "4": "FOUR",
            "5": "FIVE", "6": "SIX", "7": "SEVEN", "8": "EIGHT", "9": "NINE",
        }
        return [num_map[label]]
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
    if label.startswith("NUMPAD_"):
        return [label]
    return [label]

def _iter_all_keyconfigs():
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
            _debug_print(f"Keyconfig: {kc.name}")
    try:
        for kc in wm.keyconfigs:
            if kc and kc not in kcs:
                kcs.append(kc)
                _debug_print(f"Keyconfig: {kc.name}")
    except Exception as e:
        _debug_print(f"Error iterating keyconfigs: {e}")
    for kc in kcs:
        yield kc

def _modifiers_match(kmi, ctrl, shift, alt, cmd):
    if getattr(kmi, "any", False):
        return not (ctrl or shift or alt or cmd)
    return (
        bool(kmi.ctrl)  == bool(ctrl)  and
        bool(kmi.shift) == bool(shift) and
        bool(kmi.alt)   == bool(alt)   and
        bool(kmi.oskey) == bool(cmd)
    )

def _sig_for_kmi(km, kmi):
    return (
        km.name or "",
        kmi.idname or "",
        kmi.name or "",
        getattr(kmi, "value", "PRESS"),
        getattr(kmi, "key_modifier", "NONE"),
    )

def get_system_conflicts(key_label, editor, ctrl, shift, alt, cmd, hide_modal=False):
    def _scan(scope):
        return get_keymap_matches_in_editor(key_label, scope, ctrl, shift, alt, cmd, hide_modal=hide_modal)

    sys_labels = []
    for sys_scope in ('SCREEN', 'EMPTY'):
        sys_labels.extend(_scan(sys_scope))
    if not sys_labels:
        return []

    ed_labels = _scan(editor)
    if not ed_labels:
        return []

    return sys_labels

def get_keymap_matches(key_label, editor, ctrl, shift, alt, cmd, screen_always_on=False, hide_modal=False):
    """
    RETURN EDITOR-ONLY rows (no merge). Global rows are retrieved separately.
    """
    return get_keymap_matches_in_editor(key_label, editor, ctrl, shift, alt, cmd, hide_modal=hide_modal)

def get_global_matches(key_label, ctrl, shift, alt, cmd, hide_modal=False):
    """
    Return merged rows from Window/Screen (EMPTY + SCREEN), deduped by signature.
    Used only for the separate 'Global scopes' section.
    """
    key_types = normalize_key_types(key_label)
    disabled_bindings = _collect_disabled_binding_sigs()

    merged = {}
    order = []
    for kc in _iter_all_keyconfigs():
        kc_name = kc.name
        for km in kc.keymaps:
            if hide_modal and getattr(km, "is_modal", False):
                continue
            space = km.space_type or 'EMPTY'
            if space not in {'EMPTY', 'SCREEN'}:
                continue

            for kmi in km.keymap_items:
                if not kmi.active:
                    continue
                if kmi.type not in key_types:
                    continue
                if not _modifiers_match(kmi, ctrl, shift, alt, cmd):
                    continue
                if _full_binding_sig(km, kmi) in disabled_bindings:
                    continue

                sig = _sig_for_kmi(km, kmi)
                if sig not in merged:
                    merged[sig] = (km, kmi, {kc_name})
                    order.append(sig)
                else:
                    merged[sig][2].add(kc_name)

    out = []
    for sig in order:
        km, kmi, kc_names = merged[sig]
        label = _format_kmi_label(", ".join(sorted(kc_names)), km, kmi)
        out.append((label, sig, sorted(kc_names)))
    return out

def _format_kmi_label(kc_names, km, kmi):
    space = (km.space_type or 'EMPTY')
    editor_display = editor_map.get(space, km.name or space)
    op = (getattr(kmi, "idname", "") or "").strip()
    disp = (getattr(kmi, "name", "") or "").strip()

    if getattr(km, "is_modal", False) and not op:
        event = (
            getattr(kmi, "propvalue", None)
            or getattr(kmi, "propvalue_str", None)
            or getattr(kmi, "modal", None)
            or getattr(kmi, "type", None)
            or "Modal Event"
        )
        event_str = str(event).replace("_", " ").title()
        label = f"{kc_names}: {editor_display} > {event_str}"
    else:
        base = op if op else (disp if disp else "(Unknown)")
        label = f"{kc_names}: {editor_display} > {base}"
        if disp and disp != op:
            label += f" ({disp})"

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

def _global_editors_for_merge():
    return ('SCREEN', 'EMPTY')

def get_keymap_matches_in_editor(key_label, editor, ctrl, shift, alt, cmd, hide_modal=False):
    """
    Return rows ONLY from the selected editor (no Window/Screen merge).
    UV mode is extra‑strict: even within IMAGE_EDITOR, accept only UV operators.
    """
    key_types = normalize_key_types(key_label)
    disabled_bindings = _collect_disabled_binding_sigs()

    merged = {}
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
                if kmi.type not in key_types:
                    continue
                if not _modifiers_match(kmi, ctrl, shift, alt, cmd):
                    continue
                if _full_binding_sig(km, kmi) in disabled_bindings:
                    continue

                # Extra UV strictness: only UV operators count when editor == 'UV'
                if editor == 'UV':
                    id_lc = (getattr(kmi, "idname", "") or "").lower()
                    name_lc = (getattr(kmi, "name", "") or "").lower()
                    if not ('uv.' in id_lc or name_lc.startswith('uv ') or ' uv ' in name_lc):
                        continue

                sig = _sig_for_kmi(km, kmi)
                if sig not in merged:
                    merged[sig] = (km, kmi, {kc_name})
                    order.append(sig)
                else:
                    merged[sig][2].add(kc_name)

    out = []
    for sig in order:
        km, kmi, kc_names = merged[sig]
        label = _format_kmi_label(", ".join(sorted(kc_names)), km, kmi)
        out.append((label, sig, sorted(kc_names)))
    return out

def get_keymap_conflicts(key_label, current_editor, ctrl, shift, alt, cmd,
                         screen_always_on=False, hide_modal=False):
    """
    Returns FIVE lists (no scope mixing):
      1) editor_rows              -> all matches in the current editor
      2) global_rows              -> all matches in Window/Screen (deduped)
      3) intra_editor_conflicts   -> editor_rows if there are 2+ distinct entries, else []
      4) editor_overlap_rows      -> subset of editor_rows whose (idname,value,key_mod) also exists in global
      5) global_overlap_rows      -> subset of global_rows whose (idname,value,key_mod) also exists in editor
    """
    # Current editor matches
    editor_rows = get_keymap_matches_in_editor(
        key_label, current_editor, ctrl, shift, alt, cmd, hide_modal=hide_modal
    )

    # Global (Window/Screen) matches and compact them (dedupe spammy duplicates)
    global_full = get_global_matches(
        key_label, ctrl, shift, alt, cmd, hide_modal=hide_modal
    )
    compact = {}
    order = []
    for label_txt, sig, kc_names in global_full:
        # sig = (km.name, kmi.idname, kmi.name, value, key_modifier)
        k = (sig[1], sig[3], sig[4])  # (idname, value, key_modifier)
        if k not in compact:
            compact[k] = (label_txt, sig, kc_names)
            order.append(k)
    global_rows = [compact[k] for k in order]

    # Intra‑editor conflict = multiple distinct entries inside the editor
    intra_editor_conflicts = editor_rows if len(editor_rows) > 1 else []

    # Build overlap sets by operator signature (same binding on global & editor)
    def sig3(row):  # (idname,value,key_modifier)
        _sig = row[1]
        return (_sig[1], _sig[3], _sig[4])

    editor_sigset = {sig3(r) for r in editor_rows}
    global_sigset = {sig3(r) for r in global_rows}
    overlap = editor_sigset & global_sigset

    editor_overlap_rows = [r for r in editor_rows if sig3(r) in overlap]
    global_overlap_rows = [r for r in global_rows if sig3(r) in overlap]

    return editor_rows, global_rows, intra_editor_conflicts, editor_overlap_rows, global_overlap_rows

# ---------------------------------------------
# Operators
# ---------------------------------------------
class WM_OT_SelectKey(bpy.types.Operator):
    bl_idname = "wm.select_keymap_key"
    bl_label = "Select Key"
    key: bpy.props.StringProperty()

    def execute(self, context):
        prefs = context.scene.keymap_checker
        assigned = is_key_used_cached(context, self.key)
        if assigned:
            prefs.selected_key = self.key
        for area in context.screen.areas:
            if area.type == 'VIEW_3D':
                for region in area.regions:
                    if region.type == 'UI':
                        region.tag_redraw()
        return {'FINISHED'}

def _keybinding_search_text(key_label: str, ctrl=False, shift=False, alt=False, cmd=False) -> str:
    mods = []
    if ctrl:  mods.append("Ctrl")
    if shift: mods.append("Shift")
    if alt:   mods.append("Alt")
    if cmd and platform.system() == 'Darwin':
        mods.append("Cmd")

    k = (key_label or "").upper()

    if k.startswith("NUMPAD_"):
        tail = k.replace("NUMPAD_", "")
        numpad_map = {
            "PERIOD": "Period",
            "SLASH": "Slash",
            "ASTERIX": "*",
            "MINUS": "-",
            "PLUS": "+",
            "EQUALS": "=",
            "ENTER": "Enter",
        }
        if tail.isdigit():
            key_txt = f"Numpad {tail}"
        else:
            key_txt = f"Numpad {numpad_map.get(tail, tail.title())}"
    elif k in {"UP", "DOWN", "LEFT", "RIGHT"}:
        key_txt = f"{k.title()} Arrow"
    elif k in {"RETURN", "RET", "ENTER"}:
        key_txt = "Enter"
    elif k in {"BACK_SPACE"}:
        key_txt = "Backspace"
    elif k in {"DEL", "DELETE"}:
        key_txt = "Delete"
    elif k in set("0123456789"):
        words = ["Zero","One","Two","Three","Four","Five","Six","Seven","Eight","Nine"]
        key_txt = words[int(k)]
    elif k in {"`","-","=","[","]","\\",";","'",",",".","/","+"}:
        punct_map = {
            "`": "Accent Grave",
            "-": "Minus",
            "=": "Equal",
            "[": "Left Bracket",
            "]": "Right Bracket",
            "\\": "Back Slash",
            ";": "Semi Colon",
            "'": "Quote",
            ",": "Comma",
            ".": "Period",
            "/": "Slash",
            "+": "Plus",
        }
        key_txt = punct_map[k]
    else:
        key_txt = k.title()

    parts = mods + [key_txt]
    return " ".join(p for p in parts if p).strip()

def _open_prefs_and_focus_keymap(context):
    bpy.ops.screen.userpref_show()
    try:
        context.preferences.active_section = 'KEYMAP'
    except Exception:
        pass

    wm = context.window_manager
    pref_area = None
    pref_space = None
    for win in wm.windows:
        for area in win.screen.areas:
            if area.type == 'PREFERENCES':
                pref_area = area
                pref_space = area.spaces.active
                break
        if pref_space:
            break

    if pref_space and hasattr(pref_space, "context"):
        try:
            pref_space.context = 'KEYMAP'
        except Exception:
            pass

    return pref_area, pref_space

def _set_pref_keymap_filter_mode(pref_space, mode: str):
    if not pref_space:
        return
    wanted = []
    if mode == 'KEY_BINDING':
        wanted = ['KEY_BINDING', 'KEY BINDING', 'KEY_BINDING_SEARCH', 'KEY_BINDING_FILTER']
    elif mode == 'NAME':
        wanted = ['NAME', 'OPERATOR', 'NAME_FILTER']
    elif mode == 'IDNAME':
        wanted = ['IDENTIFIER', 'IDNAME', 'OPERATOR', 'NAME']
    else:
        wanted = [mode]

    for attr in ("keymap_filter_type", "filter_type", "search_type"):
        if hasattr(pref_space, attr):
            for val in wanted:
                try:
                    setattr(pref_space, attr, val)
                    return
                except Exception:
                    continue

def _set_keymap_search(pref_space, search_text: str, by_mode: str):
    if not pref_space:
        return
    _set_pref_keymap_filter_mode(pref_space, by_mode)
    for attr in ("keymap_filter", "filter_text", "search_filter", "search", "filter_search"):
        if hasattr(pref_space, attr):
            try:
                setattr(pref_space, attr, search_text)
                break
            except Exception:
                continue

class WM_OT_OpenKeymapInPrefs(bpy.types.Operator):
    bl_idname = "wm.open_keymap_in_prefs"
    bl_label = "See in Preferences"
    bl_description = "Open Preferences > Keymap and filter by the operator ID (exact match)"
    bl_options = {'REGISTER'}

    kc_name: bpy.props.StringProperty(name="Keyconfig Name", default="")
    km_name: bpy.props.StringProperty(name="Keymap Name")
    kmi_idname: bpy.props.StringProperty(name="Keymap Item ID")
    kmi_name: bpy.props.StringProperty(name="Keymap Item Name")
    kmi_value: bpy.props.StringProperty(name="Keymap Item Value")
    kmi_key_modifier: bpy.props.StringProperty(name="Keymap Modifier")
    key_label: bpy.props.StringProperty(name="Key Label")
    ctrl: bpy.props.BoolProperty(name="Ctrl", default=False)
    shift: bpy.props.BoolProperty(name="Shift", default=False)
    alt: bpy.props.BoolProperty(name="Alt", default=False)
    cmd: bpy.props.BoolProperty(name="Cmd", default=False)

    search_by: bpy.props.EnumProperty(
        name="Search By",
        items=(('IDNAME', "Identifier", "Search by operator identifier"),),
        default='IDNAME',
    )

    def execute(self, context):
        bpy.ops.screen.userpref_show()
        try:
            context.preferences.active_section = 'KEYMAP'
        except Exception:
            pass

        wm = context.window_manager
        pref_area = None
        pref_space = None
        for win in wm.windows:
            for area in win.screen.areas:
                if area.type == 'PREFERENCES':
                    pref_area = area
                    pref_space = area.spaces.active
                    break
            if pref_space:
                break

        if pref_space and hasattr(pref_space, "context"):
            try:
                pref_space.context = 'KEYMAP'
            except Exception:
                pass

        search_text = (self.kmi_idname or "").strip()
        if not search_text:
            search_text = (self.kmi_name or "").strip()

        _set_pref_keymap_filter_mode(pref_space, 'IDNAME')
        for attr in ("keymap_filter", "filter_text", "search_filter", "search", "filter_search"):
            if pref_space and hasattr(pref_space, attr):
                try:
                    setattr(pref_space, attr, search_text)
                    break
                except Exception:
                    continue

        if pref_area:
            try:
                pref_area.tag_redraw()
            except Exception:
                pass

        self.report({'INFO'}, f"Keymap search (IDNAME) set to: {search_text}")
        return {'FINISHED'}

class WM_OT_DisableKeymapItem(bpy.types.Operator):
    bl_idname = "wm.disable_keymap_item"
    bl_label = "Disable Keymap Item"
    bl_description = "Disable the selected keymap item"
    bl_options = {'REGISTER'}

    kc_name: bpy.props.StringProperty(name="Keyconfig Name")
    km_name: bpy.props.StringProperty(name="Keymap Name")
    kmi_idname: bpy.props.StringProperty(name="Keymap Item ID")
    kmi_name: bpy.props.StringProperty(name="Keymap Item Name")
    kmi_value: bpy.props.StringProperty(name="Keymap Item Value")
    kmi_key_modifier: bpy.props.StringProperty(name="Keymap Modifier")

    def execute(self, context):
        wm = context.window_manager
        kc = None
        for keyconfig in _iter_all_keyconfigs():
            if keyconfig.name == self.kc_name:
                kc = keyconfig
                break

        if not kc:
            self.report({'ERROR'}, f"Keyconfig '{self.kc_name}' not found")
            return {'CANCELLED'}

        km = None
        for keymap in kc.keymaps:
            if keymap.name == self.km_name:
                km = keymap
                break

        if not km:
            self.report({'ERROR'}, f"Keymap '{self.km_name}' not found in keyconfig '{self.kc_name}'")
            return {'CANCELLED'}

        kmi = None
        for item in km.keymap_items:
            sig = _sig_for_kmi(km, item)
            if sig == (
                self.km_name,
                self.kmi_idname,
                self.kmi_name,
                self.kmi_value,
                self.kmi_key_modifier
            ):
                kmi = item
                break

        if not kmi:
            self.report({'ERROR'}, "Keymap item not found")
            return {'CANCELLED'}

        kmi.active = False
        self.report({'INFO'}, f"Disabled keymap item: {self.km_name} > {self.kmi_idname or self.kmi_name}")

        clear_keymap_cache()

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

        # ---------- helpers ----------
        def compact_rows(rows):
            """Merge duplicate bindings by (idname, value, key_modifier)."""
            merged = {}
            order = []
            for label_txt, sig, kc_names in rows:
                k = (sig[1], sig[3], sig[4])  # (idname, value, key_mod)
                if k not in merged:
                    merged[k] = (label_txt, sig, list(kc_names))
                    order.append(k)
                else:
                    prev_label, prev_sig, prev_kc = merged[k]
                    merged[k] = (prev_label, prev_sig, sorted(set(prev_kc) | set(kc_names)))
            return [merged[k] for k in order]

        def only_press(rows):
            """Keep only value==PRESS to avoid DOUBLE_CLICK/CLICK/RELEASE noise."""
            return [r for r in rows if r[1][3] == 'PRESS']

        def allow_global_for_editor(opid_lc, editor_id, mode_str):
            if editor_id == 'VIEW_3D':
                allowed_by_mode = {
                    'OBJECT':       ('object.', 'mesh.', 'view3d.', 'pose.', 'armature.', 'wm.pme_user_pie_menu_call'),
                    'EDIT_MESH':    ('mesh.', 'view3d.', 'uv.', 'curve.', 'curves.', 'wm.pme_user_pie_menu_call'),
                    'EDIT_CURVE':   ('curve.', 'curves.', 'view3d.', 'wm.pme_user_pie_menu_call'),
                    'EDIT_SURFACE': ('curve.', 'view3d.', 'wm.pme_user_pie_menu_call'),
                    'SCULPT':       ('sculpt.', 'view3d.', 'wm.pme_user_pie_menu_call'),
                    'PAINT_VERTEX': ('paint.', 'view3d.', 'wm.pme_user_pie_menu_call'),
                    'PAINT_WEIGHT': ('paint.', 'view3d.', 'wm.pme_user_pie_menu_call'),
                    'PAINT_TEXTURE':('paint.', 'view3d.', 'wm.pme_user_pie_menu_call'),
                    'SCULPT_CURVES':('curves.', 'view3d.', 'wm.pme_user_pie_menu_call'),
                    'PARTICLE_EDIT':('particle.', 'view3d.', 'wm.pme_user_pie_menu_call'),
                    'POSE':         ('pose.', 'armature.', 'object.', 'view3d.', 'wm.pme_user_pie_menu_call'),
                    'EDIT_ARMATURE':('armature.', 'view3d.', 'wm.pme_user_pie_menu_call'),
                }
                allowed = allowed_by_mode.get(mode_str, ('view3d.', 'object.', 'mesh.', 'wm.pme_user_pie_menu_call'))
                return opid_lc.startswith(allowed) or (opid_lc == 'wm.pme_user_pie_menu_call')
            if editor_id == 'UV':
                return opid_lc.startswith(('uv.', 'image.', 'wm.pme_user_pie_menu_call'))
            if editor_id == 'IMAGE_EDITOR':
                return opid_lc.startswith(('image.', 'mask.', 'uv.', 'wm.pme_user_pie_menu_call'))
            family = {
                'GRAPH_EDITOR': ('graph.', 'anim.', 'wm.pme_user_pie_menu_call'),
                'DOPESHEET_EDITOR': ('anim.', 'action.', 'wm.pme_user_pie_menu_call'),
                'NLA_EDITOR': ('nla.', 'wm.pme_user_pie_menu_call'),
                'SEQUENCE_EDITOR': ('sequencer.', 'wm.pme_user_pie_menu_call'),
                'NODE_EDITOR': ('node.', 'wm.pme_user_pie_menu_call'),
                'CLIP_EDITOR': ('clip.', 'wm.pme_user_pie_menu_call'),
                'OUTLINER': ('outliner.', 'wm.pme_user_pie_menu_call'),
                'TEXT_EDITOR': ('text.', 'wm.pme_user_pie_menu_call'),
                'FILE_BROWSER': ('file.', 'wm.pme_user_pie_menu_call'),
            }.get(editor_id, ('wm.pme_user_pie_menu_call',))
            return opid_lc.startswith(family) or (opid_lc == 'wm.pme_user_pie_menu_call')

        def filter_global_rows_for_context(rows, editor_id, mode_str):
            out = []
            for label_txt, sig, kc_names in rows:
                opid_lc = (sig[1] or '').lower()
                if allow_global_for_editor(opid_lc, editor_id, mode_str):
                    out.append((label_txt, sig, kc_names))
            return out

        # --- Header controls ---
        row = layout.row(align=True)
        row.prop(prefs, "editor")
        row.prop(prefs, "screen_always_on", text="System Keymaps", toggle=True)
        row.prop(prefs, "hide_modal", text="Hide Modal", toggle=True)

        row = layout.row(align=True)
        row.prop(prefs, "ctrl", toggle=True)
        row.prop(prefs, "shift", toggle=True)
        row.prop(prefs, "alt", toggle=True)
        if platform.system() == 'Darwin':
            row.prop(prefs, "cmd", toggle=True)

        layout.separator()

        # --- Keyboard (QWERTY) ---
        box = layout.box()
        box.label(text="Keyboard:")
        for row_keys in qwerty_keys:
            row = box.row(align=True)
            for k in row_keys:
                col = row.column()
                is_used = is_key_used_cached(context, k)
                op = col.operator("wm.select_keymap_key", text=k, depress=(prefs.selected_key == k), emboss=is_used)
                op.key = k

        layout.separator()

        # --- Cursor / Numpad split ---
        split = layout.split(factor=0.5)
        col_left = split.column()
        box_left = col_left.box()
        box_left.label(text="Cursor and Navigation Keys:")
        for row_keys in cursor_keys:
            row = box_left.row(align=True)
            for k in row_keys:
                col = row.column()
                if k != ' ':
                    is_used = is_key_used_cached(context, k)
                    op = col.operator("wm.select_keymap_key", text=k, depress=(prefs.selected_key == k), emboss=is_used)
                    op.key = k

        col_right = split.column()
        box_right = col_right.box()
        box_right.label(text="Numpad:")
        for row_keys in numpad_keys:
            row = box_right.row(align=True)
            for k in row_keys:
                col = row.column()
                if k == ' ':
                    col.label(text="")
                    continue
                if k in '0123456789':
                    key_id = f"NUMPAD_{k}"
                elif k == '.':
                    key_id = "NUMPAD_PERIOD"
                elif k == '/':
                    key_id = "NUMPAD_SLASH"
                elif k == '*':
                    key_id = "NUMPAD_ASTERIX"
                elif k == '-':
                    key_id = "NUMPAD_MINUS"
                elif k == '+':
                    key_id = "NUMPAD_PLUS"
                elif k == 'ENTER':
                    key_id = "NUMPAD_ENTER"
                elif k == '=':
                    key_id = "NUMPAD_EQUALS"
                else:
                    key_id = k
                is_used = is_key_used_cached(context, key_id)
                op = col.operator("wm.select_keymap_key", text=k, depress=(prefs.selected_key == key_id), emboss=is_used)
                op.key = key_id

        layout.separator()

        # --- Details for selected key ---
        if not prefs.selected_key:
            layout.label(text="(Click an assigned key to view its assignment)")
            return

        # --- Conflicts (strict separation; no scope mixing) ---
        (editor_rows,
         global_rows,
         intra_editor_conflicts,
         editor_overlap_rows,
         global_overlap_rows) = get_keymap_conflicts(
            prefs.selected_key, prefs.editor,
            prefs.ctrl, prefs.shift, prefs.alt, prefs.cmd,
            screen_always_on=prefs.screen_always_on,
            hide_modal=prefs.hide_modal
        )

        # compact before display
        editor_rows            = compact_rows(editor_rows)
        global_rows            = compact_rows(global_rows)
        intra_editor_conflicts = compact_rows(intra_editor_conflicts)
        editor_overlap_rows    = compact_rows(editor_overlap_rows)
        global_overlap_rows    = compact_rows(global_overlap_rows)

        layout.separator()
        layout.label(text="Conflicts:")

        showed_any = False

        # 1) Intra‑editor
        if intra_editor_conflicts:
            showed_any = True
            layout.label(text="• Intra‑editor (current editor):", icon='ERROR')
            for label_txt, sig, kc_names in intra_editor_conflicts:
                row = layout.row(align=True)
                split = row.split(factor=0.90, align=True)
                left = split.row(align=True); left.label(text=label_txt, icon='ERROR')
                right = split.row(align=True); right.alignment = 'RIGHT'; right.scale_x = 0.9
                op_prefs = right.operator("wm.open_keymap_in_prefs", text="", icon='PREFERENCES', emboss=False)
                op_prefs.kc_name = kc_names[0]; op_prefs.km_name = sig[0]
                op_prefs.kmi_idname = sig[1]; op_prefs.kmi_name = sig[2]
                op_prefs.kmi_value = sig[3]; op_prefs.kmi_key_modifier = sig[4]
                op_prefs.key_label = prefs.selected_key
                op_prefs.ctrl = prefs.ctrl; op_prefs.shift = prefs.shift; op_prefs.alt = prefs.alt; op_prefs.cmd = prefs.cmd
                if hasattr(op_prefs, "search_by"):
                    op_prefs.search_by = 'IDNAME'
                op_disable = right.operator("wm.disable_keymap_item", text="", icon='X', emboss=False)
                op_disable.kc_name = kc_names[0]; op_disable.km_name = sig[0]
                op_disable.kmi_idname = sig[1]; op_disable.kmi_name = sig[2]
                op_disable.kmi_value = sig[3]; op_disable.kmi_key_modifier = sig[4]

        # 2) Overlap Editor vs Global
        if editor_overlap_rows and global_overlap_rows:
            showed_any = True
            layout.separator()
            layout.label(text="• Overlap between current editor and Global (Window/Screen):", icon='ERROR')

            layout.label(text="  – Editor entries that overlap:", icon='DOT')
            for label_txt, sig, kc_names in editor_overlap_rows:
                row = layout.row(align=True)
                split = row.split(factor=0.90, align=True)
                left = split.row(align=True); left.label(text=label_txt, icon='ERROR')
                right = split.row(align=True); right.alignment = 'RIGHT'; right.scale_x = 0.9
                op_prefs = right.operator("wm.open_keymap_in_prefs", text="", icon='PREFERENCES', emboss=False)
                op_prefs.kc_name = kc_names[0]; op_prefs.km_name = sig[0]
                op_prefs.kmi_idname = sig[1]; op_prefs.kmi_name = sig[2]
                op_prefs.kmi_value = sig[3]; op_prefs.kmi_key_modifier = sig[4]
                op_prefs.key_label = prefs.selected_key
                op_prefs.ctrl = prefs.ctrl; op_prefs.shift = prefs.shift; op_prefs.alt = prefs.alt; op_prefs.cmd = prefs.cmd
                if hasattr(op_prefs, "search_by"):
                    op_prefs.search_by = 'IDNAME'
                op_disable = right.operator("wm.disable_keymap_item", text="", icon='X', emboss=False)
                op_disable.kc_name = kc_names[0]; op_disable.km_name = sig[0]
                op_disable.kmi_idname = sig[1]; op_disable.kmi_name = sig[2]
                op_disable.kmi_value = sig[3]; op_disable.kmi_key_modifier = sig[4]

            layout.label(text="  – Global entries that overlap:", icon='DOT')
            for label_txt, sig, kc_names in global_overlap_rows:
                row = layout.row(align=True)
                split = row.split(factor=0.90, align=True)
                left = split.row(align=True); left.label(text=label_txt, icon='ERROR')
                right = split.row(align=True); right.alignment = 'RIGHT'; right.scale_x = 0.9
                op_prefs = right.operator("wm.open_keymap_in_prefs", text="", icon='PREFERENCES', emboss=False)
                op_prefs.kc_name = kc_names[0]; op_prefs.km_name = sig[0]
                op_prefs.kmi_idname = sig[1]; op_prefs.kmi_name = sig[2]
                op_prefs.kmi_value = sig[3]; op_prefs.kmi_key_modifier = sig[4]
                op_prefs.key_label = prefs.selected_key
                op_prefs.ctrl = prefs.ctrl; op_prefs.shift = prefs.shift; op_prefs.alt = prefs.alt; op_prefs.cmd = prefs.cmd
                if hasattr(op_prefs, "search_by"):
                    op_prefs.search_by = 'IDNAME'
                op_disable = right.operator("wm.disable_keymap_item", text="", icon='X', emboss=False)
                op_disable.kc_name = kc_names[0]; op_disable.km_name = sig[0]
                op_disable.kmi_idname = sig[1]; op_disable.kmi_name = sig[2]
                op_disable.kmi_value = sig[3]; op_disable.kmi_key_modifier = sig[4]

        if not showed_any:
            layout.label(text="No conflicts found.")

        # ===============================
        # Assigned in current context
        # ===============================
        layout.separator()
        layout.label(text="Assigned in current context (Editor + System):" if prefs.screen_always_on else "Assigned in current editor:")

        editor_only_rows = get_keymap_matches_in_editor(
            prefs.selected_key, prefs.editor,
            prefs.ctrl, prefs.shift, prefs.alt, prefs.cmd,
            hide_modal=prefs.hide_modal
        )
        editor_only_rows = compact_rows(only_press(editor_only_rows))

        merged_rows = list(editor_only_rows)
        if prefs.screen_always_on:
            mode_str = getattr(context, "mode", "OBJECT") or "OBJECT"
            gl_all = get_global_matches(
                prefs.selected_key,
                prefs.ctrl, prefs.shift, prefs.alt, prefs.cmd,
                hide_modal=prefs.hide_modal
            )
            gl_all = compact_rows(only_press(gl_all))
            gl_all = filter_global_rows_for_context(gl_all, prefs.editor, mode_str)
            merged_rows.extend(gl_all)
            merged_rows = compact_rows(merged_rows)

        if merged_rows:
            for label_txt, sig, kc_names in merged_rows:
                row = layout.row(align=True)
                split = row.split(factor=0.90, align=True)
                col_name = split.row(align=True); col_name.label(text=label_txt)
                col_btns = split.row(align=True); col_btns.alignment = 'RIGHT'; col_btns.scale_x = 0.9
                op_prefs = col_btns.operator("wm.open_keymap_in_prefs", text="", icon='PREFERENCES', emboss=False)
                op_prefs.kc_name = kc_names[0]
                op_prefs.km_name = sig[0]
                op_prefs.kmi_idname = sig[1]
                op_prefs.kmi_name = sig[2]
                op_prefs.kmi_value = sig[3]
                op_prefs.kmi_key_modifier = sig[4]
                op_prefs.key_label = prefs.selected_key
                op_prefs.ctrl = prefs.ctrl; op_prefs.shift = prefs.shift; op_prefs.alt = prefs.alt; op_prefs.cmd = prefs.cmd
                if hasattr(op_prefs, "search_by"):
                    op_prefs.search_by = 'IDNAME'
        else:
            layout.label(text="No assignment found in current editor.")

        # --- Global scopes (Window/Screen) — filtered + compacted ---
        if prefs.screen_always_on:
            gl_rows_all = get_global_matches(
                prefs.selected_key,
                prefs.ctrl, prefs.shift, prefs.alt, prefs.cmd,
                hide_modal=prefs.hide_modal
            )
            gl_rows_all = compact_rows(gl_rows_all)
            gl_rows_all = [r for r in gl_rows_all if r[1][3] == 'PRESS']
            mode_str = getattr(context, "mode", "OBJECT") or "OBJECT"
            gl_rows_all = filter_global_rows_for_context(gl_rows_all, prefs.editor, mode_str)
            if gl_rows_all:
                layout.separator()
                layout.label(text="In global scopes (Window / Screen):")
                for label_txt, sig, kc_names in gl_rows_all:
                    row = layout.row(align=True)
                    split = row.split(factor=0.90, align=True)
                    col_name = split.row(align=True); col_name.label(text=label_txt)
                    col_btns = split.row(align=True); col_btns.alignment = 'RIGHT'; col_btns.scale_x = 0.9
                    op_prefs = col_btns.operator("wm.open_keymap_in_prefs", text="", icon='PREFERENCES', emboss=False)
                    op_prefs.kc_name = kc_names[0]
                    op_prefs.km_name = sig[0]
                    op_prefs.kmi_idname = sig[1]
                    op_prefs.kmi_name = sig[2]
                    op_prefs.kmi_value = sig[3]
                    op_prefs.kmi_key_modifier = sig[4]
                    op_prefs.key_label = prefs.selected_key
                    op_prefs.ctrl = prefs.ctrl; op_prefs.shift = prefs.shift; op_prefs.alt = prefs.alt; op_prefs.cmd = prefs.cmd
                    if hasattr(op_prefs, "search_by"):
                        op_prefs.search_by = 'IDNAME'

        # --- Other editors (informational, **dedup + only PRESS**) ---
        other_found = False
        excluded = {'SCREEN', 'EMPTY', prefs.editor}
        for ed_id, ed_label in editor_map.items():
            if ed_id in excluded:
                continue
            other_rows = get_keymap_matches_in_editor(
                prefs.selected_key, ed_id,
                prefs.ctrl, prefs.shift, prefs.alt, prefs.cmd,
                hide_modal=prefs.hide_modal
            )
            # FIX: remove non-PRESS and then compact to kill duplicates
            other_rows = compact_rows(only_press(other_rows))
            if other_rows and not other_found:
                layout.separator()
                layout.label(text="In other editors:")
                other_found = True
            for label_txt, sig, kc_names in other_rows:
                row = layout.row(align=True)
                split = row.split(factor=0.90, align=True)
                col_name = split.row(align=True); col_name.label(text=label_txt)
                col_btns = split.row(align=True); col_btns.alignment = 'RIGHT'; col_btns.scale_x = 0.9
                op_prefs = col_btns.operator("wm.open_keymap_in_prefs", text="", icon='PREFERENCES', emboss=False)
                op_prefs.kc_name = kc_names[0]
                op_prefs.km_name = sig[0]
                op_prefs.kmi_idname = sig[1]
                op_prefs.kmi_name = sig[2]
                op_prefs.kmi_value = sig[3]
                op_prefs.kmi_key_modifier = sig[4]
                op_prefs.key_label = prefs.selected_key
                op_prefs.ctrl = prefs.ctrl; op_prefs.shift = prefs.shift; op_prefs.alt = prefs.alt; op_prefs.cmd = prefs.cmd
                if hasattr(op_prefs, "search_by"):
                    op_prefs.search_by = 'IDNAME'

        # --- Other editors (informational, dedup + only PRESS) ---
        other_found = False
        excluded = {'SCREEN', 'EMPTY', prefs.editor}
        for ed_id, ed_label in editor_map.items():
            if ed_id in excluded:
                continue
            other_rows = get_keymap_matches_in_editor(
                prefs.selected_key, ed_id,
                prefs.ctrl, prefs.shift, prefs.alt, prefs.cmd,
                hide_modal=prefs.hide_modal
            )
            # ✅ FIX: filter to PRESS *before* compacting
            other_rows = only_press(other_rows)
            other_rows = compact_rows(other_rows)

            if other_rows and not other_found:
                layout.separator()
                layout.label(text="In other editors:")
                other_found = True

            for label_txt, sig, kc_names in other_rows:
                row = layout.row(align=True)
                split = row.split(factor=0.90, align=True)
                col_name = split.row(align=True)
                col_name.label(text=label_txt)

                col_btns = split.row(align=True)
                col_btns.alignment = 'RIGHT'
                col_btns.scale_x = 0.9

                op_prefs = col_btns.operator("wm.open_keymap_in_prefs", text="", icon='PREFERENCES', emboss=False)
                op_prefs.kc_name = kc_names[0]
                op_prefs.km_name = sig[0]
                op_prefs.kmi_idname = sig[1]
                op_prefs.kmi_name = sig[2]
                op_prefs.kmi_value = sig[3]
                op_prefs.kmi_key_modifier = sig[4]
                op_prefs.key_label = prefs.selected_key
                op_prefs.ctrl = prefs.ctrl; op_prefs.shift = prefs.shift; op_prefs.alt = prefs.alt; op_prefs.cmd = prefs.cmd
                if hasattr(op_prefs, "search_by"):
                    op_prefs.search_by = 'IDNAME'



# ---------------------------------------------
# Registration
# ---------------------------------------------
classes = [
    KeymapCheckerPrefs,
    WM_OT_SelectKey,
    WM_OT_OpenKeymapInPrefs,
    WM_OT_DisableKeymapItem,
    VIEW3D_PT_KeymapChecker,
]

@persistent
def clear_cache_on_load(dummy):
    clear_keymap_cache()

def register():
    try:
        for cls in classes:
            bpy.utils.register_class(cls)
            _debug_print(f"Registered class: {cls.__name__}")
        bpy.types.Scene.keymap_checker = bpy.props.PointerProperty(type=KeymapCheckerPrefs)
        bpy.app.handlers.load_post.append(clear_cache_on_load)
    except Exception as e:
        print(f"Registration error: {e}")

def unregister():
    try:
        clear_keymap_cache()
        for cls in reversed(classes):
            bpy.utils.unregister_class(cls)
            _debug_print(f"Unregistered class: {cls.__name__}")
        del bpy.types.Scene.keymap_checker
        bpy.app.handlers.load_post.remove(clear_cache_on_load)
    except Exception as e:
        print(f"Unregistration error: {e}")

if __name__ == "__main__":
    register()
