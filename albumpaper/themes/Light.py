{
"icon_color":"black",
"settings_window":'''
    QLineEdit {
        border: 1px solid black;
        width: 150;
        height: 20px;
        background: white;
        color: black;
        padding-left: 6px;
        padding-right: 6px;
    }
    QLabel {
        color: black;
    }
    QPushButton {
        border-style: outset;
        border-width: 2px;
        border-radius: 15px;
        border-color: black;
        color: black;
        padding: 4px;
    }
    QSpinBox {
        border: 1px solid black;
        width: 150;
        height: 20px;
        background: #6f6f76;
        color: black;
        padding-left: 6px;
    }
    QSpinBox:disabled {
        border: 1px solid lightgrey;
        color: lightgrey
    }
    QDoubleSpinBox {
        border: 1px solid black;
        width: 150;
        height: 20px;
        background: #6f6f76;
        color: black;
        padding-left: 6px;
    }
    QDoubleSpinBox:disabled {
        border: 1px solid lightgrey;
        color: lightgrey
    }
    QComboBox {
        border: 1px solid black;
        width: 150;
        height: 20px;
        background-color: white;
        color: black;
        padding-left: 6px;
    }
    QComboBox QAbstractItemView {
        border: 1px solid black;
        selection-background-color: #d4d4d4;
        color:black;
    }
    QWidget {
        background-color: white;
        font-size: 15px;
    }
    QMenu {
        color: black;
    }
    QMenu::item:selected {
        background-color: #d4d4d4;
    }
    ''',
"menu":'''
    QMenu {
        background-color:white;
        color: black;
    }
    QMenu::item:selected {
        background-color: #d4d4d4;
    }
    '''
}