#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from PyQt6.QtGui import QKeySequence, QIcon, QShortcut, QDrag, QFont
from PyQt6.QtCore import QDir, Qt, QUrl, QPoint, QTime, QProcess, QRect, QThread
from PyQt6.QtMultimedia import QMediaPlayer, QAudioOutput
from PyQt6.QtMultimediaWidgets import QVideoWidget
from PyQt6.QtWidgets import (QApplication, QFileDialog, QHBoxLayout, QLineEdit,
                            QPushButton, QSlider, QMessageBox, QStyle, QVBoxLayout,  
                            QWidget, QMenu, QPlainTextEdit, QTextEdit, QDialogButtonBox, QLabel, QApplication, QDialog, QMainWindow, QPushButton)
import sys
import subprocess
import pickle as pkl
import whisper
import os
from sortedcontainers import SortedDict
#QT_DEBUG_PLUGINS

class CustomDialog(QDialog):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("Finish practice")

        QBtn = QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel

        self.buttonBox = QDialogButtonBox(QBtn)
        self.buttonBox.accepted.connect(self.accept)
        self.buttonBox.rejected.connect(self.reject)

        self.layout = QVBoxLayout()
        message = QLabel("Are you sure to finish the practice?")
        self.layout.addWidget(message)
        self.layout.addWidget(self.buttonBox)
        self.setLayout(self.layout)

