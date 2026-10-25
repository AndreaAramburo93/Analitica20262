"""Resumen detallado de DataFrames en archivos de texto.

La clase no se conecta a Hugging Face: recibe un DataFrame ya cargado
(por ejemplo, el que devuelve ``HFDatasetLoader.load()``).
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pandas as pd


class DatasetSummarizer:
    """Genera un resumen en texto plano de un DataFrame de pandas.

    El resumen incluye:
      1. Dimensiones (filas y columnas) y uso de memoria.
      2. Nombres y tipos de cada columna, con conteo de valores únicos.
      3. Valores nulos por columna (cantidad y porcentaje), cadenas vacías
         y valores de relleno (por ejemplo "[removed]" o "[deleted]").
      4. Filas duplicadas.
      5. Estadísticas descriptivas de las columnas numéricas.
      6. Estadísticas de longitud de las columnas de texto.
      7. Valores más frecuentes de las columnas categóricas.
      8. Una muestra de las primeras filas.

    El DataFrame se recibe en cada método (igual que en ``Reportes``), así
    una misma instancia sirve para resumir varios DataFrames.

    Args:
        valores_relleno: Textos que se consideran "vacíos" aunque no sean
            nulos. Por defecto ``["[removed]", "[deleted]"]``.
        max_categorias: Una columna de texto con este número de valores únicos
            o menos se trata como categórica y se listan sus frecuencias.
        filas_muestra: Número de filas que se incluyen como muestra.
        max_ancho_texto: Caracteres máximos por celda en la muestra.
    """

    VALORES_RELLENO_POR_DEFECTO = ["[removed]", "[deleted]"]

    def __init__(
        self,
        valores_relleno: list[str] | None = None,
        max_categorias: int = 20,
        filas_muestra: int = 5,
        max_ancho_texto: int = 60,
    ) -> None:
        if max_categorias < 1 or filas_muestra < 0 or max_ancho_texto < 4:
            raise ValueError("Parámetros de configuración fuera de rango.")
        self.df: pd.DataFrame | None = None
        self.valores_relleno = (
            self.VALORES_RELLENO_POR_DEFECTO if valores_relleno is None else valores_relleno
        )
        self.max_categorias = max_categorias
        self.filas_muestra = filas_muestra
        self.max_ancho_texto = max_ancho_texto

    # ------------------------------------------------------------------ #
    # Utilidades internas
    # ------------------------------------------------------------------ #
    @staticmethod
    def _titulo(texto: str) -> str:
        return f"\n{texto}\n{'-' * len(texto)}\n"

    def _columnas_texto(self) -> list[str]:
        """Columnas object/string cuyos valores no nulos son cadenas."""
        cols = []
        for col in self.df.select_dtypes(include=["object", "string"]).columns:
            no_nulos = self.df[col].dropna()
            if not no_nulos.empty and no_nulos.map(lambda v: isinstance(v, str)).all():
                cols.append(col)
        return cols

    @staticmethod
    def _validar_dataframe(df: pd.DataFrame) -> None:
        if not isinstance(df, pd.DataFrame):
            raise TypeError("df debe ser un pandas.DataFrame.")
        if df.empty:
            raise ValueError("El DataFrame está vacío; no hay nada que resumir.")

    def _recortar(self, valor) -> str:
        texto = str(valor).replace("\n", " ").replace("\r", " ")
        if len(texto) > self.max_ancho_texto:
            return texto[: self.max_ancho_texto - 3] + "..."
        return texto

    # ------------------------------------------------------------------ #
    # Secciones del resumen
    # ------------------------------------------------------------------ #
    def _seccion_dimensiones(self) -> str:
        filas, columnas = self.df.shape
        memoria_mb = self.df.memory_usage(deep=True).sum() / 1024**2
        return (
            self._titulo("1. DIMENSIONES")
            + f"Filas:    {filas:,}\n"
            + f"Columnas: {columnas}\n"
            + f"Memoria aproximada: {memoria_mb:,.2f} MB\n"
        )

    def _seccion_columnas(self) -> str:
        tabla = pd.DataFrame(
            {
                "columna": self.df.columns,
                "tipo": [str(t) for t in self.df.dtypes],
                "no_nulos": self.df.notna().sum().values,
                "valores_unicos": [self.df[c].nunique(dropna=True) for c in self.df.columns],
            }
        )
        return self._titulo("2. COLUMNAS Y TIPOS DE DATOS") + tabla.to_string(index=False) + "\n"

    def _seccion_nulos(self) -> str:
        total = len(self.df)
        nulos = self.df.isna().sum()
        texto = self._titulo("3. VALORES NULOS Y VACÍOS")

        if nulos.sum() == 0:
            texto += "No hay valores nulos (NaN/None) en ninguna columna.\n"
        else:
            tabla = pd.DataFrame(
                {"nulos": nulos, "porcentaje": (nulos / total * 100).round(2)}
            )
            tabla = tabla[tabla["nulos"] > 0].sort_values("nulos", ascending=False)
            texto += f"Total de celdas nulas: {int(nulos.sum()):,}\n"
            texto += f"Columnas con nulos: {len(tabla)} de {self.df.shape[1]}\n\n"
            texto += tabla.to_string() + "\n"

        # Cadenas vacías y valores de relleno: no son NaN pero no aportan contenido
        filas_extra = []
        for col in self._columnas_texto():
            serie = self.df[col].dropna()
            vacias = int((serie.str.strip() == "").sum())
            fila = {"columna": col, "cadenas_vacias": vacias}
            for v in self.valores_relleno:
                fila[v] = int((serie == v).sum())
            if sum(val for k, val in fila.items() if k != "columna") > 0:
                filas_extra.append(fila)

        if filas_extra:
            texto += (
                "\nValores vacíos o de relleno (no cuentan como nulos, "
                "pero no tienen contenido útil):\n"
            )
            texto += pd.DataFrame(filas_extra).to_string(index=False) + "\n"

        return texto

    def _seccion_duplicados(self) -> str:
        texto = self._titulo("4. FILAS DUPLICADAS")
        try:
            duplicadas = int(self.df.duplicated().sum())
            texto += f"Filas completamente duplicadas: {duplicadas:,}\n"
        except TypeError:
            # Columnas con listas/diccionarios no se pueden comparar
            texto += "No se pudo calcular (hay columnas con valores no comparables).\n"
        return texto

    def _seccion_numericas(self) -> str:
        numericas = self.df.select_dtypes(include="number")
        texto = self._titulo("5. ESTADÍSTICAS DESCRIPTIVAS (COLUMNAS NUMÉRICAS)")
        if numericas.empty:
            return texto + "No hay columnas numéricas.\n"
        with pd.option_context("display.float_format", "{:,.2f}".format, "display.width", 200):
            texto += numericas.describe().T.to_string() + "\n"
        return texto

    def _seccion_texto(self) -> str:
        texto = self._titulo("6. COLUMNAS DE TEXTO (LONGITUD EN CARACTERES)")
        cols = [
            c for c in self._columnas_texto()
            if self.df[c].nunique(dropna=True) > self.max_categorias
        ]
        if not cols:
            return texto + "No hay columnas de texto libre.\n"
        filas = []
        for col in cols:
            largo = self.df[col].dropna().str.len()
            filas.append(
                {
                    "columna": col,
                    "min": int(largo.min()),
                    "media": round(float(largo.mean()), 1),
                    "mediana": float(largo.median()),
                    "max": int(largo.max()),
                }
            )
        return texto + pd.DataFrame(filas).to_string(index=False) + "\n"

    def _seccion_categoricas(self) -> str:
        texto = self._titulo("7. VALORES MÁS FRECUENTES (COLUMNAS CATEGÓRICAS)")
        candidatas = list(self.df.select_dtypes(include=["category", "bool"]).columns)
        candidatas += [
            c for c in self._columnas_texto()
            if self.df[c].nunique(dropna=True) <= self.max_categorias
        ]
        if not candidatas:
            return texto + (
                f"No hay columnas con {self.max_categorias} valores únicos o menos.\n"
            )
        for col in candidatas:
            conteo = self.df[col].value_counts(dropna=False)
            pct = (conteo / len(self.df) * 100).round(2)
            tabla = pd.DataFrame({"cantidad": conteo, "porcentaje": pct})
            tabla.index = [self._recortar(v) for v in tabla.index]
            texto += f"\n> {col} ({len(conteo)} valores distintos)\n"
            texto += tabla.to_string() + "\n"
        return texto

    def _seccion_muestra(self) -> str:
        cabeza = self.df.head(self.filas_muestra)
        # DataFrame.map existe desde pandas 2.1; antes se llamaba applymap
        aplicar = getattr(cabeza, "map", None) or cabeza.applymap
        muestra = aplicar(self._recortar)
        texto = self._titulo(f"8. MUESTRA DE DATOS (primeras {len(muestra)} filas)")
        texto += f"(Textos recortados a {self.max_ancho_texto} caracteres)\n\n"
        for i, (_, fila) in enumerate(muestra.iterrows(), start=1):
            texto += f"Fila {i}:\n"
            for col, valor in fila.items():
                texto += f"   {col}: {valor}\n"
            texto += "\n"
        return texto

    # ------------------------------------------------------------------ #
    # API pública
    # ------------------------------------------------------------------ #
    def generar_resumen(self, df: pd.DataFrame, nombre: str = "DataFrame") -> str:
        """Construye y devuelve el resumen completo como texto."""
        self._validar_dataframe(df)
        self.df = df
        encabezado = (
            "=" * 70 + "\n"
            f"RESUMEN DEL DATASET: {nombre}\n"
            f"Generado: {datetime.now():%Y-%m-%d %H:%M:%S}\n"
            + "=" * 70 + "\n"
        )
        secciones = [
            self._seccion_dimensiones(),
            self._seccion_columnas(),
            self._seccion_nulos(),
            self._seccion_duplicados(),
            self._seccion_numericas(),
            self._seccion_texto(),
            self._seccion_categoricas(),
            self._seccion_muestra(),
        ]
        return encabezado + "".join(secciones)

    def imprimir_resumen(self, df: pd.DataFrame, nombre: str = "DataFrame") -> None:
        """Imprime el resumen en la consola."""
        print(self.generar_resumen(df, nombre), end="")

    def guardar_resumen(
        self, df: pd.DataFrame, ruta: str | Path, nombre: str = "DataFrame"
    ) -> Path:
        """Guarda el resumen en un .txt (UTF-8), creando carpetas si hace falta."""
        path = Path(ruta)
        if path.suffix.lower() != ".txt":
            path = path.with_suffix(".txt")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(self.generar_resumen(df, nombre), encoding="utf-8")
        return path