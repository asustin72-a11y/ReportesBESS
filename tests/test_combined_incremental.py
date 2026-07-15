"""Pruebas de combinado por minuto incremental (Fase 5.1 del plan CSV->SQLite).

generar_combinado_por_minuto() calculaba columnas derivadas (HORA, PERIODO,
kW, demanda rodante 15 min con reinicio mensual...) sobre el histórico
completo en cada corrida y reescribía COMBINADO_POR_MINUTO_*.csv entero.
Ahora, si el destino ya tiene un cursor legible (última FECHA_HORA) y
columnas compatibles, solo procesa y reescribe una ventana de los últimos
`_MARGEN_REEXPORTAR_DIAS` días (no solo lo estrictamente posterior al
cursor) -- incluyendo el contexto de hasta 2 filas previas que la demanda
rodante (rolling de 3 filas) necesita para dar el mismo resultado que una
corrida completa -- y esa ventana reemplaza lo que hubiera en el combinado
para esas fechas. Esto recoge actualizaciones que el origen (BESS/medidor)
trae para fechas ya combinadas (p.ej. ION corrigiendo el día en curso), en
vez de quedarse pegado al primer valor que vio para esa fecha.

Las pruebas cubren: primera corrida completa, incremental == completo con
un split a mitad de mes, incremental == completo con un split justo en la
frontera de un mes (para ejercitar el reinicio de la demanda rodante), no-op
sin filas en la ventana, fallback a completo si cambia el formato de
columnas, una comparación con datos reales de IUSA_1 (ION ∩ BESS), que un
día abierto recoge una actualización posterior del origen, que los días
cerrados no se tocan al recalcular la ventana, y una corrida real de
procesar_grupo() (combinado -> diario -> acumulados) dos veces seguidas
para confirmar que "sin filas nuevas" no se confunde con un fallo.
"""

from __future__ import annotations

import pandas as pd
import pytest

import bess.config.rutas as rutas_mod
from bess.config.subestaciones import SUBESTACIONES
from bess.data.aggregates.combined import generar_combinado_por_minuto
from bess.data.orchestrator import procesar_grupo

SUB_IUSA_1 = next(s for s in SUBESTACIONES if s.id == "IUSA_1")
MED_ION = next(m for m in SUB_IUSA_1.medidores_consumo if m.nombre == "ION_Testigo_IUSA1")


def _escribir_perfil(ruta, fechas, base_rec=1.0, base_ent=0.0, escala=0.01):
    ruta.parent.mkdir(parents=True, exist_ok=True)
    df = pd.DataFrame({
        "Fecha": fechas.strftime("%Y-%m-%d %H:%M:%S"),
        "KWH_REC": [base_rec + i * escala for i in range(len(fechas))],
        "KWH_ENT": [base_ent for _ in range(len(fechas))],
    })
    df.to_csv(ruta, index=False, encoding="utf-8-sig")


def _leer_salida(tmp_path):
    return pd.read_csv(MED_ION.ruta_combinado())


def test_generar_combinado_primera_vez_modo_completo(tmp_path, monkeypatch):
    monkeypatch.setattr(rutas_mod, "DIRECTORIO_REPORTES", tmp_path)

    fechas = pd.date_range("2026-01-30 00:05:00", "2026-02-01 00:00:00", freq="5min")
    ruta_bess = tmp_path / "bess.csv"
    ruta_med = tmp_path / "medidor.csv"
    _escribir_perfil(ruta_bess, fechas, base_rec=2.0, escala=0.001)
    _escribir_perfil(ruta_med, fechas, base_rec=5.0, escala=0.002)

    df = generar_combinado_por_minuto(str(ruta_bess), str(ruta_med), MED_ION.prefijo)

    assert df is not None and len(df) == len(fechas)
    salida = _leer_salida(tmp_path)
    assert len(salida) == len(fechas)
    col_dem = f"IUSA_CON_BESS_{MED_ION.prefijo}_kW_DEM_15min"
    assert col_dem in salida.columns
    # Primeros 2 registros del mes (00:05, 00:10): demanda rodante en 0.
    assert salida[col_dem].iloc[0] == 0
    assert salida[col_dem].iloc[1] == 0
    assert salida[col_dem].iloc[2] != 0


