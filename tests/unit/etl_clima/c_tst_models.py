from __future__ import annotations

from etl_clima.models import (
    FUENTE_NASA,
    ConfiguracionExtraccionClima,
    RegistroClimaMensual,
    ZonaClimatica,
)


def test_modelos_clima_tienen_campos_esperados() -> None:
    zona = ZonaClimatica(nombre="Matina", latitud=10.0, longitud=-83.35)
    registro = RegistroClimaMensual(
        zona=zona.nombre,
        latitud=zona.latitud,
        longitud=zona.longitud,
        anio=2024,
        mes=1,
        temp_max=30.1,
        temp_min=22.3,
        precipitacion=8.5,
        humedad=85.0,
        radiacion_solar=5.3,
    )
    configuracion = ConfiguracionExtraccionClima()

    assert registro.zona == "Matina"
    assert configuracion.base_url.endswith("/point")
    assert FUENTE_NASA == 4
