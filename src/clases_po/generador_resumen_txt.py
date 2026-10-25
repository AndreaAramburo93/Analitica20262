"""Genera un resumen.txt con los resultados reales de ManejadorCSV y ManejadorJSON."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any


class GeneradorResumenTXT:
    """Registra lo que hacen las clases ``ManejadorCSV`` y ``ManejadorJSON`` y escribe un resumen.

    Cómo funciona:
      1. Se crea el generador con las URL de origen del CSV y del JSON.
      2. Cada manejador se pasa por ``rastrear()``. Desde ese momento, cada método
         que se llame sobre él (importar, actualizar_valor, guardar, ...) queda
         registrado con sus argumentos, su resultado y la cantidad de registros
         antes y después de la llamada.
      3. ``generar()`` escribe ``resumen.txt`` con esos datos. Nada se escribe a
         mano: todo sale de lo que pasó en la ejecución.

    Ejemplo::

        resumen = GeneradorResumenTXT(url_csv=URL_CSV, url_json=URL_JSON)
        csv_handler = resumen.rastrear(ManejadorCSV(CSV_ORIGINAL))
        csv_handler.importar()
        ...
        resumen.generar("datos/resumen.txt")
    """

    # Clasificación de los métodos de las clases según lo que hacen
    METODOS_IMPORTAR = {"importar"}
    METODOS_GUARDAR = {"guardar"}
    METODOS_MODIFICAR = {"actualizar_valor", "agregar_registro", "eliminar_registro", "eliminar_por_valor"}

    def __init__(self, url_csv: str, url_json: str) -> None:
        self.url_csv = url_csv
        self.url_json = url_json
        self.manejadores: list[Any] = []          # objetos originales rastreados
        self.eventos: list[dict[str, Any]] = []   # una entrada por cada método llamado

    # ------------------------------------------------------------------ #
    # Registro de la ejecución
    # ------------------------------------------------------------------ #
    def rastrear(self, manejador: Any) -> "_ManejadorRastreado":
        """Devuelve el mismo manejador, pero registrando cada método que se llame sobre él."""
        self.manejadores.append(manejador)
        return _ManejadorRastreado(manejador, self)

    def _registrar(self, manejador: Any, metodo: str, args: tuple, kwargs: dict) -> Any:
        """Ejecuta el método real del manejador y guarda lo que ocurrió."""
        antes = self._contar_registros(manejador)
        valor_anterior = self._valor_actual(manejador, metodo, args, kwargs)

        resultado = getattr(manejador, metodo)(*args, **kwargs)

        self.eventos.append({
            "clase": type(manejador).__name__,
            "manejador": manejador,
            "metodo": metodo,
            "args": args,
            "kwargs": kwargs,
            "resultado": resultado,
            "valor_anterior": valor_anterior,
            "registros_antes": antes,
            "registros_despues": self._contar_registros(manejador),
            "hora": datetime.now(),
        })
        return resultado

    # ------------------------------------------------------------------ #
    # Generar el archivo
    # ------------------------------------------------------------------ #
    def generar(self, ruta_salida: str | Path = "resumen.txt") -> Path:
        """Escribe el resumen en ``ruta_salida`` y devuelve la ruta del archivo."""
        if not self.eventos:
            raise RuntimeError("No hay nada que resumir: no se ha llamado ningún método rastreado.")

        salida = Path(ruta_salida)
        salida.parent.mkdir(parents=True, exist_ok=True)

        lineas: list[str] = []
        lineas += self._seccion_encabezado()
        lineas += self._seccion_origen()
        for letra, manejador in zip("ABCDEFGH", self.manejadores):
            lineas += self._seccion_archivo(manejador, f"2{letra}")
        lineas += self._seccion_clases_metodos()
        lineas += self._seccion_totales()

        with open(salida, "w", encoding="utf-8") as archivo:
            archivo.write("\n".join(lineas) + "\n")
        return salida

    # ------------------------------------------------------------------ #
    # Secciones del resumen
    # ------------------------------------------------------------------ #
    def _seccion_encabezado(self) -> list[str]:
        return [
            "=" * 70,
            "RESUMEN DE PROCESAMIENTO DE ARCHIVOS CSV Y JSON",
            "=" * 70,
            f"Generado el: {datetime.now():%Y-%m-%d %H:%M:%S}",
            f"Generado por: {type(self).__name__} (generador_resumen_txt.py)",
            "",
        ]

    def _seccion_origen(self) -> list[str]:
        return [
            "1. URL DE ORIGEN DE LOS DATOS",
            "-" * 70,
            f"CSV : {self.url_csv}",
            f"JSON: {self.url_json}",
            "",
        ]

    def _seccion_archivo(self, manejador: Any, numero: str = "2") -> list[str]:
        clase = type(manejador).__name__
        eventos = [e for e in self.eventos if e["manejador"] is manejador]
        importaciones = [e for e in eventos if e["metodo"] in self.METODOS_IMPORTAR]
        modificaciones = [e for e in eventos if e["metodo"] in self.METODOS_MODIFICAR]
        guardados = [e for e in eventos if e["metodo"] in self.METODOS_GUARDAR]

        lineas = [f"{numero}. ARCHIVO PROCESADO CON {clase}", "-" * 70]

        # Archivo importado
        ruta_original = getattr(manejador, "ruta", "(sin ruta)")
        if importaciones:
            e = importaciones[0]
            lineas.append(f"Archivo importado : {ruta_original}")
            lineas.append(f"Registros leídos  : {e['registros_despues']}")
            columnas = self._columnas(manejador)
            if columnas:
                lineas.append(f"Columnas/campos   : {', '.join(columnas)}")
            formato = getattr(manejador, "formato_origen", None)
            if formato:
                lineas.append(f"Formato de origen : {formato}")
        else:
            lineas.append(f"Archivo importado : {ruta_original} (importar() no se llamó)")

        # Modificaciones
        lineas.append("")
        lineas.append(f"Modificaciones realizadas: {len(modificaciones)}")
        for numero, e in enumerate(modificaciones, start=1):
            lineas.append(f"  {numero}. {self._describir_modificacion(e)}")
        if not modificaciones:
            lineas.append("  (ninguna)")

        # Archivos guardados
        lineas.append("")
        if guardados:
            for e in guardados:
                ruta_nueva = Path(e["resultado"]) if e["resultado"] else None
                lineas.append(f"Archivo guardado  : {ruta_nueva}")
                if ruta_nueva and ruta_nueva.exists():
                    lineas.append(f"Tamaño en disco   : {ruta_nueva.stat().st_size:,} bytes")
                lineas.append(f"Registros guardados: {e['registros_despues']}")
        else:
            lineas.append("Archivo guardado  : (guardar() no se llamó)")
        lineas.append("")
        return lineas

    def _seccion_clases_metodos(self) -> list[str]:
        lineas = ["3. CLASES Y MÉTODOS UTILIZADOS", "-" * 70]

        # Clases y los métodos de cada una, en el orden en que se usaron
        for manejador in self.manejadores:
            clase = type(manejador).__name__
            modulo = type(manejador).__module__.split(".")[-1]
            metodos: dict[str, int] = {}
            for e in self.eventos:
                if e["manejador"] is manejador:
                    metodos[e["metodo"]] = metodos.get(e["metodo"], 0) + 1
            lineas.append(f"{clase} ({modulo}.py)")
            for metodo, veces in metodos.items():
                lineas.append(f"  - {metodo}()  x{veces}  [{self._tipo_metodo(metodo)}]")
        lineas.append(f"{type(self).__name__} (generador_resumen_txt.py)")
        lineas.append("  - rastrear(), generar()")
        lineas.append("")

        lineas.append("Secuencia de ejecución:")
        for numero, e in enumerate(self.eventos, start=1):
            lineas.append(
                f"  {numero:>2}. {e['hora']:%H:%M:%S}  {e['clase']}.{e['metodo']}()"
                f"  registros: {e['registros_antes']} -> {e['registros_despues']}"
            )
        lineas.append("")
        return lineas

    def _seccion_totales(self) -> list[str]:
        lineas = ["4. CANTIDAD DE REGISTROS PROCESADOS", "-" * 70]
        total_leidos = total_guardados = 0
        for manejador in self.manejadores:
            clase = type(manejador).__name__
            eventos = [e for e in self.eventos if e["manejador"] is manejador]
            leidos = next((e["registros_despues"] for e in eventos if e["metodo"] in self.METODOS_IMPORTAR), 0)
            guardados = next(
                (e["registros_despues"] for e in reversed(eventos) if e["metodo"] in self.METODOS_GUARDAR), 0
            )
            total_leidos += leidos
            total_guardados += guardados
            lineas.append(f"{clase:<14} leídos: {leidos:>8,}   guardados: {guardados:>8,}   diferencia: {guardados - leidos:+,}")
        lineas.append(f"{'TOTAL':<14} leídos: {total_leidos:>8,}   guardados: {total_guardados:>8,}")
        lineas.append("=" * 70)
        return lineas

    # ------------------------------------------------------------------ #
    # Utilidades internas
    # ------------------------------------------------------------------ #
    def _tipo_metodo(self, metodo: str) -> str:
        if metodo in self.METODOS_IMPORTAR:
            return "importación"
        if metodo in self.METODOS_MODIFICAR:
            return "modificación"
        if metodo in self.METODOS_GUARDAR:
            return "guardado"
        return "consulta"

    def _describir_modificacion(self, e: dict[str, Any]) -> str:
        args, kwargs, metodo = e["args"], e["kwargs"], e["metodo"]
        params = list(args) + list(kwargs.values())

        if metodo == "actualizar_valor" and len(params) >= 3:
            indice, campo, nuevo = params[:3]
            return (f"actualizar_valor: registro {indice}, campo '{campo}': "
                    f"{self._corto(e['valor_anterior'])} -> {self._corto(nuevo)}")
        if metodo == "agregar_registro":
            return f"agregar_registro: se agregó {self._corto(params[0] if params else None)}"
        if metodo == "eliminar_registro":
            return (f"eliminar_registro: se eliminó el registro {params[0] if params else '?'} "
                    f"-> {self._corto(e['resultado'])}")
        if metodo == "eliminar_por_valor" and len(params) >= 2:
            return (f"eliminar_por_valor: se eliminaron {e['resultado']} registro(s) "
                    f"donde '{params[0]}' = {self._corto(params[1])}")
        return f"{metodo}{tuple(params)}"

    @staticmethod
    def _contar_registros(manejador: Any) -> int:
        return len(getattr(manejador, "registros", []) or [])

    @staticmethod
    def _columnas(manejador: Any) -> list[str]:
        if getattr(manejador, "encabezados", None):      # ManejadorCSV
            return list(manejador.encabezados)
        registros = getattr(manejador, "registros", None)
        if registros and isinstance(registros[0], dict):  # ManejadorJSON
            return list(registros[0].keys())
        return []

    @staticmethod
    def _valor_actual(manejador: Any, metodo: str, args: tuple, kwargs: dict) -> Any:
        """Antes de actualizar_valor, guarda el valor que había para mostrar 'antes -> después'."""
        if metodo != "actualizar_valor":
            return None
        params = list(args) + list(kwargs.values())
        try:
            indice, campo = params[0], params[1]
            registro = manejador.registros[indice]
            if isinstance(registro, dict):
                return registro.get(campo)
            columna = manejador.encabezados.index(campo) if isinstance(campo, str) else campo
            return registro[columna]
        except Exception:
            return None

    @staticmethod
    def _corto(valor: Any, limite: int = 60) -> str:
        texto = repr(valor).replace("\n", " ")
        return texto if len(texto) <= limite else texto[: limite - 3] + "..."


class _ManejadorRastreado:
    """Envoltura que pasa cada llamada al manejador real y la registra en el generador.

    Los atributos (``registros``, ``encabezados``, ``ruta``...) se leen directo del
    manejador, así que en el notebook se usa igual que la clase original.
    """

    def __init__(self, manejador: Any, generador: GeneradorResumenTXT) -> None:
        object.__setattr__(self, "_manejador", manejador)
        object.__setattr__(self, "_generador", generador)

    def __getattr__(self, nombre: str) -> Any:
        atributo = getattr(self._manejador, nombre)
        if callable(atributo) and not nombre.startswith("_"):
            def llamada(*args, **kwargs):
                return self._generador._registrar(self._manejador, nombre, args, kwargs)
            return llamada
        return atributo

    def __setattr__(self, nombre: str, valor: Any) -> None:
        setattr(self._manejador, nombre, valor)

    def __repr__(self) -> str:
        return f"<{type(self._manejador).__name__} rastreado>"
