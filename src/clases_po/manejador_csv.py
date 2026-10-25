"""Lectura, modificación y escritura de archivos CSV con el módulo estándar ``csv``."""
from __future__ import annotations

import csv
from pathlib import Path


class ManejadorCSV:
    """Importa un CSV con ``csv.reader``, permite modificarlo y lo guarda con ``csv.writer``.

    Los datos se mantienen en memoria como:
      - ``encabezados``: lista con los nombres de las columnas (primera fila).
      - ``registros``: lista de filas; cada fila es una lista de strings.

    Args:
        ruta: Ruta relativa del CSV original.
        delimitador: Separador de columnas (por defecto ``,``).
        codificacion: Codificación del archivo (por defecto ``utf-8``).
    """

    def __init__(self, ruta: str | Path, delimitador: str = ",", codificacion: str = "utf-8") -> None:
        self.ruta = Path(ruta)
        self.delimitador = delimitador
        self.codificacion = codificacion
        self.encabezados: list[str] = []
        self.registros: list[list[str]] = []

    # ------------------------------------------------------------------ #
    # Importar
    # ------------------------------------------------------------------ #
    def importar(self) -> list[list[str]]:
        """Lee el CSV con ``csv.reader``. La primera fila se toma como encabezados."""
        if not self.ruta.exists():
            raise FileNotFoundError(f"No se encontró el archivo: {self.ruta}")

        # utf-8-sig elimina el BOM que a veces agregan Excel u otras herramientas
        codificacion = "utf-8-sig" if self.codificacion.lower() == "utf-8" else self.codificacion
        with open(self.ruta, "r", encoding=codificacion, newline="") as archivo:
            lector = csv.reader(archivo, delimiter=self.delimitador)
            filas = [fila for fila in lector if fila]  # ignora líneas vacías

        if not filas:
            raise ValueError("El archivo CSV está vacío.")

        self.encabezados = filas[0]
        self.registros = filas[1:]
        return self.registros

    # ------------------------------------------------------------------ #
    # Consultar
    # ------------------------------------------------------------------ #
    def info(self) -> dict[str, object]:
        """Resumen básico de los datos cargados."""
        self._verificar_cargado()
        return {
            "archivo": str(self.ruta),
            "columnas": len(self.encabezados),
            "registros": len(self.registros),
            "encabezados": self.encabezados,
        }

    def mostrar(self, n: int = 5) -> None:
        """Imprime los encabezados y las primeras ``n`` filas."""
        self._verificar_cargado()
        print(self.delimitador.join(self.encabezados))
        for fila in self.registros[:n]:
            print(self.delimitador.join(fila))

    # ------------------------------------------------------------------ #
    # Modificar
    # ------------------------------------------------------------------ #
    def actualizar_valor(self, indice_fila: int, columna: str, nuevo_valor: object) -> tuple[str, str]:
        """Cambia el valor de una celda. Devuelve ``(valor_anterior, valor_nuevo)``.

        ``indice_fila`` empieza en 0 y no cuenta la fila de encabezados.
        """
        self._verificar_cargado()
        col = self._indice_columna(columna)
        self._verificar_indice(indice_fila)
        anterior = self.registros[indice_fila][col]
        self.registros[indice_fila][col] = str(nuevo_valor)
        return anterior, str(nuevo_valor)

    def agregar_registro(self, registro: dict[str, object] | list[object]) -> list[str]:
        """Agrega una fila al final.

        Acepta un diccionario ``{columna: valor}`` (las columnas faltantes quedan
        vacías) o una lista con un valor por columna, en el mismo orden.
        """
        self._verificar_cargado()
        if isinstance(registro, dict):
            desconocidas = set(registro) - set(self.encabezados)
            if desconocidas:
                raise KeyError(f"Columnas que no existen en el CSV: {sorted(desconocidas)}")
            fila = [str(registro.get(col, "")) for col in self.encabezados]
        else:
            if len(registro) != len(self.encabezados):
                raise ValueError(
                    f"El registro tiene {len(registro)} valores y el CSV {len(self.encabezados)} columnas."
                )
            fila = [str(v) for v in registro]
        self.registros.append(fila)
        return fila

    def eliminar_registro(self, indice_fila: int) -> list[str]:
        """Elimina la fila indicada (desde 0, sin contar encabezados) y la devuelve."""
        self._verificar_cargado()
        self._verificar_indice(indice_fila)
        return self.registros.pop(indice_fila)

    def eliminar_por_valor(self, columna: str, valor: object) -> int:
        """Elimina todas las filas donde ``columna == valor``. Devuelve cuántas se eliminaron."""
        self._verificar_cargado()
        col = self._indice_columna(columna)
        antes = len(self.registros)
        self.registros = [fila for fila in self.registros if fila[col] != str(valor)]
        return antes - len(self.registros)

    # ------------------------------------------------------------------ #
    # Guardar
    # ------------------------------------------------------------------ #
    def guardar(self, ruta_salida: str | Path) -> Path:
        """Escribe encabezados y registros en un CSV nuevo con ``csv.writer``.

        Para conservar el original, la ruta de salida no puede ser la misma.
        """
        self._verificar_cargado()
        salida = Path(ruta_salida)
        if salida.resolve() == self.ruta.resolve():
            raise ValueError("La salida debe tener un nombre distinto al archivo original.")
        salida.parent.mkdir(parents=True, exist_ok=True)

        with open(salida, "w", encoding="utf-8", newline="") as archivo:
            escritor = csv.writer(archivo, delimiter=self.delimitador)
            escritor.writerow(self.encabezados)
            escritor.writerows(self.registros)
        return salida

    # ------------------------------------------------------------------ #
    # Validaciones internas
    # ------------------------------------------------------------------ #
    def _verificar_cargado(self) -> None:
        if not self.encabezados:
            raise RuntimeError("Primero llama a importar().")

    def _indice_columna(self, columna: str) -> int:
        if columna not in self.encabezados:
            raise KeyError(f"La columna '{columna}' no existe. Opciones: {self.encabezados}")
        return self.encabezados.index(columna)

    def _verificar_indice(self, indice_fila: int) -> None:
        if not 0 <= indice_fila < len(self.registros):
            raise IndexError(f"Índice {indice_fila} fuera de rango (0 a {len(self.registros) - 1}).")
