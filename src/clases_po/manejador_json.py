"""Lectura, modificación y escritura de archivos JSON con el módulo estándar ``json``."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from clases_po.generador_resumen_txt import GeneradorResumenTXT


class ManejadorJSON:
    """Importa un JSON con ``json.load``, permite modificarlo y lo guarda con ``json.dump``.

    Trabaja con JSON cuyo contenido es una lista de registros (objetos), por ejemplo
    ``[{"id": 1, ...}, {"id": 2, ...}]``. También acepta un objeto que contenga esa
    lista en una clave, por ejemplo ``{"data": [...]}``; en ese caso se indica la
    clave con ``clave_registros`` o se detecta automáticamente.

    Si el archivo es JSON Lines (``.jsonl``: un objeto por línea), ``json.load``
    falla porque el archivo completo no es un único JSON. En ese caso la clase lo
    lee línea por línea con ``json.loads`` y guarda la salida como una lista JSON
    normal con ``json.dump``.

    Args:
        ruta: Ruta relativa del JSON original.
        clave_registros: Clave donde está la lista de registros, si el JSON es un objeto.
        codificacion: Codificación del archivo (por defecto ``utf-8``).
    """

    def __init__(
        self, ruta: str | Path, clave_registros: str | None = None, codificacion: str = "utf-8"
    ) -> None:
        self.ruta = Path("datos\originales\aci_train.jsonl")
        self.clave_registros = clave_registros
        self.codificacion = codificacion
        self.contenido: Any = None            # JSON completo tal como se leyó
        self.registros: list[dict[str, Any]] = []
        self.formato_origen: str | None = None  # "json" o "jsonl"

    # ------------------------------------------------------------------ #
    # Importar
    # ------------------------------------------------------------------ #
    def importar(self) -> list[dict[str, Any]]:
        """Lee el archivo con ``json.load`` y ubica la lista de registros."""
        if not self.ruta.exists():
            raise FileNotFoundError(f"No se encontró el archivo: {self.ruta}")

        with open(self.ruta, "r", encoding=self.codificacion) as archivo:
            try:
                self.contenido = json.load(archivo)
                self.formato_origen = "json"
            except json.JSONDecodeError as error:
                if "Extra data" not in str(error):
                    raise ValueError(f"No es un JSON válido: {error}") from error
                self.contenido = None

        if self.contenido is None:
            # JSON Lines: varios objetos JSON, uno por línea
            with open(self.ruta, "r", encoding=self.codificacion) as archivo:
                self.contenido = [json.loads(linea) for linea in archivo if linea.strip()]
            self.formato_origen = "jsonl"

        if isinstance(self.contenido, list):
            self.registros = self.contenido
        elif isinstance(self.contenido, dict):
            clave = self.clave_registros or self._detectar_clave_lista()
            if clave is None:
                raise ValueError(
                    "El JSON es un objeto y no contiene ninguna lista de registros. "
                    f"Claves disponibles: {list(self.contenido)}"
                )
            self.clave_registros = clave
            self.registros = self.contenido[clave]
        else:
            raise ValueError("El JSON debe ser una lista u objeto que contenga una lista.")
        return self.registros

    # ------------------------------------------------------------------ #
    # Consultar
    # ------------------------------------------------------------------ #
    def campos(self) -> list[str]:
        """Campos (claves) que aparecen en los registros, en orden de aparición."""
        self._verificar_cargado()
        vistos: dict[str, None] = {}
        for registro in self.registros:
            if isinstance(registro, dict):
                vistos.update(dict.fromkeys(registro))
        return list(vistos)

    def info(self) -> dict[str, Any]:
        """Resumen básico de los datos cargados."""
        self._verificar_cargado()
        return {
            "archivo": str(self.ruta),
            "formato_origen": self.formato_origen,
            "estructura": "lista" if self.clave_registros is None else f"objeto -> '{self.clave_registros}'",
            "registros": len(self.registros),
            "campos": self.campos(),
        }

    def mostrar(self, n: int = 3) -> None:
        """Imprime los primeros ``n`` registros con formato legible."""
        self._verificar_cargado()
        print(json.dumps(self.registros[:n], ensure_ascii=False, indent=2))

    # ------------------------------------------------------------------ #
    # Modificar
    # ------------------------------------------------------------------ #
    def actualizar_valor(self, indice: int, campo: str, nuevo_valor: Any) -> tuple[Any, Any]:
        """Cambia el valor de un campo en un registro. Devuelve ``(anterior, nuevo)``."""
        self._verificar_cargado()
        self._verificar_indice(indice)
        registro = self.registros[indice]
        if campo not in registro:
            raise KeyError(f"El campo '{campo}' no existe en el registro {indice}: {list(registro)}")
        anterior = registro[campo]
        registro[campo] = nuevo_valor
        return anterior, nuevo_valor

    def agregar_registro(self, registro: dict[str, Any]) -> dict[str, Any]:
        """Agrega un registro (diccionario) al final de la lista."""
        self._verificar_cargado()
        if not isinstance(registro, dict):
            raise TypeError("El registro debe ser un diccionario.")
        self.registros.append(registro)
        return registro

    def eliminar_registro(self, indice: int) -> dict[str, Any]:
        """Elimina el registro en la posición indicada y lo devuelve."""
        self._verificar_cargado()
        self._verificar_indice(indice)
        return self.registros.pop(indice)

    def eliminar_por_valor(self, campo: str, valor: Any) -> int:
        """Elimina los registros donde ``campo == valor``. Devuelve cuántos se eliminaron."""
        self._verificar_cargado()
        antes = len(self.registros)
        # Se modifica la lista en su lugar para que siga enlazada con self.contenido
        self.registros[:] = [r for r in self.registros if r.get(campo) != valor]
        return antes - len(self.registros)

    # ------------------------------------------------------------------ #
    # Guardar
    # ------------------------------------------------------------------ #
    def guardar(self, ruta_salida: str | Path, indent: int = 2) -> Path:
        """Escribe el JSON (con la misma estructura del original) usando ``json.dump``."""
        self._verificar_cargado()
        salida = Path(ruta_salida)
        if salida.resolve() == self.ruta.resolve():
            raise ValueError("La salida debe tener un nombre distinto al archivo original.")
        salida.parent.mkdir(parents=True, exist_ok=True)

        with open(salida, "w", encoding="utf-8") as archivo:
            json.dump(self.contenido, archivo, ensure_ascii=False, indent=indent)
        return salida

    # ------------------------------------------------------------------ #
    # Validaciones internas
    # ------------------------------------------------------------------ #
    def _detectar_clave_lista(self) -> str | None:
        for clave, valor in self.contenido.items():
            if isinstance(valor, list) and valor and isinstance(valor[0], dict):
                return clave
        return None

    def _verificar_cargado(self) -> None:
        if self.contenido is None:
            raise RuntimeError("Primero llama a importar().")

    def _verificar_indice(self, indice: int) -> None:
        if not 0 <= indice < len(self.registros):
            raise IndexError(f"Índice {indice} fuera de rango (0 a {len(self.registros) - 1}).")