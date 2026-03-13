# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'ComputeResponseMatrix_GUI.ui'
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
from PySide6.QtWidgets import (QAbstractItemView, QApplication, QCheckBox, QHBoxLayout,
    QLabel, QLineEdit, QListWidget, QListWidgetItem,
    QMainWindow, QPushButton, QSizePolicy, QSpacerItem,
    QVBoxLayout, QWidget)

class Ui_MainWindow(object):
    def setupUi(self, MainWindow):
        if not MainWindow.objectName():
            MainWindow.setObjectName(u"MainWindow")
        MainWindow.resize(1512, 864)
        self.centralwidget = QWidget(MainWindow)
        self.centralwidget.setObjectName(u"centralwidget")
        self.main_layout = QVBoxLayout(self.centralwidget)
        self.main_layout.setObjectName(u"main_layout")
        self.main_layout.setContentsMargins(4, 4, 4, 4)
        self.dir_layout = QVBoxLayout()
        self.dir_layout.setObjectName(u"dir_layout")
        self.dir_layout.setContentsMargins(4, 4, 4, 4)
        self.dirA_layout = QHBoxLayout()
        self.dirA_layout.setObjectName(u"dirA_layout")
        self.label_dir_1 = QLabel(self.centralwidget)
        self.label_dir_1.setObjectName(u"label_dir_1")

        self.dirA_layout.addWidget(self.label_dir_1)

        self.data_directory_1 = QLineEdit(self.centralwidget)
        self.data_directory_1.setObjectName(u"data_directory_1")

        self.dirA_layout.addWidget(self.data_directory_1)

        self.choose_directory_1 = QPushButton(self.centralwidget)
        self.choose_directory_1.setObjectName(u"choose_directory_1")
        self.choose_directory_1.setMaximumSize(QSize(40, 16777215))

        self.dirA_layout.addWidget(self.choose_directory_1)


        self.dir_layout.addLayout(self.dirA_layout)

        self.diff_layout = QHBoxLayout()
        self.diff_layout.setObjectName(u"diff_layout")
        self.diff_checkbox = QCheckBox(self.centralwidget)
        self.diff_checkbox.setObjectName(u"diff_checkbox")

        self.diff_layout.addWidget(self.diff_checkbox)

        self.diff_spacer = QSpacerItem(40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        self.diff_layout.addItem(self.diff_spacer)


        self.dir_layout.addLayout(self.diff_layout)

        self.dirB_layout = QHBoxLayout()
        self.dirB_layout.setObjectName(u"dirB_layout")
        self.label_dir_2 = QLabel(self.centralwidget)
        self.label_dir_2.setObjectName(u"label_dir_2")
        self.label_dir_2.setEnabled(False)

        self.dirB_layout.addWidget(self.label_dir_2)

        self.data_directory_2 = QLineEdit(self.centralwidget)
        self.data_directory_2.setObjectName(u"data_directory_2")
        self.data_directory_2.setEnabled(False)

        self.dirB_layout.addWidget(self.data_directory_2)

        self.choose_directory_2 = QPushButton(self.centralwidget)
        self.choose_directory_2.setObjectName(u"choose_directory_2")
        self.choose_directory_2.setEnabled(False)
        self.choose_directory_2.setMaximumSize(QSize(40, 16777215))

        self.dirB_layout.addWidget(self.choose_directory_2)


        self.dir_layout.addLayout(self.dirB_layout)


        self.main_layout.addLayout(self.dir_layout)

        self.content_layout = QHBoxLayout()
        self.content_layout.setObjectName(u"content_layout")
        self.left_layout = QVBoxLayout()
        self.left_layout.setObjectName(u"left_layout")
        self.left_layout.setContentsMargins(13, 4, 4, 4)
        self.label_correctors = QLabel(self.centralwidget)
        self.label_correctors.setObjectName(u"label_correctors")

        self.left_layout.addWidget(self.label_correctors)

        self.correctors_list = QListWidget(self.centralwidget)
        self.correctors_list.setObjectName(u"correctors_list")
        self.correctors_list.setSelectionMode(QAbstractItemView.ExtendedSelection)

        self.left_layout.addWidget(self.correctors_list)

        self.correctors_buttons_layout = QHBoxLayout()
        self.correctors_buttons_layout.setObjectName(u"correctors_buttons_layout")
        self.save_correctors_button = QPushButton(self.centralwidget)
        self.save_correctors_button.setObjectName(u"save_correctors_button")

        self.correctors_buttons_layout.addWidget(self.save_correctors_button)

        self.load_correctors_button = QPushButton(self.centralwidget)
        self.load_correctors_button.setObjectName(u"load_correctors_button")

        self.correctors_buttons_layout.addWidget(self.load_correctors_button)

        self.clear_correctors_button = QPushButton(self.centralwidget)
        self.clear_correctors_button.setObjectName(u"clear_correctors_button")

        self.correctors_buttons_layout.addWidget(self.clear_correctors_button)


        self.left_layout.addLayout(self.correctors_buttons_layout)

        self.label_bpms = QLabel(self.centralwidget)
        self.label_bpms.setObjectName(u"label_bpms")

        self.left_layout.addWidget(self.label_bpms)

        self.bpms_list = QListWidget(self.centralwidget)
        self.bpms_list.setObjectName(u"bpms_list")
        self.bpms_list.setSelectionMode(QAbstractItemView.ExtendedSelection)

        self.left_layout.addWidget(self.bpms_list)

        self.bpms_buttons_layout = QHBoxLayout()
        self.bpms_buttons_layout.setObjectName(u"bpms_buttons_layout")
        self.save_bpms_button = QPushButton(self.centralwidget)
        self.save_bpms_button.setObjectName(u"save_bpms_button")

        self.bpms_buttons_layout.addWidget(self.save_bpms_button)

        self.load_bpms_button = QPushButton(self.centralwidget)
        self.load_bpms_button.setObjectName(u"load_bpms_button")

        self.bpms_buttons_layout.addWidget(self.load_bpms_button)

        self.clear_bpms_button = QPushButton(self.centralwidget)
        self.clear_bpms_button.setObjectName(u"clear_bpms_button")

        self.bpms_buttons_layout.addWidget(self.clear_bpms_button)


        self.left_layout.addLayout(self.bpms_buttons_layout)


        self.content_layout.addLayout(self.left_layout)

        self.right_layout = QVBoxLayout()
        self.right_layout.setObjectName(u"right_layout")
        self.right_layout.setContentsMargins(0, 4, 4, 4)
        self.triangular_layout = QHBoxLayout()
        self.triangular_layout.setObjectName(u"triangular_layout")
        self.tri_spacer_left = QSpacerItem(40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        self.triangular_layout.addItem(self.tri_spacer_left)

        self.triangular_checkbox = QCheckBox(self.centralwidget)
        self.triangular_checkbox.setObjectName(u"triangular_checkbox")

        self.triangular_layout.addWidget(self.triangular_checkbox)

        self.tri_spacer_right = QSpacerItem(40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        self.triangular_layout.addItem(self.tri_spacer_right)


        self.right_layout.addLayout(self.triangular_layout)

        self.plot_widget = QWidget(self.centralwidget)
        self.plot_widget.setObjectName(u"plot_widget")
        sizePolicy = QSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.plot_widget.sizePolicy().hasHeightForWidth())
        self.plot_widget.setSizePolicy(sizePolicy)
        self.plot_widget.setMinimumSize(QSize(450, 500))

        self.right_layout.addWidget(self.plot_widget)

        self.operation_layout = QHBoxLayout()
        self.operation_layout.setObjectName(u"operation_layout")
        self.compute_button = QPushButton(self.centralwidget)
        self.compute_button.setObjectName(u"compute_button")
        self.compute_button.setStyleSheet(u"background-color: green; color: white;")

        self.operation_layout.addWidget(self.compute_button)

        self.save_as_button = QPushButton(self.centralwidget)
        self.save_as_button.setObjectName(u"save_as_button")
        self.save_as_button.setStyleSheet(u"background-color: red; color: white;")

        self.operation_layout.addWidget(self.save_as_button)


        self.right_layout.addLayout(self.operation_layout)


        self.content_layout.addLayout(self.right_layout)


        self.main_layout.addLayout(self.content_layout)

        MainWindow.setCentralWidget(self.centralwidget)

        self.retranslateUi(MainWindow)

        QMetaObject.connectSlotsByName(MainWindow)
    # setupUi

    def retranslateUi(self, MainWindow):
        MainWindow.setWindowTitle(QCoreApplication.translate("MainWindow", u"Compute Response Matrix Tool", None))
        self.label_dir_1.setText(QCoreApplication.translate("MainWindow", u"Data directory:", None))
        self.choose_directory_1.setText(QCoreApplication.translate("MainWindow", u"...", None))
        self.diff_checkbox.setText(QCoreApplication.translate("MainWindow", u"Compute the difference between two directories", None))
        self.label_dir_2.setText(QCoreApplication.translate("MainWindow", u"Second data directory:", None))
        self.choose_directory_2.setText(QCoreApplication.translate("MainWindow", u"...", None))
        self.label_correctors.setText(QCoreApplication.translate("MainWindow", u"Correctors:", None))
        self.save_correctors_button.setText(QCoreApplication.translate("MainWindow", u"Save As..", None))
        self.load_correctors_button.setText(QCoreApplication.translate("MainWindow", u"Load..", None))
        self.clear_correctors_button.setText(QCoreApplication.translate("MainWindow", u"Clear", None))
        self.label_bpms.setText(QCoreApplication.translate("MainWindow", u"BPMs:", None))
        self.save_bpms_button.setText(QCoreApplication.translate("MainWindow", u"Save As..", None))
        self.load_bpms_button.setText(QCoreApplication.translate("MainWindow", u"Load..", None))
        self.clear_bpms_button.setText(QCoreApplication.translate("MainWindow", u"Clear", None))
        self.triangular_checkbox.setText(QCoreApplication.translate("MainWindow", u"Force triangular matrix", None))
        self.compute_button.setText(QCoreApplication.translate("MainWindow", u"Compute", None))
        self.save_as_button.setText(QCoreApplication.translate("MainWindow", u"Save As..", None))
    # retranslateUi