class VideoPlayer(QWidget):

    def __init__(self, aPath, parent=None):
        super(VideoPlayer, self).__init__(parent)

        self.setAttribute( Qt.WidgetAttribute.WA_NoSystemBackground, True )
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested[QPoint].connect(self.contextMenuRequested)
        self.setAcceptDrops(True)
        self.mediaPlayer = QMediaPlayer()
        self.mediaPlayer.mediaStatusChanged.connect(self.printMediaData)
        self.audioOutput = QAudioOutput()
        self.mediaPlayer.setAudioOutput(self.audioOutput)
        self.videoWidget = QVideoWidget(self)
        self.audioOutput.setVolume(0.8)
                
        self.lbl = QLineEdit('00:00:00')
        self.lbl.setReadOnly(True)
        self.lbl.setFixedWidth(70)
        self.lbl.setUpdatesEnabled(True)
        self.lbl.setStyleSheet(stylesheet(self))
        self.lbl.selectionChanged.connect(lambda: self.lbl.setSelection(0, 0))
        
        self.elbl = QLineEdit('00:00:00')
        self.elbl.setReadOnly(True)
        self.elbl.setFixedWidth(70)
        self.elbl.setUpdatesEnabled(True)
        self.elbl.setStyleSheet(stylesheet(self))
        self.elbl.selectionChanged.connect(lambda: self.elbl.setSelection(0, 0))

        self.playButton = QPushButton()
        self.playButton.setEnabled(False)
        self.playButton.setFixedWidth(32)
        self.playButton.setStyleSheet("background-color: black")
        
        self.playIcon = getattr(QStyle.StandardPixmap, "SP_MediaPlay")
        self.pauseIcon = getattr(QStyle.StandardPixmap, "SP_MediaPause")
        self.playButton.setIcon(self.style().standardIcon(self.playIcon))
        self.playButton.clicked.connect(self.play)

        self.positionSlider = QSlider(Qt.Orientation.Horizontal, self)
        self.positionSlider.setStyleSheet(stylesheet(self)) 
        self.positionSlider.setRange(0, 100)
        self.positionSlider.sliderMoved.connect(self.setPosition)
        self.positionSlider.setSingleStep(2)
        self.positionSlider.setPageStep(20)
        self.positionSlider.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        
        self.practice_mode = False
        self.caption_show = False
        
        self.caption = QLineEdit(self)
        self.caption.setReadOnly(True)
        self.caption.setTextMargins(10, 10, 10, 10)
        self.caption.setFont(QFont('BIZ UDMincho', 15))
        
        self.caption_input = QLineEdit(self)
        self.caption_input.setTextMargins(10, 10, 10, 10)
        self.caption_input.setFont(QFont('BIZ UDMincho', 15))
        
        self.caption_time = SortedDict()
        self.caption_text = None
        self.caption_answer = None
        self.caption_idx = -1


        self.clip = QApplication.clipboard()
        self.process = QProcess(self)
        self.process.readyRead.connect(self.dataReady)
        self.process.finished.connect(self.playFromURL)

        self.myurl = ""
        self.fullscreen = False
        self.rect = QRect()
        
        controlLayout = QHBoxLayout()
        controlLayout.setContentsMargins(5, 0, 5, 0)
        controlLayout.addWidget(self.playButton)
        controlLayout.addWidget(self.lbl)
        controlLayout.addWidget(self.positionSlider)
        controlLayout.addWidget(self.elbl)
        
        inputLayout = QVBoxLayout()
        inputLayout.setContentsMargins(5, 0, 5, 0)
        inputLayout.addWidget(self.caption_input)
        inputLayout.addWidget(self.caption)

        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 250)
        layout.addWidget(self.videoWidget)
        layout.addLayout(inputLayout)
        layout.addLayout(controlLayout)

        self.setLayout(layout)
        
        self.myinfo = "©2016\nAxel Schneider\n\nMouse Wheel = Zoom\nUP = Volume Up\nDOWN = Volume Down\n" + \
                "LEFT = < 1 Minute\nRIGHT = > 1 Minute\n" + \
                "SHIFT+LEFT = < 10 Minutes\nSHIFT+RIGHT = > 10 Minutes"

        self.widescreen = True
        
        self.shortcut = QShortcut(QKeySequence(Qt.Key.Key_Return), self.caption_input)
        self.shortcut.activated.connect(self.nextCaption)
        self.shortcut = QShortcut(QKeySequence(Qt.Key.Key_Down), self.caption_input)
        self.shortcut.activated.connect(lambda: self.nextCaption(True))
        self.shortcut = QShortcut(QKeySequence(Qt.Key.Key_Up), self.caption_input)
        self.shortcut.activated.connect(self.lastCaption)
        self.shortcut = QShortcut(QKeySequence(Qt.Key.Key_Enter), self.caption_input)
        self.shortcut.activated.connect(self.replay_caption)
        
        self.caption_input.textChanged.connect(self.text_input_change)
        
        self.whisper_model = None
        self.media_source = None

        self.mediaPlayer.setVideoOutput(self.videoWidget)
        self.mediaPlayer.playbackStateChanged.connect(self.mediaStateChanged)
        self.mediaPlayer.positionChanged.connect(self.positionChanged)
        self.mediaPlayer.durationChanged.connect(self.durationChanged)
        self.mediaPlayer.errorChanged.connect(self.handleError)

        print("QT5 Player started")
        print("press 'o' to open file (see context menu for more)")
        self.suspend_screensaver()

        
    def mouseDoubleClickEvent(self, event):
        self.handleFullscreen()

    def playFromURL(self):
        self.mediaPlayer.pause()
        self.myurl = self.clip.text()
        self.mediaPlayer.setSource(QUrl(self.myurl))
        self.playButton.setEnabled(True)
        self.mediaPlayer.play()
        self.hideSlider()
        print(self.myurl)

    def getYTUrl(self):
        cmd = f"youtube-dl -g -f worst {self.clip.text()}"
        print(f"grabbing YouTube URL\n{cmd}")
        #self.process.start(cmd)
        self.myurl = subprocess.check_output(cmd, shell=True).decode()
        self.myurl = self.myurl.partition("\n")[0]
        print(self.myurl)
        self.clip.setText(self.myurl)
        self.playFromURL()

    def dataReady(self):
        self.myurl = str(self.process.readAll(), encoding = 'utf8').rstrip() ###
        self.myurl = self.myurl.partition("\n")[0]
        print(self.myurl)
        self.clip.setText(self.myurl)
        self.playFromURL()

    def suspend_screensaver(self):
        'suspend linux screensaver'
        proc = subprocess.Popen('gsettings set org.gnome.desktop.screensaver idle-activation-enabled false', shell=True)
        proc.wait()

    def resume_screensaver(self):
        'resume linux screensaver'
        proc = subprocess.Popen('gsettings set org.gnome.desktop.screensaver idle-activation-enabled true', shell=True)
        proc.wait()

    def openFile(self):
        fileName, _ = QFileDialog.getOpenFileName(self, "Open Movie",
                QDir.homePath() + "/Videos", "Media (*.webm *.mp4 *.ts *.avi *.mpeg *.mpg *.mkv *.VOB *.m4v *.3gp *.mp3 *.m4a *.wav *.ogg *.flac *.m3u *.m3u8)")
        path, _ = os.path.splitext(fileName)
        
        if fileName != '':
            self.loadFilm(fileName)
            if os.path.exists(path + ".caption"):
                self.openCaption(path + ".caption")
            print("File loaded")
            
    def openCaption(self, fileName = None):
        if fileName is None:
            fileName, _ = QFileDialog.getOpenFileName(self, "Open Caption",
                QDir.homePath() + "/Videos", "caption (*.caption)")

        if fileName != '':
            self.caption_time.clear()
            self.caption_text = pkl.load(open(fileName, "rb"))
            self.caption_answer = [""] * len(self.caption_text)
            self.caption_idx = 0
            self.setPosition(0)
            if self.caption_text is not None and len(self.caption_text) > 0:
                if "language" in self.caption_text[0]:
                    if self.caption_text[0]["language"] == "ja":
                        self.caption.setFont(QFont('BIZ UDMincho', 15))
                        self.caption_input.setFont(QFont('BIZ UDMincho', 15))
                    elif self.caption_text[0]["language"] == "en":
                        self.caption.setFont(QFont('times new roman', 16))
                        self.caption_input.setFont(QFont('times new roman', 16))
                for seg in self.caption_text:
                    start_time = int(seg["start"] * 1000)
                    end_time = int(seg["end"] * 1000)
                    self.caption_time[start_time] = end_time

            print(f"Caption loaded: {fileName}")
        else:
            self.caption_time.clear()
            self.caption_text = None
            self.caption_answer = None
            self.caption_idx = -1
            print("Caption unloaded")
        

    def play(self):
        if self.mediaPlayer.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self.mediaPlayer.pause()
        else:
            self.mediaPlayer.play()
    
    def mediaStateChanged(self, state):
        if self.mediaPlayer.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self.playButton.setIcon(self.style().standardIcon(self.playIcon))
        else:
            self.playButton.setIcon(self.style().standardIcon(self.pauseIcon))

    def text_input_change(self, text):
        if self.caption_text is not None:
            self.caption_answer[self.caption_idx] = self.caption_input.text()

    def positionChanged(self, position):
        def find_time_interval(container:SortedDict, time_intervals):
            pos = container.bisect_left(time_intervals)
            
            if pos != len(container):
                elements = container.peekitem(pos)
                if elements[0] <= time_intervals and time_intervals <= elements[1]:
                    return pos
            if pos != 0:
                elements = container.peekitem(pos - 1)
                if elements[0] <= time_intervals and time_intervals <= elements[1]:
                    return pos
            return None
        self.positionSlider.setValue(position)

        mtime = QTime(0,0,0,0)
        mtime = mtime.addMSecs(self.mediaPlayer.position())
        self.lbl.setText(mtime.toString())
        self.caption.setText("")
        if self.caption_text is not None:
            seg = self.caption_text[self.caption_idx]
            if self.practice_mode:
                end_time = seg["end"] * 1000
                if end_time < position:
                    self.mediaPlayer.pause()
                
            if self.caption_show:
                if self.practice_mode:
                    self.caption.setText(seg["text"])
                else:
                    res = find_time_interval(self.caption_time, position)
                    if res is not None:
                        self.caption.setText(self.caption_text[res - 1]["text"])
            
    def replay_caption(self):
        if self.caption_text is not None:
            start_time = int(self.caption_text[self.caption_idx]["start"] * 1000)
            start_time = 0 if start_time < 0 else start_time
            self.setPosition(start_time)
            self.mediaPlayer.play()
            
            
    def lastCaption(self):
        if self.caption_text is not None:
            if self.caption_idx > 0:
                self.caption_idx = self.caption_idx - 1
            self.caption_input.setText(self.caption_answer[self.caption_idx])
            self.replay_caption()
                
            
    def nextCaption(self, next_flag = False):
        if self.caption_text is not None:
            if not next_flag and not self.caption_input.text():
                self.caption_input.setText(self.caption_answer[self.caption_idx])
                self.replay_caption()

            elif self.caption_idx < len(self.caption_text) - 1:
                self.caption_idx = self.caption_idx + 1
                self.caption_input.setText(self.caption_answer[self.caption_idx])
                self.replay_caption()
                
            else:
                dlg = CustomDialog()
                self.mediaPlayer.pause()
                if dlg.exec():
                    self.result_publish()
                    print("Success!")
                    self.handleQuit()
                else:
                    print("Cancel!")
                    
    def switch_practice_mode(self):
        self.practice_mode = not self.practice_mode
        if not self.practice_mode:
            self.caption_input.setEnabled(False)
            self.caption.setText("")
        else:
            self.caption_input.setEnabled(True)
            self.caption.setText("")
            
    def videoTranscript(self):
        if self.media_source is None:
            return
        
        self.mediaPlayer.pause()
        msgBox = QMessageBox(self)
        # msgBox.setWindowFlags(Qt.WindowType.CustomizeWindowHint | Qt.WindowType.WindowTitleHint)     
        msgBox.setText("Please wait...")
        
        wps = whisper_process_thread(self)
        wps.finished.connect(msgBox.close)
        wps.start()
        
        msgBox.show()
            
       
            
    def show_caption(self):
        self.caption_show = not self.caption_show
        if not self.caption_show:
            self.caption.setText("")

            
    def result_publish(self):
        result_log = ""
        for idx, (text, ans) in enumerate(zip(self.caption_text, self.caption_answer)):
            text = text["text"]
            result_log += f"idx:{idx}\n"
            result_log += f"text:{text}\n"
            result_log += f"your answer:{ans}\n"
            result_log += "\n"
            
        
        from datetime import datetime
        now = datetime.now()
        date_time = now.strftime("%Y-%m-%d-%H-%M-%S")
        
        with open(f"./{str(date_time)}.txt", "w+") as input_str:
            input_str.write(result_log)
            
        print(result_log)
        
        
    def durationChanged(self, duration):
        self.positionSlider.setRange(0, duration)
        mtime = QTime(0,0,0,0)
        mtime = mtime.addMSecs(self.mediaPlayer.duration())
        self.elbl.setText(mtime.toString())

    def setPosition(self, position):
        self.mediaPlayer.setPosition(position)

    def handleError(self):
        print("handleError")
        self.playButton.setEnabled(False)
        print("Error: ", self.mediaPlayer.errorString())
        self.errorbox(self.mediaPlayer.errorString())

    def errorbox(self, message):
        msg = QMessageBox(2, "Error", message, QMessageBox.StandardButtons.Ok)
        msg.exec()

    def handleQuit(self):
        self.mediaPlayer.stop()
        self.resume_screensaver()
        print("Goodbye ...")
        app.quit()
    
    def contextMenuRequested(self,point):
        menu = QMenu()
        actionFile = menu.addAction(QIcon.fromTheme("video-x-generic"),"open File (o)")
        actionCaption = menu.addAction(QIcon.fromTheme("video-x-generic"),"open Caption (null)")
        actionTranscript = menu.addAction(QIcon.fromTheme("video-x-generic"),"transcript Video (null)")
        actionclipboard = menu.addSeparator() 
        actionPractice = menu.addAction(QIcon.fromTheme("video-x-generic"),"pratice Mode (null)")
        actionShowCaption = menu.addAction(QIcon.fromTheme("video-x-generic"),"show caption (null)")
        actionURL = menu.addAction(QIcon.fromTheme("browser"),"URL from Clipboard (u)")
        actionclipboard = menu.addSeparator() 
        actionYTurl = menu.addAction(QIcon.fromTheme("youtube"), "URL from YouTube (y)")
        actionclipboard = menu.addSeparator() 
        actionToggle = menu.addAction(QIcon.fromTheme("next"),"show / hide Slider (s)") 
        actionFull = menu.addAction(QIcon.fromTheme("view-fullscreen"),"Fullscreen (f)")
        action169 = menu.addAction(QIcon.fromTheme("tv-symbolic"),"16 : 9")
        action43 = menu.addAction(QIcon.fromTheme("tv-symbolic"),"4 : 3")
        actionSep = menu.addSeparator()
        actionInfo = menu.addAction(QIcon.fromTheme("help-about"),"Info (i)")
        action5 = menu.addSeparator() 
        actionQuit = menu.addAction(QIcon.fromTheme("application-exit"),"Exit (q)")
        
        
        actionFile.triggered.connect(self.openFile)
        actionCaption.triggered.connect(lambda: self.openCaption())
        actionTranscript.triggered.connect(self.videoTranscript)
        actionPractice.triggered.connect(self.switch_practice_mode)
        actionShowCaption.triggered.connect(self.show_caption)
        actionQuit.triggered.connect(self.handleQuit)
        actionFull.triggered.connect(self.handleFullscreen)
        actionInfo.triggered.connect(self.handleInfo)
        actionToggle.triggered.connect(self.toggleSlider)
        actionURL.triggered.connect(self.playFromURL)
        actionYTurl.triggered.connect(self.getYTUrl)
        action169.triggered.connect(self.screen169)
        action43.triggered.connect(self.screen43)
        menu.exec(self.mapToGlobal(point))

    def wheelEvent(self,event):
        mwidth = self.frameGeometry().width()
        mleft = self.frameGeometry().left()
        mtop = self.frameGeometry().top()
        mscale = round(event.angleDelta().y() / 5)
        if self.widescreen == True:
            self.setGeometry(mleft, mtop, mwidth + mscale, round((mwidth + mscale) / 1.778)) 
        else:
            self.setGeometry(mleft, mtop, mwidth + mscale, round((mwidth + mscale) / 1.33))

    def screen169(self):
        self.widescreen = True
        mwidth = self.frameGeometry().width()
        mleft = self.frameGeometry().left()
        mtop = self.frameGeometry().top()
        mratio = 1.778
        self.setGeometry(mleft, mtop, mwidth, round(mwidth / mratio))

    def screen43(self):
        self.widescreen = False
        mwidth = self.frameGeometry().width()
        mleft = self.frameGeometry().left()
        mtop = self.frameGeometry().top()
        mratio = 1.33
        self.setGeometry(mleft, mtop, mwidth, round(mwidth / mratio))

    def handleFullscreen(self):
        if self.fullscreen == True:
            self.showNormal()
            self.setGeometry(self.rect)
            QApplication.setOverrideCursor(Qt.CursorShape.BlankCursor)
            self.fullscreen = False
            print("Fullscreen aus")
        else:
            self.rect = self.geometry()
            self.showFullScreen()
            QApplication.setOverrideCursor(Qt.CursorShape.ArrowCursor)
            self.fullscreen = True
            print("Fullscreen an")
        self.handleCursor()

    def handleCursor(self):
        if  QApplication.overrideCursor() ==  Qt.CursorShape.ArrowCursor:
            QApplication.setOverrideCursor(Qt.CursorShape.BlankCursor)
        else:
            QApplication.setOverrideCursor(Qt.CursorShape.ArrowCursor)

    def handleInfo(self):
        msg = QMessageBox.about(self, "QT6 Player based on OpenAI Whisper", self.myinfo)
            
    def toggleSlider(self):    
        if self.positionSlider.isVisible():
            self.hideSlider()
        else:
            self.showSlider()
    
    def hideSlider(self):
            self.playButton.hide()
            self.lbl.hide()
            self.positionSlider.hide()
            self.elbl.hide()
            mwidth = self.frameGeometry().width()
            mleft = self.frameGeometry().left()
            mtop = self.frameGeometry().top()
            if self.widescreen == True:
                self.setGeometry(mleft, mtop, mwidth, round(mwidth / 1.778))
            else:
                self.setGeometry(mleft, mtop, mwidth, round(mwidth / 1.33))
    
    def showSlider(self):
            self.playButton.show()
            self.lbl.show()
            self.positionSlider.show()
            self.elbl.show()
            mwidth = self.frameGeometry().width()
            mleft = self.frameGeometry().left()
            mtop = self.frameGeometry().top()
            if self.widescreen == True:
                self.setGeometry(mleft, mtop, mwidth, round(mwidth / 1.55))
            else:
                self.setGeometry(mleft, mtop, mwidth, round(mwidth / 1.33))
    
    def forwardSlider(self):
        self.mediaPlayer.setPosition(self.mediaPlayer.position() + 1000*60)

    def forwardSlider10(self):
        self.mediaPlayer.setPosition(self.mediaPlayer.position() + 10000*60)

    def backSlider(self):
        self.mediaPlayer.setPosition(self.mediaPlayer.position() - 1000*60)

    def backSlider10(self):
        self.mediaPlayer.setPosition(self.mediaPlayer.position() - 10000*60)
        
    def volumeUp(self):
        self.audioOutput.setVolume(self.audioOutput.volume() + 0.05)
        print(f"Volume: {self.audioOutput.volume():.2f}")
    
    def volumeDown(self):
        self.audioOutput.setVolume(self.audioOutput.volume() - 0.05)
        print(f"Volume: {self.audioOutput.volume():.2f}")
    
    def mousePressEvent(self, evt):
        self.oldPos = evt.position()

    def mouseMoveEvent(self, evt):
        delta = evt.position() - self.oldPos
        self.move(round(self.x() + delta.x()), round(self.y() + delta.y()))
        self.oldPos = evt.position()
        
    def dragEnterEvent(self, event):
        print("drag", event.mimeData())
        if event.mimeData().hasUrls():
            event.accept()
        elif event.mimeData().hasText():
            event.accept()
        else:
            event.ignore()

    def dropEvent(self, event):
        print("drop")        
        if event.mimeData().hasUrls():
            url = event.mimeData().urls()[0].toString().rstrip()
            print("url = ", url)
            self.mediaPlayer.stop()
            self.mediaPlayer.setSource(QUrl(url))
            self.playButton.setEnabled(True)
            self.mediaPlayer.play()
        elif event.mimeData().hasText():
            mydrop =  event.mimeData().text().rstrip()
            ### YouTube url
            if "youtube" in mydrop:
                print("is YouTube", mydrop)
                self.clip.setText(mydrop)
                self.getYTUrl()
            else:
                ### normal url
                print("generic url = ", mydrop)
                self.mediaPlayer.setSource(QUrl(mydrop))
                self.playButton.setEnabled(True)
                self.mediaPlayer.play()
                self.hideSlider()
    
    def loadFilm(self, f):
        self.media_source = f
        self.mediaPlayer.setSource(QUrl.fromLocalFile(f))
        self.playButton.setEnabled(True)
        self.mediaPlayer.play()



    def printMediaData(self):
        if self.mediaPlayer.mediaStatus() == 6:
            if self.mediaPlayer.isMetaDataAvailable():
                res = str(self.mediaPlayer.metaData("Resolution")).partition("PyQt6.QtCore.QSize(")[2].replace(", ", "x").replace(")", "")
                print("%s%s" % ("Video Resolution = ",res))
                if res:
                    v = round(int(res.partition("x")[0]) / int(res.partition("x")[2]))
                    if v < 1.5:
                        self.screen43()
                    else:
                        self.screen169()
            else:
                print("no metaData available")
      
    def openFileAtStart(self, filelist):
            matching = [s for s in filelist if ".myformat" in s]
            if len(matching) > 0:
                self.loadFilm(matching)

