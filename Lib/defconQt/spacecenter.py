from PyQt5.QtCore import QAbstractTableModel, QSize, Qt
from PyQt5.QtGui import (QBrush, QColor, QFont, QLinearGradient, QPainter,
        QPainterPath, QPalette, QPen)
from PyQt5.QtWidgets import (QAbstractItemView, QApplication, QComboBox, QGridLayout, QLabel, QLineEdit,
        QMainWindow, QScrollArea, QTableView, QTableWidget, QTableWidgetItem, QVBoxLayout, QSizePolicy, QSpinBox, QToolBar, QWidget)

defaultPointSize = 150

class MainSpaceWindow(QWidget):
    def __init__(self, font, string="Hello World", pointSize=defaultPointSize, parent=None):
        super(MainSpaceWindow, self).__init__(parent, Qt.Window)

        self.font = font
        self.glyphs = []
        self._subscribeToGlyphsText(string)
        self.toolbar = FontToolBar(string, pointSize, self)
        self.canvas = GlyphsCanvas(self.font, self.glyphs, pointSize, self)
        self.table = SpaceTable(self.glyphs, self)
        
        layout = QVBoxLayout(self)
        layout.addWidget(self.toolbar)
        layout.addWidget(self.canvas)
        layout.addWidget(self.table)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        self.setLayout(layout)
        self.resize(600,500)
        self.toolbar.comboBox.currentIndexChanged[str].connect(self.canvas._pointSizeChanged)
        self.toolbar.textField.textEdited.connect(self._textChanged)
        
        self.font.info.addObserver(self, "_fontInfoChanged", "Info.Changed")

        self.setWindowTitle("%s%s%s%s" % ("Space center – ", self.font.info.familyName, " ", self.font.info.styleName))

    def setupFileMenu(self):
        fileMenu = QMenu("&File", self)
        self.menuBar().addMenu(fileMenu)

        fileMenu.addAction("&Save...", self.save, "Ctrl+S")
        fileMenu.addAction("E&xit", self.close, "Ctrl+Q")
    
    def close(self):
        self.font.info.removeObserver(self, "Info.Changed")
        self._unsubscribeFromGlyphs()
        super(MainSpaceWindow, self).close()
    
    def _fontInfoChanged(self):
        self.canvas.update()
    
    def _glyphChanged(self, event):
        self.canvas.update()
        self.table.blockSignals(True)
        self.table.fillGlyphs()
        self.table.blockSignals(False)
    
    def _textChanged(self, newText):
        self.setGlyphs(newText)
        self.canvas._glyphsChanged(self.glyphs)
        self.table.blockSignals(True)
        self.table._glyphsChanged(self.glyphs)
        self.table.blockSignals(False)
    
    def _subscribeToGlyphsText(self, newText):
        glyphs = []
        # TODO: lexer
        for c in newText:
            name = self.font.unicodeData.glyphNameForUnicode(ord(c))
            if name not in self.font: continue
            glyphs.append(self.font[name])
        self.glyphs = glyphs

        handledGlyphs = set()
        for glyph in self.glyphs:
            if glyph in handledGlyphs:
                continue
            handledGlyphs.add(glyph)
            glyph.addObserver(self, "_glyphChanged", "Glyph.Changed")
        
    def _unsubscribeFromGlyphs(self):
        handledGlyphs = set()
        for glyph in self.glyphs:
            if glyph in handledGlyphs:
                continue
            handledGlyphs.add(glyph)
            glyph.removeObserver(self, "Glyph.Changed")
        #self.glyphs = None

    def setGlyphs(self, string):
        # unsubscribe from the old glyphs
        self._unsubscribeFromGlyphs()
        # subscribe to the new glyphs
        self._subscribeToGlyphsText(string)
        # set the records into the view
        self.canvas._glyphsChanged(self.glyphs)
        self.table._glyphsChanged(self.glyphs)

pointSizes = [50, 75, 100, 125, 150, 200, 250, 300, 350, 400, 450, 500]

class FontToolBar(QToolBar):
    def __init__(self, string, pointSize, parent=None):
        super(FontToolBar, self).__init__(parent)
        self.textField = QLineEdit(string)
        self.comboBox = QComboBox()
        self.comboBox.setEditable(True)
        for p in pointSizes:
            self.comboBox.addItem(str(p))
        self.comboBox.lineEdit().setText(str(pointSize))

        self.addWidget(self.textField)
        self.addWidget(self.comboBox)

