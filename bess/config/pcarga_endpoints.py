"""Endpoints Ethernet y Ke para descarga pcarga (Mantenimiento DB).

Solo medidores alcanzables por red desde el servidor BESS.
CS1980 y granja quedan fuera (solo API).
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class EndpointPCarga:
    """Configuración de un medidor para pcarga por red."""

    medidor_id: str
    serie: str
    ip: str
    puerto: int
    # Factor externo si MULT internos = 1. Si el medidor ya escala, usar 1.0.
    ke: float
    # True: Ke ya aplicado en el medidor; pcarga Wh → kWh solo /1000 (ke=1).
    ya_escalado: bool = False
    etiqueta: str = ""

    @property
    def ke_efectivo(self) -> float:
        return 1.0 if self.ya_escalado else float(self.ke)


# Medidores operativos para descarga pcarga desde Mantenimiento DB.
ENDPOINTS_PCARGA: dict[str, EndpointPCarga] = {
    "Banco_1": EndpointPCarga(
        medidor_id="Banco_1",
        serie="CS1996",
        ip="172.16.111.10",
        puerto=5,
        ke=18400.0,
        etiqueta="Banco 1 (IUSA 1)",
    ),
    "BESS_NORTE": EndpointPCarga(
        medidor_id="BESS_NORTE",
        serie="CS3878",
        ip="172.16.111.10",
        puerto=7,
        ke=14400.0,
        etiqueta="BESS Norte (IUSA 1)",
    ),
    "Cogeneracion": EndpointPCarga(
        medidor_id="Cogeneracion",
        serie="CS1305",
        ip="172.16.138.38",
        puerto=5,
        ke=1.0,
        ya_escalado=True,
        etiqueta="Cogeneración",
    ),
    "BESS_SUR": EndpointPCarga(
        medidor_id="BESS_SUR",
        serie="CS3190",
        ip="10.255.253.246",
        puerto=5,
        ke=7200.0,
        etiqueta="BESS Sur / IUSA 2",
    ),
    "BESS_ARAGON": EndpointPCarga(
        medidor_id="BESS_ARAGON",
        serie="CYM773",
        ip="10.255.253.139",
        puerto=6,
        ke=1.0,
        ya_escalado=True,
        etiqueta="BESS Aragón",
    ),
}


def lista_medidores_pcarga() -> list[str]:
    return sorted(ENDPOINTS_PCARGA.keys())


def endpoint_pcarga(medidor_id: str) -> EndpointPCarga | None:
    return ENDPOINTS_PCARGA.get((medidor_id or "").strip())