def test_generar_combinado_incremental_equivale_a_completo_split_mitad(tmp_path, monkeypatch):
    fechas = pd.date_range("2026-01-30 00:05:00", "2026-02-01 00:00:00", freq="5min")
    mitad = len(fechas) // 2

    dir_inc = tmp_path / "inc"
    dir_inc.mkdir()
    monkeypatch.setattr(rutas_mod, "DIRECTORIO_REPORTES", dir_inc)
    ruta_bess = dir_inc / "bess.csv"
    ruta_med = dir_inc / "medidor.csv"

    # 1a corrida: solo la primera mitad procesada por Verificar/Filtrar.
    _escribir_perfil(ruta_bess, fechas[:mitad], base_rec=2.0, escala=0.001)
    _escribir_perfil(ruta_med, fechas[:mitad], base_rec=5.0, escala=0.002)
    generar_combinado_por_minuto(str(ruta_bess), str(ruta_med), MED_ION.prefijo)

    # 2a corrida: se agrega el resto.
    _escribir_perfil(ruta_bess, fechas, base_rec=2.0, escala=0.001)
    _escribir_perfil(ruta_med, fechas, base_rec=5.0, escala=0.002)
    generar_combinado_por_minuto(str(ruta_bess), str(ruta_med), MED_ION.prefijo)

    salida_inc = pd.read_csv(MED_ION.ruta_combinado())

    dir_full = tmp_path / "full"
    dir_full.mkdir()
    monkeypatch.setattr(rutas_mod, "DIRECTORIO_REPORTES", dir_full)
    ruta_bess_full = dir_full / "bess.csv"
    ruta_med_full = dir_full / "medidor.csv"
    _escribir_perfil(ruta_bess_full, fechas, base_rec=2.0, escala=0.001)
    _escribir_perfil(ruta_med_full, fechas, base_rec=5.0, escala=0.002)
    generar_combinado_por_minuto(str(ruta_bess_full), str(ruta_med_full), MED_ION.prefijo)
    salida_full = pd.read_csv(MED_ION.ruta_combinado())

    assert len(salida_inc) == len(fechas)
    pd.testing.assert_frame_equal(salida_inc, salida_full)


def test_generar_combinado_incremental_equivale_a_completo_split_frontera_mes(tmp_path, monkeypatch):
    """Split justo donde termina enero y empieza febrero: ejercita el caso
    donde las filas de contexto (fin de enero) quedan en un grupo de mes
    distinto al de las filas de la ventana (inicio de febrero) -- el
    rolling debe reiniciar en 0 para las primeras filas de febrero, igual
    que en una corrida completa."""
    fechas = pd.date_range("2026-01-31 23:45:00", "2026-02-01 01:00:00", freq="5min")
    corte = fechas[fechas < pd.Timestamp("2026-02-01 00:05:00")]
    assert 0 < len(corte) < len(fechas)

    dir_inc = tmp_path / "inc"
    dir_inc.mkdir()
    monkeypatch.setattr(rutas_mod, "DIRECTORIO_REPORTES", dir_inc)
    ruta_bess = dir_inc / "bess.csv"
    ruta_med = dir_inc / "medidor.csv"

    _escribir_perfil(ruta_bess, corte, base_rec=3.0, escala=0.001)
    _escribir_perfil(ruta_med, corte, base_rec=6.0, escala=0.002)
    generar_combinado_por_minuto(str(ruta_bess), str(ruta_med), MED_ION.prefijo)

    _escribir_perfil(ruta_bess, fechas, base_rec=3.0, escala=0.001)
    _escribir_perfil(ruta_med, fechas, base_rec=6.0, escala=0.002)
    generar_combinado_por_minuto(str(ruta_bess), str(ruta_med), MED_ION.prefijo)

    salida_inc = pd.read_csv(MED_ION.ruta_combinado())

    dir_full = tmp_path / "full"
    dir_full.mkdir()
    monkeypatch.setattr(rutas_mod, "DIRECTORIO_REPORTES", dir_full)
    ruta_bess_full = dir_full / "bess.csv"
    ruta_med_full = dir_full / "medidor.csv"
    _escribir_perfil(ruta_bess_full, fechas, base_rec=3.0, escala=0.001)
    _escribir_perfil(ruta_med_full, fechas, base_rec=6.0, escala=0.002)
    generar_combinado_por_minuto(str(ruta_bess_full), str(ruta_med_full), MED_ION.prefijo)
    salida_full = pd.read_csv(MED_ION.ruta_combinado())

    pd.testing.assert_frame_equal(salida_inc, salida_full)

    # Las primeras 2 filas del día operativo 01/02 (la columna "FECHA", no
    # FECHA_HORA: el registro de las 00:00 pertenece operativamente al 31/01)
    # deben tener demanda rodante en 0 -- reinicio mensual -- tanto en la
    # corrida incremental como en la completa.
    col_dem = f"IUSA_CON_BESS_{MED_ION.prefijo}_kW_DEM_15min"
    es_febrero = salida_inc["FECHA"] == "01/02/2026"
    valores_febrero = salida_inc.loc[es_febrero, col_dem].tolist()
    assert valores_febrero[0] == 0
    assert valores_febrero[1] == 0


