# Code adapted from the MapSwipe plugin
# (C) 2015 by Hirofumi Hayashi and Luiz Motta
# email: hayashi@apptec.co.jp and motta.luiz@gmail.com

from qgis.PyQt.QtCore import Qt, QPoint

from qgis.PyQt.QtGui import QCursor

from qgis.gui import QgsMapTool

from .swipemap import SwipeMap


class MapSwipeTool(QgsMapTool):
    def __init__(self, canvas, layers):
        super().__init__(canvas)
        self.swipe = SwipeMap(canvas)
        self.layers = layers
        self.checkDirection = self.hasSwipe = self.disabledSwipe = None
        self.firstPoint = QPoint()
        self.cursorV = QCursor(Qt.SplitVCursor)
        self.cursorH = QCursor(Qt.SplitHCursor)

    def _connect(self, isConnect=True):
        if isConnect:
            self.canvas().mapCanvasRefreshed.connect(self.swipe.setMap)
        else:
            self.canvas().mapCanvasRefreshed.disconnect(self.swipe.setMap)

    def activate(self):
        super().activate()
        self.canvas().setCursor(QCursor(Qt.PointingHandCursor))
        self._connect()
        self.hasSwipe = False
        self.disabledSwipe = False
        self.setLayersSwipe()
        self.swipe.setIsVertical(True)
        self.swipe.setLength(
            self.swipe.boundingRect().width() / 2,
            self.swipe.boundingRect().height() / 2,
        )

    def deactivate(self):
        super().deactivate()
        self.deactivated.emit()
        self.swipe.clear()
        self._connect(False)

    def canvasPressEvent(self, e):
        self.hasSwipe = True
        self.firstPoint.setX(e.x())
        self.firstPoint.setY(e.y())
        self.checkDirection = True

    def canvasReleaseEvent(self, e):
        self.hasSwipe = False
        self.canvas().setCursor(QCursor(Qt.PointingHandCursor))

    def canvasMoveEvent(self, e):
        if self.hasSwipe:
            if self.checkDirection:
                dX = abs(e.x() - self.firstPoint.x())
                dY = abs(e.y() - self.firstPoint.y())
                isVertical = dX > dY
                self.swipe.setIsVertical(isVertical)
                self.checkDirection = False
                self.canvas().setCursor(self.cursorH if isVertical else self.cursorV)

            self.swipe.setLength(e.x(), e.y())

    def setLayersSwipe(self):
        if self.disabledSwipe:
            return
        self.swipe.clear()
        self.swipe.setLayers(self.layers)
        self.swipe.setMap()

    def disable(self):
        self.swipe.clear()
        self.hasSwipe = False
        self.disabledSwipe = True
