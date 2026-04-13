from __future__ import annotations

from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestRegressor
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LinearRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder

from modelo_predictivo_cba.models import ConfiguracionModeloCBA


class ModeloLinealSimpleCBA:
    def __init__(
        self,
        configuracion: ConfiguracionModeloCBA | None = None,
        algoritmo: str | None = None,
    ) -> None:
        self.configuracion = configuracion or ConfiguracionModeloCBA()
        self.algoritmo = (algoritmo or self.configuracion.algoritmo_por_defecto).strip().lower()
        self.metricas_algoritmos: list[dict[str, object]] = []
        self.pipeline: Pipeline | None = None

    def fit(self, dataframe: pd.DataFrame) -> "ModeloLinealSimpleCBA":
        self._validar_dataframe_entrenamiento(dataframe)
        self.pipeline = self._crear_pipeline()
        self.pipeline.fit(
            dataframe[list(self.configuracion.columnas_features_modelo)],
            pd.to_numeric(
                dataframe[self.configuracion.columna_objetivo],
                errors="raise",
            ).astype(float),
        )
        return self

    def predict(self, dataframe: pd.DataFrame) -> np.ndarray:
        self._validar_ajuste()
        faltantes = [
            columna
            for columna in self.configuracion.columnas_features_modelo
            if columna not in dataframe.columns
        ]
        if faltantes:
            raise ValueError(
                f"Faltan columnas de entrada para el modelo CBA: {', '.join(faltantes)}"
            )
        predicciones = self.pipeline.predict(dataframe[list(self.configuracion.columnas_features_modelo)])
        return np.maximum(np.asarray(predicciones, dtype=float), 0.0)

    def guardar(self, ruta: Path) -> Path:
        self._validar_ajuste()
        ruta.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump(
            {
                "algoritmo": self.algoritmo,
                "pipeline": self.pipeline,
                "metricas_algoritmos": self.metricas_algoritmos,
                "columnas_features_modelo": list(self.configuracion.columnas_features_modelo),
            },
            ruta,
        )
        return ruta

    @classmethod
    def cargar(cls, ruta: Path, configuracion: ConfiguracionModeloCBA | None = None) -> "ModeloLinealSimpleCBA":
        contenido = joblib.load(ruta)
        modelo = cls(
            configuracion=configuracion,
            algoritmo=str(contenido["algoritmo"]),
        )
        modelo.pipeline = contenido["pipeline"]
        modelo.metricas_algoritmos = list(contenido.get("metricas_algoritmos", []))
        return modelo

    def _crear_pipeline(self) -> Pipeline:
        transformador = ColumnTransformer(
            transformers=[
                (
                    "categoricas",
                    Pipeline(
                        steps=[
                            ("imputer", SimpleImputer(strategy="most_frequent")),
                            ("encoder", OneHotEncoder(handle_unknown="ignore", sparse_output=False)),
                        ]
                    ),
                    list(self.configuracion.columnas_categoricas),
                ),
                (
                    "numericas",
                    Pipeline(
                        steps=[
                            ("imputer", SimpleImputer(strategy="median")),
                        ]
                    ),
                    list(self.configuracion.columnas_numericas_modelo),
                ),
            ]
        )

        if self.algoritmo == "lineal":
            regresor = LinearRegression()
        elif self.algoritmo == "random_forest":
            regresor = RandomForestRegressor(
                n_estimators=250,
                max_depth=6,
                min_samples_split=8,
                min_samples_leaf=4,
                max_features=0.7,
                random_state=42,
                n_jobs=1,
            )
        else:
            raise ValueError(f"Algoritmo no soportado para el modelo CBA: {self.algoritmo}")

        return Pipeline(
            steps=[
                ("preprocesamiento", transformador),
                ("regresor", regresor),
            ]
        )

    def _validar_dataframe_entrenamiento(self, dataframe: pd.DataFrame) -> None:
        faltantes = [
            columna
            for columna in (self.configuracion.columna_objetivo,) + self.configuracion.columnas_features_modelo
            if columna not in dataframe.columns
        ]
        if faltantes:
            raise ValueError(
                f"Faltan columnas para entrenar el modelo CBA: {', '.join(faltantes)}"
            )
        if dataframe.empty:
            raise ValueError("No hay filas disponibles para entrenar el modelo CBA.")
        if dataframe[self.configuracion.columna_objetivo].isna().any():
            raise ValueError("La vista de entrenamiento contiene nulos en la variable objetivo.")

    def _validar_ajuste(self) -> None:
        if self.pipeline is None:
            raise ValueError("El modelo CBA aun no ha sido entrenado o cargado.")
