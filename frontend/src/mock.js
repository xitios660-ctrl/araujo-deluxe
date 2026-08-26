// Mock data for "Linhas Indonésia — Dente de Cobra" cinematic clone.
// NOTE: All data below is MOCKED for the frontend teaser.

const CDN = "https://acdn-us.mitiendanube.com/stores/004/809/543/products";

export const brand = {
  name: "DENTE DE COBRA",
  subtitle: "LINHAS INDONÉSIA",
  whatsapp: "5511984134127",
  whatsappDisplay: "(11) 98413-4127",
  instagram: "reidaindonesia",
  instagramUrl: "https://www.instagram.com/reidaindonesia",
  tagline: "A linha que corta o céu",
};

export const nav = [
  { label: "Início", href: "#inicio" },
  { label: "Destaques", href: "#destaques" },
  { label: "Lançamentos", href: "#lancamentos" },
  { label: "Promoções", href: "#promocoes" },
  { label: "Rastreio", href: "/rastreio" },
  { label: "Contato", href: "#contato" },
];

export const heroSlides = [
  {
    id: 1,
    kicker: "CAMPEÃ EM APELAÇÃO",
    title: "DENTE DE COBRA",
    highlight: "INDONÉSIA",
    desc: "Linhas de alta performance para quem leva o cortante a sério. Blindada, áspera e emborrachada.",
    cta: "Ver arsenal",
    ctaHref: "#destaques",
    tone: "primary",
  },
  {
    id: 2,
    kicker: "FRETE COM SUPER DESCONTO",
    title: "CORTE SEM",
    highlight: "PIEDADE",
    desc: "Do 2 passadas ao blindado 5P com cerâmico + carbeto. Escolha sua arma e domine o vento.",
    cta: "Explorar linhas",
    ctaHref: "#lancamentos",
    tone: "gold",
  },
  {
    id: 3,
    kicker: "ATACADO E VAREJO",
    title: "PRA QUEM VIVE",
    highlight: "O CÉU",
    desc: "Kits atacado com até 6 unidades, carretéis de 500 jds e rabiolas. Preço de quem entende.",
    cta: "Ver promoções",
    ctaHref: "#promocoes",
    tone: "primary",
  },
];

export const benefits = [
  {
    icon: "Truck",
    title: "Frete com desconto",
    desc: "Enviamos para todo o Brasil",
  },
  {
    icon: "CreditCard",
    title: "Parcele suas compras",
    desc: "Em até 12x no cartão",
  },
  {
    icon: "ShieldCheck",
    title: "Loja 100% segura",
    desc: "Seus dados sempre protegidos",
  },
  {
    icon: "MessageCircle",
    title: "Atendimento humano",
    desc: "Fale conosco no WhatsApp",
  },
];

const p = (id, name, image, oldPrice, price, rating, reviews, specs, badge) => ({
  id,
  name,
  image,
  art: `/generated/${id}.png`,
  oldPrice,
  price,
  off: oldPrice > price ? Math.round(((oldPrice - price) / oldPrice) * 100) : 0,
  rating,
  reviews,
  specs,
  badge,
  freeShipping: true,
});

export const destaques = [
  p("atacado-6-2p", "ATACADO 6 UNIDADES 2´P", `${CDN}/ecc7f5a9-eafa-409e-a2d6-8633fb4a5761-6a4100715a936896b517312098267609-1024-1024.webp`, 2000, 1980, 5, 6,
    { passadas: "2 Passadas", jardas: "Atacado", tipo: "Kit 6 Unidades" }, "KIT"),
  p("atacado-6-3mil", "ATACADO 6 UNIDADES DE 3MIL JDS", `${CDN}/b71e2ab1-9b27-48b8-accc-64e306dcc756-49ff5aea237ec6b65317312104137086-1024-1024.webp`, 600, 570, 5, 7,
    { passadas: "Kit", jardas: "3 Mil JDS", tipo: "Kit 6 Unidades" }, "KIT"),
  p("indonesia-3p-blindada-6mil", "INDONÉSIA 3P BLINDADA 6mil jds", `${CDN}/6mil-9c6ce9195bdc6623e317410472150471-1024-1024.webp`, 220, 220, 5, 4,
    { passadas: "3 Passadas", jardas: "6 Mil JDS", tipo: "Blindada" }, null),
  p("carretel-500", "PACOTE 10 CARRETEL DE 500 JDS", `${CDN}/carretel-de-500-c87a84b3e7dfaf70e217312107288605-1024-1024.webp`, 270, 220, 5, 5,
    { passadas: "—", jardas: "500 JDS", tipo: "Pacote 10 un" }, null),
  p("indonesia-2p-040", "INDONÉSIA 2 PASSADA 040", `${CDN}/1-5c90d7193dd17555c417312037196108-1024-1024.webp`, 130, 115, 5, 12,
    { passadas: "2 Passadas", jardas: "3 Mil JDS", tipo: "040" }, null),
  p("indonesia-3p-emborrachada", "INDONÉSIA 3 PASSADAS EMBORRACHADA LISA", `${CDN}/3-126b8c62634b25b5e117312044724532-1024-1024.webp`, 190, 115, 4.5, 7,
    { passadas: "3 Passadas", jardas: "3 Mil JDS", tipo: "Emborrachada Lisa" }, "TOP"),
  p("indonesia-5p-blindada", "INDONÉSIA 5P BLINDADA (cerâmico + carbeto)", `${CDN}/23-50487166cfab41685117312051580321-1024-1024.webp`, 240, 230, 5, 10,
    { passadas: "5 Passadas", jardas: "3 Mil JDS", tipo: "Blindada Cerâmico" }, "PRO"),
  p("indonesia-3p-aspera", "INDONÉSIA 3P ÁSPERA (óxido)", `${CDN}/17-31ba5948fc2685749517312062992287-1024-1024.webp`, 180, 110, 5, 11,
    { passadas: "3 Passadas", jardas: "3 Mil JDS", tipo: "Áspera Óxido" }, "TOP"),
  p("12mil-3p-meio-termo", "12MIL JDS 3P MEIO TERMO", `${CDN}/2-5cf9b98a2742b76ac817312073485916-1024-1024.webp`, 360, 310, 5, 21,
    { passadas: "3 Passadas", jardas: "12 Mil JDS", tipo: "Meio Termo" }, null),
];

