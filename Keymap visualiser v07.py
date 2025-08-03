
bl_info = {
    "name": "Keymap Visualizer - Enhanced Layout",
    "author": "ChatGPT + User",
    "version": (1, 26),
    "blender": (3, 0, 0),
    "location": "3D View > Sidebar > Keymap",
    "description": "Visualizes assigned hotkeys with enhanced keyboard layout, full hierarchy support",
    "category": "Interface",
}

import bpy
import platform

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
    'CHANNELS': 'Animation Channels',
}

qwerty_keys = [
    ['`', '1', '2', '3', '4', '5', '6', '7', '8', '9', '0', '-', '=', 'DELETE'],
    ['ESC', 'F1', 'F2', 'F3', 'F4', 'F5', 'F6', 'F7', 'F8', 'F9', 'F10', 'F11', 'F12'],
    ['TAB', 'Q', 'W', 'E', 'R', 'T', 'Y', 'U', 'I', 'O', 'P', '[', ']', '\\'],
    ['A', 'S', 'D', 'F', 'G', 'H', 'J', 'K', 'L', ';', "'", 'RETURN'],
    ['Z', 'X', 'C', 'V', 'B', 'N', 'M', ',', '.', '/'],
    ['SPACE', 'ENTER', 'BACK_SPACE']
]

numpad_keys = [
    ['F16', 'F17', 'F18', 'F19'],
    [' ', '=', '/', '*'],
    ['7', '8', '9', '-'],
    ['4', '5', '6', '+'],
    ['1', '2', '3', ' '],
    [' ', '0', '.', 'ENTER']
]

cursor_keys = [
    ['F13', 'F14', 'F15'],
    ['INSERT', 'HOME', 'PAGE_UP'],
    ['DELETE', 'END', 'PAGE_DOWN'],
    [' ', 'UP', ' '],
    ['DOWN', 'LEFT', 'RIGHT']
]

class KeymapCheckerPrefs(bpy.types.PropertyGroup):
    editor: bpy.props.EnumProperty(
        name="Editor",
        items=[(k, v, "") for k, v in editor_map.items()],
        default='VIEW_3D'
    )
    ctrl: bpy.props.BoolProperty(name="Ctrl", default=False)
    shift: bpy.props.BoolProperty(name="Shift", default=False)
    alt: bpy.props.BoolProperty(name="Alt", default=False)
    cmd: bpy.props.BoolProperty(name="Cmd", default=False, description="Mac Command key") if platform.system() == 'Darwin' else bpy.props.BoolProperty(name="Cmd", default=False)
    selected_key: bpy.props.StringProperty(name="Selected Key", default="")


def is_relevant_keymap(km, editor):
    name = km.name
    space = km.space_type

    # Direct match
    if space == editor:
        return True

    # Editor-specific logic
    match_map = {
        'VIEW_3D': ["3D View", "Object Mode", "Mesh", "Sculpt", "Pose", "Armature", "Weight Paint", "Vertex Paint", "Tool:", "PME"],
        'GRAPH_EDITOR': ["Graph Editor", "F-Curve", "Drivers"],
        'DOPESHEET_EDITOR': ["Dopesheet", "Action", "Grease Pencil", "Shape Key"],
        'NLA_EDITOR': ["NLA"],
        'IMAGE_EDITOR': ["Image", "UV", "Mask"],
        'NODE_EDITOR': ["Node Editor", "Shader", "Compositor", "Geometry"],
        'SEQUENCE_EDITOR': ["Sequence", "Video"],
        'FILE_BROWSER': ["File Browser"],
        'TEXT_EDITOR': ["Text"],
        'CONSOLE': ["Console"],
        'CLIP_EDITOR': ["Clip", "Tracking", "Stabilization"],
        'GREASE_PENCIL': ["Grease Pencil", "Draw", "Sculpt", "Paint"],
        'MASK_EDITOR': ["Mask"],
        'USER_INTERFACE': ["User Interface", "UI", "Window", "Screen"],
        'VIEW_2D': ["View2D"],
        'VIEW_2D_BUTTONS_LIST': ["Buttons List"],
        'EMPTY': ["Window", "Screen", "Global", "PME"],
        'SCREEN': ["Window", "Screen", "Global", "PME"],
        'INFO': ["Info"],
        'PROPERTIES': ["Property Editor", "Properties"],
        'OUTLINER': ["Outliner"],
        'TIMELINE': ["Frames", "Timeline"],
        'MARKER': ["Markers"],
        'ANIMATION': ["Animation"],
        'CHANNELS': ["Channels", "Dope Sheet"]
    }

    keywords = match_map.get(editor, [])
    return any(k in name for k in keywords)