class whisper_process_thread(QThread):
    def __init__(self, context:VideoPlayer):
        super().__init__()
        self.context = context

    def run(self):
        if self.context.whisper_model is None:
            self.context.whisper_model = whisper.load_model("medium").cuda()
        result = self.context.whisper_model.transcribe(self.context.media_source, verbose=True)
        output_text_pkl = []
        for seg in result["segments"]:
            output_text_pkl.append({
                "id": seg["id"], 
                "start": seg["start"], 
                "end": seg["end"], 
                "text": seg["text"], 
                "language": result["language"]
            })
        save_path, _ = os.path.splitext(self.context.media_source)
        pkl.dump(output_text_pkl, open(save_path + ".caption", "wb+"))
        self.context.openCaption(save_path + ".caption")

##################### end ##################################

def stylesheet(self):
    return """

QSlider::handle:horizontal 
{
background: transparent;
width: 8px;
}

QSlider::groove:horizontal {
border: 1px solid #444444;
height: 8px;
     background: qlineargradient(y1: 0, y2: 1,
                                 stop: 0 #2e3436, stop: 1.0 #000000);
}

QSlider::sub-page:horizontal {
background: qlineargradient( y1: 0, y2: 1,
    stop: 0 #729fcf, stop: 1 #2a82da);
border: 1px solid #777;
height: 8px;
}

QSlider::handle:horizontal:hover {
background: #2a82da;
height: 8px;
width: 18px;
border: 1px solid #2e3436;
}

QSlider::sub-page:horizontal:disabled {
background: #bbbbbb;
border-color: #999999;
}

QSlider::add-page:horizontal:disabled {
background: #2a82da;
border-color: #999999;
}

QSlider::handle:horizontal:disabled {
background: #2a82da;
}

QLineEdit
{
background: black;
color: #585858;
border: 0px solid #076100;
font-size: 8pt;
font-weight: bold;
}
    """


if __name__ == '__main__':
    app = QApplication(sys.argv)
    player = VideoPlayer('')
    #player.setAcceptDrops(True)
    player.setWindowTitle("QT5 Player")
    player.setWindowIcon(QIcon.fromTheme("multimedia-video-player"))
    # player.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint)
    player.setGeometry(100, 300, 600, 380)
    #player.rect = player.geometry()

    player.hideSlider()
    player.show()
    player.widescreen = True
    if len(sys.argv) > 1:
        print(sys.argv[1])
        if sys.argv[1].startswith("http"):
            player.myurl = sys.argv[1]
            player.playFromURL()
        else:
            player.loadFilm(sys.argv[1])
            player.toggleSlider()
sys.exit(app.exec())