class GlyphsCanvas(QWidget):
    def __init__(self, font, glyphs, pointSize=defaultPointSize, parent=None):
        super(GlyphsCanvas, self).__init__(parent)

        self.descender = font.info.descender
        if self.descender is None: self.descender = 250
        self.upm = font.info.unitsPerEm
        if self.upm is None or not self.upm > 0: self.upm = 1000
        self.glyphs = glyphs
        self.ptSize = pointSize
        self.calculateScale()
        self.padding = 10

    def calculateScale(self):
        scale = self.ptSize / float(self.upm)
        if scale < .01: scale = 0.01
        self.scale = scale
    
    def _pointSizeChanged(self, pointSize):
        self.ptSize = int(pointSize)
        self.calculateScale()
        self.update()
    
    def _glyphsChanged(self, newGlyphs):
        self.glyphs = newGlyphs
        self.update()
    
    # if we have a cell clicked in and we click on the canvas,
    # give focus to the canvas in order to quit editing
    # TODO: Focus on individual chars and show BBox + active cell (see how rf does active cells)
    # QTableWidget.scrollToItem()
    def mousePressEvent(self, event):
        self.setFocus(Qt.MouseFocusReason)
    
    def wheelEvent(self, event):
        # TODO: should it snap to predefined pointSizes? is the scaling factor okay?
        # see how rf behaves
        decay = event.angleDelta().y() / 120.0
        newPointSize = self.ptSize + int(decay) * 10
        self._pointSizeChanged(newPointSize)
        
        comboBox = self.parent().toolbar.comboBox
        comboBox.blockSignals(True)
        comboBox.setEditText(str(newPointSize))
        comboBox.blockSignals(False)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.fillRect(0, 0, self.width(), self.height(), Qt.white)
        # TODO: should padding be added for the right boundary as well? I'd say no but not sure
        painter.translate(self.padding, self.padding+self.ptSize+self.descender*self.scale)

        cur_width = 0
        for glyph in self.glyphs:
            # line wrapping
            if cur_width + glyph.width*self.scale + self.padding > self.width():
                painter.translate(-cur_width, self.ptSize)
                cur_width = glyph.width*self.scale
            else:
                cur_width += glyph.width*self.scale
            glyphPath = glyph.getRepresentation("defconQt.QPainterPath")
            painter.save()
            painter.scale(self.scale, -self.scale)
            painter.fillPath(glyphPath, Qt.black)
            painter.restore()
            painter.translate(glyph.width*self.scale, 0)

    '''
        painter.setPen(
                QPen(self.penColor, self.penWidth, Qt.SolidLine, Qt.RoundCap,
                        Qt.RoundJoin))
        gradient = QLinearGradient(0, 0, 0, 100)
        gradient.setColorAt(0.0, self.fillColor1)
        gradient.setColorAt(1.0, self.fillColor2)
        painter.setBrush(QBrush(gradient))
        painter.drawPath(self.path)
    '''

class SpaceTable(QTableWidget):
    def __init__(self, glyphs, parent=None):
        self.glyphs = glyphs
        super(SpaceTable, self).__init__(4, len(glyphs)+1, parent)
        # XXX: dunno why but without updating col count
        # scrollbar reports incorrect height...
        # fillGlyphs() will change this value back
        self.setColumnCount(len(self.glyphs)+2)
        data = [None, "Width", "Left", "Right"]
        for index, item in enumerate(data):
            cell = QTableWidgetItem(item)
            # don't set ItemIsEditable
            cell.setFlags(Qt.ItemIsEnabled)
            self.setItem(index, 0, cell)
        # let's use this one column to compute the width of others
        self._cellWidth = .7*self.columnWidth(0)
        self.setColumnWidth(0, .6*self.columnWidth(0))
        self.horizontalHeader().hide()
        self.verticalHeader().hide()

        # always show a scrollbar to fix layout
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOn)
        self.setSizePolicy(QSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed))
        self.fillGlyphs()
        self.resizeRowsToContents()
        self.cellChanged.connect(self._cellEdited)
        # edit cell on single click, not double
        self.setEditTriggers(QAbstractItemView.CurrentChanged)
        # TODO: investigate changing cell color as in robofont
        # http://stackoverflow.com/a/13926342/2037879

    def _glyphsChanged(self, newGlyphs):
        self.glyphs = newGlyphs
        # TODO: we don't need to reallocate cells, split alloc and fill
        self.fillGlyphs()
    
    def _cellEdited(self, row, col):
        if row == 0 or col == 0: return
        item = self.item(row, col).text()
        # Glyphs that do not have outlines leave empty cells, can't call
        # int() on that
        if not item: return
        item = int(item)
        # -1 because the first col contains descriptive text
        glyph = self.glyphs[col-1]
        if row == 1:
            glyph.width = item
        elif row == 2:
            glyph.leftMargin = item
        elif row == 3:
            glyph.rightMargin = item
        # defcon callbacks do the update

    def sizeHint(self):
        # http://stackoverflow.com/a/7216486/2037879
        height = sum(self.rowHeight(k) for k in range(self.rowCount()))
        height += self.horizontalScrollBar().height()
        margins = self.contentsMargins()
        height += margins.top() + margins.bottom()
        return QSize(self.width(), height)

    def fillGlyphs(self):
        def glyphTableWidgetItem(content, blockEdition=False):
            if content is not None: content = str(content)
            item = QTableWidgetItem(content)
            if content is None or blockEdition:
                # don't set ItemIsEditable
                item.setFlags(Qt.ItemIsEnabled)
            # TODO: also set alignment during edition
            # or leave it as it is now, is fine by me...
            #item.setTextAlignment(Qt.AlignCenter)
            return item

        self.setColumnCount(len(self.glyphs)+1)
        for index, glyph in enumerate(self.glyphs):
            # TODO: should glyph name edit really be permitted here?
            self.setItem(0, index+1, glyphTableWidgetItem(glyph.name, True))
            self.setItem(1, index+1, glyphTableWidgetItem(glyph.width))
            self.setItem(2, index+1, glyphTableWidgetItem(glyph.leftMargin))
            self.setItem(3, index+1, glyphTableWidgetItem(glyph.rightMargin))
            self.setColumnWidth(index+1, self._cellWidth)
        
    def wheelEvent(self, event):
        cur = self.horizontalScrollBar().value()
        self.horizontalScrollBar().setValue(cur - event.angleDelta().y() / 120)
        event.accept()

if __name__ == '__main__':
    import sys
# registerallfactories
    app = QApplication(sys.argv)
    window = Window()
    window.show()
    sys.exit(app.exec_())