# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'SysID_GUI.ui'
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
from PySide6.QtWidgets import (QAbstractItemView, QApplication, QComboBox, QDoubleSpinBox,
    QGridLayout, QHBoxLayout, QLabel, QLayout,
    QLineEdit, QListWidget, QListWidgetItem, QMainWindow,
    QProgressBar, QPushButton, QSizePolicy, QVBoxLayout,
    QWidget)

class Ui_MainWindow(object):
    def setupUi(self, MainWindow):
        if not MainWindow.objectName():
            MainWindow.setObjectName(u"MainWindow")
        MainWindow.resize(1126, 831)
        self.centralwidget = QWidget(MainWindow)
        self.centralwidget.setObjectName(u"centralwidget")
        self.centralwidget.setEnabled(True)
        self.verticalLayout_2 = QVBoxLayout(self.centralwidget)
        self.verticalLayout_2.setObjectName(u"verticalLayout_2")
        self.verticalLayout_2.setContentsMargins(16, 16, 16, 16)
        self.verticalLayout = QVBoxLayout()
        self.verticalLayout.setObjectName(u"verticalLayout")
        self.horizontal_layout = QHBoxLayout()
        self.horizontal_layout.setObjectName(u"horizontal_layout")
        self.left_layout = QVBoxLayout()
        self.left_layout.setSpacing(2)
        self.left_layout.setObjectName(u"left_layout")
        self.left_layout.setSizeConstraint(QLayout.SetDefaultConstraint)
        self.correctors_header_layout = QHBoxLayout()
        self.correctors_header_layout.setObjectName(u"correctors_header_layout")
        self.correctors_label = QLabel(self.centralwidget)
        self.correctors_label.setObjectName(u"correctors_label")

        self.correctors_header_layout.addWidget(self.correctors_label)


        self.left_layout.addLayout(self.correctors_header_layout)

        self.correctors_list = QListWidget(self.centralwidget)
        self.correctors_list.setObjectName(u"correctors_list")
        sizePolicy = QSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.correctors_list.sizePolicy().hasHeightForWidth())
        self.correctors_list.setSizePolicy(sizePolicy)
        self.correctors_list.setSelectionMode(QAbstractItemView.NoSelection)

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

        self.bpms_header_layout = QHBoxLayout()
        self.bpms_header_layout.setObjectName(u"bpms_header_layout")
        self.bpms_label = QLabel(self.centralwidget)
        self.bpms_label.setObjectName(u"bpms_label")

        self.bpms_header_layout.addWidget(self.bpms_label)


        self.left_layout.addLayout(self.bpms_header_layout)

        self.bpms_list = QListWidget(self.centralwidget)
        self.bpms_list.setObjectName(u"bpms_list")
        sizePolicy.setHeightForWidth(self.bpms_list.sizePolicy().hasHeightForWidth())
        self.bpms_list.setSizePolicy(sizePolicy)
        self.bpms_list.setSelectionMode(QAbstractItemView.NoSelection)

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


        self.horizontal_layout.addLayout(self.left_layout)

        self.right_layout = QVBoxLayout()
        self.right_layout.setSpacing(2)
        self.right_layout.setObjectName(u"right_layout")
        self.info_label = QLabel(self.centralwidget)
        self.info_label.setObjectName(u"info_label")
        sizePolicy1 = QSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        sizePolicy1.setHorizontalStretch(0)
        sizePolicy1.setVerticalStretch(0)
        sizePolicy1.setHeightForWidth(self.info_label.sizePolicy().hasHeightForWidth())
        self.info_label.setSizePolicy(sizePolicy1)

        self.right_layout.addWidget(self.info_label)

        self.working_directory_layout = QHBoxLayout()
        self.working_directory_layout.setObjectName(u"working_directory_layout")
        self.working_directory_input = QLineEdit(self.centralwidget)
        self.working_directory_input.setObjectName(u"working_directory_input")

        self.working_directory_layout.addWidget(self.working_directory_input)

        self.working_directory_dialog = QPushButton(self.centralwidget)
        self.working_directory_dialog.setObjectName(u"working_directory_dialog")

        self.working_directory_layout.addWidget(self.working_directory_dialog)


        self.right_layout.addLayout(self.working_directory_layout)

        self.options_layout = QVBoxLayout()
        self.options_layout.setObjectName(u"options_layout")
        self.options_label = QLabel(self.centralwidget)
        self.options_label.setObjectName(u"options_label")
        sizePolicy1.setHeightForWidth(self.options_label.sizePolicy().hasHeightForWidth())
        self.options_label.setSizePolicy(sizePolicy1)

        self.options_layout.addWidget(self.options_label)

        self.correction_mode = QHBoxLayout()
        self.correction_mode.setObjectName(u"correction_mode")
        self.label = QLabel(self.centralwidget)
        self.label.setObjectName(u"label")

        self.correction_mode.addWidget(self.label)

        self.choose_mode = QComboBox(self.centralwidget)
        self.choose_mode.addItem("")
        self.choose_mode.addItem("")
        self.choose_mode.addItem("")
        self.choose_mode.addItem("")
        self.choose_mode.setObjectName(u"choose_mode")
        self.choose_mode.setMaximumSize(QSize(300, 16777215))

        self.correction_mode.addWidget(self.choose_mode)

        self.cycle_mode_label = QLabel(self.centralwidget)
        self.cycle_mode_label.setObjectName(u"cycle_mode_label")
        self.cycle_mode_label.setMaximumSize(QSize(170, 16777215))

        self.correction_mode.addWidget(self.cycle_mode_label)

        self.niter_number = QLineEdit(self.centralwidget)
        self.niter_number.setObjectName(u"niter_number")
        self.niter_number.setMaximumSize(QSize(150, 16777215))

        self.correction_mode.addWidget(self.niter_number)


        self.options_layout.addLayout(self.correction_mode)

        self.change_layout = QGridLayout()
        self.change_layout.setObjectName(u"change_layout")
        self.max_horizontal_current_spinbox = QDoubleSpinBox(self.centralwidget)
        self.max_horizontal_current_spinbox.setObjectName(u"max_horizontal_current_spinbox")
        sizePolicy2 = QSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        sizePolicy2.setHorizontalStretch(0)
        sizePolicy2.setVerticalStretch(0)
        sizePolicy2.setHeightForWidth(self.max_horizontal_current_spinbox.sizePolicy().hasHeightForWidth())
        self.max_horizontal_current_spinbox.setSizePolicy(sizePolicy2)
        self.max_horizontal_current_spinbox.setMaximumSize(QSize(70, 16777215))
        self.max_horizontal_current_spinbox.setSingleStep(0.010000000000000)

        self.change_layout.addWidget(self.max_horizontal_current_spinbox, 0, 4, 1, 1)

        self.vertical_current_label = QLabel(self.centralwidget)
        self.vertical_current_label.setObjectName(u"vertical_current_label")
        sizePolicy2.setHeightForWidth(self.vertical_current_label.sizePolicy().hasHeightForWidth())
        self.vertical_current_label.setSizePolicy(sizePolicy2)

        self.change_layout.addWidget(self.vertical_current_label, 0, 5, 1, 1)

        self.horizontal_current_label = QLabel(self.centralwidget)
        self.horizontal_current_label.setObjectName(u"horizontal_current_label")
        sizePolicy2.setHeightForWidth(self.horizontal_current_label.sizePolicy().hasHeightForWidth())
        self.horizontal_current_label.setSizePolicy(sizePolicy2)

        self.change_layout.addWidget(self.horizontal_current_label, 0, 3, 1, 1)

        self.max_vertical_current_spinbox = QDoubleSpinBox(self.centralwidget)
        self.max_vertical_current_spinbox.setObjectName(u"max_vertical_current_spinbox")
        self.max_vertical_current_spinbox.setEnabled(True)
        sizePolicy2.setHeightForWidth(self.max_vertical_current_spinbox.sizePolicy().hasHeightForWidth())
        self.max_vertical_current_spinbox.setSizePolicy(sizePolicy2)
        self.max_vertical_current_spinbox.setMaximumSize(QSize(70, 16777215))
        self.max_vertical_current_spinbox.setSingleStep(0.010000000000000)

        self.change_layout.addWidget(self.max_vertical_current_spinbox, 0, 6, 1, 1)

        self.initial_hkick_label = QLabel(self.centralwidget)
        self.initial_hkick_label.setObjectName(u"initial_hkick_label")
        sizePolicy2.setHeightForWidth(self.initial_hkick_label.sizePolicy().hasHeightForWidth())
        self.initial_hkick_label.setSizePolicy(sizePolicy2)

        self.change_layout.addWidget(self.initial_hkick_label, 0, 0, 1, 1)

        self.initial_hkick_settings = QLineEdit(self.centralwidget)
        self.initial_hkick_settings.setObjectName(u"initial_hkick_settings")
        sizePolicy2.setHeightForWidth(self.initial_hkick_settings.sizePolicy().hasHeightForWidth())
        self.initial_hkick_settings.setSizePolicy(sizePolicy2)
        self.initial_hkick_settings.setMaximumSize(QSize(300, 16777215))

        self.change_layout.addWidget(self.initial_hkick_settings, 0, 1, 1, 1)

        self.current_label = QLabel(self.centralwidget)
        self.current_label.setObjectName(u"current_label")
        sizePolicy2.setHeightForWidth(self.current_label.sizePolicy().hasHeightForWidth())
        self.current_label.setSizePolicy(sizePolicy2)
        self.current_label.setMaximumSize(QSize(170, 16777215))

        self.change_layout.addWidget(self.current_label, 0, 2, 1, 1)


        self.options_layout.addLayout(self.change_layout)

        self.excursion_layout = QHBoxLayout()
        self.excursion_layout.setObjectName(u"excursion_layout")
        self.excursion_layout.setContentsMargins(0, -1, -1, -1)
        self.initial_vkick_label = QLabel(self.centralwidget)
        self.initial_vkick_label.setObjectName(u"initial_vkick_label")
        sizePolicy2.setHeightForWidth(self.initial_vkick_label.sizePolicy().hasHeightForWidth())
        self.initial_vkick_label.setSizePolicy(sizePolicy2)

        self.excursion_layout.addWidget(self.initial_vkick_label)

        self.initial_vkick_settings = QLineEdit(self.centralwidget)
        self.initial_vkick_settings.setObjectName(u"initial_vkick_settings")
        sizePolicy2.setHeightForWidth(self.initial_vkick_settings.sizePolicy().hasHeightForWidth())
        self.initial_vkick_settings.setSizePolicy(sizePolicy2)
        self.initial_vkick_settings.setMaximumSize(QSize(300, 16777215))

        self.excursion_layout.addWidget(self.initial_vkick_settings)

        self.excursion_label = QLabel(self.centralwidget)
        self.excursion_label.setObjectName(u"excursion_label")
        sizePolicy2.setHeightForWidth(self.excursion_label.sizePolicy().hasHeightForWidth())
        self.excursion_label.setSizePolicy(sizePolicy2)
        self.excursion_label.setMaximumSize(QSize(170, 16777215))

        self.excursion_layout.addWidget(self.excursion_label)

        self.horizontal_excursion_label = QLabel(self.centralwidget)
        self.horizontal_excursion_label.setObjectName(u"horizontal_excursion_label")
        sizePolicy2.setHeightForWidth(self.horizontal_excursion_label.sizePolicy().hasHeightForWidth())
        self.horizontal_excursion_label.setSizePolicy(sizePolicy2)

        self.excursion_layout.addWidget(self.horizontal_excursion_label)

        self.horizontal_excursion_spinbox = QDoubleSpinBox(self.centralwidget)
        self.horizontal_excursion_spinbox.setObjectName(u"horizontal_excursion_spinbox")
        sizePolicy2.setHeightForWidth(self.horizontal_excursion_spinbox.sizePolicy().hasHeightForWidth())
        self.horizontal_excursion_spinbox.setSizePolicy(sizePolicy2)
        self.horizontal_excursion_spinbox.setMaximumSize(QSize(70, 16777215))
        self.horizontal_excursion_spinbox.setSingleStep(0.100000000000000)
        self.horizontal_excursion_spinbox.setValue(0.500000000000000)

        self.excursion_layout.addWidget(self.horizontal_excursion_spinbox)

        self.vertical_excursion_label = QLabel(self.centralwidget)
        self.vertical_excursion_label.setObjectName(u"vertical_excursion_label")
        sizePolicy2.setHeightForWidth(self.vertical_excursion_label.sizePolicy().hasHeightForWidth())
        self.vertical_excursion_label.setSizePolicy(sizePolicy2)

        self.excursion_layout.addWidget(self.vertical_excursion_label)

        self.vertical_excursion_spinbox = QDoubleSpinBox(self.centralwidget)
        self.vertical_excursion_spinbox.setObjectName(u"vertical_excursion_spinbox")
        sizePolicy2.setHeightForWidth(self.vertical_excursion_spinbox.sizePolicy().hasHeightForWidth())
        self.vertical_excursion_spinbox.setSizePolicy(sizePolicy2)
        self.vertical_excursion_spinbox.setMaximumSize(QSize(70, 16777215))
        self.vertical_excursion_spinbox.setSingleStep(0.100000000000000)
        self.vertical_excursion_spinbox.setValue(0.500000000000000)

        self.excursion_layout.addWidget(self.vertical_excursion_spinbox)


        self.options_layout.addLayout(self.excursion_layout)

        self.plot_widget = QWidget(self.centralwidget)
        self.plot_widget.setObjectName(u"plot_widget")
        sizePolicy3 = QSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        sizePolicy3.setHorizontalStretch(0)
        sizePolicy3.setVerticalStretch(0)
        sizePolicy3.setHeightForWidth(self.plot_widget.sizePolicy().hasHeightForWidth())
        self.plot_widget.setSizePolicy(sizePolicy3)
        self.plot_widget.setMinimumSize(QSize(400, 300))

        self.options_layout.addWidget(self.plot_widget)


        self.right_layout.addLayout(self.options_layout)


        self.horizontal_layout.addLayout(self.right_layout)


        self.verticalLayout.addLayout(self.horizontal_layout)

        self.progressBar = QProgressBar(self.centralwidget)
        self.progressBar.setObjectName(u"progressBar")
        self.progressBar.setValue(0)

        self.verticalLayout.addWidget(self.progressBar)

        self.buttons_layout = QHBoxLayout()
        self.buttons_layout.setObjectName(u"buttons_layout")
        self.start_button = QPushButton(self.centralwidget)
        self.start_button.setObjectName(u"start_button")
        self.start_button.setStyleSheet(u"background-color: red; color: white;")

        self.buttons_layout.addWidget(self.start_button)

        self.stop_button = QPushButton(self.centralwidget)
        self.stop_button.setObjectName(u"stop_button")
        self.stop_button.setStyleSheet(u"background-color: green; color: white;")

        self.buttons_layout.addWidget(self.stop_button)


        self.verticalLayout.addLayout(self.buttons_layout)


        self.verticalLayout_2.addLayout(self.verticalLayout)

        MainWindow.setCentralWidget(self.centralwidget)

        self.retranslateUi(MainWindow)

        QMetaObject.connectSlotsByName(MainWindow)
    # setupUi

    def retranslateUi(self, MainWindow):
        MainWindow.setWindowTitle(QCoreApplication.translate("MainWindow", u"SYSID", None))
        self.correctors_label.setText(QCoreApplication.translate("MainWindow", u"Correctors", None))
        self.save_correctors_button.setText(QCoreApplication.translate("MainWindow", u"Save As..", None))
        self.load_correctors_button.setText(QCoreApplication.translate("MainWindow", u"Load..", None))
        self.clear_correctors_button.setText(QCoreApplication.translate("MainWindow", u"Clear", None))
        self.bpms_label.setText(QCoreApplication.translate("MainWindow", u"BPMs", None))
        self.save_bpms_button.setText(QCoreApplication.translate("MainWindow", u"Save As..", None))
        self.load_bpms_button.setText(QCoreApplication.translate("MainWindow", u"Load..", None))
        self.clear_bpms_button.setText(QCoreApplication.translate("MainWindow", u"Clear", None))
        self.info_label.setText(QCoreApplication.translate("MainWindow", u"Data Storage:", None))
        self.working_directory_input.setPlaceholderText(QCoreApplication.translate("MainWindow", u"Working directory:", None))
        self.working_directory_dialog.setText(QCoreApplication.translate("MainWindow", u"...", None))
        self.options_label.setText(QCoreApplication.translate("MainWindow", u"Options", None))
        self.label.setText(QCoreApplication.translate("MainWindow", u"Correction Mode", None))
        self.choose_mode.setItemText(0, QCoreApplication.translate("MainWindow", u"Orbit Correction", None))
        self.choose_mode.setItemText(1, QCoreApplication.translate("MainWindow", u"Changed energy", None))
        self.choose_mode.setItemText(2, QCoreApplication.translate("MainWindow", u"Changed intensity", None))
        self.choose_mode.setItemText(3, QCoreApplication.translate("MainWindow", u"All modes at once", None))

        self.cycle_mode_label.setText(QCoreApplication.translate("MainWindow", u"Number of cycles", None))
        self.niter_number.setText(QCoreApplication.translate("MainWindow", u"3", None))
        self.vertical_current_label.setText(QCoreApplication.translate("MainWindow", u" V:", None))
        self.horizontal_current_label.setText(QCoreApplication.translate("MainWindow", u"H:", None))
        self.initial_hkick_label.setText(QCoreApplication.translate("MainWindow", u"Initial hkick", None))
        self.current_label.setText(QCoreApplication.translate("MainWindow", u"Max strength (gauss*m)", None))
        self.initial_vkick_label.setText(QCoreApplication.translate("MainWindow", u"Initial vkick", None))
        self.excursion_label.setText(QCoreApplication.translate("MainWindow", u"Target orbit excursion (mm)", None))
        self.horizontal_excursion_label.setText(QCoreApplication.translate("MainWindow", u"H:", None))
        self.vertical_excursion_label.setText(QCoreApplication.translate("MainWindow", u"V:", None))
        self.start_button.setText(QCoreApplication.translate("MainWindow", u"START", None))
        self.stop_button.setText(QCoreApplication.translate("MainWindow", u"STOP", None))
    # retranslateUi

