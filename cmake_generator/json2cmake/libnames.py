__all__ = ['LIBNAME_MAP', ]

LIBNAME_MAP = {
    'z': ('ZLIB', None, 'ZLIB_LIBRARIES', 'ZLIB_INCLUDE_DIRS'),
    'lzma': ('LibLZMA', None, 'LIBLZMA_LIBRARIES', 'LIBLZMA_INCLUDE_DIRS'),
    'X11': ('X11', None, 'X11_LIBRARIES', 'X11_INCLUDE_DIRS'),
}
QT5MODULES = (
    "3DAnimation", "3DCore", "3DExtras", "3DInput", "3DLogic", "3DQuick", "3DQuickAnimation",
    "3DQuickExtras", "3DQuickInput", "3DQuickRender", "3DQuickScene2D", "3DRender", "Bluetooth",
    "Charts", "Concurrent", "Contacts", "Core", "DBus", "Designer", "GStreamer", "Gui", "Help",
    "LinguistTools", "Location", "Multimedia", "MultimediaWidgets", "Network", "Nfc", "OpenGL",
    "OpenGLExtensions", "Organizer", "Positioning", "PrintSupport", "Qml", "Quick", "QuickControls2",
    "QuickTest", "QuickWidgets", "Script", "ScriptTools", "Sensors", "SerialPort", "Sql", "Svg",
    "Test", "TextToSpeech", "UiPlugin", "UiTools", "Versit", "VersitOrganizer", "WaylandClient",
    "WaylandCompositor", "WebChannel", "WebEngine", "WebEngineCore", "WebEngineWidgets", "WebKit",
    "WebKitWidgets", "WebSockets", "WebView", "Widgets", "X11Extras", "Xml", "XmlPatterns",
)
for module in QT5MODULES:
    LIBNAME_MAP['Qt5' + module] = ('Qt5', module, 'Qt5::' + module, 'Qt5%s_INCLUDE_DIR' % module)