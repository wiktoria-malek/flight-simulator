# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'Emittance_Measurement_GUI.ui'
##
## Created by: Qt User Interface Compiler version 6.9.2
##
## WARNING! All changes made in this file will be lost when recompiling UI file!
################################################################################

from PySide6.QtCore import (QCoreApplication, QDate, QDateTime, QLocale,
    QMetaObject, QObject, QPoint, QRect,
    QSize, QTime, QUrl, Qt)
from PySide6.QtGui import (QAction, QBrush, QColor, QConicalGradient,
    QCursor, QFont, QFontDatabase, QGradient,
    QIcon, QImage, QKeySequence, QLinearGradient,
    QPainter, QPalette, QPixmap, QRadialGradient,
    QTransform)
from PySide6.QtWidgets import (QAbstractItemView, QApplication, QComboBox, QDoubleSpinBox,
    QGridLayout, QGroupBox, QHBoxLayout, QHeaderView,
    QLabel, QLineEdit, QListWidget, QListWidgetItem,
    QMainWindow, QPushButton, QSizePolicy, QSpinBox,
    QStatusBar, QTabWidget, QTableWidget, QTableWidgetItem,
    QVBoxLayout, QWidget)

class Ui_EmittanceMainWindow(object):
    def setupUi(self, EmittanceMainWindow):
        if not EmittanceMainWindow.objectName():
            EmittanceMainWindow.setObjectName(u"EmittanceMainWindow")
        EmittanceMainWindow.resize(1347, 868)
        self.actionss = QAction(EmittanceMainWindow)
        self.actionss.setObjectName(u"actionss")
        self.actions = QAction(EmittanceMainWindow)
        self.actions.setObjectName(u"actions")
        self.actions_2 = QAction(EmittanceMainWindow)
        self.actions_2.setObjectName(u"actions_2")
        self.centralwidget = QWidget(EmittanceMainWindow)
        self.centralwidget.setObjectName(u"centralwidget")
        self.horizontalLayout = QHBoxLayout(self.centralwidget)
        self.horizontalLayout.setObjectName(u"horizontalLayout")
        self.leftPanelGroup = QGroupBox(self.centralwidget)
        self.leftPanelGroup.setObjectName(u"leftPanelGroup")
        self.leftVBox = QVBoxLayout(self.leftPanelGroup)
        self.leftVBox.setObjectName(u"leftVBox")
        self.elementsGroup = QGroupBox(self.leftPanelGroup)
        self.elementsGroup.setObjectName(u"elementsGroup")
        self.elementsVBox = QVBoxLayout(self.elementsGroup)
        self.elementsVBox.setObjectName(u"elementsVBox")
        self.quadsScreensHBox = QHBoxLayout()
        self.quadsScreensHBox.setObjectName(u"quadsScreensHBox")
        self.quadsGroup = QGroupBox(self.elementsGroup)
        self.quadsGroup.setObjectName(u"quadsGroup")
        self.quadsVBox = QVBoxLayout(self.quadsGroup)
        self.quadsVBox.setObjectName(u"quadsVBox")
        self.quadrupoles_list = QListWidget(self.quadsGroup)
        self.quadrupoles_list.setObjectName(u"quadrupoles_list")
        self.quadrupoles_list.setSelectionMode(QAbstractItemView.ExtendedSelection)

        self.quadsVBox.addWidget(self.quadrupoles_list)

        self.load_quadrupoles_button = QPushButton(self.quadsGroup)
        self.load_quadrupoles_button.setObjectName(u"load_quadrupoles_button")

        self.quadsVBox.addWidget(self.load_quadrupoles_button)


        self.quadsScreensHBox.addWidget(self.quadsGroup)

        self.screensGroup = QGroupBox(self.elementsGroup)
        self.screensGroup.setObjectName(u"screensGroup")
        self.screensVBox = QVBoxLayout(self.screensGroup)
        self.screensVBox.setObjectName(u"screensVBox")
        self.screens_list = QListWidget(self.screensGroup)
        self.screens_list.setObjectName(u"screens_list")
        self.screens_list.setSelectionMode(QAbstractItemView.ExtendedSelection)

        self.screensVBox.addWidget(self.screens_list)

        self.load_screens_button = QPushButton(self.screensGroup)
        self.load_screens_button.setObjectName(u"load_screens_button")

        self.screensVBox.addWidget(self.load_screens_button)


        self.quadsScreensHBox.addWidget(self.screensGroup)


        self.elementsVBox.addLayout(self.quadsScreensHBox)

        self.firstScreenHBox = QHBoxLayout()
        self.firstScreenHBox.setObjectName(u"firstScreenHBox")
        self.labelFirstScreen = QLabel(self.elementsGroup)
        self.labelFirstScreen.setObjectName(u"labelFirstScreen")

        self.firstScreenHBox.addWidget(self.labelFirstScreen)

        self.first_screen_choice = QComboBox(self.elementsGroup)
        self.first_screen_choice.setObjectName(u"first_screen_choice")

        self.firstScreenHBox.addWidget(self.first_screen_choice)


        self.elementsVBox.addLayout(self.firstScreenHBox)


        self.leftVBox.addWidget(self.elementsGroup)

        self.scanGroup = QGroupBox(self.leftPanelGroup)
        self.scanGroup.setObjectName(u"scanGroup")
        self.gridScan = QGridLayout(self.scanGroup)
        self.gridScan.setObjectName(u"gridScan")
        self.delta_min_scan = QDoubleSpinBox(self.scanGroup)
        self.delta_min_scan.setObjectName(u"delta_min_scan")
        self.delta_min_scan.setDecimals(4)
        self.delta_min_scan.setMinimum(-10.000000000000000)
        self.delta_min_scan.setMaximum(10.000000000000000)
        self.delta_min_scan.setValue(-0.050000000000000)

        self.gridScan.addWidget(self.delta_min_scan, 0, 1, 1, 1)

        self.labelDeltaMax = QLabel(self.scanGroup)
        self.labelDeltaMax.setObjectName(u"labelDeltaMax")

        self.gridScan.addWidget(self.labelDeltaMax, 1, 0, 1, 1)

        self.delta_max_scan = QDoubleSpinBox(self.scanGroup)
        self.delta_max_scan.setObjectName(u"delta_max_scan")
        self.delta_max_scan.setDecimals(4)
        self.delta_max_scan.setMinimum(-10.000000000000000)
        self.delta_max_scan.setMaximum(10.000000000000000)
        self.delta_max_scan.setValue(0.050000000000000)

        self.gridScan.addWidget(self.delta_max_scan, 1, 1, 1, 1)

        self.labelSteps = QLabel(self.scanGroup)
        self.labelSteps.setObjectName(u"labelSteps")

        self.gridScan.addWidget(self.labelSteps, 2, 0, 1, 1)

        self.steps_settings = QSpinBox(self.scanGroup)
        self.steps_settings.setObjectName(u"steps_settings")
        self.steps_settings.setMinimum(3)
        self.steps_settings.setMaximum(101)
        self.steps_settings.setValue(10)

        self.gridScan.addWidget(self.steps_settings, 2, 1, 1, 1)

        self.labelShots = QLabel(self.scanGroup)
        self.labelShots.setObjectName(u"labelShots")

        self.gridScan.addWidget(self.labelShots, 3, 0, 1, 1)

        self.meas_per_step = QSpinBox(self.scanGroup)
        self.meas_per_step.setObjectName(u"meas_per_step")
        self.meas_per_step.setMinimum(1)
        self.meas_per_step.setMaximum(200)
        self.meas_per_step.setValue(1)

        self.gridScan.addWidget(self.meas_per_step, 3, 1, 1, 1)

        self.label = QLabel(self.scanGroup)
        self.label.setObjectName(u"label")

        self.gridScan.addWidget(self.label, 0, 0, 1, 1)


        self.leftVBox.addWidget(self.scanGroup)

        self.actionsGroup = QGroupBox(self.leftPanelGroup)
        self.actionsGroup.setObjectName(u"actionsGroup")
        self.actionsGroup.setLayoutDirection(Qt.LeftToRight)
        self.gridActions = QGridLayout(self.actionsGroup)
        self.gridActions.setObjectName(u"gridActions")
        self.fit_emm_twiss_button = QPushButton(self.actionsGroup)
        self.fit_emm_twiss_button.setObjectName(u"fit_emm_twiss_button")

        self.gridActions.addWidget(self.fit_emm_twiss_button, 0, 0, 1, 1)

        self.pushButton = QPushButton(self.actionsGroup)
        self.pushButton.setObjectName(u"pushButton")
        self.pushButton.setMaximumSize(QSize(200, 16777215))
        self.pushButton.setLayoutDirection(Qt.RightToLeft)

        self.gridActions.addWidget(self.pushButton, 0, 1, 1, 1)

        self.session_database = QLineEdit(self.actionsGroup)
        self.session_database.setObjectName(u"session_database")

        self.gridActions.addWidget(self.session_database, 1, 1, 1, 1)

        self.label_2 = QLabel(self.actionsGroup)
        self.label_2.setObjectName(u"label_2")

        self.gridActions.addWidget(self.label_2, 1, 0, 1, 1)

        self.load_session_button = QPushButton(self.actionsGroup)
        self.load_session_button.setObjectName(u"load_session_button")

        self.gridActions.addWidget(self.load_session_button, 1, 2, 1, 1)


        self.leftVBox.addWidget(self.actionsGroup)


        self.horizontalLayout.addWidget(self.leftPanelGroup)

        self.tabs = QTabWidget(self.centralwidget)
        self.tabs.setObjectName(u"tabs")
        self.scanTab = QWidget()
        self.scanTab.setObjectName(u"scanTab")
        self.scanVBox = QVBoxLayout(self.scanTab)
        self.scanVBox.setObjectName(u"scanVBox")
        self.plotSelectorsHBox = QHBoxLayout()
        self.plotSelectorsHBox.setObjectName(u"plotSelectorsHBox")
        self.labelQuadPlot = QLabel(self.scanTab)
        self.labelQuadPlot.setObjectName(u"labelQuadPlot")

        self.plotSelectorsHBox.addWidget(self.labelQuadPlot)

        self.quad_on_plot = QComboBox(self.scanTab)
        self.quad_on_plot.setObjectName(u"quad_on_plot")

        self.plotSelectorsHBox.addWidget(self.quad_on_plot)

        self.labelScreenPlot = QLabel(self.scanTab)
        self.labelScreenPlot.setObjectName(u"labelScreenPlot")

        self.plotSelectorsHBox.addWidget(self.labelScreenPlot)

        self.screen_on_plot = QComboBox(self.scanTab)
        self.screen_on_plot.setObjectName(u"screen_on_plot")

        self.plotSelectorsHBox.addWidget(self.screen_on_plot)


        self.scanVBox.addLayout(self.plotSelectorsHBox)

        self.plotPlaceholder = QWidget(self.scanTab)
        self.plotPlaceholder.setObjectName(u"plotPlaceholder")

        self.scanVBox.addWidget(self.plotPlaceholder)

        self.startStopHBox = QHBoxLayout()
        self.startStopHBox.setObjectName(u"startStopHBox")
        self.start_button = QPushButton(self.scanTab)
        self.start_button.setObjectName(u"start_button")
        self.start_button.setStyleSheet(u"background-color: red; color: white;")

        self.startStopHBox.addWidget(self.start_button)

        self.stop_button = QPushButton(self.scanTab)
        self.stop_button.setObjectName(u"stop_button")
        self.stop_button.setStyleSheet(u"background-color: green; color: white;")

        self.startStopHBox.addWidget(self.stop_button)


        self.scanVBox.addLayout(self.startStopHBox)

        self.tabs.addTab(self.scanTab, "")
        self.fitTab = QWidget()
        self.fitTab.setObjectName(u"fitTab")
        self.fitVBox = QVBoxLayout(self.fitTab)
        self.fitVBox.setObjectName(u"fitVBox")
        self.resultsTable = QTableWidget(self.fitTab)
        if (self.resultsTable.columnCount() < 5):
            self.resultsTable.setColumnCount(5)
        __qtablewidgetitem = QTableWidgetItem()
        self.resultsTable.setHorizontalHeaderItem(0, __qtablewidgetitem)
        __qtablewidgetitem1 = QTableWidgetItem()
        self.resultsTable.setHorizontalHeaderItem(1, __qtablewidgetitem1)
        __qtablewidgetitem2 = QTableWidgetItem()
        self.resultsTable.setHorizontalHeaderItem(2, __qtablewidgetitem2)
        __qtablewidgetitem3 = QTableWidgetItem()
        self.resultsTable.setHorizontalHeaderItem(3, __qtablewidgetitem3)
        __qtablewidgetitem4 = QTableWidgetItem()
        self.resultsTable.setHorizontalHeaderItem(4, __qtablewidgetitem4)
        if (self.resultsTable.rowCount() < 2):
            self.resultsTable.setRowCount(2)
        self.resultsTable.setObjectName(u"resultsTable")
        self.resultsTable.setRowCount(2)
        self.resultsTable.setColumnCount(5)

        self.fitVBox.addWidget(self.resultsTable)

        self.tabs.addTab(self.fitTab, "")

        self.horizontalLayout.addWidget(self.tabs)

        EmittanceMainWindow.setCentralWidget(self.centralwidget)
        self.statusbar = QStatusBar(EmittanceMainWindow)
        self.statusbar.setObjectName(u"statusbar")
        EmittanceMainWindow.setStatusBar(self.statusbar)

        self.retranslateUi(EmittanceMainWindow)

        self.tabs.setCurrentIndex(0)


        QMetaObject.connectSlotsByName(EmittanceMainWindow)
    # setupUi

    def retranslateUi(self, EmittanceMainWindow):
        EmittanceMainWindow.setWindowTitle(QCoreApplication.translate("EmittanceMainWindow", u"Emittance Measurement", None))
        self.actionss.setText(QCoreApplication.translate("EmittanceMainWindow", u"ss", None))
        self.actions.setText(QCoreApplication.translate("EmittanceMainWindow", u"s", None))
        self.actions_2.setText(QCoreApplication.translate("EmittanceMainWindow", u"s", None))
        self.leftPanelGroup.setTitle("")
        self.elementsGroup.setTitle(QCoreApplication.translate("EmittanceMainWindow", u"Devices", None))
        self.quadsGroup.setTitle(QCoreApplication.translate("EmittanceMainWindow", u"Quadrupoles", None))
        self.load_quadrupoles_button.setText(QCoreApplication.translate("EmittanceMainWindow", u"Load...", None))
        self.screensGroup.setTitle(QCoreApplication.translate("EmittanceMainWindow", u"Screens", None))
        self.load_screens_button.setText(QCoreApplication.translate("EmittanceMainWindow", u"Load...", None))
        self.labelFirstScreen.setText(QCoreApplication.translate("EmittanceMainWindow", u"First (reference) screen", None))
        self.scanGroup.setTitle(QCoreApplication.translate("EmittanceMainWindow", u"Quadrupole scan settings", None))
        self.labelDeltaMax.setText(QCoreApplication.translate("EmittanceMainWindow", u"Delta max", None))
        self.labelSteps.setText(QCoreApplication.translate("EmittanceMainWindow", u"Steps", None))
        self.labelShots.setText(QCoreApplication.translate("EmittanceMainWindow", u"Measurements per step", None))
        self.label.setText(QCoreApplication.translate("EmittanceMainWindow", u"Delta min", None))
        self.actionsGroup.setTitle(QCoreApplication.translate("EmittanceMainWindow", u"Measurement", None))
        self.fit_emm_twiss_button.setText(QCoreApplication.translate("EmittanceMainWindow", u"Fit emittance / Twiss", None))
        self.pushButton.setText(QCoreApplication.translate("EmittanceMainWindow", u"Restore quadrupole settings", None))
        self.label_2.setText(QCoreApplication.translate("EmittanceMainWindow", u"Load session settings", None))
        self.load_session_button.setText(QCoreApplication.translate("EmittanceMainWindow", u"...", None))
        self.labelQuadPlot.setText(QCoreApplication.translate("EmittanceMainWindow", u"Quadrupole", None))
        self.labelScreenPlot.setText(QCoreApplication.translate("EmittanceMainWindow", u"Screen", None))
        self.start_button.setText(QCoreApplication.translate("EmittanceMainWindow", u"START SCAN", None))
        self.stop_button.setText(QCoreApplication.translate("EmittanceMainWindow", u"STOP", None))
        self.tabs.setTabText(self.tabs.indexOf(self.scanTab), QCoreApplication.translate("EmittanceMainWindow", u"Scan plots", None))
        ___qtablewidgetitem = self.resultsTable.horizontalHeaderItem(0)
        ___qtablewidgetitem.setText(QCoreApplication.translate("EmittanceMainWindow", u"Plane", None));
        ___qtablewidgetitem1 = self.resultsTable.horizontalHeaderItem(1)
        ___qtablewidgetitem1.setText(QCoreApplication.translate("EmittanceMainWindow", u"epsilon", None));
        ___qtablewidgetitem2 = self.resultsTable.horizontalHeaderItem(2)
        ___qtablewidgetitem2.setText(QCoreApplication.translate("EmittanceMainWindow", u"beta", None));
        ___qtablewidgetitem3 = self.resultsTable.horizontalHeaderItem(3)
        ___qtablewidgetitem3.setText(QCoreApplication.translate("EmittanceMainWindow", u"alpha", None));
        ___qtablewidgetitem4 = self.resultsTable.horizontalHeaderItem(4)
        ___qtablewidgetitem4.setText(QCoreApplication.translate("EmittanceMainWindow", u"chi2", None));
        self.tabs.setTabText(self.tabs.indexOf(self.fitTab), QCoreApplication.translate("EmittanceMainWindow", u"Fit summary", None))
    # retranslateUi

