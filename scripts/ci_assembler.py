#!/usr/bin/env python3
"""Assemble, pour la CI, la configuration du compteur et le paquet ntfy.

Usage : ci_assembler.py <dossier_config_principale> <dossier_sortie>

- copie compteur-eau-lora.yaml et ntfy.yaml dans <dossier_sortie> ;
- ajoute les substitutions ntfy_topic_* et ntfy_token (lues depuis secrets.yaml) ;
- inclut le paquet (packages: ntfy: !include ntfy.yaml) ;
- écrit secrets.yaml = secrets.example.yaml + secrets.ntfy.example.yaml.

Bibliothèque standard uniquement.
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

SUBSTITUTIONS = "".join(
    f"  ntfy_topic_{n}: !secret ntfy_topic_{n}\n" for n in ("moi", "v1", "v2", "v3", "v4")
) + "  ntfy_token: !secret ntfy_token\n"


def assembler(source: Path, sortie: Path) -> None:
    """Écrit la configuration assemblée dans « sortie »."""
    sortie.mkdir(parents=True, exist_ok=True)
    config = (source / "compteur-eau-lora.yaml").read_text(encoding="utf-8")
    if "\nsubstitutions:\n" not in config or "\nesphome:\n" not in config:
        raise SystemExit("compteur-eau-lora.yaml : blocs substitutions/esphome introuvables")
    config = config.replace("\nsubstitutions:\n", "\nsubstitutions:\n" + SUBSTITUTIONS, 1)
    config = config.replace("\nesphome:\n", "\npackages:\n  ntfy: !include ntfy.yaml\n\nesphome:\n", 1)
    (sortie / "compteur-eau-lora.yaml").write_text(config, encoding="utf-8")
    shutil.copy("ntfy.yaml", sortie / "ntfy.yaml")
    secrets = (source / "secrets.example.yaml").read_text(encoding="utf-8")
    secrets += "\n" + Path("secrets.ntfy.example.yaml").read_text(encoding="utf-8")
    (sortie / "secrets.yaml").write_text(secrets, encoding="utf-8")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        raise SystemExit(__doc__)
    assembler(Path(sys.argv[1]), Path(sys.argv[2]))
    print(f"Configuration assemblée dans {sys.argv[2]}/")
