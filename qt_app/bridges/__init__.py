"""Register the two optional wave extensions before the shell is loaded."""
from importlib import import_module

from PySide6.QtCore import QObject, Slot
from PySide6.QtQml import QQmlComponent, qmlContext
from PySide6.QtQuick import QQuickItem


KNOWN_EXTENSIONS = ("reliability", "features")


def load_extensions(app_context):
    objects = {}
    for name in KNOWN_EXTENSIONS:
        module_name = f"qt_app.bridges.{name}_bridge"
        try:
            module = import_module(module_name)
        except ModuleNotFoundError as exc:
            if exc.name == module_name:
                continue
            raise
        for key, obj in module.create(app_context).items():
            if not isinstance(key, str) or not key.isidentifier() or not isinstance(obj, QObject):
                raise TypeError(f"Invalid QML context property from {module_name}")
            if key in objects or app_context.qml_context.contextProperty(key) is not None:
                raise ValueError(f"Duplicate QML context property: {key}")
            objects[key] = obj
    for key, obj in objects.items():
        app_context.qml_context.setContextProperty(key, obj)
    return objects


class FeatureFactory(QObject):
    """Create an optional visual once and keep component failures local to its slot."""

    @Slot(QQmlComponent, QQuickItem, str, QObject, result=QQuickItem)
    def create(self, component, host, language, theme):
        feature = component.beginCreate(qmlContext(host))
        if feature is None:
            return None
        feature.setParent(host)
        meta = feature.metaObject()
        compatible = isinstance(feature, QQuickItem) and all(
            meta.indexOfProperty(key) >= 0 and meta.property(meta.indexOfProperty(key)).isWritable()
            for key in ("language", "theme")
        )
        if compatible:
            feature.setParentItem(host)
            component.setInitialProperties(feature, {"language": language, "theme": theme})
        # QQmlComponent records missing required properties in errors(). A plain
        # Loader would also print those optional-component failures to stderr.
        component.completeCreate()
        if not compatible or component.isError():
            feature.deleteLater()
            return None
        return feature