def test_generar_combinado_sin_datos_nuevos_es_no_op(tmp_path, monkeypatch):
    monkeypatch.setattr(rutas_mod, "DIRECTORIO_REPORTES", tmp_path)
    fechas = pd.date_range("2026-03-01 00:05:00", "2026-03-01 06:00:00", freq="5min")
    ruta_bess = tmp_path / "bess.csv"
    ruta_med = tmp_path / "medidor.csv"
    _escribir_perfil(ruta_bess, fechas)
    _escribir_perfil(ruta_med, fechas)

    generar_combinado_por_minuto(str(ruta_bess), str(ruta_med), MED_ION.prefijo)
    contenido_antes = MED_ION.ruta_combinado().read_bytes()

    df = generar_combinado_por_minuto(str(ruta_bess), str(ruta_med), MED_ION.prefijo)

    assert df is not None and len(df) == len(fechas)  # no confundir "sin novedades" con fallo
    assert MED_ION.ruta_combinado().read_bytes() == contenido_antes


def test_generar_combinado_columnas_distintas_recalcula_completo(tmp_path, monkeypatch):
    monkeypatch.setattr(rutas_mod, "DIRECTORIO_REPORTES", tmp_path)
    fechas = pd.date_range("2026-04-01 00:05:00", "2026-04-01 02:00:00", freq="5min")
    ruta_bess = tmp_path / "bess.csv"
    ruta_med = tmp_path / "medidor.csv"
    _escribir_perfil(ruta_bess, fechas)
    _escribir_perfil(ruta_med, fechas)

    # Un COMBINADO_POR_MINUTO previo con columnas incompatibles (formato
    # viejo/distinto): debe recalcular completo, no intentar anexar.
    ruta_salida = MED_ION.ruta_combinado()
    ruta_salida.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame({"FECHA_HORA": ["01/04/2026 00:05"], "OTRA_COL": [1]}).to_csv(
        ruta_salida, index=False
    )

    df = generar_combinado_por_minuto(str(ruta_bess), str(ruta_med), MED_ION.prefijo)

    assert df is not None
    salida = pd.read_csv(ruta_salida)
    assert len(salida) == len(fechas)
    assert "OTRA_COL" not in salida.columns


