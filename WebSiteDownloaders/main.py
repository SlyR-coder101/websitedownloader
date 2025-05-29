import os
import base64
import requests
import datetime
import subprocess
from urllib.parse import urljoin
from bs4 import BeautifulSoup
from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QLineEdit,
    QPushButton, QLabel, QProgressBar
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from playwright.sync_api import sync_playwright


class TelechargeurThread(QThread):
    progression = pyqtSignal(int)
    message = pyqtSignal(str)
    termine = pyqtSignal(str, str)  # Ajout du chemin dossier

    def __init__(self, url):
        super().__init__()
        self.url = url

    def run(self):
        try:
            self.message.emit("🌐 Chargement de la page...")
            with sync_playwright() as p:
                navigateur = p.chromium.launch(headless=True)
                page = navigateur.new_page()
                page.goto(self.url, wait_until="networkidle")
                html = page.content()
                base_url = page.url
                navigateur.close()

            self.message.emit("🧠 Intégration des ressources...")
            soup = BeautifulSoup(html, "html.parser")

            images = soup.find_all("img")
            total = len(images) + 1
            for i, img in enumerate(images):
                src = img.get("src")
                if src:
                    try:
                        lien = urljoin(base_url, src)
                        r = requests.get(lien, timeout=10)
                        if r.status_code == 200:
                            mime = r.headers.get("Content-Type", "image/png")
                            enc = base64.b64encode(r.content).decode("utf-8")
                            img["src"] = f"data:{mime};base64,{enc}"
                    except:
                        continue
                self.progression.emit(int((i / total) * 100))

            styles = soup.find_all("link", rel="stylesheet")
            for link in styles:
                href = link.get("href")
                if href:
                    try:
                        lien = urljoin(base_url, href)
                        r = requests.get(lien, timeout=10)
                        if r.status_code == 200:
                            style_tag = soup.new_tag("style")
                            style_tag.string = r.text
                            link.replace_with(style_tag)
                    except:
                        continue

            scripts = soup.find_all("script", src=True)
            for script in scripts:
                src = script["src"]
                try:
                    lien = urljoin(base_url, src)
                    r = requests.get(lien, timeout=10)
                    if r.status_code == 200:
                        script_tag = soup.new_tag("script")
                        script_tag.string = r.text
                        script.replace_with(script_tag)
                except:
                    continue

            self.progression.emit(100)

            horodatage = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            dossier = f"site_{horodatage}"
            os.makedirs(dossier, exist_ok=True)
            chemin = os.path.join(dossier, "page.html")

            with open(chemin, "w", encoding="utf-8") as f:
                f.write(str(soup))

            self.termine.emit(f"✅ Terminé : {chemin}", os.path.abspath(dossier))
        except Exception as e:
            self.termine.emit(f"❌ Erreur : {str(e)}", "")


class Interface(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Téléchargeur de Site Web")
        self.setMinimumWidth(500)

        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText("Entrez l'URL du site...")

        self.download_button = QPushButton("Télécharger le site")
        self.download_button.clicked.connect(self.demarrer_telechargement)

        self.progress = QProgressBar()
        self.progress.setValue(0)

        self.status_label = QLabel("")

        self.open_folder_button = QPushButton("📂 Ouvrir le dossier")
        self.open_folder_button.setEnabled(False)
        self.open_folder_button.clicked.connect(self.ouvrir_dossier)

        layout = QVBoxLayout()
        layout.addWidget(self.url_input)
        layout.addWidget(self.download_button)
        layout.addWidget(self.progress)
        layout.addWidget(self.status_label)
        layout.addWidget(self.open_folder_button)

        self.setLayout(layout)
        self.dossier_final = None

    def demarrer_telechargement(self):
        url = self.url_input.text().strip()
        if not url:
            self.status_label.setText("❗ Entrez une URL valide.")
            return

        self.progress.setValue(0)
        self.status_label.setText("📥 Téléchargement en cours...")
        self.open_folder_button.setEnabled(False)
        self.dossier_final = None

        self.thread = TelechargeurThread(url)
        self.thread.progression.connect(self.progress.setValue)
        self.thread.message.connect(self.status_label.setText)
        self.thread.termine.connect(self.terminer)
        self.thread.start()

    def terminer(self, message, dossier):
        self.status_label.setText(message)
        if dossier:
            self.dossier_final = dossier
            self.open_folder_button.setEnabled(True)

    def ouvrir_dossier(self):
        if self.dossier_final and os.path.exists(self.dossier_final):
            subprocess.Popen(f'explorer "{self.dossier_final}"')


if __name__ == "__main__":
    import sys
    app = QApplication(sys.argv)
    window = Interface()
    window.show()
    sys.exit(app.exec())
