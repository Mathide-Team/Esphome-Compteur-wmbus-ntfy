"""Tests de ``scripts/ci_assembler.py`` (issue #13, couverture à 95 %).

Le script lit ``secrets.ntfy.example.yaml``, ``ntfy.yaml`` et
``ntfy-voisin.yaml`` dans le dossier courant (racine du dépôt, comme en CI) :
chaque test s'y place. La configuration principale est une copie réduite,
fictive, de celle d'Esphome-Compteur-wmbus (même structure : secrets fusionnés
dans les substitutions, bloc ``packages:`` avec ``voisins/voisins.yaml``).
"""

from __future__ import annotations

import importlib.util
import runpy
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "ci_assembler.py"

_spec = importlib.util.spec_from_file_location("ci_assembler", SCRIPT)
ci_assembler = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ci_assembler)

CONFIG = """\
substitutions:
  <<: !include {fusion}
  num_compteur: !secret compteur0

esphome:
  name: compteur-eau

packages:
  voisins:
    url: https://exemple.invalid/voisins
    files: [voisins/voisins.yaml]
"""

SECRETS = """\
compteur0: "0x12345678"          # TON compteur
compteur1: "0x23456789"          # voisin 1
compteur3: 0x34567890
# compteur4: "0x45678901"        # voisin désactivé (commenté)
compteur10: "0x56789012"
nomcompteur1: "Voisin du dessus"
"""


