"""Pruebas unitarias del valor de Shapley (2 y 3 jugadores)."""

from __future__ import annotations

from itertools import combinations

from bess.cfe.shapley import _shapley_valores


def test_shapley_dos_jugadores_clasico():
    # v(∅)=0, v({g})=10, v({b})=20, v({g,b})=40
    # φ_g = 1/2*(10-0) + 1/2*(40-20) = 15
    # φ_b = 1/2*(20-0) + 1/2*(40-10) = 25
    jugadores = ("g", "b")
    v = {
        frozenset(): 0.0,
        frozenset({"g"}): 10.0,
        frozenset({"b"}): 20.0,
        frozenset({"g", "b"}): 40.0,
    }
    phi = _shapley_valores(v, jugadores)
    assert abs(phi["g"] - 15.0) < 1e-9
    assert abs(phi["b"] - 25.0) < 1e-9
    assert abs(sum(phi.values()) - 40.0) < 1e-9


def test_shapley_tres_jugadores_aditivo():
    jugadores = ("c", "s", "b")
    v: dict[frozenset[str], float] = {frozenset(): 0.0}
    for r in range(1, 4):
        for s in combinations(jugadores, r):
            v[frozenset(s)] = float(len(s))
    phi = _shapley_valores(v, jugadores)
    assert abs(phi["c"] - 1.0) < 1e-9
    assert abs(phi["s"] - 1.0) < 1e-9
    assert abs(phi["b"] - 1.0) < 1e-9
    assert abs(sum(phi.values()) - 3.0) < 1e-9


def test_shapley_tres_jugadores_asimetrico():
    pesos = {"c": 2.0, "s": 3.0, "b": 5.0}
    jugadores = ("c", "s", "b")
    v: dict[frozenset[str], float] = {frozenset(): 0.0}
    for r in range(1, 4):
        for s in combinations(jugadores, r):
            v[frozenset(s)] = sum(pesos[p] for p in s)
    phi = _shapley_valores(v, jugadores)
    assert abs(phi["c"] - 2.0) < 1e-9
    assert abs(phi["s"] - 3.0) < 1e-9
    assert abs(phi["b"] - 5.0) < 1e-9
    assert abs(sum(phi.values()) - 10.0) < 1e-9
