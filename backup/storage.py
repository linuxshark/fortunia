"""Guardia de disco montado.

Si el disco externo está desconectado, el mount point queda vacío y los escritos
irían silenciosamente a la capa efímera del contenedor. Un archivo centinela
(creado en el setup, nunca por el servicio) prueba que el disco real está montado.
"""
from pathlib import Path


class DiskUnavailable(RuntimeError):
    pass


def disk_available(backup_dir: Path, sentinel_name: str) -> bool:
    return (Path(backup_dir) / sentinel_name).exists()


def require_disk(backup_dir: Path, sentinel_name: str) -> None:
    if not disk_available(backup_dir, sentinel_name):
        raise DiskUnavailable(
            f"Disco de backups no disponible: falta el centinela "
            f"'{sentinel_name}' en {backup_dir}. ¿Está montado el disco externo "
            f"y ejecutaste 'make backup-init'?"
        )