@pytest.fixture
def source(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Dossier de configuration principale fictif ; dossier courant = racine du dépôt."""
    monkeypatch.chdir(ROOT)
    dossier = tmp_path / "compteur"
    (dossier / "voisins").mkdir(parents=True)
    (dossier / "voisins" / "voisins.yaml").write_text("# voisins\n", encoding="utf-8")
    (dossier / "options").mkdir()
    (dossier / "options" / "ecran.yaml").write_text("# option écran\n", encoding="utf-8")
    (dossier / "compteur-eau-lora.yaml").write_text(CONFIG.format(fusion="secrets.yaml"), encoding="utf-8")
    (dossier / "secrets.example.yaml").write_text(SECRETS, encoding="utf-8")
    return dossier


def _ntfy_sans_sujets_voisins() -> str:
    lignes = (ROOT / "secrets.ntfy.example.yaml").read_text(encoding="utf-8").splitlines(keepends=True)
    return "".join(ligne for ligne in lignes if not ligne.startswith("ntfy_topic_v"))


def test_assemblage_nominal(source: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """CI : dépôt principal sans secrets.yaml -> secrets.example.yaml fusionné, sujets par voisin."""
    sortie = tmp_path / "ci"
    ci_assembler.assembler(source, sortie)

    config = (sortie / "compteur-eau-lora.yaml").read_text(encoding="utf-8")
    assert "\npackages:\n  ntfy: !include ntfy.yaml\n  voisins:\n" in config
    assert config.count("ntfy: !include ntfy.yaml") == 1

    secrets = (sortie / "secrets.yaml").read_text(encoding="utf-8")
    assert secrets.startswith(SECRETS)
    # Sujets d'exemple des voisins remplacés par un sujet de test par voisin présent.
    assert 'ntfy_topic_v1: "eau-a81d' not in secrets
    sujets = [ligne for ligne in secrets.splitlines() if ligne.startswith("ntfy_topic_v")]
    assert sujets == [
        'ntfy_topic_v1: "eau-ci-v1"',
        'ntfy_topic_v3: "eau-ci-v3"',
        'ntfy_topic_v10: "eau-ci-v10"',
    ]
    assert "ntfy_topic_moi:" in secrets  # le reste du paquet ntfy est conservé
    assert secrets.endswith(_ntfy_sans_sujets_voisins() + "\n".join(sujets) + "\n")

    assert (sortie / "voisins" / "voisins.yaml").read_text(encoding="utf-8") == "# voisins\n"
    assert (sortie / "options" / "ecran.yaml").exists()
    assert (sortie / "ntfy.yaml").read_bytes() == (ROOT / "ntfy.yaml").read_bytes()
    assert (sortie / "ntfy-voisin.yaml").read_bytes() == (ROOT / "ntfy-voisin.yaml").read_bytes()
    assert capsys.readouterr().out == f"Configuration assemblée dans {sortie}/ : 3 voisin(s) avec sujet ntfy\n"


def test_secrets_reels_prioritaires(source: Path, tmp_path: Path) -> None:
    """Un secrets.yaml présent dans la configuration principale est utilisé tel quel."""
    (source / "secrets.yaml").write_text('compteur0: "0x11111111"\ncompteur2: "0x22222222"\n', encoding="utf-8")
    sortie = tmp_path / "ci"
    ci_assembler.assembler(source, sortie)
    secrets = (sortie / "secrets.yaml").read_text(encoding="utf-8")
    assert secrets.startswith('compteur0: "0x11111111"\ncompteur2: "0x22222222"\n')
    assert [ligne for ligne in secrets.splitlines() if ligne.startswith("ntfy_topic_v")] == [
        'ntfy_topic_v2: "eau-ci-v2"'
    ]


def test_sans_voisin(source: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """Aucun voisin (0 voisin en CI) : aucun sujet de voisin, assemblage valide."""
    (source / "secrets.example.yaml").write_text('compteur0: "0x12345678"\n', encoding="utf-8")
    sortie = tmp_path / "ci-0"
    ci_assembler.assembler(source, sortie)
    secrets = (sortie / "secrets.yaml").read_text(encoding="utf-8")
    assert not [ligne for ligne in secrets.splitlines() if ligne.startswith("ntfy_topic_v")]
    assert capsys.readouterr().out.endswith(": 0 voisin(s) avec sujet ntfy\n")


def test_fichier_de_configuration_choisi_et_fusion_dediee(source: Path, tmp_path: Path) -> None:
    """Fichier CI des voisins (ci_voisins.py) fusionnant un autre fichier de secrets.

    La sortie s'appelle toujours compteur-eau-lora.yaml ; le fichier fusionné
    garde son nom, et un secrets.yaml (pour les !secret) est écrit à partir de
    secrets.example.yaml + paquet ntfy.
    """
    (source / "ci-voisins-10.yaml").write_text(CONFIG.format(fusion="secrets-voisins-10.yaml"), encoding="utf-8")
    (source / "secrets-voisins-10.yaml").write_text(
        "".join(f'compteur{i}: "0x0000000{i}"\n' for i in range(1, 10)) + 'compteur10: "0x00000010"\n',
        encoding="utf-8",
    )
    sortie = tmp_path / "ci-10"
    ci_assembler.assembler(source, sortie, "ci-voisins-10.yaml")

    assert (sortie / "compteur-eau-lora.yaml").exists()
    assert not (sortie / "ci-voisins-10.yaml").exists()
    fusionne = (sortie / "secrets-voisins-10.yaml").read_text(encoding="utf-8")
    assert [ligne for ligne in fusionne.splitlines() if ligne.startswith("ntfy_topic_v")] == [
        f'ntfy_topic_v{i}: "eau-ci-v{i}"' for i in range(1, 11)
    ]
    secrets = (sortie / "secrets.yaml").read_text(encoding="utf-8")
    assert secrets == SECRETS + "\n" + _ntfy_sans_sujets_voisins()


def test_dossier_de_sortie_existant_complete(source: Path, tmp_path: Path) -> None:
    """Relancer l'assemblage sur un dossier déjà rempli le met à jour sans erreur."""
    sortie = tmp_path / "ci"
    ci_assembler.assembler(source, sortie)
    (source / "options" / "nouvelle.yaml").write_text("# nouvelle option\n", encoding="utf-8")
    ci_assembler.assembler(source, sortie)
    assert (sortie / "options" / "nouvelle.yaml").exists()
    config = (sortie / "compteur-eau-lora.yaml").read_text(encoding="utf-8")
    assert config.count("ntfy: !include ntfy.yaml") == 1


@pytest.mark.parametrize(
    ("ancienne", "retire"),
    [
        pytest.param("files: [voisins/voisins.yaml]", "files: []", id="sans-voisins"),
        pytest.param("  <<: !include secrets.yaml\n", "", id="sans-secrets-fusionnes"),
        pytest.param("\npackages:\n", "\npaquets:\n", id="sans-packages"),
    ],
)
def test_configuration_trop_ancienne(source: Path, tmp_path: Path, ancienne: str, retire: str) -> None:
    """Configuration sans voisins/voisins.yaml, secrets fusionnés ou packages : refus explicite."""
    fichier = source / "compteur-eau-lora.yaml"
    fichier.write_text(fichier.read_text(encoding="utf-8").replace(ancienne, retire), encoding="utf-8")
    sortie = tmp_path / "ci"
    with pytest.raises(SystemExit, match="compteur-eau-lora.yaml : configuration sans voisins/voisins.yaml"):
        ci_assembler.assembler(source, sortie)
    assert not (sortie / "compteur-eau-lora.yaml").exists()


def test_fichier_de_configuration_manquant(source: Path, tmp_path: Path) -> None:
    """Fichier de configuration absent : erreur qui nomme le fichier."""
    with pytest.raises(FileNotFoundError, match="absent.yaml"):
        ci_assembler.assembler(source, tmp_path / "ci", "absent.yaml")


def test_fichier_fusionne_manquant(source: Path, tmp_path: Path) -> None:
    """Fichier fusionné autre que secrets.yaml absent : pas de repli silencieux sur l'exemple."""
    fichier = source / "compteur-eau-lora.yaml"
    fichier.write_text(CONFIG.format(fusion="secrets-absent.yaml"), encoding="utf-8")
    with pytest.raises(FileNotFoundError, match="secrets-absent.yaml"):
        ci_assembler.assembler(source, tmp_path / "ci")


@pytest.mark.parametrize("arguments", [[], ["compteur"], ["a", "b", "c", "d"]])
def test_ligne_de_commande_arguments_invalides(monkeypatch: pytest.MonkeyPatch, arguments: list[str]) -> None:
    """Mauvais nombre d'arguments : l'usage est affiché (SystemExit avec la docstring)."""
    monkeypatch.setattr(sys, "argv", [str(SCRIPT), *arguments])
    with pytest.raises(SystemExit) as sortie:
        runpy.run_path(str(SCRIPT), run_name="__main__")
    assert str(sortie.value).startswith("Assemble, pour la CI,")
    assert "Usage : ci_assembler.py" in str(sortie.value)


@pytest.mark.parametrize("avec_fichier", [False, True])
def test_ligne_de_commande(
    source: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, avec_fichier: bool
) -> None:
    """Appel en ligne de commande, avec ou sans fichier de configuration explicite (comme en CI)."""
    sortie = tmp_path / "ci"
    arguments = [str(source), str(sortie)] + (["compteur-eau-lora.yaml"] if avec_fichier else [])
    monkeypatch.setattr(sys, "argv", [str(SCRIPT), *arguments])
    runpy.run_path(str(SCRIPT), run_name="__main__")
    assert (sortie / "compteur-eau-lora.yaml").exists()
    assert (sortie / "secrets.yaml").exists()
