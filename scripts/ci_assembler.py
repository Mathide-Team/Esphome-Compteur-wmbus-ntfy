#!/usr/bin/env python3
"""Assemble, pour la CI, la configuration du compteur et le paquet ntfy.

Usage : ci_assembler.py <dossier_config_principale> <dossier_sortie> [fichier_config]

- lit <fichier_config> (défaut : compteur-eau-lora.yaml) dans <dossier_config_principale> ;
- ajoute « ntfy: !include ntfy.yaml » au bloc « packages: » (rien d'autre : tout passe par
  secrets.yaml, fusionné dans les substitutions par « <<: !include <fichier> ») ;
- écrit le fichier de secrets fusionné, complété par secrets.ntfy.example.yaml et un sujet de
  test ntfy_topic_vN pour chaque voisin compteurN présent ;
- copie voisins/, options/, ntfy.yaml et ntfy-voisin.yaml ;
- écrit secrets.yaml = secrets.example.yaml + secrets.ntfy.example.yaml (pour les !secret).

Bibliothèque standard uniquement.
"""

from __future__ import annotations

import re
import shutil
import sys
from pathlib import Path

FUSION = re.compile(r"^  <<: !include (\S+)\s*$", re.M)
VOISIN = re.compile(r"^compteur([1-9]|10):\s*\"?([^\"\s#]+)", re.M)


def assembler(source: Path, sortie: Path, fichier: str = "compteur-eau-lora.yaml") -> None:
    """Écrit la configuration assemblée dans « sortie »."""
    sortie.mkdir(parents=True, exist_ok=True)
    config = (source / fichier).read_text(encoding="utf-8")
    fusion = FUSION.search(config)
    if "voisins/voisins.yaml" not in config or not fusion or "\npackages:\n" not in config:
        raise SystemExit(f"{fichier} : configuration sans voisins/voisins.yaml ni secrets fusionnés, trop ancienne pour ce paquet")
    config = config.replace("\npackages:\n", "\npackages:\n  ntfy: !include ntfy.yaml\n", 1)
    (sortie / "compteur-eau-lora.yaml").write_text(config, encoding="utf-8")

    ntfy = Path("secrets.ntfy.example.yaml").read_text(encoding="utf-8")
    ntfy = re.sub(r"^ntfy_topic_v\d+:.*\n", "", ntfy, flags=re.M)
    chemin = source / fusion.group(1)
    if not chemin.exists() and fusion.group(1) == "secrets.yaml":
        chemin = source / "secrets.example.yaml"   # CI : dépôt principal sans secrets.yaml
    fusionne = chemin.read_text(encoding="utf-8")
    voisins = sorted({int(n) for n, num in VOISIN.findall(fusionne)})
    sujets = "".join(f'ntfy_topic_v{i}: "eau-ci-v{i}"\n' for i in voisins)
    (sortie / fusion.group(1)).write_text(fusionne + "\n" + ntfy + sujets, encoding="utf-8")

    for dossier in ("voisins", "options"):
        shutil.copytree(source / dossier, sortie / dossier, dirs_exist_ok=True)
    shutil.copy("ntfy.yaml", sortie / "ntfy.yaml")
    shutil.copy("ntfy-voisin.yaml", sortie / "ntfy-voisin.yaml")
    if fusion.group(1) != "secrets.yaml":
        secrets = (source / "secrets.example.yaml").read_text(encoding="utf-8")
        (sortie / "secrets.yaml").write_text(secrets + "\n" + ntfy, encoding="utf-8")
    print(f"Configuration assemblée dans {sortie}/ : {len(voisins)} voisin(s) avec sujet ntfy")


if __name__ == "__main__":
    if len(sys.argv) not in (3, 4):
        raise SystemExit(__doc__)
    assembler(Path(sys.argv[1]), Path(sys.argv[2]), *(sys.argv[3:]))
