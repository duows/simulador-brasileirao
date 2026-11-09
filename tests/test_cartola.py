import itertools

import numpy as np
import pandas as pd
import pytest

from futdados.cartola import model as cm
from futdados.cartola.optimize import best_team

SCHEMES = {"4-3-3": {"gol": 1, "lat": 2, "zag": 2, "mei": 3, "ata": 3, "tec": 1},
           "3-5-2": {"gol": 1, "lat": 0, "zag": 3, "mei": 5, "ata": 2, "tec": 1}}


def _players(seed=0, per_pos=4):
    rng = np.random.default_rng(seed)
    rows = []
    for pos in ["gol", "lat", "zag", "mei", "ata", "tec"]:
        for i in range(per_pos):
            preco = round(float(rng.uniform(2, 17)), 2)
            rows.append({"atleta_id": len(rows), "apelido": f"{pos}{i}", "posicao": pos, "preco": preco,
                         "esperado": round(0.5 + 0.4 * preco + float(rng.uniform(0, 3)), 2)})
    return pd.DataFrame(rows)


def _brute(p, budget, mult):
    best = -np.inf
    for s in SCHEMES.values():
        options = [list(itertools.combinations(p[p.posicao == pos].index, k)) for pos, k in s.items()]
        for combo in itertools.product(*options):
            idx = [i for c in combo for i in c]
            if p.loc[idx, "preco"].sum() > budget + 1e-9:
                continue
            sel = p.loc[idx]
            cap = sel[sel.posicao != "tec"].esperado.max()
            best = max(best, sel.esperado.sum() + (mult - 1) * cap)
    return best


@pytest.mark.parametrize("seed,budget", [(1, 80), (1, 110), (2, 100), (3, 120)])
def test_milp_matches_brute_force(seed, budget):
    p = _players(seed)
    res = best_team(p, budget, SCHEMES, 1.5)
    bf = _brute(p, budget, 1.5)
    if bf == -np.inf:  # nenhum time cabe no orçamento
        assert res["ok"] is False
        return
    assert res["ok"] and res["pontos_esperados"] == pytest.approx(bf)
    t = res["time"]
    assert len(t) == 12 and t.preco.sum() <= budget + 1e-9
    assert t.capitao.sum() == 1 and not t[t.capitao].posicao.eq("tec").any()


def test_insufficient_budget():
    assert best_team(_players(4), 5, SCHEMES)["ok"] is False


def test_prior_means_do_not_use_current_round():
    pontos = pd.DataFrame({"atleta_id": [1, 1, 1, 2, 2], "rodada": [1, 2, 3, 1, 2], "posicao": ["ata"] * 5,
                           "pontos": [10.0, 0.0, 99.0, 2.0, 4.0], "jogou": [True] * 5})
    df = cm.add_prior_means(pontos, shrink=0).set_index(["atleta_id", "rodada"])
    assert df.loc[(1, 3), "media_previa"] == pytest.approx(5.0)   # só rodadas 1 e 2
    assert np.isnan(df.loc[(1, 1), "media_previa"])
    shr = cm.add_prior_means(pontos, shrink=5).set_index(["atleta_id", "rodada"])
    # rodada 2: média da posição só com a rodada 1 = (10 + 2) / 2 = 6
    assert shr.loc[(2, 2), "media_ajustada"] == pytest.approx((2 + 5 * 6) / 6)


def test_decomposition_sums_to_prediction():
    rows = pd.DataFrame({"posicao": ["zag"] * 50, "media_ajustada": np.linspace(1, 6, 50), "p_sg": np.linspace(0.1, 0.6, 50),
                         "gols_time": 1.2, "mando": [0, 1] * 25, "p_vitoria": 0.4})
    rows["pontos"] = 0.5 + 0.8 * rows.media_ajustada + 4 * rows.p_sg
    coefs = cm.fit_position_models(rows, alpha=0.01)
    pred = cm.predict(rows, coefs)
    dec = cm.decompose(rows.iloc[7], coefs["zag"])
    assert sum(dec.values()) == pytest.approx(pred[7])
    assert np.allclose(pred, rows.pontos, atol=0.05)