export const lancamentos = [
  p("indonesia-3mil-aspera-2p", "INDONÉSIA 3 MIL JARDAS ÁSPERA 2P (óxido)", `${CDN}/11-9e3adae7aba73f37bf17312060608758-1024-1024.webp`, 140, 110, 5, 8,
    { passadas: "2 Passadas", jardas: "3 Mil JDS", tipo: "Áspera Óxido" }, "NOVO"),
  p("12mil-aspera-3p", "12 MIL JARDAS ÁSPERA 3P", `${CDN}/2-0b90bcf5be97965c4417312069910923-1024-1024.webp`, 430, 320, 5, 4,
    { passadas: "3 Passadas", jardas: "12 Mil JDS", tipo: "Áspera" }, "NOVO"),
  p("12mil-5p-blindada-asp", "12MIL JDS 5 PASSADAS BLINDADA ASP", `${CDN}/2-0166a8216e62aa205417312071787586-1024-1024.webp`, 550, 520, 5, 5,
    { passadas: "5 Passadas", jardas: "12 Mil JDS", tipo: "Blindada Áspera" }, "NOVO"),
  p("12mil-5p-blindada", "12MIL JDS 5PASSADAS BLINDADA", `${CDN}/2-fdf8dfec5b84dda64817312075880839-1024-1024.webp`, 580, 540, 5, 9,
    { passadas: "5 Passadas", jardas: "12 Mil JDS", tipo: "Blindada" }, "NOVO"),
];

export const promocoes = [
  p("12mil-emborrachada-lisa-3p", "INDONÉSIA 12 MIL JDS EMBORRACHADA LISA 3P", `${CDN}/2-5cf9b98a2742b76ac817312073485916-1024-1024.webp`, 380, 330, 5, 6,
    { passadas: "3 Passadas", jardas: "12 Mil JDS", tipo: "Emborrachada Lisa" }, "-13%"),
  p("3mil-meio-termo-2p", "3MIL JARDAS MEIO TERMO 2P (especial)", `${CDN}/chatgpt-image-11-de-dez-de-2025-23_59_28-a15564571cb39aaec717655480420902-1024-1024.webp`, 140, 110, 5, 7,
    { passadas: "2 Passadas", jardas: "3 Mil JDS", tipo: "Meio Termo Especial" }, "-21%"),
  p("indonesia-3p-aspera-promo", "INDONÉSIA 3P ÁSPERA (óxido)", `${CDN}/17-31ba5948fc2685749517312062992287-1024-1024.webp`, 180, 110, 5, 11,
    { passadas: "3 Passadas", jardas: "3 Mil JDS", tipo: "Áspera Óxido" }, "-39%"),
  p("12mil-aspera-2p", "12 MIL JARDAS ÁSPERA 2P", `${CDN}/2-ef860c38ce455d167e17312068183116-1024-1024.webp`, 360, 300, 5, 6,
    { passadas: "2 Passadas", jardas: "12 Mil JDS", tipo: "Áspera" }, "-17%"),
  p("rabiola-100m", "RABIOLA 100 METROS", `${CDN}/rabiola-4a3aeed73e254663de17312092715590-1024-1024.webp`, 20, 20, 5, 0,
    { passadas: "—", jardas: "100 Metros", tipo: "Rabiola" }, null),
];

export const testimonials = [
  { name: "Amaral Pipas", handle: "Cliente verificado", rating: 5, text: "Linhas muito boa, estou satisfeito, meus clientes também. Recomendo!" },
  { name: "Rafael", handle: "Comprou 3P Áspera", rating: 5, text: "Comprei, testei e super aprovei. Virei cliente de vez!" },
  { name: "Diego", handle: "Comprou Meio Termo", rating: 5, text: "No puxão meio termo esqueci... só vapoo! Linha top demais." },
  { name: "Léo da Quebrada", handle: "Comprou 5P Blindada", rating: 5, text: "Chegou hoje, já testei e aprovei kkkk parabéns mano, apelação total." },
  { name: "Marcão", handle: "Cliente verificado", rating: 5, text: "Linha poderosa, no primeiro dia usando já foi 5 aprovada. A linha top." },
  { name: "João V.", handle: "Comprou Atacado 6un", rating: 5, text: "Chegou tudo ok mano, Deus abençoe. Recomendooo demais!" },
];

export const instagramShots = destaques.slice(0, 6).map((d) => d.art);

export const formatBRL = (v) =>
  v.toLocaleString("pt-BR", { style: "currency", currency: "BRL" });
