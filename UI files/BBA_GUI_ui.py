# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'BBA_GUI.ui'
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
from PySide6.QtWidgets import (QAbstractItemView, QApplication, QCheckBox, QDoubleSpinBox,
    QGroupBox, QHBoxLayout, QLabel, QLineEdit,
    QListWidget, QListWidgetItem, QMainWindow, QPushButton,
    QRadioButton, QSizePolicy, QSpacerItem, QTabWidget,
    QVBoxLayout, QWidget)

class Ui_MainWindow(object):
    def setupUi(self, MainWindow):
        if not MainWindow.objectName():
            MainWindow.setObjectName(u"MainWindow")
        MainWindow.resize(1141, 886)
        self.centralwidget = QWidget(MainWindow)
        self.centralwidget.setObjectName(u"centralwidget")
        self.centralwidget.setEnabled(True)
        self.horizontalLayout = QHBoxLayout(self.centralwidget)
        self.horizontalLayout.setObjectName(u"horizontalLayout")
        self.horizontalLayout_2 = QHBoxLayout()
        self.horizontalLayout_2.setObjectName(u"horizontalLayout_2")
        self.tabWidget = QTabWidget(self.centralwidget)
        self.tabWidget.setObjectName(u"tabWidget")
        self.tabWidget.setTabPosition(QTabWidget.North)
        self.tab_response = QWidget()
        self.tab_response.setObjectName(u"tab_response")
        self.verticalLayout_7 = QVBoxLayout(self.tab_response)
        self.verticalLayout_7.setObjectName(u"verticalLayout_7")
        self.session_group_3 = QGroupBox(self.tab_response)
        self.session_group_3.setObjectName(u"session_group_3")
        self.verticalLayout_31 = QVBoxLayout(self.session_group_3)
        self.verticalLayout_31.setObjectName(u"verticalLayout_31")
        self.verticalLayout_31.setContentsMargins(4, 4, 4, 4)
        self.database_dir_layout_3 = QHBoxLayout()
        self.database_dir_layout_3.setObjectName(u"database_dir_layout_3")
        self.label_31 = QLabel(self.session_group_3)
        self.label_31.setObjectName(u"label_31")

        self.database_dir_layout_3.addWidget(self.label_31)

        self.session_database_3 = QLineEdit(self.session_group_3)
        self.session_database_3.setObjectName(u"session_database_3")
        self.session_database_3.setMaximumSize(QSize(500, 16777215))

        self.database_dir_layout_3.addWidget(self.session_database_3)

        self.pushButton_11 = QPushButton(self.session_group_3)
        self.pushButton_11.setObjectName(u"pushButton_11")
        sizePolicy = QSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.pushButton_11.sizePolicy().hasHeightForWidth())
        self.pushButton_11.setSizePolicy(sizePolicy)

        self.database_dir_layout_3.addWidget(self.pushButton_11)


        self.verticalLayout_31.addLayout(self.database_dir_layout_3)


        self.verticalLayout_7.addWidget(self.session_group_3)

        self.trajectory_group_3 = QGroupBox(self.tab_response)
        self.trajectory_group_3.setObjectName(u"trajectory_group_3")
        self.verticalLayout_9 = QVBoxLayout(self.trajectory_group_3)
        self.verticalLayout_9.setObjectName(u"verticalLayout_9")
        self.verticalLayout_9.setContentsMargins(4, 4, 4, 4)
        self.trajectory_response_layout_3 = QHBoxLayout()
        self.trajectory_response_layout_3.setObjectName(u"trajectory_response_layout_3")
        self.label_18 = QLabel(self.trajectory_group_3)
        self.label_18.setObjectName(u"label_18")

        self.trajectory_response_layout_3.addWidget(self.label_18)

        self.trajectory_response_3 = QLineEdit(self.trajectory_group_3)
        self.trajectory_response_3.setObjectName(u"trajectory_response_3")
        self.trajectory_response_3.setMaximumSize(QSize(500, 16777215))

        self.trajectory_response_layout_3.addWidget(self.trajectory_response_3)

        self.pushButton_8 = QPushButton(self.trajectory_group_3)
        self.pushButton_8.setObjectName(u"pushButton_8")
        sizePolicy.setHeightForWidth(self.pushButton_8.sizePolicy().hasHeightForWidth())
        self.pushButton_8.setSizePolicy(sizePolicy)

        self.trajectory_response_layout_3.addWidget(self.pushButton_8)


        self.verticalLayout_9.addLayout(self.trajectory_response_layout_3)


        self.verticalLayout_7.addWidget(self.trajectory_group_3)

        self.groupBox_6 = QGroupBox(self.tab_response)
        self.groupBox_6.setObjectName(u"groupBox_6")
        self.verticalLayout_19 = QVBoxLayout(self.groupBox_6)
        self.verticalLayout_19.setObjectName(u"verticalLayout_19")
        self.verticalLayout_19.setContentsMargins(4, 4, 4, 4)
        self.verticalLayout_10 = QVBoxLayout()
        self.verticalLayout_10.setObjectName(u"verticalLayout_10")
        self.horizontalLayout_16 = QHBoxLayout()
        self.horizontalLayout_16.setObjectName(u"horizontalLayout_16")
        self.label_19 = QLabel(self.groupBox_6)
        self.label_19.setObjectName(u"label_19")

        self.horizontalLayout_16.addWidget(self.label_19)

        self.dfs_response_3 = QLineEdit(self.groupBox_6)
        self.dfs_response_3.setObjectName(u"dfs_response_3")
        self.dfs_response_3.setMaximumSize(QSize(500, 16777215))

        self.horizontalLayout_16.addWidget(self.dfs_response_3)

        self.pushButton_9 = QPushButton(self.groupBox_6)
        self.pushButton_9.setObjectName(u"pushButton_9")
        sizePolicy.setHeightForWidth(self.pushButton_9.sizePolicy().hasHeightForWidth())
        self.pushButton_9.setSizePolicy(sizePolicy)

        self.horizontalLayout_16.addWidget(self.pushButton_9)


        self.verticalLayout_10.addLayout(self.horizontalLayout_16)

        self.horizontalLayout_17 = QHBoxLayout()
        self.horizontalLayout_17.setObjectName(u"horizontalLayout_17")

        self.verticalLayout_10.addLayout(self.horizontalLayout_17)

        self.horizontalLayout_18 = QHBoxLayout()
        self.horizontalLayout_18.setObjectName(u"horizontalLayout_18")

        self.verticalLayout_10.addLayout(self.horizontalLayout_18)


        self.verticalLayout_19.addLayout(self.verticalLayout_10)


        self.verticalLayout_7.addWidget(self.groupBox_6)

        self.groupBox_7 = QGroupBox(self.tab_response)
        self.groupBox_7.setObjectName(u"groupBox_7")
        self.verticalLayout_20 = QVBoxLayout(self.groupBox_7)
        self.verticalLayout_20.setObjectName(u"verticalLayout_20")
        self.verticalLayout_20.setContentsMargins(4, 4, 4, 4)
        self.horizontalLayout_19 = QHBoxLayout()
        self.horizontalLayout_19.setObjectName(u"horizontalLayout_19")
        self.label_22 = QLabel(self.groupBox_7)
        self.label_22.setObjectName(u"label_22")

        self.horizontalLayout_19.addWidget(self.label_22)

        self.wfs_response_3 = QLineEdit(self.groupBox_7)
        self.wfs_response_3.setObjectName(u"wfs_response_3")
        self.wfs_response_3.setMaximumSize(QSize(500, 16777215))

        self.horizontalLayout_19.addWidget(self.wfs_response_3)

        self.pushButton_10 = QPushButton(self.groupBox_7)
        self.pushButton_10.setObjectName(u"pushButton_10")
        sizePolicy.setHeightForWidth(self.pushButton_10.sizePolicy().hasHeightForWidth())
        self.pushButton_10.setSizePolicy(sizePolicy)

        self.horizontalLayout_19.addWidget(self.pushButton_10)


        self.verticalLayout_20.addLayout(self.horizontalLayout_19)

        self.horizontalLayout_20 = QHBoxLayout()
        self.horizontalLayout_20.setObjectName(u"horizontalLayout_20")

        self.verticalLayout_20.addLayout(self.horizontalLayout_20)

        self.horizontalLayout_21 = QHBoxLayout()
        self.horizontalLayout_21.setObjectName(u"horizontalLayout_21")

        self.verticalLayout_20.addLayout(self.horizontalLayout_21)


        self.verticalLayout_7.addWidget(self.groupBox_7)

        self.groupBox_9 = QGroupBox(self.tab_response)
        self.groupBox_9.setObjectName(u"groupBox_9")
        self.verticalLayout_2 = QVBoxLayout(self.groupBox_9)
        self.verticalLayout_2.setObjectName(u"verticalLayout_2")
        self.triangular_checkbox = QCheckBox(self.groupBox_9)
        self.triangular_checkbox.setObjectName(u"triangular_checkbox")

        self.verticalLayout_2.addWidget(self.triangular_checkbox, 0, Qt.AlignHCenter)


        self.verticalLayout_7.addWidget(self.groupBox_9)

        self.verticalSpacer = QSpacerItem(20, 40, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding)

        self.verticalLayout_7.addItem(self.verticalSpacer)

        self.tabWidget.addTab(self.tab_response, "")
        self.tab_corrbpms = QWidget()
        self.tab_corrbpms.setObjectName(u"tab_corrbpms")
        self.horizontalLayout_6 = QVBoxLayout(self.tab_corrbpms)
        self.horizontalLayout_6.setObjectName(u"horizontalLayout_6")
        self.horizontalLayout_corrbpms_tables = QHBoxLayout()
        self.horizontalLayout_corrbpms_tables.setObjectName(u"horizontalLayout_corrbpms_tables")
        self.groupBox_5 = QGroupBox(self.tab_corrbpms)
        self.groupBox_5.setObjectName(u"groupBox_5")
        self.groupBox_5.setMaximumSize(QSize(16777215, 750))
        self.verticalLayout_14 = QVBoxLayout(self.groupBox_5)
        self.verticalLayout_14.setObjectName(u"verticalLayout_14")
        self.verticalLayout = QVBoxLayout()
        self.verticalLayout.setObjectName(u"verticalLayout")
        self.correctors_list = QListWidget(self.groupBox_5)
        self.correctors_list.setObjectName(u"correctors_list")
        self.correctors_list.setMaximumSize(QSize(16777215, 700))
        self.correctors_list.setSelectionMode(QAbstractItemView.ExtendedSelection)

        self.verticalLayout.addWidget(self.correctors_list)


        self.verticalLayout_14.addLayout(self.verticalLayout)

        self.load_correctors_button = QPushButton(self.groupBox_5)
        self.load_correctors_button.setObjectName(u"load_correctors_button")

        self.verticalLayout_14.addWidget(self.load_correctors_button)


        self.horizontalLayout_corrbpms_tables.addWidget(self.groupBox_5)

        self.groupBox_8 = QGroupBox(self.tab_corrbpms)
        self.groupBox_8.setObjectName(u"groupBox_8")
        self.groupBox_8.setMaximumSize(QSize(16777215, 750))
        self.verticalLayout_15 = QVBoxLayout(self.groupBox_8)
        self.verticalLayout_15.setObjectName(u"verticalLayout_15")
        self.verticalLayout_13 = QVBoxLayout()
        self.verticalLayout_13.setObjectName(u"verticalLayout_13")
        self.bpms_list = QListWidget(self.groupBox_8)
        self.bpms_list.setObjectName(u"bpms_list")
        self.bpms_list.setMaximumSize(QSize(16777215, 700))
        self.bpms_list.setSelectionMode(QAbstractItemView.ExtendedSelection)

        self.verticalLayout_13.addWidget(self.bpms_list)


        self.verticalLayout_15.addLayout(self.verticalLayout_13)

        self.load_bpms_button = QPushButton(self.groupBox_8)
        self.load_bpms_button.setObjectName(u"load_bpms_button")

        self.verticalLayout_15.addWidget(self.load_bpms_button)


        self.horizontalLayout_corrbpms_tables.addWidget(self.groupBox_8)


        self.horizontalLayout_6.addLayout(self.horizontalLayout_corrbpms_tables)

        self.groupBox_10 = QGroupBox(self.tab_corrbpms)
        self.groupBox_10.setObjectName(u"groupBox_10")
        sizePolicy1 = QSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        sizePolicy1.setHorizontalStretch(0)
        sizePolicy1.setVerticalStretch(0)
        sizePolicy1.setHeightForWidth(self.groupBox_10.sizePolicy().hasHeightForWidth())
        self.groupBox_10.setSizePolicy(sizePolicy1)
        self.verticalLayout_16 = QVBoxLayout(self.groupBox_10)
        self.verticalLayout_16.setObjectName(u"verticalLayout_16")
        self.horizontalLayout_modes = QHBoxLayout()
        self.horizontalLayout_modes.setObjectName(u"horizontalLayout_modes")
        self.mode_orbit = QRadioButton(self.groupBox_10)
        self.mode_orbit.setObjectName(u"mode_orbit")
        self.mode_orbit.setChecked(True)

        self.horizontalLayout_modes.addWidget(self.mode_orbit)

        self.mode_dispersion = QRadioButton(self.groupBox_10)
        self.mode_dispersion.setObjectName(u"mode_dispersion")

        self.horizontalLayout_modes.addWidget(self.mode_dispersion)

        self.mode_wakefield = QRadioButton(self.groupBox_10)
        self.mode_wakefield.setObjectName(u"mode_wakefield")
        sizePolicy2 = QSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Expanding)
        sizePolicy2.setHorizontalStretch(0)
        sizePolicy2.setVerticalStretch(0)
        sizePolicy2.setHeightForWidth(self.mode_wakefield.sizePolicy().hasHeightForWidth())
        self.mode_wakefield.setSizePolicy(sizePolicy2)

        self.horizontalLayout_modes.addWidget(self.mode_wakefield)


        self.verticalLayout_16.addLayout(self.horizontalLayout_modes)

        self.compute_response_matrix_button = QPushButton(self.groupBox_10)
        self.compute_response_matrix_button.setObjectName(u"compute_response_matrix_button")
        sizePolicy3 = QSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding)
        sizePolicy3.setHorizontalStretch(0)
        sizePolicy3.setVerticalStretch(0)
        sizePolicy3.setHeightForWidth(self.compute_response_matrix_button.sizePolicy().hasHeightForWidth())
        self.compute_response_matrix_button.setSizePolicy(sizePolicy3)
        self.compute_response_matrix_button.setMaximumSize(QSize(2000, 16777215))

        self.verticalLayout_16.addWidget(self.compute_response_matrix_button)


        self.horizontalLayout_6.addWidget(self.groupBox_10)

        self.tabWidget.addTab(self.tab_corrbpms, "")
        self.tab_correction = QWidget()
        self.tab_correction.setObjectName(u"tab_correction")
        self.verticalLayout_6 = QVBoxLayout(self.tab_correction)
        self.verticalLayout_6.setObjectName(u"verticalLayout_6")
        self.groupBox = QGroupBox(self.tab_correction)
        self.groupBox.setObjectName(u"groupBox")
        self.verticalLayout_3 = QVBoxLayout(self.groupBox)
        self.verticalLayout_3.setObjectName(u"verticalLayout_3")
        self.horizontalLayout_3 = QHBoxLayout()
        self.horizontalLayout_3.setObjectName(u"horizontalLayout_3")
        self.label = QLabel(self.groupBox)
        self.label.setObjectName(u"label")

        self.horizontalLayout_3.addWidget(self.label)

        self.lineEdit = QLineEdit(self.groupBox)
        self.lineEdit.setObjectName(u"lineEdit")
        self.lineEdit.setMaximumSize(QSize(410, 16777215))
        self.lineEdit.setToolTipDuration(5)

        self.horizontalLayout_3.addWidget(self.lineEdit)


        self.verticalLayout_3.addLayout(self.horizontalLayout_3)

        self.horizontalLayout_4 = QHBoxLayout()
        self.horizontalLayout_4.setObjectName(u"horizontalLayout_4")
        self.label_2 = QLabel(self.groupBox)
        self.label_2.setObjectName(u"label_2")

        self.horizontalLayout_4.addWidget(self.label_2)

        self.lineEdit_2 = QLineEdit(self.groupBox)
        self.lineEdit_2.setObjectName(u"lineEdit_2")
        self.lineEdit_2.setMaximumSize(QSize(410, 16777215))

        self.horizontalLayout_4.addWidget(self.lineEdit_2)


        self.verticalLayout_3.addLayout(self.horizontalLayout_4)

        self.horizontalLayout_5 = QHBoxLayout()
        self.horizontalLayout_5.setObjectName(u"horizontalLayout_5")
        self.label_3 = QLabel(self.groupBox)
        self.label_3.setObjectName(u"label_3")

        self.horizontalLayout_5.addWidget(self.label_3)

        self.lineEdit_3 = QLineEdit(self.groupBox)
        self.lineEdit_3.setObjectName(u"lineEdit_3")
        self.lineEdit_3.setMaximumSize(QSize(410, 16777215))

        self.horizontalLayout_5.addWidget(self.lineEdit_3)


        self.verticalLayout_3.addLayout(self.horizontalLayout_5)

        self.horizontalLayout_8 = QHBoxLayout()
        self.horizontalLayout_8.setObjectName(u"horizontalLayout_8")
        self.label_4 = QLabel(self.groupBox)
        self.label_4.setObjectName(u"label_4")

        self.horizontalLayout_8.addWidget(self.label_4)

        self.lineEdit_4 = QLineEdit(self.groupBox)
        self.lineEdit_4.setObjectName(u"lineEdit_4")
        self.lineEdit_4.setMaximumSize(QSize(410, 16777215))

        self.horizontalLayout_8.addWidget(self.lineEdit_4)


        self.verticalLayout_3.addLayout(self.horizontalLayout_8)

        self.horizontalLayout_10 = QHBoxLayout()
        self.horizontalLayout_10.setObjectName(u"horizontalLayout_10")
        self.label_5 = QLabel(self.groupBox)
        self.label_5.setObjectName(u"label_5")

        self.horizontalLayout_10.addWidget(self.label_5)

        self.lineEdit_5 = QLineEdit(self.groupBox)
        self.lineEdit_5.setObjectName(u"lineEdit_5")
        self.lineEdit_5.setMaximumSize(QSize(410, 16777215))

        self.horizontalLayout_10.addWidget(self.lineEdit_5)


        self.verticalLayout_3.addLayout(self.horizontalLayout_10)

        self.horizontalLayout_31 = QHBoxLayout()
        self.horizontalLayout_31.setObjectName(u"horizontalLayout_31")
        self.label_6 = QLabel(self.groupBox)
        self.label_6.setObjectName(u"label_6")

        self.horizontalLayout_31.addWidget(self.label_6)

        self.lineEdit_6 = QLineEdit(self.groupBox)
        self.lineEdit_6.setObjectName(u"lineEdit_6")
        self.lineEdit_6.setMaximumSize(QSize(410, 16777215))

        self.horizontalLayout_31.addWidget(self.lineEdit_6)


        self.verticalLayout_3.addLayout(self.horizontalLayout_31)

        self.horizontalLayout_beta = QHBoxLayout()
        self.horizontalLayout_beta.setObjectName(u"horizontalLayout_beta")
        self.label_beta = QLabel(self.groupBox)
        self.label_beta.setObjectName(u"label_beta")

        self.horizontalLayout_beta.addWidget(self.label_beta)

        self.lineEdit_beta = QLineEdit(self.groupBox)
        self.lineEdit_beta.setObjectName(u"lineEdit_beta")
        self.lineEdit_beta.setMaximumSize(QSize(410, 16777215))

        self.horizontalLayout_beta.addWidget(self.lineEdit_beta)


        self.verticalLayout_3.addLayout(self.horizontalLayout_beta)


        self.verticalLayout_6.addWidget(self.groupBox)

        self.buttons_layout_2 = QHBoxLayout()
        self.buttons_layout_2.setObjectName(u"buttons_layout_2")
        self.clear_graphs_button = QPushButton(self.tab_correction)
        self.clear_graphs_button.setObjectName(u"clear_graphs_button")
        sizePolicy.setHeightForWidth(self.clear_graphs_button.sizePolicy().hasHeightForWidth())
        self.clear_graphs_button.setSizePolicy(sizePolicy)

        self.buttons_layout_2.addWidget(self.clear_graphs_button)

        self.pushButton_log = QPushButton(self.tab_correction)
        self.pushButton_log.setObjectName(u"pushButton_log")

        self.buttons_layout_2.addWidget(self.pushButton_log)

        self.pushButton_testorb = QPushButton(self.tab_correction)
        self.pushButton_testorb.setObjectName(u"pushButton_testorb")

        self.buttons_layout_2.addWidget(self.pushButton_testorb)

        self.restore_initial_settings = QPushButton(self.tab_correction)
        self.restore_initial_settings.setObjectName(u"restore_initial_settings")

        self.buttons_layout_2.addWidget(self.restore_initial_settings)

        self.pushButton_reset_ref_orbit = QPushButton(self.tab_correction)
        self.pushButton_reset_ref_orbit.setObjectName(u"pushButton_reset_ref_orbit")
        self.pushButton_reset_ref_orbit.setStyleSheet(u"background-color: red; color: white;")

        self.buttons_layout_2.addWidget(self.pushButton_reset_ref_orbit)

        self.current_layout = QHBoxLayout()
        self.current_layout.setObjectName(u"current_layout")
        self.current_label = QLabel(self.tab_correction)
        self.current_label.setObjectName(u"current_label")

        self.current_layout.addWidget(self.current_label)

        self.current_spacer = QSpacerItem(40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        self.current_layout.addItem(self.current_spacer)

        self.horizontal_current_label = QLabel(self.tab_correction)
        self.horizontal_current_label.setObjectName(u"horizontal_current_label")

        self.current_layout.addWidget(self.horizontal_current_label)

        self.max_horizontal_current_spinbox = QDoubleSpinBox(self.tab_correction)
        self.max_horizontal_current_spinbox.setObjectName(u"max_horizontal_current_spinbox")
        self.max_horizontal_current_spinbox.setSingleStep(0.010000000000000)

        self.current_layout.addWidget(self.max_horizontal_current_spinbox)

        self.vertical_current_label = QLabel(self.tab_correction)
        self.vertical_current_label.setObjectName(u"vertical_current_label")

        self.current_layout.addWidget(self.vertical_current_label)

        self.max_vertical_current_spinbox = QDoubleSpinBox(self.tab_correction)
        self.max_vertical_current_spinbox.setObjectName(u"max_vertical_current_spinbox")
        self.max_vertical_current_spinbox.setSingleStep(0.010000000000000)

        self.current_layout.addWidget(self.max_vertical_current_spinbox)


        self.buttons_layout_2.addLayout(self.current_layout)


        self.verticalLayout_6.addLayout(self.buttons_layout_2)

        self.groupBox_2 = QGroupBox(self.tab_correction)
        self.groupBox_2.setObjectName(u"groupBox_2")
        self.verticalLayout_8 = QVBoxLayout(self.groupBox_2)
        self.verticalLayout_8.setObjectName(u"verticalLayout_8")
        self.plot_widget_3 = QWidget(self.groupBox_2)
        self.plot_widget_3.setObjectName(u"plot_widget_3")
        sizePolicy4 = QSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        sizePolicy4.setHorizontalStretch(0)
        sizePolicy4.setVerticalStretch(0)
        sizePolicy4.setHeightForWidth(self.plot_widget_3.sizePolicy().hasHeightForWidth())
        self.plot_widget_3.setSizePolicy(sizePolicy4)
        self.plot_widget_3.setMinimumSize(QSize(300, 100))

        self.verticalLayout_8.addWidget(self.plot_widget_3)


        self.verticalLayout_6.addWidget(self.groupBox_2)

        self.groupBox_3 = QGroupBox(self.tab_correction)
        self.groupBox_3.setObjectName(u"groupBox_3")
        self.verticalLayout_4 = QVBoxLayout(self.groupBox_3)
        self.verticalLayout_4.setObjectName(u"verticalLayout_4")
        self.plot_widget_4 = QWidget(self.groupBox_3)
        self.plot_widget_4.setObjectName(u"plot_widget_4")
        sizePolicy4.setHeightForWidth(self.plot_widget_4.sizePolicy().hasHeightForWidth())
        self.plot_widget_4.setSizePolicy(sizePolicy4)
        self.plot_widget_4.setMinimumSize(QSize(300, 100))

        self.verticalLayout_4.addWidget(self.plot_widget_4)


        self.verticalLayout_6.addWidget(self.groupBox_3)

        self.groupBox_4 = QGroupBox(self.tab_correction)
        self.groupBox_4.setObjectName(u"groupBox_4")
        self.verticalLayout_5 = QVBoxLayout(self.groupBox_4)
        self.verticalLayout_5.setObjectName(u"verticalLayout_5")
        self.plot_widget_5 = QWidget(self.groupBox_4)
        self.plot_widget_5.setObjectName(u"plot_widget_5")
        sizePolicy4.setHeightForWidth(self.plot_widget_5.sizePolicy().hasHeightForWidth())
        self.plot_widget_5.setSizePolicy(sizePolicy4)
        self.plot_widget_5.setMinimumSize(QSize(300, 100))

        self.verticalLayout_5.addWidget(self.plot_widget_5)


        self.verticalLayout_6.addWidget(self.groupBox_4)

        self.buttons_layout = QHBoxLayout()
        self.buttons_layout.setObjectName(u"buttons_layout")
        self.start_button = QPushButton(self.tab_correction)
        self.start_button.setObjectName(u"start_button")
        self.start_button.setStyleSheet(u"background-color: red; color: white;")

        self.buttons_layout.addWidget(self.start_button)

        self.stop_button = QPushButton(self.tab_correction)
        self.stop_button.setObjectName(u"stop_button")
        self.stop_button.setStyleSheet(u"background-color: green; color: white;")

        self.buttons_layout.addWidget(self.stop_button)


        self.verticalLayout_6.addLayout(self.buttons_layout)

        self.tabWidget.addTab(self.tab_correction, "")

        self.horizontalLayout_2.addWidget(self.tabWidget)


        self.horizontalLayout.addLayout(self.horizontalLayout_2)

        MainWindow.setCentralWidget(self.centralwidget)

        self.retranslateUi(MainWindow)

        self.tabWidget.setCurrentIndex(0)


        QMetaObject.connectSlotsByName(MainWindow)
    # setupUi

    def retranslateUi(self, MainWindow):
        MainWindow.setWindowTitle(QCoreApplication.translate("MainWindow", u"CERN BBA", None))
        self.session_group_3.setTitle(QCoreApplication.translate("MainWindow", u"Restore desired session's settings", None))
        self.label_31.setText(QCoreApplication.translate("MainWindow", u"Database", None))
        self.pushButton_11.setText(QCoreApplication.translate("MainWindow", u"...", None))
        self.trajectory_group_3.setTitle(QCoreApplication.translate("MainWindow", u"Trajectory Correction", None))
        self.label_18.setText(QCoreApplication.translate("MainWindow", u"Response", None))
        self.pushButton_8.setText(QCoreApplication.translate("MainWindow", u"...", None))
        self.groupBox_6.setTitle(QCoreApplication.translate("MainWindow", u"Dispersion-Free Steering", None))
        self.label_19.setText(QCoreApplication.translate("MainWindow", u"Response", None))
        self.pushButton_9.setText(QCoreApplication.translate("MainWindow", u"...", None))
        self.groupBox_7.setTitle(QCoreApplication.translate("MainWindow", u"Wakefield-Free Steering", None))
        self.label_22.setText(QCoreApplication.translate("MainWindow", u"Response", None))
        self.pushButton_10.setText(QCoreApplication.translate("MainWindow", u"...", None))
        self.groupBox_9.setTitle(QCoreApplication.translate("MainWindow", u"Computation", None))
        self.triangular_checkbox.setText(QCoreApplication.translate("MainWindow", u"Force triangular matrix", None))
        self.tabWidget.setTabText(self.tabWidget.indexOf(self.tab_response), QCoreApplication.translate("MainWindow", u"Response Matrices", None))
        self.groupBox_5.setTitle(QCoreApplication.translate("MainWindow", u"Correctors", None))
        self.load_correctors_button.setText(QCoreApplication.translate("MainWindow", u"Load...", None))
        self.groupBox_8.setTitle(QCoreApplication.translate("MainWindow", u"BPMs (click twice to adjust weights)", None))
        self.load_bpms_button.setText(QCoreApplication.translate("MainWindow", u"Load...", None))
        self.groupBox_10.setTitle(QCoreApplication.translate("MainWindow", u"Compute Response Matrix", None))
        self.mode_orbit.setText(QCoreApplication.translate("MainWindow", u"Orbit", None))
        self.mode_dispersion.setText(QCoreApplication.translate("MainWindow", u"Dispersion", None))
        self.mode_wakefield.setText(QCoreApplication.translate("MainWindow", u"Wakefield", None))
        self.compute_response_matrix_button.setText(QCoreApplication.translate("MainWindow", u"Compute Response Matrix", None))
        self.tabWidget.setTabText(self.tabWidget.indexOf(self.tab_corrbpms), QCoreApplication.translate("MainWindow", u"Correctors && BPMs", None))
        self.groupBox.setTitle(QCoreApplication.translate("MainWindow", u"Settings", None))
        self.label.setText(QCoreApplication.translate("MainWindow", u"Orbit weight", None))
        self.label_2.setText(QCoreApplication.translate("MainWindow", u"Dispersion weight", None))
        self.label_3.setText(QCoreApplication.translate("MainWindow", u"Wakefield weight", None))
        self.label_4.setText(QCoreApplication.translate("MainWindow", u"PINV tolerance", None))
        self.label_5.setText(QCoreApplication.translate("MainWindow", u"Number of iterations", None))
        self.label_6.setText(QCoreApplication.translate("MainWindow", u"Gain", None))
        self.label_beta.setText(QCoreApplication.translate("MainWindow", u"Beta parameter", None))
        self.clear_graphs_button.setText(QCoreApplication.translate("MainWindow", u"Clear plots", None))
        self.pushButton_log.setText(QCoreApplication.translate("MainWindow", u"Log Console", None))
        self.pushButton_testorb.setText(QCoreApplication.translate("MainWindow", u"Display test orbits", None))
        self.restore_initial_settings.setText(QCoreApplication.translate("MainWindow", u"Restore initial settings", None))
        self.pushButton_reset_ref_orbit.setText(QCoreApplication.translate("MainWindow", u"Reset reference orbit", None))
        self.current_label.setText(QCoreApplication.translate("MainWindow", u"Max strength (gauss*m)", None))
        self.horizontal_current_label.setText(QCoreApplication.translate("MainWindow", u"H:", None))
        self.vertical_current_label.setText(QCoreApplication.translate("MainWindow", u" V:", None))
        self.groupBox_2.setTitle(QCoreApplication.translate("MainWindow", u"Trajectory", None))
        self.groupBox_3.setTitle(QCoreApplication.translate("MainWindow", u"Dispersion", None))
        self.groupBox_4.setTitle(QCoreApplication.translate("MainWindow", u"Wakefield", None))
        self.start_button.setText(QCoreApplication.translate("MainWindow", u"START", None))
        self.stop_button.setText(QCoreApplication.translate("MainWindow", u"STOP", None))
        self.tabWidget.setTabText(self.tabWidget.indexOf(self.tab_correction), QCoreApplication.translate("MainWindow", u"Correction", None))
    # retranslateUi