def test_generar_combinado_incremental_equivale_a_completo_datos_reales(tmp_path, monkeypatch):
    """Misma prueba de equivalencia que split_mitad, pero con los CSV
    filtrados reales de IUSA_1 (ION_Testigo_IUSA1 ∩ BESS)."""
    ruta_bess_real = "data/ArchivosProcesados/IUSA_1/BESS_IUSA_1_Filtrado.csv"
    ruta_med_real = "data/ArchivosProcesados/IUSA_1/ION_Testigo_IUSA1_Filtrado.csv"

    df_bess_real = pd.read_csv(ruta_bess_real, encoding="utf-8-sig")
    if len(df_bess_real) < 500:
        pytest.skip("no hay suficientes datos reales de IUSA_1 para esta prueba")
    mitad = len(df_bess_real) // 2
    # Fecha viene como DD/MM/YYYY HH:MM:SS (normalizar_fecha): comparar como
    # texto sería incorrecto (orden lexicográfico != cronológico), hay que
    # parsear con dayfirst antes de cortar.
    fecha_corte = pd.to_datetime(df_bess_real["Fecha"].iloc[mitad], dayfirst=True)

    dir_inc = tmp_path / "inc"
    dir_inc.mkdir()
    monkeypatch.setattr(rutas_mod, "DIRECTORIO_REPORTES", dir_inc)

    ruta_bess_parcial = dir_inc / "bess_parcial.csv"
    ruta_med_parcial = dir_inc / "medidor_parcial.csv"
    df_bess_real.iloc[:mitad].to_csv(ruta_bess_parcial, index=False, encoding="utf-8-sig")
    df_med_real = pd.read_csv(ruta_med_real, encoding="utf-8-sig")
    fechas_med_dt = pd.to_datetime(df_med_real["Fecha"], dayfirst=True)
    df_med_real[fechas_med_dt <= fecha_corte].to_csv(
        ruta_med_parcial, index=False, encoding="utf-8-sig"
    )
    generar_combinado_por_minuto(str(ruta_bess_parcial), str(ruta_med_parcial), MED_ION.prefijo)

    generar_combinado_por_minuto(ruta_bess_real, ruta_med_real, MED_ION.prefijo)
    salida_inc = pd.read_csv(MED_ION.ruta_combinado())

    dir_full = tmp_path / "full"
    dir_full.mkdir()
    monkeypatch.setattr(rutas_mod, "DIRECTORIO_REPORTES", dir_full)
    generar_combinado_por_minuto(ruta_bess_real, ruta_med_real, MED_ION.prefijo)
    salida_full = pd.read_csv(MED_ION.ruta_combinado())

    pd.testing.assert_frame_equal(salida_inc, salida_full)


def test_generar_combinado_dia_abierto_recoge_actualizacion_posterior(tmp_path, monkeypatch):
    """Si el origen (BESS/medidor) trae un valor actualizado para una fecha
    que ya se había combinado en una corrida anterior -- p.ej. porque ION
    corrigió el día en curso -- la siguiente corrida debe recoger el nuevo
    valor, no quedarse pegada al primero que vio."""
    monkeypatch.setattr(rutas_mod, "DIRECTORIO_REPORTES", tmp_path)
    fechas = pd.date_range("2026-05-01 00:05:00", "2026-05-02 00:00:00", freq="5min")
    ruta_bess = tmp_path / "bess.csv"
    ruta_med = tmp_path / "medidor.csv"
    _escribir_perfil(ruta_bess, fechas, base_rec=2.0, escala=0.001)
    _escribir_perfil(ruta_med, fechas, base_rec=5.0, escala=0.002)

    generar_combinado_por_minuto(str(ruta_bess), str(ruta_med), MED_ION.prefijo)

    fila_objetivo = "01/05/2026 12:00"
    salida_antes = pd.read_csv(MED_ION.ruta_combinado())
    valores_antes = salida_antes.loc[salida_antes["FECHA_HORA"] == fila_objetivo, "BESS_REC_kW"]
    assert len(valores_antes) == 1
    valor_antes = valores_antes.iloc[0]

    # Actualizacion del origen para una fecha ya combinada (dentro del
    # margen de reexportacion).
    df_bess = pd.read_csv(ruta_bess, encoding="utf-8-sig")
    idx = df_bess.index[df_bess["Fecha"] == "2026-05-01 12:00:00"]
    assert len(idx) == 1
    df_bess.loc[idx, "KWH_REC"] = 999.0
    df_bess.to_csv(ruta_bess, index=False, encoding="utf-8-sig")

    generar_combinado_por_minuto(str(ruta_bess), str(ruta_med), MED_ION.prefijo)

    salida_despues = pd.read_csv(MED_ION.ruta_combinado())
    valores_despues = salida_despues.loc[salida_despues["FECHA_HORA"] == fila_objetivo, "BESS_REC_kW"]
    assert len(valores_despues) == 1
    valor_despues = valores_despues.iloc[0]

    assert valor_despues != valor_antes
    assert valor_despues == pytest.approx(999.0 * 12)


