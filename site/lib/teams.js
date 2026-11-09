// Monograma de 3 letras (sem escudos). Siglas usuais; para os demais, as 3 primeiras letras do nome.
const SIGLAS = {
  "america-mg": "AME", "athletico-pr": "CAP", "atletico-go": "ACG", "atletico-mg": "CAM", avai: "AVA",
  bahia: "BAH", botafogo: "BOT", bragantino: "RBB", ceara: "CEA", chapecoense: "CHA", corinthians: "COR",
  coritiba: "CFC", criciuma: "CRI", cruzeiro: "CRU", cuiaba: "CUI", flamengo: "FLA", fluminense: "FLU",
  fortaleza: "FOR", goias: "GOI", gremio: "GRE", internacional: "INT", juventude: "JUV", mirassol: "MIR",
  palmeiras: "PAL", remo: "REM", santos: "SAN", "sao-paulo": "SAO", sport: "SPT", vasco: "VAS", vitoria: "VIT",
};

export function sigla(id, nome) {
  if (SIGLAS[id]) return SIGLAS[id];
  return (nome || id).normalize("NFD").replace(/[^A-Za-z]/g, "").slice(0, 3).toUpperCase();
}

export function Monogram({ id, nome, large = false }) {
  return <span className={`mono${large ? " lg" : ""}`} aria-hidden="true">{sigla(id, nome)}</span>;
}
