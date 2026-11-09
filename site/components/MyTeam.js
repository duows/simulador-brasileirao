"use client";
// "Meu time": escolha da pessoa, salva no localStorage. Padrão: nenhum time destacado.
// Componentes leem com useMyTeam(); o seletor fica no cabeçalho de todas as páginas.
import { createContext, useCallback, useContext, useEffect, useState } from "react";

const KEY = "futdados:meu-time";
const Ctx = createContext({ team: null, setTeam: () => {} });

function readStored() {
  try { return window.localStorage.getItem(KEY) || null; } catch { return null; }
}

export function MyTeamProvider({ children }) {
  const [team, setTeamState] = useState(null);
  useEffect(() => { setTeamState(readStored()); }, []);
  const setTeam = useCallback((id) => {
    setTeamState(id || null);
    try {
      if (id) window.localStorage.setItem(KEY, id); else window.localStorage.removeItem(KEY);
    } catch { /* navegação privada: vale só nesta página */ }
  }, []);
  return <Ctx.Provider value={{ team, setTeam }}>{children}</Ctx.Provider>;
}

export function useMyTeam() {
  return useContext(Ctx);
}

export function MyTeamSelect({ teams }) {
  const { team, setTeam } = useMyTeam();
  return (
    <label className="myteam">
      <span>Meu time</span>
      <select value={team || ""} onChange={(e) => setTeam(e.target.value)} aria-label="Escolher meu time para destacar">
        <option value="">Nenhum</option>
        {teams.map((t) => <option key={t.id} value={t.id}>{t.nome}</option>)}
      </select>
    </label>
  );
}
