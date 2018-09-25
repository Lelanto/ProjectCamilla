from PyQt4 import QtCore, QtGui, QtWebKit
from selenium import webdriver
import sys

class Browser(QtGui.QMainWindow):

    def __init__(self, size=[800,600], frame=None, centralWidget=None, default_url='https://www.google.com', backButton=True, forwardButton=True, topBar=True):
        """
            Initialize the browser GUI and connect the events
        """

        self.showBackButton = backButton
        self.showForwardButton = forwardButton
        self.showTopBar = topBar

        QtGui.QMainWindow.__init__(self)
        self.resize(size[0],size[1])
        if (centralWidget == None):
            self.centralwidget = QtGui.QWidget(self)
        else:
            self.centralwidget = centralWidget

        self.mainLayout = QtGui.QHBoxLayout(self.centralwidget)
        self.mainLayout.setSpacing(0)
        self.mainLayout.setMargin(1)

        if (frame == None):
            self.frame = QtGui.QFrame(self.centralwidget)
        else:
            self.frame = frame

        self.gridLayout = QtGui.QVBoxLayout(self.frame)
        self.gridLayout.setMargin(0)
        self.gridLayout.setSpacing(0)

        self.horizontalLayout = QtGui.QHBoxLayout()
        if (self.showTopBar):
            self.tb_url = QtGui.QLineEdit(self.frame)
        if (self.showBackButton):
            self.bt_back = QtGui.QPushButton(self.frame)
        if (self.showForwardButton):
            self.bt_ahead = QtGui.QPushButton(self.frame)

        if (self.showBackButton):
            self.bt_back.setIcon(QtGui.QIcon().fromTheme("go-previous"))
        if (self.showForwardButton):
            self.bt_ahead.setIcon(QtGui.QIcon().fromTheme("go-next"))

        if (self.showBackButton):
            self.horizontalLayout.addWidget(self.bt_back)
        if (self.showForwardButton):
            self.horizontalLayout.addWidget(self.bt_ahead)
        if (self.showTopBar):
            self.horizontalLayout.addWidget(self.tb_url)
        self.gridLayout.addLayout(self.horizontalLayout)

        self.html = QtWebKit.Webdriver()
        self.gridLayout.addWidget(self.html)
        self.mainLayout.addWidget(self.frame)
        #self.setCentralWidget(self.centralwidget)  ---  Not needed when embedding into a frame

        if (self.showTopBar):
            self.connect(self.tb_url, QtCore.SIGNAL("returnPressed()"), self.browse)
        if (self.showBackButton):
            self.connect(self.bt_back, QtCore.SIGNAL("clicked()"), self.html.back)
        if (self.showForwardButton):
            self.connect(self.bt_ahead, QtCore.SIGNAL("clicked()"), self.html.forward)
        self.connect(self.html, QtCore.SIGNAL("urlChanged(const QUrl)"), self.url_changed)

        self.default_url = default_url
        if (self.showTopBar):
            self.tb_url.setText(self.default_url)
        self.open(self.default_url)

    def browse(self):
        """
            Make a web browse on a specific url and show the page on the
            Webview widget.
        """

        if (self.showTopBar):
            url = self.tb_url.text() if self.tb_url.text() else self.default_url
            self.html.load(QtCore.QUrl(url))
            self.html.show()
        else:
            pass

    def url_changed(self, url):
        """
            Triggered when the url is changed
        """
        if (self.showTopBar):
            self.tb_url.setText(url.toString())
        else:
            pass

    def open(self, url):
        self.html.load(QtCore.QUrl(url))
        self.html.show()

