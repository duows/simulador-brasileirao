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