def is_key_assigned(key, editor, ctrl, shift, alt, cmd):
    wm = bpy.context.window_manager
    keyconfigs = [wm.keyconfigs.active]
    for kc in keyconfigs:
        if not kc:
            continue
        for km in kc.keymaps:
            if not is_relevant_keymap(km, editor):
                continue
            for kmi in km.keymap_items:
                if kmi.type == key and kmi.active:
                    if (kmi.ctrl == ctrl and kmi.shift == shift and kmi.alt == alt and kmi.oskey == cmd):
                        return True
    return False

def get_keymap_matches(key, editor, ctrl, shift, alt, cmd):
    results = []
    wm = bpy.context.window_manager
    keyconfigs = [('Active', wm.keyconfigs.active)]
    for origin, kc in keyconfigs:
        if not kc:
            continue
        for km in kc.keymaps:
            if not is_relevant_keymap(km, editor):
                continue
            for kmi in km.keymap_items:
                if kmi.type == key and kmi.active:
                    if (kmi.ctrl == ctrl and kmi.shift == shift and kmi.alt == alt and kmi.oskey == cmd):
                        label = f"{origin}: {km.name} > {kmi.idname}"
                        if kmi.name and kmi.name != kmi.idname:
                            label += f" ({kmi.name})"
                        results.append(label)
    return results

class WM_OT_SelectKey(bpy.types.Operator):
    bl_idname = "wm.select_keymap_key"
    bl_label = "Select Key"
    key: bpy.props.StringProperty()

    def execute(self, context):
        prefs = context.scene.keymap_checker
        if is_key_assigned(self.key, prefs.editor, prefs.ctrl, prefs.shift, prefs.alt, prefs.cmd):
            prefs.selected_key = self.key
        for area in context.screen.areas:
            if area.type == 'VIEW_3D':
                for region in area.regions:
                    if region.type == 'UI':
                        region.tag_redraw()
        return {'FINISHED'}

class VIEW3D_PT_KeymapChecker(bpy.types.Panel):
    bl_label = "Keymap Visualizer"
    bl_idname = "VIEW3D_PT_keymap_visualizer"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'Keymap'
    bl_context = "objectmode"

    def draw(self, context):
        layout = self.layout
        prefs = context.scene.keymap_checker

        layout.prop(prefs, "editor")
        row = layout.row(align=True)
        row.prop(prefs, "ctrl", toggle=True)
        row.prop(prefs, "shift", toggle=True)
        row.prop(prefs, "alt", toggle=True)
        if platform.system() == 'Darwin':
            row.prop(prefs, "cmd", toggle=True)
        layout.separator()
        layout.label(text="Keyboard:")
        for row_keys in qwerty_keys:
            row = layout.row(align=True)
            for k in row_keys:
                col = row.column()
                col.scale_x = 1.0
                is_used = is_key_assigned(k, prefs.editor, prefs.ctrl, prefs.shift, prefs.alt, prefs.cmd)
                props = col.operator("wm.select_keymap_key", text=k, depress=(prefs.selected_key == k), emboss=is_used)
                props.key = k
        layout.separator()
        split = layout.split(factor=0.5)
        col_left = split.column()
        col_left.label(text="Cursor and Navigation Keys:")
        for row_keys in cursor_keys:
            row = col_left.row(align=True)
            for k in row_keys:
                col = row.column()
                col.scale_x = 1.0 if k != ' ' else 0.5
                if k != ' ':
                    is_used = is_key_assigned(k, prefs.editor, prefs.ctrl, prefs.shift, prefs.alt, prefs.cmd)
                    props = col.operator("wm.select_keymap_key", text=k, depress=(prefs.selected_key == k), emboss=is_used)
                    props.key = k
        col_right = split.column()
        col_right.label(text="Numpad:")
        for row_keys in numpad_keys:
            row = col_right.row(align=True)
            for k in row_keys:
                col = row.column()
                col.scale_x = 1.0
                is_used = is_key_assigned(k if k in ['ENTER', '/', '*', '-', '+', '.', '='] else f"NUMPAD_{k}", prefs.editor, prefs.ctrl, prefs.shift, prefs.alt, prefs.cmd)
                props = col.operator("wm.select_keymap_key", text=k, depress=(prefs.selected_key == k), emboss=is_used)
                props.key = k if k in ['ENTER', '/', '*', '-', '+', '.', '='] else f"NUMPAD_{k}"
        layout.separator()
        layout.label(text="Assignment Details:")
        if prefs.selected_key:
            layout.label(text=f"Selected: {prefs.selected_key} with modifiers:")
            label = []
            if prefs.ctrl: label.append("Ctrl")
            if prefs.shift: label.append("Shift")
            if prefs.alt: label.append("Alt")
            if prefs.cmd and platform.system() == 'Darwin': label.append("Cmd")
            layout.label(text="+".join(label) or "None")
            matches = get_keymap_matches(prefs.selected_key, prefs.editor, prefs.ctrl, prefs.shift, prefs.alt, prefs.cmd)
            if matches:
                for m in matches:
                    layout.label(text=m)
            else:
                layout.label(text="No assignment found.")
        else:
            layout.label(text="(Click an assigned key to view its assignment)")

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
