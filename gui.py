import sys
from PyQt4.QtCore import *
from PyQt4.QtGui import *
from Browser import Browser
from bot import Bot
from config import options


class tabdemo(QTabWidget):
    def __init__(self, parent=None):
        super(tabdemo, self).__init__(parent)
        self.tabMain = QWidget()
        self.tabConfig = QWidget()
        self.tabInactive = QWidget()
        self.resize(1500,900)
        self.addTab(self.tabMain, "Tab 1")
        self.addTab(self.tabConfig, "Tab 2")
        self.addTab(self.tabInactive, "Tab 3")
        self.tabMainUI()
        self.tabConfigUI()
        self.tabInactiveUi()
        self.setWindowTitle("OgameBot")

    def tabConfigUI(self):
        import sqlite3
        db_filename = 'todo.db'
        with sqlite3.connect(db_filename) as conn:
            cursor = conn.cursor()
            cursor.execute("""select Server, Username, Password ,ChatIdTelegram, BotTelegram, LastUpdateId, PlayerId from UserConfiguration""")
            for row in cursor.fetchall():
                Server, Username, Password, ChatIdTelegram, BotTelegram, LastUpdateId, PlayerId = row
        layout = QFormLayout()
        layout.addRow("Server", QLineEdit(Server))
        layout.addRow("Username", QLineEdit(Username))
        layout.addRow("Password", QLineEdit(Password))
        layout.addRow("ChatIdTelegram", QLineEdit(ChatIdTelegram))
        layout.addRow("BotTelegram", QLineEdit(BotTelegram))
        layout.addRow("LastUpdateId", QLineEdit(LastUpdateId))
        layout.addRow("PlayerId", QLineEdit(PlayerId))

        self.setTabText(1, "Configurazioni")
        self.tabConfig.setLayout(layout)

    def tabInactiveUi(self):
            layout = QFormLayout()
            planets =QComboBox()
            planets.addItem("c")
            layout.addRow("Pianeta",planets)
            layout.addRow("Range", QLineEdit())
            button = QPushButton("Click me")
            layout.addRow(button)
            self.setTabText(2, "Trova Inattivi")
            self.tabInactive.setLayout(layout)
            self.tbl = QTableWidget(4, 3)
            header_labels = ['Coordinate', 'Name', 'Value']
            self.tbl.setHorizontalHeaderLabels(header_labels)
            layout.addWidget(self.tbl)

            buttonStart = QPushButton("AVVIA BOT")
            layout.addRow(buttonStart)
            credentials = options['credentials']
            self.bot = Bot(credentials['username'], credentials['password'], credentials['server'])
            buttonStart.clicked.connect(self.bot.start)

            button.clicked.connect(self.bot.searchInactive)

    def addItem(self):
        rowPosition=self.tbl.rowCount()
        self.tbl.insertRow(rowPosition)
        self.tbl.setItem(rowPosition, 0,QTableWidgetItem(coords))
        self.tbl.setItem(rowPosition, 1, QTableWidgetItem(name))
        self.tbl.setItem(rowPosition, 2, QTableWidgetItem(value))
    def tabMainUI(self):


        self.setTabText(0, "Main")



def main():
    app = QApplication(sys.argv)
    ex = tabdemo()
    ex.show()
    sys.exit(app.exec_())


if __name__ == '__main__':
    main()

