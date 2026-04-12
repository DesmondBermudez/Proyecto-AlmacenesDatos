from __future__ import annotations


def formatear_duracion(segundos: float) -> str:
    if segundos < 60:
        return f"{segundos:.2f}s"

    minutos, seg = divmod(segundos, 60)
    horas, minutos = divmod(int(minutos), 60)

    if horas:
        return f"{horas:02d}h {minutos:02d}m {seg:05.2f}s"
    return f"{minutos:02d}m {seg:05.2f}s"
