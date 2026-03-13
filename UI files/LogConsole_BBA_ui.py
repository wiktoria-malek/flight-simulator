# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'LogConsole_BBA.ui'
##
## Created by: Qt User Interface Compiler version 6.9.2
##
## WARNING! All changes made in this file will be lost when recompiling UI file!
################################################################################

from PySide6.QtCore import (QCoreApplication, QDate, QDateTime, QLocale,
    QMetaObject, QObject, QPoint, QRect,
    QSize, QTime, QUrl, Qt)
from PySide6.QtGui import (QBrush, QColor, QConicalGradient, QCursor,
    QFont, QFontDatabase, QGradient, QIcon,
    QImage, QKeySequence, QLinearGradient, QPainter,
    QPalette, QPixmap, QRadialGradient, QTransform)
from PySide6.QtWidgets import (QApplication, QDialog, QScrollArea, QSizePolicy,
    QWidget)

class Ui_LogConsole(object):
    def setupUi(self, LogConsole):
        if not LogConsole.objectName():
            LogConsole.setObjectName(u"LogConsole")
        LogConsole.resize(400, 300)
        self.scrollArea = QScrollArea(LogConsole)
        self.scrollArea.setObjectName(u"scrollArea")
        self.scrollArea.setGeometry(QRect(0, 0, 401, 301))
        self.scrollArea.setWidgetResizable(True)
        self.scrollAreaWidgetContents = QWidget()
        self.scrollAreaWidgetContents.setObjectName(u"scrollAreaWidgetContents")
        self.scrollAreaWidgetContents.setGeometry(QRect(0, 0, 399, 299))
        self.scrollArea.setWidget(self.scrollAreaWidgetContents)

        self.retranslateUi(LogConsole)

        QMetaObject.connectSlotsByName(LogConsole)
    # setupUi

    def retranslateUi(self, LogConsole):
        LogConsole.setWindowTitle(QCoreApplication.translate("LogConsole", u"Log Console", None))
    # retranslateUi

