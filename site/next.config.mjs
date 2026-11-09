/** Export estático: `next build` gera site/out/ com HTML puro, sem servidor. */
const nextConfig = {
  output: "export",
  trailingSlash: true,
  images: { unoptimized: true },
  poweredByHeader: false,
};
export default nextConfig;
