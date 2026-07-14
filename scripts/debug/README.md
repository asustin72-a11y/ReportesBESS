# scripts/debug/

Scripts y salidas puntuales usados para depurar discrepancias entre fuentes
de datos (ION vs IUSASOL API, purgas de API, verificación REC/ENT). No forman
parte del pipeline (`bess/data/pipeline/`) ni se ejecutan automáticamente.

Se movieron aquí desde `data/` (donde quedaban mezclados con los datos reales
del pipeline) el 2026-07-14, junto con `_compare_out.txt` de la raíz del repo.

| Archivo | Origen | Qué hace |
|---------|--------|----------|
| `compare_csv_only.py` | `data/tmp_compare_csv_only.py` | Compara CSV entre sí sin tocar la BD. |
| `compare_ion_iusa2.py` | `data/tmp_compare_ion_iusa2.py` | Compara datos ION vs IUSA2. |
| `purgar_ion_iusa2.py` | `data/tmp_purgar_ion_iusa2.py` | Purga puntual de registros ION/IUSA2. |
| `verify_rec_ent.py` | `data/tmp_verify_rec_ent.py` | Verifica intercambio REC/ENT (Banco 1). |
| `compare_result.txt`, `purgar_result.txt`, `_compare_out.txt` | resultados guardados de corridas anteriores | Solo referencia; no se regeneran automáticamente. |