def test_generar_combinado_dias_cerrados_no_se_tocan_al_recalcular_ventana(tmp_path, monkeypatch):
    """Al recalcular la ventana de los últimos días, los días ya cerrados
    (fuera del margen de reexportación) deben quedar exactamente igual --
    se preservan crudos, no se vuelven a calcular ni reformatear."""
    monkeypatch.setattr(rutas_mod, "DIRECTORIO_REPORTES", tmp_path)
    fechas = pd.date_range("2026-06-01 00:05:00", "2026-06-05 00:00:00", freq="5min")
    ruta_bess = tmp_path / "bess.csv"
    ruta_med = tmp_path / "medidor.csv"
    _escribir_perfil(ruta_bess, fechas, base_rec=2.0, escala=0.0001)
    _escribir_perfil(ruta_med, fechas, base_rec=5.0, escala=0.0002)

    generar_combinado_por_minuto(str(ruta_bess), str(ruta_med), MED_ION.prefijo)

    salida_antes = pd.read_csv(MED_ION.ruta_combinado())
    dia1_antes = salida_antes[salida_antes["FECHA"] == "01/06/2026"].reset_index(drop=True)
    assert len(dia1_antes) > 0, "la prueba no esta comparando nada: revisar el formato de FECHA"

    # Se agrega un día más (día 6): dispara una nueva corrida incremental
    # cuya ventana cubre solo los últimos días, no el día 1.
    fechas_ext = pd.date_range("2026-06-01 00:05:00", "2026-06-06 00:00:00", freq="5min")
    _escribir_perfil(ruta_bess, fechas_ext, base_rec=2.0, escala=0.0001)
    _escribir_perfil(ruta_med, fechas_ext, base_rec=5.0, escala=0.0002)
    generar_combinado_por_minuto(str(ruta_bess), str(ruta_med), MED_ION.prefijo)

    salida_despues = pd.read_csv(MED_ION.ruta_combinado())
    dia1_despues = salida_despues[salida_despues["FECHA"] == "01/06/2026"].reset_index(drop=True)

    pd.testing.assert_frame_equal(dia1_antes, dia1_despues)


def test_procesar_grupo_segunda_corrida_sin_datos_nuevos_no_es_fallo():
    """Corre procesar_grupo() (combinado -> diario -> acumulados) dos veces
    seguidas contra los datos reales de IUSA_1·ION. orchestrator.procesar_grupo
    trata `df_combinado is None or len(df_combinado) == 0` como fallo: hay
    que confirmar que "sin filas nuevas" (no-op incremental) sigue
    devolviendo el merge completo -- no vacío -- y por lo tanto la segunda
    corrida no se reporta como fallida. También confirma que el
    COMBINADO_POR_MINUTO no cambia entre las dos corridas."""
    med = MED_ION
    ruta_bess = str(SUB_IUSA_1.ruta_bess_lectura(filtrado=True))
    ruta_med = str(med.ruta_consumo_lectura(filtrado=True))

    exito1, _ = procesar_grupo(
        ruta_bess, ruta_med, med.prefijo, med.consumo_lectura,
        esquema_tarifa_id=SUB_IUSA_1.esquema_tarifa_id,
    )
    assert exito1

    contenido_antes = med.ruta_combinado().read_bytes()

    exito2, _ = procesar_grupo(
        ruta_bess, ruta_med, med.prefijo, med.consumo_lectura,
        esquema_tarifa_id=SUB_IUSA_1.esquema_tarifa_id,
    )
    assert exito2, "sin filas nuevas no debe reportarse como fallo"
    assert med.ruta_combinado().read_bytes() == contenido_antes
