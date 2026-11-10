"""Threads de mise à jour et boutons de session (lot 3 de l'audit).

- Le thread d'installation ne QUITTE jamais sur échec : la vérification
  manuelle reste bloquée « déjà en cours » pour toujours, et réessayer
  écrase un QThread encore vivant (crash Qt).
- Chaque vérification qui trouve une version AJOUTE un bouton : deux
  vérifications, deux boutons « Nouvelle version ».
- `_une_analyse_faite` n'était jamais mis à vrai : « Recommencer » restait
  grisé à vie. Il vit de l'arrêt d'une analyse engagée à la vidéo suivante.

Les workers réseau sont remplacés par des fakes à signaux : le test observe
le CYCLE DE VIE du thread, pas le téléchargement.
"""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import time  # noqa: E402

import pytest  # noqa: E402

pytest.importorskip("PySide6")

from PySide6.QtCore import QObject, QThread, Signal  # noqa: E402
from PySide6.QtWidgets import QApplication, QMessageBox, QPushButton  # noqa: E402

import interface.app as module_app  # noqa: E402
from interface.app import FenetrePrincipale  # noqa: E402


@pytest.fixture
def application():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def fenetre(application):
    f = FenetrePrincipale()
    yield f
    f.close()


class FauxCapture:
    def get(self, prop):
        return 0.0

    def read(self):
        return False, None

    def set(self, prop, value):
        pass

    def release(self):
        pass


class FauxWorkerEchec(QObject):
    """Émet l'échec dès son démarrage : le chemin réseau n'est pas exercé."""

    progression = Signal(int, int)
    etape = Signal(str)
    echouee = Signal(str)
    prete = Signal(str)

    def __init__(self, info, dossier):
        super().__init__()

    def run(self):
        self.echouee.emit("panne simulée")

    def annuler(self):
        pass


class FauxWorkerMuet(QObject):
    """Ne fait rien : son thread reste vivant tant qu'on ne le quitte pas."""

    progression = Signal(int, int)
    etape = Signal(str)
    echouee = Signal(str)
    prete = Signal(str)

    def __init__(self, info, dossier):
        super().__init__()

    def run(self):
        pass

    def annuler(self):
        pass


class FauxVerification(QObject):
    fini = Signal(object)

    def __init__(self, version, dossier):
        super().__init__()

    def run(self):
        self.fini.emit(None)


INFO = {
    "version": "9.9.9",
    "sha256": "empreinte",
    "taille_zip": 1024 * 1024,
    "url_zip": "https://example.invalid/archive.zip",
    "url_page": "",
}


def pomper(condition, delai_s=2.0):
    debut = time.monotonic()
    while time.monotonic() - debut < delai_s:
        QApplication.processEvents()
        if condition():
            return True
        time.sleep(0.01)
    return False


@pytest.fixture
def installation_echouee(fenetre, monkeypatch, tmp_path):
    """Branche une installation qui échoue, sans réseau ni dialogue modal."""
    monkeypatch.setattr(
        module_app.mise_a_jour, "dossier_application", lambda: tmp_path
    )
    monkeypatch.setattr(
        module_app.QMessageBox, "question",
        lambda *a, **k: QMessageBox.StandardButton.Yes,
    )
    monkeypatch.setattr(module_app, "_InstallationMaj", FauxWorkerEchec)
    fenetre._installer_maj(INFO)
    return fenetre


def test_le_thread_d_installation_quitte_apres_un_echec(installation_echouee):
    f = installation_echouee
    assert pomper(lambda: not f._thread_maj.isRunning()), (
        "le thread d'installation reste vivant après l'échec"
    )


def test_verification_possible_apres_un_echec_installation(
    installation_echouee, monkeypatch
):
    """Le symptôme opérateur : « Une vérification est déjà en cours… » à vie."""
    f = installation_echouee
    pomper(lambda: not f._thread_maj.isRunning())
    monkeypatch.setattr(module_app, "_VerificationMaj", FauxVerification)
    assert f._verifier_mise_a_jour() is True
    pomper(lambda: not f._thread_maj.isRunning())


def test_installation_refusee_si_un_thread_tourne_deja(
    fenetre, monkeypatch, tmp_path
):
    """Réessayer ne doit pas écraser un QThread vivant : crash Qt garanti."""
    monkeypatch.setattr(
        module_app.mise_a_jour, "dossier_application", lambda: tmp_path
    )
    monkeypatch.setattr(
        module_app.QMessageBox, "question",
        lambda *a, **k: QMessageBox.StandardButton.Yes,
    )
    monkeypatch.setattr(module_app, "_InstallationMaj", FauxWorkerMuet)
    thread = QThread()
    thread.start()
    f = fenetre
    f._thread_maj = thread
    try:
        f._installer_maj(INFO)
        assert f._thread_maj is thread
    finally:
        thread.quit()
        thread.wait(2000)


def test_un_seul_bouton_maj_meme_apres_deux_verifications(fenetre):
    f = fenetre
    f._maj_trouvee(dict(INFO, version="3.2.0"))
    premier = f.btn_maj
    f._maj_trouvee(dict(INFO, version="3.3.0"))
    assert len(f.findChildren(QPushButton, "maj_disponible")) == 1
    assert f.btn_maj is premier
    assert "3.3.0" in f.btn_maj.text()


def test_recommencer_actif_apres_un_arret(fenetre):
    f = fenetre
    f.cap = FauxCapture()
    f.definir_ligne((300.0, 20.0), (300.0, 460.0))
    f._ouvrir_session()
    f.arreter()
    assert f._une_analyse_faite is True
    assert f.btn_recommencer.isEnabled()


def test_recommencer_repart_de_zero_avec_une_nouvelle_video(fenetre):
    f = fenetre
    f.cap = FauxCapture()
    f.definir_ligne((300.0, 20.0), (300.0, 460.0))
    f._ouvrir_session()
    f.arreter()
    f._reset_analyse()
    f._maj_boutons()
    assert f._une_analyse_faite is False
    assert not f.btn_recommencer.isEnabled()