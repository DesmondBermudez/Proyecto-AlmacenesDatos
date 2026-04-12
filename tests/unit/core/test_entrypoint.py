from __future__ import annotations

import ETL


class DummyParametros:
    def __init__(
        self,
        debe_ejecutar_pruebas: bool,
        debe_ejecutar_solo_pruebas: bool = False,
        modo_carga_indicado: bool = False,
    ) -> None:
        self.debe_ejecutar_pruebas = debe_ejecutar_pruebas
        self.debe_ejecutar_solo_pruebas = debe_ejecutar_solo_pruebas
        self.modo_carga_indicado = modo_carga_indicado


def test_main_ejecuta_flujo_real_directamente_si_no_hay_pruebas(monkeypatch) -> None:
    llamadas: list[str] = []
    parametros = DummyParametros(debe_ejecutar_pruebas=False)

    class FakeCLI:
        def parsear(self):
            return parametros

    class FakeApp:
        def __init__(self, params, base_dir) -> None:
            assert params is parametros

        def ejecutar(self) -> int:
            llamadas.append("app")
            return 0

    monkeypatch.setattr(ETL, "GestorCLI", lambda: FakeCLI())
    monkeypatch.setattr(ETL, "ETLDolarCanastaApp", FakeApp)

    assert ETL.main() == 0
    assert llamadas == ["app"]


def test_main_ejecuta_pruebas_y_luego_flujo_real_si_pasan(monkeypatch) -> None:
    llamadas: list[str] = []
    parametros = DummyParametros(debe_ejecutar_pruebas=True)

    class FakeCLI:
        def parsear(self):
            return parametros

    class FakeRunner:
        def __init__(self, base_dir, params) -> None:
            assert params is parametros

        def ejecutar(self) -> int:
            llamadas.append("tests")
            return 0

    class FakeApp:
        def __init__(self, params, base_dir) -> None:
            assert params is parametros

        def ejecutar(self) -> int:
            llamadas.append("app")
            return 0

    monkeypatch.setattr(ETL, "GestorCLI", lambda: FakeCLI())
    monkeypatch.setattr(ETL, "EjecutorPruebas", FakeRunner)
    monkeypatch.setattr(ETL, "ETLDolarCanastaApp", FakeApp)

    assert ETL.main() == 0
    assert llamadas == ["tests", "app"]


def test_main_no_continua_al_flujo_real_si_pruebas_fallan(monkeypatch) -> None:
    llamadas: list[str] = []
    parametros = DummyParametros(debe_ejecutar_pruebas=True)

    class FakeCLI:
        def parsear(self):
            return parametros

    class FakeRunner:
        def __init__(self, base_dir, params) -> None:
            assert params is parametros

        def ejecutar(self) -> int:
            llamadas.append("tests")
            return 1

    class FakeApp:
        def __init__(self, params, base_dir) -> None:
            assert params is parametros

        def ejecutar(self) -> int:
            llamadas.append("app")
            return 0

    monkeypatch.setattr(ETL, "GestorCLI", lambda: FakeCLI())
    monkeypatch.setattr(ETL, "EjecutorPruebas", FakeRunner)
    monkeypatch.setattr(ETL, "ETLDolarCanastaApp", FakeApp)

    assert ETL.main() == 1
    assert llamadas == ["tests"]


def test_main_no_continua_al_flujo_real_si_only_test_esta_activo(monkeypatch) -> None:
    llamadas: list[str] = []
    parametros = DummyParametros(debe_ejecutar_pruebas=True, debe_ejecutar_solo_pruebas=True)

    class FakeCLI:
        def parsear(self):
            return parametros

    class FakeRunner:
        def __init__(self, base_dir, params) -> None:
            assert params is parametros

        def ejecutar(self) -> int:
            llamadas.append("tests")
            return 0

    class FakeApp:
        def __init__(self, params, base_dir) -> None:
            assert params is parametros

        def ejecutar(self) -> int:
            llamadas.append("app")
            return 0

    monkeypatch.setattr(ETL, "GestorCLI", lambda: FakeCLI())
    monkeypatch.setattr(ETL, "EjecutorPruebas", FakeRunner)
    monkeypatch.setattr(ETL, "ETLDolarCanastaApp", FakeApp)

    assert ETL.main() == 0
    assert llamadas == ["tests"]


def test_main_imprime_aviso_only_test_antes_de_las_pruebas(monkeypatch, capsys) -> None:
    llamadas: list[str] = []
    parametros = DummyParametros(
        debe_ejecutar_pruebas=True,
        debe_ejecutar_solo_pruebas=True,
        modo_carga_indicado=True,
    )

    class FakeCLI:
        def parsear(self):
            return parametros

    class FakeRunner:
        def __init__(self, base_dir, params) -> None:
            assert params is parametros

        def ejecutar(self) -> int:
            llamadas.append("tests")
            return 0

    monkeypatch.setattr(ETL, "GestorCLI", lambda: FakeCLI())
    monkeypatch.setattr(ETL, "EjecutorPruebas", FakeRunner)

    assert ETL.main() == 0

    captured = capsys.readouterr()
    assert "!!! Aviso: --only-test invalida --modo-carga !!!" in captured.out
    assert llamadas == ["tests"]
