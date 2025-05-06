from PyQt5.QtWidgets import QApplication, QDialog, QVBoxLayout, QPushButton, QLabel
from PyQt5.QtCore import Qt

def select_opening(openings):
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    
    dialog = QDialog()
    dialog.setWindowTitle('Select Opening')
    dialog.setFixedSize(400, 300)
    
    layout = QVBoxLayout()
    
    # Add a label
    label = QLabel("Select an opening:")
    layout.addWidget(label)
    
    # Create buttons for each opening
    opening_selected = [None]  # Use a list to store the selection
    
    def on_opening_selected(opening):
        opening_selected[0] = opening
        dialog.accept()

    for opening_name in openings:
        button = QPushButton(opening_name)
        button.clicked.connect(lambda checked, name=opening_name: on_opening_selected(name))
        layout.addWidget(button)
    
    dialog.setLayout(layout)
    dialog.exec_()

    return opening_selected[0]
