# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'BPM_weights.ui'
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
from PySide6.QtWidgets import (QApplication, QDialog, QDoubleSpinBox, QGridLayout,
    QGroupBox, QHBoxLayout, QLabel, QPushButton,
    QSizePolicy, QVBoxLayout, QWidget)

class Ui_WeightsForm(object):
    def setupUi(self, WeightsForm):
        if not WeightsForm.objectName():
            WeightsForm.setObjectName(u"WeightsForm")
        WeightsForm.resize(494, 242)
        self.verticalLayout = QVBoxLayout(WeightsForm)
        self.verticalLayout.setObjectName(u"verticalLayout")
        self.groupBox = QGroupBox(WeightsForm)
        self.groupBox.setObjectName(u"groupBox")
        self.gridLayout = QGridLayout(self.groupBox)
        self.gridLayout.setObjectName(u"gridLayout")
        self.w_wfs = QDoubleSpinBox(self.groupBox)
        self.w_wfs.setObjectName(u"w_wfs")
        self.w_wfs.setDecimals(0)
        self.w_wfs.setMinimum(0.000000000000000)
        self.w_wfs.setMaximum(100.000000000000000)
        self.w_wfs.setSingleStep(0.100000000000000)
        self.w_wfs.setValue(1.000000000000000)

        self.gridLayout.addWidget(self.w_wfs, 2, 1, 1, 1)

        self.w_dfs = QDoubleSpinBox(self.groupBox)
        self.w_dfs.setObjectName(u"w_dfs")
        self.w_dfs.setDecimals(0)
        self.w_dfs.setMinimum(0.000000000000000)
        self.w_dfs.setMaximum(100.000000000000000)
        self.w_dfs.setSingleStep(0.100000000000000)
        self.w_dfs.setValue(1.000000000000000)

        self.gridLayout.addWidget(self.w_dfs, 1, 1, 1, 1)

        self.label_dfs = QLabel(self.groupBox)
        self.label_dfs.setObjectName(u"label_dfs")

        self.gridLayout.addWidget(self.label_dfs, 1, 0, 1, 1)

        self.w_orbit = QDoubleSpinBox(self.groupBox)
        self.w_orbit.setObjectName(u"w_orbit")
        self.w_orbit.setDecimals(0)
        self.w_orbit.setMinimum(0.000000000000000)
        self.w_orbit.setMaximum(100.000000000000000)
        self.w_orbit.setSingleStep(0.100000000000000)
        self.w_orbit.setValue(1.000000000000000)

        self.gridLayout.addWidget(self.w_orbit, 0, 1, 1, 1)

        self.label_orbit = QLabel(self.groupBox)
        self.label_orbit.setObjectName(u"label_orbit")

        self.gridLayout.addWidget(self.label_orbit, 0, 0, 1, 1)

        self.label_wfs = QLabel(self.groupBox)
        self.label_wfs.setObjectName(u"label_wfs")

        self.gridLayout.addWidget(self.label_wfs, 2, 0, 1, 1)


        self.verticalLayout.addWidget(self.groupBox)

        self.buttonsLayout = QHBoxLayout()
        self.buttonsLayout.setObjectName(u"buttonsLayout")
        self.button_apply = QPushButton(WeightsForm)
        self.button_apply.setObjectName(u"button_apply")

        self.buttonsLayout.addWidget(self.button_apply)

        self.button_cancel = QPushButton(WeightsForm)
        self.button_cancel.setObjectName(u"button_cancel")

        self.buttonsLayout.addWidget(self.button_cancel)


        self.verticalLayout.addLayout(self.buttonsLayout)


        self.retranslateUi(WeightsForm)

        QMetaObject.connectSlotsByName(WeightsForm)
    # setupUi

    def retranslateUi(self, WeightsForm):
        WeightsForm.setWindowTitle(QCoreApplication.translate("WeightsForm", u"BPM weights", None))
        self.groupBox.setTitle(QCoreApplication.translate("WeightsForm", u"Weights for a selected BPM", None))
        self.label_dfs.setText(QCoreApplication.translate("WeightsForm", u"DFS", None))
        self.label_orbit.setText(QCoreApplication.translate("WeightsForm", u"Orbit", None))
        self.label_wfs.setText(QCoreApplication.translate("WeightsForm", u"WFS", None))
        self.button_apply.setText(QCoreApplication.translate("WeightsForm", u"Apply", None))
        self.button_cancel.setText(QCoreApplication.translate("WeightsForm", u"Cancel", None))
    # retranslateUi