def test_reserves_respect_price_rule_and_skip_tecnico():
    from futdados.cartola.optimize import add_reserves

    pl = _players(5, per_pos=6).assign(p_jogar=0.95)
    res = best_team(pl, 120, SCHEMES, 1.5, reserves={"ativo": True, "preco_maximo": "titular_mais_barato"})
    assert res["ok"]
    t, rv = res["time"], res["reservas"]
    assert "tec" not in set(rv.posicao)
    for r in rv.itertuples():
        assert r.atleta_id not in set(t.atleta_id)
        assert r.preco <= t[t.posicao == r.posicao].preco.min() + 1e-9
        n = (t.posicao == r.posicao).sum()
        assert r.chance_de_entrar == pytest.approx(1 - 0.95**n)
    assert res["pontos_esperados_com_reservas"] == pytest.approx(
        res["pontos_esperados"] + res.get("valor_vice", 0) + res["valor_reservas"])
    # esquema sem laterais: não há reserva de lateral
    t352 = best_team(pl, 120, SCHEMES, 1.5, only="3-5-2")["time"]
    assert "lat" not in set(add_reserves(t352, pl, {"ativo": True, "preco_maximo": "livre"}).posicao)


def test_team_real_points_with_bench_and_captain():
    from futdados.cartola.project import team_real_points

    real = pd.DataFrame({"pontos": [10.0, 0.0, 6.0, 4.0], "jogou": [True, False, True, True]}, index=[1, 2, 3, 4])
    t = {"atletas": [1, 2, 3], "capitao": 1, "posicoes": {"1": "ata", "2": "ata", "3": "mei"}, "reservas": {"ata": 4}}
    # 10 + 0 + 6, capitão +0,5×10, reserva do ataque entra no lugar do 2 (não jogou): +4
    assert team_real_points(t, real, 1.5) == pytest.approx(25.0)
    t["capitao"] = 2  # capitão que não jogou não multiplica nada
    assert team_real_points(t, real, 1.5) == pytest.approx(20.0)


def test_real_points_vice_negative_reserve_and_luxury():
    from futdados.cartola.project import team_real_points

    real = pd.DataFrame({"pontos": [10.0, 0.0, 6.0, -2.0, 1.0, 9.0], "jogou": [False, False, True, True, True, True]},
                        index=[1, 2, 3, 4, 5, 6])
    # 1 capitão (não jogou), 2 vice? não: 3 é o vice; 1 e 5 atacantes; 3 meia; reserva do ataque 4 (negativo)
    t = {"atletas": [1, 3, 5], "capitao": 1, "vice": 3, "posicoes": {"1": "ata", "3": "mei", "5": "ata"},
         "reservas": {"ata": 4, "mei": 6}, "luxo": 6}
    # banco do ataque: reserva 4 jogou mas fez -2 → não entra (titular 1 fica com 0)
    # luxo no meio: reserva 6 (9) > titular 3 (6) → troca, meia vale 9
    # capitão 1 não jogou → vice 3 herda; vice (posição de meia) agora vale 9 → +0,5×9
    total = 0 + 9 + 1 + 0.5 * 9
    assert team_real_points(t, real, 1.5) == pytest.approx(total)


def test_bench_simulation_luxury_has_value():
    from futdados.cartola.optimize import bench_simulation

    team = pd.DataFrame({"posicao": ["ata", "ata"], "p_jogar": [1.0, 1.0], "previsto_se_jogar": [5.0, 5.0]})
    res = pd.DataFrame({"posicao": ["ata"], "p_jogar": [1.0], "previsto_se_jogar": [5.0]})
    sim = bench_simulation(team, res, n=4000)
    assert sim["ata"]["banco"] == 0  # ninguém falta: o banco nunca entra
    assert sim["ata"]["luxo"] > 1    # mas o luxo substitui o pior titular com frequência
