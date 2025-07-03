import sys
from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QPushButton, QLabel, QTextEdit, QHBoxLayout
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtGui import QFont, QIcon, QColor

from main import listen_for_hotword, record_audio, transcribe_audio, classify_intent, match_command, ask_llm, speak

class AuraWorker(QThread):
    update_text = pyqtSignal(str)
    hotword_detected = pyqtSignal()

    def run(self):
        listen_for_hotword()
        self.hotword_detected.emit()

        if record_audio():
            text = transcribe_audio()
            self.update_text.emit(f"USER: {text}")
            if text in ["exit", "quit", "stop", "close"]:
                self.update_text.emit("AURA: Goodbye! Have a wonderful day ahead.")
                speak("Goodbye! Have a wonderful day ahead.")
                return

            intent = classify_intent(text)
            if intent == "system_command":
                action = match_command(text)
                if action:
                    action()
                else:
                    response = "I couldn't find a matching system command."
                    speak(response)
                    self.update_text.emit("AURA: " + response)
            else:
                speak("Let me think about that for a moment...")
                self.update_text.emit("AURA: Let me think about that for a moment...")
                reply = ask_llm(text)
                speak(reply)
                self.update_text.emit("AURA: " + reply)

class AuraGUI(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("AURA Assistant")
        self.setGeometry(300, 100, 600, 500)
        self.setStyleSheet("background-color: #1e1e2f; color: white;")

        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout()

        self.title = QLabel("✨ AURA Assistant")
        self.title.setFont(QFont("Arial", 20))
        self.title.setAlignment(Qt.AlignCenter)

        self.conversation = QTextEdit()
        self.conversation.setReadOnly(True)
        self.conversation.setStyleSheet("background-color: #2b2b3d; color: white; font-size: 14px;")

        self.status = QLabel("Status: Waiting for Hotword...")
        self.status.setStyleSheet("color: lightgray;")

        button_layout = QHBoxLayout()
        self.mic_button = QPushButton("🎙️ Start Listening")
        self.mic_button.setStyleSheet("background-color: #3e8ef7; color: white; padding: 10px; border-radius: 10px;")
        self.mic_button.clicked.connect(self.activate_aura)

        button_layout.addWidget(self.mic_button)

        layout.addWidget(self.title)
        layout.addWidget(self.conversation)
        layout.addWidget(self.status)
        layout.addLayout(button_layout)

        self.setLayout(layout)

    def activate_aura(self):
        self.status.setText("Status: Listening for 'Hey Aura'...")
        self.worker = AuraWorker()
        self.worker.update_text.connect(self.append_conversation)
        self.worker.hotword_detected.connect(lambda: self.status.setText("Status: Hotword detected! Listening..."))
        self.worker.start()

    def append_conversation(self, text):
        self.conversation.append(text)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    aura = AuraGUI()
    aura.show()
    sys.exit(app.exec_())
