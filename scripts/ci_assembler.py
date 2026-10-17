#!/usr/bin/env python3
"""Assemble, pour la CI, la configuration du compteur et le paquet ntfy.

Usage : ci_assembler.py <dossier_config_principale> <dossier_sortie> [fichier_config]

- lit <fichier_config> (défaut : compteur-eau-lora.yaml) dans <dossier_config_principale> ;
- ajoute les substitutions ntfy_topic_moi et ntfy_token (lues depuis secrets.yaml) ;
- ajoute à « packages: » le paquet ntfy.yaml et une ligne ntfy-voisin.yaml par voisin déclaré
  (même « i » que sa ligne voisins/voisin.yaml, sujet de test) ;
- copie voisins/, ntfy.yaml et ntfy-voisin.yaml ;
- écrit secrets.yaml = secrets.example.yaml + secrets.ntfy.example.yaml.

Bibliothèque standard uniquement.
"""

from __future__ import annotations

import re
import shutil
import sys
from pathlib import Path

SUBSTITUTIONS = "  ntfy_topic_moi: !secret ntfy_topic_moi\n  ntfy_token: !secret ntfy_token\n"
LIGNE_VOISIN = re.compile(r"^\s+voisin(\d+):.*voisins/voisin\.yaml", re.M)


def assembler(source: Path, sortie: Path, fichier: str = "compteur-eau-lora.yaml") -> None:
    """Écrit la configuration assemblée dans « sortie »."""
    sortie.mkdir(parents=True, exist_ok=True)
    config = (source / fichier).read_text(encoding="utf-8")
    if "\nsubstitutions:\n" not in config:
        raise SystemExit(f"{fichier} : bloc substitutions introuvable")
    if "voisins/voisin.yaml" not in config and "\npackages: {}\n" not in config:
        raise SystemExit(f"{fichier} : configuration sans voisins/voisin.yaml, trop ancienne pour ce paquet")
    voisins = sorted({int(n) for n in LIGNE_VOISIN.findall(config)})
    paquets = "  ntfy: !include ntfy.yaml\n" + "".join(
        f'  ntfy_voisin{i}: !include {{ file: ntfy-voisin.yaml, vars: {{ i: {i}, nom: "Voisin {i}", topic: "eau-ci-v{i}" }} }}\n'
        for i in voisins
    )
    config = config.replace("\nsubstitutions:\n", "\nsubstitutions:\n" + SUBSTITUTIONS, 1)
    if "\npackages: {}\n" in config:
        config = config.replace("\npackages: {}\n", "\npackages:\n" + paquets, 1)
    else:
        config = config.replace("\npackages:\n", "\npackages:\n" + paquets, 1)
    (sortie / "compteur-eau-lora.yaml").write_text(config, encoding="utf-8")
    shutil.copytree(source / "voisins", sortie / "voisins", dirs_exist_ok=True)
    shutil.copy("ntfy.yaml", sortie / "ntfy.yaml")
    shutil.copy("ntfy-voisin.yaml", sortie / "ntfy-voisin.yaml")
    secrets = (source / "secrets.example.yaml").read_text(encoding="utf-8")
    secrets += "\n" + Path("secrets.ntfy.example.yaml").read_text(encoding="utf-8")
    (sortie / "secrets.yaml").write_text(secrets, encoding="utf-8")
    print(f"Configuration assemblée dans {sortie}/ : {len(voisins)} voisin(s)")


if __name__ == "__main__":
    if len(sys.argv) not in (3, 4):
        raise SystemExit(__doc__)
    assembler(Path(sys.argv[1]), Path(sys.argv[2]), *(sys.argv[3:]))
