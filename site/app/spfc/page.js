// A antiga página do São Paulo virou /times/sao-paulo. Export estático não tem redirect de
// servidor, então esta página redireciona pelo navegador e mantém um link para quem não tiver JS.
export const metadata = {
  title: "São Paulo · futdados",
  other: { refresh: "0;url=/times/sao-paulo/" },
};

export default function SpfcRedirect() {
  return (
    <>
      <meta httpEquiv="refresh" content="0;url=/times/sao-paulo/" />
      <h1>Página movida</h1>
      <p className="lead">A página do São Paulo agora fica em <a href="/times/sao-paulo/">/times/sao-paulo</a>.</p>
    </>
  );
}
